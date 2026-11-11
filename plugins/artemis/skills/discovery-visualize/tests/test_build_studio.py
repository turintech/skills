#!/usr/bin/env python3
"""Checks for the chart studio page and its builder, drawn in headless Chrome."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import build_studio  # noqa: E402
import collect_discovery  # noqa: E402
from studio_fixtures import (  # noqa: E402
    CHROME, VISIBLE, embedded, failed_run, low_then_high, probed, project_snapshot, run_snapshot, with_intervals,
)


class BuildTests(unittest.TestCase):
    def test_a_run_snapshot_is_one_dataset(self) -> None:
        html = build_studio.build([run_snapshot()])
        for key in ("__TITLE__", "__STUDIO_DATA__"):
            self.assertNotIn(key, html)
        data = embedded(html)["datasets"]
        self.assertEqual(len(data), 1)
        self.assertIn("snapshot", data[0])
        self.assertTrue(data[0]["id"].startswith("r-"))

    def test_a_project_snapshot_is_its_runs_as_sessions(self) -> None:
        data = embedded(build_studio.build([project_snapshot(3)], labels=["Build time"]))["datasets"]
        self.assertEqual(data[0]["label"], "Build time")
        self.assertEqual([s["run"]["id"] for s in data[0]["sessions"]], ["run-0", "run-1", "run-2"])

    def test_a_one_run_project_is_drawn_as_that_run(self) -> None:
        data = embedded(build_studio.build([project_snapshot(1)]))["datasets"]
        self.assertIn("snapshot", data[0])

    def test_the_same_run_twice_gets_two_entries(self) -> None:
        data = embedded(build_studio.build([run_snapshot(), run_snapshot()]))["datasets"]
        self.assertEqual(len({d["id"] for d in data}), 2)

    def test_data_cannot_close_its_script_element(self) -> None:
        snap = run_snapshot()
        snap["run"]["projectName"] = "A <!-- B </script><script>alert(1)</script>"
        html = build_studio.build([snap])
        self.assertNotIn("</script><script>alert(1)", html)
        self.assertNotIn("<!-- B", html)
        self.assertEqual(embedded(html)["datasets"][0]["label"], snap["run"]["projectName"])

    def test_bad_snapshots_are_refused_not_crashed_on(self) -> None:
        no_run = run_snapshot()
        no_run["run"] = None
        no_base = run_snapshot()
        del no_base["baseline"]
        no_base_metrics = run_snapshot()
        no_base_metrics["baseline"] = {}
        no_winners = run_snapshot()
        del no_winners["perMetricWinners"]
        unmeasured = run_snapshot()
        unmeasured["metrics"] = []  # versions keep their readings, but on no metric the run defines
        cases = [
            ([[run_snapshot()]], "expected a collector snapshot"),
            ([no_run], "`run` is missing or is not a JSON object"),
            ([no_base], "`baseline` is missing"),
            ([no_base_metrics], "`baseline.metrics` is missing"),
            ([no_winners], "`perMetricWinners` is missing"),
            ([dict(run_snapshot(), versions={})], "`versions` is missing or is not a list"),
            ([dict(run_snapshot(), versions=["v1"])], "an item of `versions` is not a JSON object"),
            ([dict(run_snapshot(), metrics=["x"])], "an item of `metrics` is not a JSON object"),
            ([dict(project_snapshot(2), skipped=["x"])], "`skipped` is not a list of JSON objects"),
            ([{"schemaVersion": 2, "kind": "project", "projectId": 7, "runs": [dict(run_snapshot(), versions=[{"version": 1, "metrics": {"compile_runtime": 5}}])]}], "metric reading is not a JSON object"),
            ([unmeasured], "no measured version"),
            ([{"schemaVersion": 2, "kind": "project", "runs": [None]}], "not a JSON object"),
        ]
        for snaps, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message), contextlib.redirect_stderr(io.StringIO()):
                build_studio.build(snaps)

    def test_a_run_with_readings_on_no_defined_metric_is_left_out(self) -> None:
        project = project_snapshot(3)
        project["runs"][0]["metrics"] = []
        with contextlib.redirect_stderr(io.StringIO()) as err:
            data = embedded(build_studio.build([project]))["datasets"]
        self.assertEqual([s["run"]["id"] for s in data[0]["sessions"]], ["run-1", "run-2"])
        self.assertIn("left out run run-0", err.getvalue())

    def test_title_is_escaped(self) -> None:
        self.assertIn("<title>A&lt;b>&amp;</title>", build_studio.build([run_snapshot()], title="A<b>&"))

    def test_failed_versions_are_deduplicated_and_the_project_name_is_the_default_label(self) -> None:
        project = project_snapshot(2)
        for r in project["runs"]:
            r["run"]["projectName"] = "Build time"
        data = embedded(build_studio.build([project], failed=["1:1:2,2"]))["datasets"]
        self.assertEqual(data[0]["correctness"], {"1": [2]})
        # A repeat for the same session adds to it.
        data = embedded(build_studio.build([project], failed=["1:1:2", "1:1:3"]))["datasets"]
        self.assertEqual(data[0]["correctness"], {"1": [2, 3]})
        self.assertEqual(data[0]["label"], "Build time")
        project["runs"][0]["run"].pop("projectName")
        self.assertEqual(embedded(build_studio.build([project]))["datasets"][0]["label"], "Project proj-1")

    def test_failed_marks_land_on_the_named_session(self) -> None:
        data = embedded(build_studio.build([run_snapshot(), project_snapshot(2)], failed=["2:2:3,1", "1:1:2"]))["datasets"]
        self.assertEqual(data[1]["correctness"], {"2": [1, 3]})
        self.assertEqual(data[0]["correctness"], {"1": [2]})
        # A lone run stays a run: no sessions, so the page keeps the plain-run layout.
        self.assertIn("snapshot", data[0])
        self.assertNotIn("sessions", data[0])

    def test_bad_input_is_refused_with_a_reason(self) -> None:
        old = run_snapshot()
        old["schemaVersion"] = 1
        cases = [
            ([], [], [], "at least one"),
            ([old], [], [], "schemaVersion"),
            ([run_snapshot()], ["a", "b"], [], "more --label"),
            ([run_snapshot()], [], ["1-2-3"], "expected N:SESSION:VERSIONS"),
            ([run_snapshot()], [], ["2:1:1"], "no snapshot 2"),
            ([run_snapshot()], [], ["1:2:1"], "only session is 1"),
            ([project_snapshot(2)], [], ["1:3:1"], "has 2 session"),
            ([run_snapshot()], [], ["1:1:99"], "no version 99"),
            ([failed_run()], [], [], "no measured version"),
        ]
        for snaps, labels, failed, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                build_studio.build(snaps, labels, failed)

    def test_the_page_starts_in_standards_mode(self) -> None:
        self.assertTrue(build_studio.build([run_snapshot()]).startswith("<!doctype html>"))

    def test_a_run_with_no_measured_version_is_left_out_and_named(self) -> None:
        project = project_snapshot(2)
        project["runs"].insert(0, failed_run())
        project["skipped"] = [{"id": "gone-run-1", "status": "failed", "reason": "no comparison"}]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            data = embedded(build_studio.build([project], failed=["1:2:1"]))["datasets"]
        self.assertEqual([s["run"]["id"] for s in data[0]["sessions"]], ["run-0", "run-1"])
        # SESSION is the number the page shows, after the left-out run: session 2 is run-1.
        self.assertEqual(data[0]["correctness"], {"2": [1]})
        self.assertIn("left out run dead-run (failed)", err.getvalue())
        self.assertIn("skipped run gone-run (failed): no comparison", err.getvalue())

    def test_cli_writes_the_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snap, out = Path(tmp) / "snap.json", Path(tmp) / "studio.html"
            snap.write_text(json.dumps(run_snapshot()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as said:
                self.assertEqual(build_studio.main(["--snapshot", str(snap), "--output", str(out)]), 0)
            self.assertIn("wrote", said.getvalue())
            self.assertIn("studio-data", out.read_text(encoding="utf-8"))
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(build_studio.main(["--snapshot", str(Path(tmp) / "missing.json"), "--output", str(out)]), 2)
            self.assertIn("No such file", err.getvalue())
            listed = Path(tmp) / "list.json"
            listed.write_text("[]", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(build_studio.main(["--snapshot", str(listed), "--output", str(out)]), 2)
                self.assertEqual(build_studio.main(["--snapshot", str(snap), "--output", str(Path(tmp) / "no" / "dir.html")]), 2)
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(build_studio.main(["--snapshot", str(bad), "--output", str(out)]), 2)
            self.assertIn(f"{bad} is not JSON", err.getvalue())
            # --label and --failed reach the page through the command line.
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(build_studio.main(["--snapshot", str(snap), "--label", "Build time", "--failed", "1:1:2", "--output", str(out)]), 0)
            data = embedded(out.read_text(encoding="utf-8"))["datasets"][0]
            self.assertEqual((data["label"], data["correctness"]), ("Build time", {"1": [2]}))


class PhoneAndDesktopLayoutTests(unittest.TestCase):
    """What a phone and a desktop show: zero, Best and verdicts in view, the chosen session marked, CSV under each top."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_a_phone_keeps_zero_best_and_verdicts_visible_and_fits_five_groups(self) -> None:
        project = project_snapshot(5)
        titles = ["Use bucket_time_keys_before_probing_hash_join_partitions in query_planner.optimize",
                  "Use BucketTimeKeysBeforeProbingHashJoinPartitionsInQueryPlannerOptimize now",
                  "Pin a3f9c2e81b7d4f06a5e3c9b2d1f8e7a6c5b4d3e2f1a0b9c8 as the seed"]
        for v, title in zip(project["runs"][0]["versions"], titles):
            v["experimentTitle"] = title
        html = build_studio.build([project])
        got = probed(html, "p-proj-1", VISIBLE + """
          return { ranked: texts('ranked'), forest: texts('forest'), swipe: !!card('box').querySelector('.hint'),
                   wide: document.documentElement.scrollWidth, table: card('table').querySelector('table').getBoundingClientRect().width,
                   box: card('box').getBoundingClientRect().width, inner: innerWidth, tableText: card('table').textContent };""", phone=True, more=True)
        self.assertIn("0%", got["ranked"])
        self.assertFalse(any("Best" in t for t in got["ranked"]), "Best is the Composite pick; one metric's chart never marks it")
        run = build_studio.build([with_intervals(run_snapshot())])
        forest = probed(run, embedded(run)["datasets"][0]["id"], VISIBLE + "return texts('forest');", phone=True)
        # A phone shows each verdict as its mark beside the change; every version keeps one.
        self.assertTrue(any(t.endswith("▲") for t in forest) and any(t.endswith("≈") for t in forest), forest)
        self.assertFalse(got["swipe"], "five box groups should fit a phone with no Swipe hint")
        self.assertEqual(got["inner"], 390)
        self.assertLessEqual(got["wide"], 390)
        self.assertLessEqual(got["table"], got["box"], "a long code name in a title pushed the table off the screen")
        self.assertIn("query_\u200bplanner.\u200boptimize", got["tableText"], "a code name should break at its _ and . first")

    def test_a_desktop_shows_the_verdict_wording_and_marks_the_chosen_session(self) -> None:
        project = project_snapshot(3)
        html = build_studio.build([project])
        got = probed(html, "p-proj-1", VISIBLE + """
          var theme = document.documentElement.getAttribute('data-theme');
          var cap = [].filter.call(document.querySelectorAll('.ctl > span'), function (s) { return s.textContent === 'Theme'; })[0];
          if (cap) cap.click();
          var ctlTag = cap ? cap.parentNode.tagName : null;
          var bold = [].filter.call(card('sessions').querySelectorAll('svg text tspan'), function (t) { return /^Discovery session 2$/.test(t.textContent) && +getComputedStyle(t).fontWeight >= 600; }).length;
          return { themeAfter: document.documentElement.getAttribute('data-theme'), theme: theme, ctlTag: ctlTag, bold: bold,
                   best: card('best').textContent, table: card('table').textContent, sessions: card('sessions').textContent };""", session=1)
        self.assertEqual(got["themeAfter"], got["theme"], "a click on the Theme caption changed the theme")
        self.assertEqual(got["ctlTag"], "DIV", "a button group's caption must not be a <label>")
        self.assertGreater(got["bold"], 0, "the chosen session's label should be bold")
        self.assertRegex(got["table"], r"\d+ of \d+ significantly improved")
        self.assertRegex(got["sessions"], r"Discovery session 1's top( correct version)? on [^:]+: v\d")
        self.assertNotIn("'s best", got["sessions"], "a per-metric top is never called best")
        self.assertNotIn("Top by", got["sessions"])

    def test_the_forest_log_scale_reads_one_times_at_no_change(self) -> None:
        html = build_studio.build([with_intervals(run_snapshot())])
        ds = embedded(html)["datasets"][0]["id"]
        got = probed(html, ds, VISIBLE + "return { ticks: texts('forest'), log: card('forest').querySelector('.seg button[aria-pressed=true]').textContent };",
                     act="[].filter.call(document.querySelectorAll('[data-card=\"forest\"] .seg button'), function (x) { return /^Log/.test(x.textContent); })[0].click();")
        self.assertEqual(got["log"], "Log (×)")
        self.assertIn("1×", got["ticks"], got)

    def test_a_label_shortened_once_takes_new_text_after_a_switch(self) -> None:
        html = build_studio.build([run_snapshot()])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var swapped = window.__sw, kept = window.__kp;
          return { swapped: swapped.textContent, swappedFull: swapped.dataset.full || null, kept: kept.textContent.indexOf('Old metric with') === 0 };""", act="""
          var svg = document.querySelector('[data-card="ranked"] svg.recharts-surface'), ns = 'http://www.w3.org/2000/svg';
          var make = function (txt) { var t = document.createElementNS(ns, 'text'); t.setAttribute('x', 10); t.setAttribute('y', 20); t.textContent = txt; svg.appendChild(t); return t; };
          var swapped = make('New metric'); swapped.dataset.full = 'Old metric with a long name'; swapped.dataset.short = 'Old metric with…';
          var kept = make('Old metric with…'); kept.dataset.full = 'Old metric with a long name'; kept.dataset.short = 'Old metric with…';
          window.__sw = swapped; window.__kp = kept;
          window.dispatchEvent(new Event('resize'));""")
        self.assertEqual(got["swapped"], "New metric", "the pass wrote the old label over React's new one")
        self.assertIsNone(got["swappedFull"])
        self.assertTrue(got["kept"])

    def test_csv_keeps_every_run_under_each_runs_top(self) -> None:
        project = project_snapshot(6)
        per_run = len(project["runs"][0]["rankings"][project["runs"][0]["metrics"][0]["key"]])
        self.assertGreater(per_run, 1)
        html = build_studio.build([project])
        got = probed(html, "p-proj-1", "return { csv: window.__csv || null };", act="""
          window.claude = { use: function () { return Promise.resolve({ save: function (o) { window.__csv = o.data; return Promise.resolve(); } }); } };
          var c = document.querySelector('[data-card="sessions"]');
          var dl = [].filter.call(c.querySelectorAll('button'), function (b) { return b.textContent === 'Download'; })[0]; dl.click();
          setTimeout(function () { var o = [].filter.call(c.querySelectorAll('button'), function (b) { return /CSV/.test(b.textContent); })[0]; if (o) o.click(); }, 100);""")
        self.assertIsNotNone(got["csv"], "the sessions card saved no CSV")
        self.assertEqual(len(got["csv"].strip().splitlines()) - 1, 6 * per_run, "the CSV dropped the rows Show hides")


class LeadMetricAndTypeTests(unittest.TestCase):
    """The lead metric, no style editing, the Own layout, text of 15px or more, and Conclusion boxes."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_the_page_leads_with_the_most_important_metric(self) -> None:
        js = ("return { h1: document.querySelector('h1').textContent, best: document.querySelector('[data-card=best] .means').textContent,"
              " panels: [].map.call(document.querySelectorAll('[data-card=best] .ptitle'), function (t) { return t.textContent; }),"
              " reset: [].map.call(document.querySelectorAll('button'), function (b) { return b.textContent; }).filter(function (t) { return /Reset/.test(t); }) };")
        # Without the collector's bestLines.metric (an older snapshot), the page ranks by importance itself.
        for told in (True, False):
            with self.subTest(bestLines_metric=told):
                snap = low_then_high()
                if not told:
                    snap["bestLines"].pop("metric")
                html = build_studio.build([snap])
                got = probed(html, embedded(html)["datasets"][0]["id"], js)
                self.assertIn("Latency", got["h1"], "the headline led on a low-importance metric that did not move")
                self.assertNotIn("db size", got["h1"].lower())
                self.assertIn("Latency", got["best"])
                self.assertTrue(got["panels"] and got["panels"][0].startswith("Latency"), f"the Best card should show the most important metric first: {got['panels']}")
                self.assertEqual(got["reset"], ["Reset"])

    def test_no_card_offers_style_editing_and_old_edits_do_not_come_back(self) -> None:
        html = build_studio.build([run_snapshot()])
        ds = embedded(html)["datasets"][0]["id"]
        got = probed(html, ds, """
          return { style: [].filter.call(document.querySelectorAll('button'), function (b) { return b.textContent === 'Style'; }).length,
                   editable: document.querySelectorAll('[contenteditable]').length,
                   colour: document.querySelectorAll('input[type=color]').length,
                   h2: document.querySelector('[data-card=\\\"ranked\\\"] h2').textContent };""",
                     act="")
        self.assertEqual((got["style"], got["editable"], got["colour"]), (0, 0, 0))
        # A browser that saved an edited title before still sees the question.
        key = "dv-studio:v1:" + ds + ":" + embedded(html)["datasets"][0]["snapshot"]["run"]["id"] + ":ranked"
        seeded = html.replace("<!doctype html>\n", "<!doctype html>\n<script>try { localStorage.setItem('" + key + "', JSON.stringify({ title: 'My old title', labels: { x: 'old axis' }, offV: ['v1'] })); } catch (e) {}</script>", 1)
        again = probed(seeded, ds, "var c = document.querySelector('[data-card=\\\"ranked\\\"]'); return { text: c.textContent, v1: [].some.call(c.querySelectorAll('svg text'), function (t) { return /^v1\\b/.test(t.textContent); }) };")
        self.assertFalse(again["v1"], "the seeded state was not read, so this test checks nothing")
        self.assertNotIn("My old title", again["text"])
        self.assertNotIn("old axis", again["text"])

    def test_own_scale_puts_every_panel_in_one_row_on_desktop_and_two_columns_on_a_phone(self) -> None:
        html = build_studio.build([run_snapshot()])
        ds = embedded(html)["datasets"][0]["id"]
        act = "var c = document.querySelector('[data-card=\\\"box\\\"]'); [].filter.call(c.querySelectorAll('.seg button'), function (b) { return b.textContent === 'Own'; })[0].click();"
        read = "var ps = [].map.call(document.querySelectorAll('[data-card=\\\"box\\\"] .multi .panel'), function (p) { var r = p.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(p.querySelector('svg').getBoundingClientRect().width)]; }); return ps;"
        desk = probed(html, ds, read, act=act, more=True)
        self.assertGreater(len(desk), 2)
        self.assertEqual(len({p[1] for p in desk}), 1, f"panels wrapped onto more than one row: {desk}")
        self.assertTrue(all(abs(p[2] - p[3]) <= 2 for p in desk), f"a chart is narrower than its panel: {desk}")
        phone = probed(html, ds, read, act=act, phone=True, more=True)
        self.assertEqual(len({p[0] for p in phone}), 2, f"a phone should show two columns: {phone}")
        # Nine groups split into rows of 5 and 4 rather than a full row and one panel alone.
        many = run_snapshot()
        donor = next(v for v in many["versions"] if (v["metrics"].get("latency_ms") or {}).get("runs"))
        for n in range(6, 11):
            many["versions"].append(dict(copy.deepcopy(donor), version=n, label=f"v{n}", id=f"ver-{n}"))
        built = build_studio.build([many])
        rows = probed(built, embedded(built)["datasets"][0]["id"], read, act=act, more=True)
        per_row = [sum(1 for p in rows if p[1] == top) for top in sorted({p[1] for p in rows})]
        self.assertEqual(sum(per_row), 9, rows)
        self.assertEqual(sorted(per_row), [4, 5], f"rows should be as even as nine allows: {per_row}")

    def test_conclusions_are_called_conclusion_and_no_text_is_under_15px(self) -> None:
        html = build_studio.build([run_snapshot()])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var small = []; var walk = document.createTreeWalker(document.getElementById('root'), NodeFilter.SHOW_TEXT);
          for (var n = walk.nextNode(); n; n = walk.nextNode()) { var el = n.parentElement; if (!n.data.trim() || !el || el.closest('[hidden]')) continue;
            var cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none') continue;
            if (parseFloat(cs.fontSize) < 15) small.push(n.data.trim().slice(0, 30) + ' ' + cs.fontSize); }
          var heads = [].map.call(document.querySelectorAll('.means h3'), function (h) { return h.textContent; });
          var mono = [].filter.call(document.querySelectorAll('svg text, svg tspan, table.sum td.n'), function (t) { return /Mono|monospace/.test(getComputedStyle(t).fontFamily); }).length;
          return { small: small.slice(0, 5), heads: heads, mono: mono, old: document.getElementById('root').textContent.indexOf('What this means') };""")
        self.assertEqual(got["small"], [])
        self.assertTrue(got["heads"] and all(h == "Conclusion" for h in got["heads"]), got["heads"])
        self.assertEqual(got["old"], -1)
        self.assertEqual(got["mono"], 0, "numbers should be in the text face")

    def test_a_long_rotated_axis_title_stays_inside_its_chart(self) -> None:
        snap = run_snapshot()
        for m in snap["metrics"]:
            m["label"] = "host work between chunks reduction for " + m["key"]
        html = build_studio.build([snap])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          return [].map.call(document.querySelectorAll('svg.recharts-surface'), function (svg) { var b = svg.getBoundingClientRect();
            return [].filter.call(svg.querySelectorAll('text[transform]'), function (t) { var r = t.getBoundingClientRect(); return r.height && (r.top < b.top - 1 || r.bottom > b.bottom + 1); }).map(function (t) { return t.textContent; }); })
            .reduce(function (a, b) { return a.concat(b); }, []);""", more=True)
        self.assertEqual(got, [], "a rotated axis title runs past its chart")

    def test_six_digit_ticks_clear_the_axis_title_on_a_phone(self) -> None:
        snap = run_snapshot()

        def scale(st: dict) -> None:
            for k in ("mean", "min", "max", "q1", "median", "q3"):
                if isinstance(st.get(k), (int, float)):
                    st[k] = st[k] * 12500
            if st.get("runs"):
                st["runs"] = [r * 12500 if isinstance(r, (int, float)) else r for r in st["runs"]]
        scale(snap["baseline"]["metrics"]["latency_ms"])
        for v in snap["versions"]:
            if v["metrics"].get("latency_ms"):
                scale(v["metrics"]["latency_ms"])
        html = build_studio.build([snap])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var card = document.querySelector('[data-card="box"]'), title = card.querySelector('svg text[transform]');
          if (!title) return { title: false };
          var t = title.getBoundingClientRect();
          var ticks = [].filter.call(card.querySelectorAll('.recharts-cartesian-axis-tick-label'), function (x) { return getComputedStyle(x).visibility !== 'hidden'; });
          return { title: true, ticks: ticks.length, hit: ticks.filter(function (x) { var r = x.getBoundingClientRect(); return r.left < t.right && r.right > t.left && r.top < t.bottom && r.bottom > t.top; }).map(function (x) { return x.textContent; }) };""",
                     phone=True, more=True)
        self.assertTrue(got["title"])
        self.assertGreater(got["ticks"], 1)
        self.assertEqual(got["hit"], [], "a y tick overprints the axis title")


class SessionNamingAndOnlyTests(unittest.TestCase):
    """Discovery sessions are never called runs, --only draws one card, and the forest shades both sides."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_no_label_calls_a_discovery_session_a_run(self) -> None:
        project = project_snapshot(3)
        project["runs"][1]["run"]["taskDescription"] = "A different task entirely"
        html = build_studio.build([project])
        text = probed(html, "p-proj-1", "return document.getElementById('root').innerText;", session=1)
        self.assertIsNone(re.search(r"\bRuns?\b \d|\bRuns in\b|\brun \d", text), "a Discovery session is labelled as a run")
        self.assertIn("Discovery session 2", text)

    def test_only_draws_one_card_with_no_switchers(self) -> None:
        html = build_studio.build([run_snapshot()], only="forest")
        got = probed(html, embedded(html)["datasets"][0]["id"], "return { cards: [].map.call(document.querySelectorAll('section.card'), function (c) { return c.dataset.card; }), switches: [].map.call(document.querySelectorAll('.bar .ctl > span:first-child'), function (s) { return s.textContent; }), h1: document.querySelectorAll('h1').length };")
        self.assertEqual(got, {"cards": ["forest"], "switches": ["Theme"], "h1": 0})
        with self.assertRaisesRegex(ValueError, "--only must be one of"):
            build_studio.build([run_snapshot()], only="pie")

    def test_the_forest_shades_the_better_side_green_and_the_worse_side_red(self) -> None:
        html = build_studio.build([with_intervals(run_snapshot())])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var svg = document.querySelector('[data-card="forest"] svg.recharts-surface'), zero = null;
          var areas = [].map.call(svg.querySelectorAll('.recharts-reference-area rect, .recharts-reference-area path'), function (r) { var b = r.getBoundingClientRect(); return { left: b.left, right: b.right, fill: r.getAttribute('fill') }; });
          var line = svg.querySelector('.recharts-reference-line line'); if (line) zero = line.getBoundingClientRect().left;
          var first = svg.querySelector('.recharts-reference-area'), marks = svg.querySelector('.recharts-scatter'), labels = [].filter.call(svg.querySelectorAll('text'), function (t) { return /less|more|improved|regressed|difference/.test(t.textContent); });
          var after = function (n) { return !!(first && n && (first.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_FOLLOWING)); };
          return { areas: areas, zero: zero, behind: after(marks) && labels.length > 0 && labels.every(after) };""")
        self.assertEqual(len(got["areas"]), 2, got)
        left, right = sorted(got["areas"], key=lambda a: a["left"])
        self.assertLessEqual(abs(left["right"] - got["zero"]), 1.5)
        self.assertLessEqual(abs(right["left"] - got["zero"]), 1.5)
        self.assertNotEqual(left["fill"], right["fill"])
        self.assertTrue(got["behind"], "the bands should sit behind the rows and their labels")


class ConclusionBulletTests(unittest.TestCase):
    """Fewer words: no reading notes or method block, no "(Best)" in titles, Conclusions as bullets."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_the_page_carries_no_reading_notes_and_conclusions_are_bullets(self) -> None:
        html = build_studio.build([with_intervals(run_snapshot())])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var root = document.getElementById('root');
          return { text: root.innerText, titles: [].map.call(document.querySelectorAll('h1, section.card h2'), function (h) { return h.textContent; }),
                   boxes: [].map.call(document.querySelectorAll('.means'), function (m) { return m.querySelectorAll('li').length; }),
                   colours: [].map.call(document.querySelectorAll('.means li span[class^="v-"]'), function (x) { return x.className + '|' + getComputedStyle(x).color; }) };""")
        for gone in ("How to read this", "Verdicts, changes and 95% intervals", "Versions are numbered", "Not shown for this", "stay in this browser only"):
            self.assertNotIn(gone, got["text"])
        self.assertFalse([t for t in got["titles"] if "(Best)" in t], got["titles"])
        self.assertTrue(got["boxes"] and all(n >= 1 for n in got["boxes"]), f"every Conclusion should be bullets: {got['boxes']}")
        better = {c.split("|")[1] for c in got["colours"] if c.startswith("v-better")}
        noise = {c.split("|")[1] for c in got["colours"] if c.startswith("v-noise")}
        self.assertTrue(better and noise and not (better & noise), got["colours"])


class ValueAxisAndVerdictTests(unittest.TestCase):
    """Bar charts get a value axis from zero, every Conclusion looks the same, and every verdict is said."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_bars_have_a_value_axis_from_zero_and_every_conclusion_looks_the_same(self) -> None:
        html = build_studio.build([run_snapshot()])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var best = document.querySelector('[data-card="best"]');
          var ticks = [].map.call(best.querySelectorAll('.recharts-yAxis .recharts-cartesian-axis-tick-value, .recharts-cartesian-axis-tick-label'), function (t) { return t.textContent; });
          var borders = [].map.call(document.querySelectorAll('.means'), function (m) { return getComputedStyle(m).borderTopColor + ' ' + getComputedStyle(m).borderTopStyle; });
          var top = document.querySelector('header .means li');
          return { ticks: ticks, grid: best.querySelectorAll('.recharts-cartesian-grid-horizontal line').length, borders: borders, first: top ? top.textContent : '', chose: document.getElementById('root').innerText.indexOf('How Artemis chose Best') };""", more=True)
        self.assertIn("0", got["ticks"], got["ticks"])
        self.assertGreater(got["grid"], 0, "the Best card's bars need light gridlines")
        self.assertGreater(len(got["borders"]), 2)
        self.assertEqual(len(set(got["borders"])), 1, got["borders"])
        self.assertEqual(got["first"], "Best = highest Composite score across all metrics.")
        self.assertEqual(got["chose"], -1)

    def test_the_forest_shows_both_bands_when_one_change_is_huge(self) -> None:
        # This run's shape: a 99.9% gain next to a 500% regression.
        snap = with_intervals(run_snapshot())
        moved = [v for v in snap["versions"] if (v["metrics"].get("latency_ms") or {}).get("vsBaseline")]
        moved[0]["metrics"]["latency_ms"]["vsBaseline"].update(improvementPct=99.9, ciLowPct=99.8, ciHighPct=99.95, verdict="better")
        moved[-1]["metrics"]["latency_ms"]["vsBaseline"].update(improvementPct=-500.0, ciLowPct=-900.0, ciHighPct=-150.0, verdict="worse")
        html = build_studio.build([snap])
        widths = probed(html, embedded(html)["datasets"][0]["id"], """
          var rects = [].map.call(document.querySelectorAll('[data-card="forest"] .recharts-reference-area rect, [data-card="forest"] .recharts-reference-area path'), function (r) { return r.getBoundingClientRect().width; });
          return rects;""")
        self.assertEqual(len(widths), 2, widths)
        # -900% is past the outlier rule's 5x, so that row is clipped at the edge; and "% better" can't pass +100% on a lower-is-better time, so the green band is small but there.
        self.assertGreaterEqual(min(widths) / sum(widths), 0.05, f"one band is gone: {widths}")

    def test_every_verdict_reaches_the_conclusion_when_the_composite_best_is_not_significant_and_the_rest_regressed(self) -> None:
        # A real run's shape: Best at 1.4% less with an interval across 0, every other version significantly regressed.
        snap = with_intervals(run_snapshot())
        moved = [v for v in snap["versions"] if (v["metrics"].get("latency_ms") or {}).get("vsBaseline")]
        self.assertGreaterEqual(len(moved), 2)
        for best in (snap["webUiBest"], snap["bestLines"]):
            best.update(version=moved[0]["version"], label=moved[0]["label"])
        changes = [(1.4, -2.0, 4.0, "noise")] + [(-70.0 - 50 * i, -90.0 - 50 * i, -50.0 - 50 * i, "worse") for i in range(len(moved) - 1)]
        for v, (pct, lo, hi, verdict) in zip(moved, changes):
            v["metrics"]["latency_ms"]["pctBetter"] = pct
            v["metrics"]["latency_ms"]["vsBaseline"].update(improvementPct=pct, ciLowPct=lo, ciHighPct=hi, verdict=verdict)
            for r in snap["rankings"].get("latency_ms", []):
                if r["version"] == v["version"]:
                    r["pctBetter"] = pct
        html = build_studio.build([snap])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var lines = function (id) { var c = document.querySelector('[data-card="' + id + '"]'); return c ? [].map.call(c.querySelectorAll('.means li'), function (l) { return l.textContent; }) : null; };
          return { forest: lines('forest'), table: lines('table') };""", more=True)
        worst = moved[-1]["label"]
        for card in ("forest", "table"):
            text = " | ".join(got[card] or [])
            self.assertNotIn("No interval clears", text)
            self.assertRegex(text, rf"{len(moved) - 1} of \d+ significantly regressed: {worst} ", card)
        self.assertRegex(" | ".join(got["forest"]), rf"1 of {len(moved)} no significant difference: {moved[0]['label']} 1.4% less")
        self.assertNotIn("Best", " | ".join(got["forest"] + got["table"]), "one metric's Conclusion never names the Composite Best")


class BuilderRefusalAndTooltipTests(unittest.TestCase):
    """--only refuses a chart the data lacks, the pp line is falcon's, and a box needs falcon's quartiles."""

    def test_only_refuses_a_chart_the_data_cannot_draw(self) -> None:
        snap = run_snapshot()
        bare = copy.deepcopy(snap)  # no AI Metric: no AI chart and no second metric for the trade-off
        bare["metrics"] = [m for m in bare["metrics"] if m["kind"] != "quality"]
        for v in bare["versions"]:
            v["metrics"].pop("quality_score", None)
        for card, why in (("sessions", "one run has no sessions chart"), ("ai", "no version has an AI Metric score"), ("pareto", "no two metrics")):
            with self.subTest(card=card), self.assertRaisesRegex(ValueError, f"--only {card}: {why}"):
                build_studio.build([bare], only=card)
        for card in ("ai", "pareto"):  # the full fixture has both
            build_studio.build([snap], only=card)
        build_studio.build([project_snapshot(2)], only="sessions")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            path.write_text(json.dumps(snap), encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = build_studio.main(["--snapshot", str(path), "--only", "sessions", "--output", str(Path(tmp) / "out.html")])
            self.assertEqual(code, 2)
            self.assertFalse((Path(tmp) / "out.html").exists())
            self.assertIn("--only sessions:", err.getvalue())

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_the_builder_refuses_exactly_the_charts_the_page_leaves_out(self) -> None:
        # drawable() restates the page's pareto() and hasAIScores(); this holds the two together.
        full = run_snapshot()
        bare = copy.deepcopy(full)
        bare["metrics"] = [m for m in bare["metrics"] if m["kind"] != "quality"]
        for v in bare["versions"]:
            v["metrics"].pop("quality_score", None)
        flat = copy.deepcopy(full)
        for v in flat["versions"]:
            if v["metrics"].get("quality_score"):
                v["metrics"]["quality_score"]["mean"] = 0.5
        unscored = copy.deepcopy(full)
        for v in unscored["versions"]:
            if v["metrics"].get("quality_score"):
                v["metrics"]["quality_score"]["mean"] = None

        def with_axes(snap, keys):  # --pareto, built the way the collector builds it
            snap = copy.deepcopy(snap)
            defs = {m["key"]: m for m in snap["metrics"]}
            snap["pareto"] = {"axes": [{"key": k, "higherIsBetter": defs[k]["higherIsBetter"], "kind": defs[k]["kind"]} for k in keys],
                              "points": collect_discovery.pareto_front(snap["versions"], keys, defs)}
            return snap
        axes = with_axes(full, ["latency_ms", "compile_runtime"])
        same = copy.deepcopy(bare)
        for v in same["versions"]:
            if v["metrics"].get("compile_runtime"):
                v["metrics"]["compile_runtime"]["mean"] = 2.0
        flat_axes = with_axes(same, ["latency_ms", "compile_runtime"])
        no_front, no_points = copy.deepcopy(axes), copy.deepcopy(axes)
        no_front["pareto"]["points"] = []
        del no_points["pareto"]["points"]
        for name, snap in (("full", full), ("bare", bare), ("flat", flat), ("unscored", unscored), ("axes", axes), ("flat axes", flat_axes),
                           ("empty front", no_front), ("no points", no_points)):
            html = build_studio.build([snap])
            ds = embedded(html)["datasets"][0]
            drawn = probed(html, ds["id"], "return [].map.call(document.querySelectorAll('section.card'), function (c) { return c.dataset.card; });", more=True)
            for card in ("pareto", "ai"):
                with self.subTest(snapshot=name, card=card):
                    self.assertEqual(card in drawn, build_studio.drawable(card, ds) is None, drawn)
            if name in ("empty front", "no points"):  # left out cleanly: no card, no error message anywhere
                self.assertNotIn("pareto", drawn)
                self.assertEqual(probed(html, ds["id"], "return document.querySelectorAll('.err').length;", more=True), 0, name)

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_the_forest_tooltip_shows_falcons_points_change_and_never_works_one_out(self) -> None:
        def page(points):
            snap = with_intervals(run_snapshot())
            for m in snap["metrics"]:
                if m["key"] == "latency_ms":
                    m.update(family="model", higherIsBetter=True, bounded=True, unit="")
            for v in snap["versions"]:
                vb = (v["metrics"].get("latency_ms") or {}).get("vsBaseline")
                if vb and points is not None:
                    vb["improvementPoints"] = points
            return build_studio.build([snap], only="forest")
        hover = "var d = document.querySelector('[data-card=\"forest\"] .recharts-scatter-symbol'); ['mouseover', 'mousemove'].forEach(function (t) { d.dispatchEvent(new MouseEvent(t, { bubbles: true })); });"
        tip = "var w = document.querySelector('.recharts-tooltip-wrapper'); return w ? w.innerText : '';"
        with_points, without = (probed(h, embedded(h)["datasets"][0]["id"], tip, act=hover) for h in (page(0.05), page(None)))
        self.assertIn("+5.0 pp, falcon's difference of the means", with_points)
        self.assertIn("vs the original", without)  # the tooltip drew
        self.assertNotIn(" pp", without)

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_a_machine_group_draws_its_runs_not_a_box_without_falcons_quartiles(self) -> None:
        snap = run_snapshot()
        sides = [snap["baseline"]["metrics"]["latency_ms"]] + [v["metrics"]["latency_ms"] for v in snap["versions"] if v["metrics"].get("latency_ms")]
        for k, st in enumerate(sides):
            st["runs"] = [{"value": 5.0 + k + i * 0.5, "runner": "box-a" if i % 2 else "box-b"} for i in range(6)]
            st.update(min=5.0 + k, max=7.5 + k, q1=5.6 + k, median=6.2 + k, q3=6.9 + k)
        html = build_studio.build([snap], only="box")
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var c = document.querySelector('[data-card="box"]');
          return { rects: [].filter.call(c.querySelectorAll('svg rect'), function (r) { return /NaN/.test(r.outerHTML); }).length,
                   lines: [].filter.call(c.querySelectorAll('svg line'), function (l) { return /NaN/.test(l.outerHTML); }).length,
                   dots: c.querySelectorAll('svg circle').length,
                   machine: [].some.call(c.querySelectorAll('button'), function (b) { return b.getAttribute('aria-pressed') === 'true' && /Machine/.test(b.textContent); }) };""",
            act="[].forEach.call(document.querySelectorAll('[data-card=\"box\"] button'), function (b) { if (/^Machine$/.test(b.textContent.trim())) b.click(); });")
        self.assertTrue(got["machine"], "the Machine grouping did not switch on")
        self.assertEqual((got["rects"], got["lines"]), (0, 0), got)
        self.assertGreaterEqual(got["dots"], 12)


class BestOnlyOverallTests(unittest.TestCase):
    @unittest.skipUnless(CHROME, "no Chrome")
    def test_best_is_marked_only_where_the_chart_is_about_the_overall_pick(self) -> None:
        html = build_studio.build([with_intervals(run_snapshot())])
        got = probed(html, embedded(html)["datasets"][0]["id"], VISIBLE + r"""
          var cards = ['ranked', 'forest', 'time', 'box', 'table', 'pareto', 'ai'].filter(card);
          return { marked: cards.filter(function (id) { return /\bBest\b/.test(card(id).innerText); }),
                   best: /\bBest\b/.test(card('best').innerText), cards: cards };""", more=True)
        self.assertGreaterEqual(len(got["cards"]), 6, got)
        self.assertEqual(got["marked"], [], "a per-metric chart marks the Composite Best")
        self.assertTrue(got["best"], "the Is-it-better card still names Best")
        project = build_studio.build([project_snapshot(2)])
        sessions = probed(project, embedded(project)["datasets"][0]["id"], "return document.querySelector('[data-card=\"sessions\"]').innerText;")
        self.assertNotRegex(sessions, r"\bBest\b", "the sessions chart marks a Composite Best")


class OutlierAndAxisTests(unittest.TestCase):
    """The outlier rule, no impossible axis values, even ticks, phone labels clear of marks, plain words."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    @staticmethod
    def shop_shape() -> dict:
        # A real run's shape: three ~98-99.9% gains on a lower-is-better time, and v4 at 517.6% more, interval 11x the rest.
        snap = with_intervals(run_snapshot())
        moved = [v for v in snap["versions"] if (v["metrics"].get("latency_ms") or {}).get("vsBaseline")]
        for v, (pct, lo, hi, verdict) in zip(moved, [(99.9, 99.8, 99.95, "better"), (98.3, 98.1, 98.6, "better"), (-517.6, -1100.0, -60.0, "worse")]):
            v["metrics"]["latency_ms"]["pctBetter"] = pct
            v["metrics"]["latency_ms"]["vsBaseline"].update(improvementPct=pct, ciLowPct=lo, ciHighPct=hi, verdict=verdict)
            for r in snap["rankings"]["latency_ms"]:
                if r["version"] == v["version"]:
                    r["pctBetter"] = pct
        sides = [snap["baseline"]["metrics"]["latency_ms"]] + [v["metrics"]["latency_ms"] for v in moved]
        for st, runs in zip(sides, ([9641.3, 9358.7, 9266.0, 9379.5, 9400.0], [9.0, 9.5, 10.0, 10.5, 11.0], [150.0, 160.0, 170.0, 165.0, 155.0], [57000.0, 70000.0, 81000.0, 90000.0, 99053.0])):
            st.update(runs=runs, min=min(runs), max=max(runs), mean=sum(runs) / len(runs), count=len(runs), q1=sorted(runs)[1], median=sorted(runs)[2], q3=sorted(runs)[3])
        return snap

    TICKS = r"""
      var axisText = function (id, axis) { return [].map.call(document.querySelectorAll('[data-card="' + id + '"] .recharts-' + axis + '-tick-labels text'), function (t) { return t.textContent.trim(); }).filter(function (t) { return /^[\u2212+-]?[\d,.]+%?$/.test(t); }); };
      var ticks = function (id) { return axisText(id, 'xAxis'); }, yticks = function (id) { return axisText(id, 'yAxis'); };
      var arrows = function (id) { return document.querySelectorAll('[data-card="' + id + '"] .clip-arrow').length; };
      var txt = function (id) { return document.querySelector('[data-card="' + id + '"]').innerText; };"""

    @staticmethod
    def pct(t: str) -> float:
        return float(t.replace("−", "-").replace("+", "").replace("%", ""))

    def test_a_far_outlier_is_clipped_at_the_edge_with_its_value_and_the_axis_fits_the_rest(self) -> None:
        html = build_studio.build([self.shop_shape()])
        got = probed(html, embedded(html)["datasets"][0]["id"], self.TICKS + """
          return { forest: ticks('forest'), ranked: ticks('ranked'), box: yticks('box'), arrows: [arrows('forest'), arrows('ranked'), arrows('box')],
                   forestText: txt('forest'), boxText: txt('box'), h1: document.querySelector('h1').textContent };""", more=True)
        forest = [self.pct(t) for t in got["forest"]]
        self.assertEqual(got["arrows"][0], 1, "the forest clips v4 at its edge")
        self.assertGreaterEqual(min(forest), -200, f"the forest axis fits the rest, not v4: {forest}")
        self.assertIn("517.6% more", got["forestText"], "a clipped row keeps its value")
        self.assertEqual(got["arrows"][1], 1, "the ranked bars clip v4's 517.6% too (5.2x the rest)")
        self.assertLess(min(self.pct(t) for t in got["ranked"]), 0, "a clipped regression keeps room on the worse side")
        self.assertLessEqual(-min(self.pct(t) for t in got["ranked"]), 100, got["ranked"])
        self.assertEqual(got["arrows"][2], 1, "the box card clips v4's 99,053 ms group")
        box = [float(t.replace(",", "")) for t in got["box"]]
        self.assertGreaterEqual(min(box), 0, f"ms can't go below 0: {box}")
        self.assertLess(max(box), 20000, f"the box axis fits the rest: {box}")
        self.assertIn("to 99,053", got["boxText"].replace("\\n", " "))

    def test_no_axis_shows_an_impossible_value_and_ticks_step_evenly(self) -> None:
        html = build_studio.build([self.shop_shape()])
        got = probed(html, embedded(html)["datasets"][0]["id"], self.TICKS + """
          return { forest: ticks('forest'), ranked: ticks('ranked'), time: yticks('time') };""", more=True)
        for card in ("forest", "ranked"):
            vals = [self.pct(t) for t in got[card]]
            with self.subTest(card=card):
                self.assertLessEqual(max(vals), 100, f"a lower-is-better time can't be more than 100% better: {vals}")
                steps = {round(b - a, 6) for a, b in zip(vals, vals[1:])}
                self.assertEqual(len(steps), 1, f"one step on both sides of 0: {vals}")
        self.assertLessEqual(max(self.pct(t) for t in got["time"]), 100, got["time"])

    def test_a_phone_forest_keeps_values_clear_of_the_marks(self) -> None:
        html = build_studio.build([self.shop_shape()])
        hits = probed(html, embedded(html)["datasets"][0]["id"], """
          var c = document.querySelector('[data-card="forest"] svg.recharts-surface'), box = function (e) { return e.getBoundingClientRect(); };
          var marks = [].slice.call(c.querySelectorAll('.recharts-scatter-symbol circle, .recharts-scatter-symbol polygon, .recharts-errorBar line'));
          var labels = [].filter.call(c.querySelectorAll('text'), function (t) { return /% (less|more)/.test(t.textContent); });
          var out = []; labels.forEach(function (t) { var a = box(t); marks.forEach(function (m) { var b = box(m); if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) out.push(t.textContent); }); });
          return { hits: out, labels: labels.length };""", phone=True)
        self.assertGreaterEqual(hits["labels"], 3, hits)
        self.assertEqual(hits["hits"], [], "a value covers a dot or an interval on a phone")

    def test_the_trend_draws_versions_as_dots_not_a_joined_line(self) -> None:
        html = build_studio.build([self.shop_shape()])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var curve = document.querySelector('[data-card="time"] .recharts-line-curve');
          return { stroke: curve ? curve.getAttribute('stroke') : 'none', dots: document.querySelectorAll('[data-card="time"] .recharts-line-dots circle, [data-card="time"] .recharts-line-dots > g circle').length };""", more=True)
        self.assertEqual(got["stroke"], "none", "independent versions are never joined into a trend line")
        self.assertGreater(got["dots"], 0, got)

    def test_conclusions_say_each_count_once_in_plain_words(self) -> None:
        html = build_studio.build([self.shop_shape()])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var lines = function (id) { return [].map.call(document.querySelectorAll('[data-card="' + id + '"] .means li'), function (l) { return l.textContent; }); };
          return { forest: lines('forest'), table: lines('table') };""", more=True)
        text = " | ".join(got["forest"] + got["table"])
        self.assertNotIn("Highest floor", text)
        self.assertIn("Surest gain: v1, at least 99.8% less, the low end of its 95% interval", text)
        self.assertEqual(sum("significantly improved" in l for l in got["table"]), 1, got["table"])

    def test_the_headline_names_both_when_the_overall_pick_is_not_the_best_on_the_lead_metric(self) -> None:
        snap = self.shop_shape()
        v2 = next(v for v in snap["versions"] if v["label"] == "v2")
        for best in (snap["webUiBest"], snap["bestLines"]):
            best.update(version=v2["version"], label="v2")
        snap["perMetricWinners"]["latency_ms"]["raw"].update(version=1, label="v1", pctBetter=99.9)
        html = build_studio.build([snap])
        h1 = probed(html, embedded(html)["datasets"][0]["id"], "return document.querySelector('h1').textContent;")
        self.assertEqual(h1, "v2, Artemis's overall pick, takes 98.3% less time than the original on Latency (ms), significantly improved; v1 is fastest on Latency (ms) alone (99.9% less)")


class OneCardPageTests(unittest.TestCase):
    """A one-card page names the Best version, since it has no headline."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_a_one_card_page_names_the_best_version(self) -> None:
        snap = run_snapshot()
        html = build_studio.build([snap], only="forest")
        text = probed(html, embedded(html)["datasets"][0]["id"], "return document.getElementById('root').innerText;")
        self.assertIn(f"Best = highest Composite score across all metrics: {snap['bestLines']['label']}.", text)


class IterationWordingTests(unittest.TestCase):
    """A run is a script run and an iteration is one reading, as the Web UI says "Iterations 8"."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_reading_counts_say_iterations_never_runs(self) -> None:
        snap = with_intervals(run_snapshot())
        html = build_studio.build([snap])
        text = probed(html, embedded(html)["datasets"][0]["id"], "return document.getElementById('root').innerText;", more=True).replace("\u00ad", "")
        self.assertRegex(text, r"from \d+ iterations")
        self.assertIn("Iterations", text)  # the table's column
        self.assertIn("How spread out are the iterations on", text)
        self.assertIsNone(re.search(r"\b\d+ runs\b|\b1 run\b|\bRuns\b", text), re.findall(r".{30}\b(?:\d+ runs|1 run|Runs)\b.{20}", text))


class AIScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_an_ai_score_equal_to_the_originals_reads_plain_not_like_a_verdict(self) -> None:
        # A judged score of 0.75 against the original's 0.75 is falcon's 0%; it must not look like the amber of a verdict.
        snap = run_snapshot()
        scored = [v for v in snap["versions"] if (v["metrics"].get("quality_score") or {}).get("mean") is not None]
        scored[0]["metrics"]["quality_score"]["pctBetter"] = 0.0
        html = build_studio.build([snap])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          document.querySelectorAll('details').forEach(function (d) { d.open = true; });
          var c = document.querySelector('[data-card="ai"]'), noise = getComputedStyle(document.documentElement).getPropertyValue('--noise').trim();
          var fills = [].map.call(c.querySelectorAll('svg rect'), function (r) { return (r.getAttribute('fill') || '').trim(); });
          return { zero: [].some.call(c.querySelectorAll('svg text'), function (t) { return t.textContent === '0%'; }), amber: fills.filter(function (f) { return f === noise; }).length,
                   pills: c.querySelectorAll('svg rect[rx="11"]').length };""", act="document.querySelectorAll('details').forEach(function (d) { d.open = true; });", more=True)
        self.assertTrue(got["zero"], got)
        self.assertEqual((got["amber"], got["pills"]), (0, 0), "a same score is drawn plain, never in the amber of a verdict")


class VersionLinkTests(unittest.TestCase):
    """A ranked bar or a forest row opens that version's Code tab in Artemis, built from the snapshot's own ids only."""

    BASE = "https://testing.artemis.turintech.ai/projects/proj-1/discover/run-1"
    JS = r"""
      var links = function (id) { return [].map.call(document.querySelectorAll('[data-card="' + id + '"] svg a'), function (a) { return { href: a.getAttribute('href'), target: a.getAttribute('target'), rel: a.getAttribute('rel'), label: a.getAttribute('aria-label') }; }); };
      var tabbable = function (id) { return [].filter.call(document.querySelectorAll('[data-card="' + id + '"] svg a'), function (a) { return a.getAttribute('tabindex') !== '-1'; }); };
      var a = tabbable('ranked')[0]; if (a) a.focus();
      return { ranked: links('ranked'), forest: links('forest'), focused: !!a && document.activeElement === a,
               stops: [tabbable('ranked').length, tabbable('forest').length], rows: [document.querySelectorAll('[data-card="ranked"] .recharts-bar-rectangle').length, document.querySelectorAll('[data-card="forest"] .recharts-scatter-symbol').length] };"""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def page(self, url, ids=True) -> dict:
        snap = with_intervals(run_snapshot())
        snap["run"]["webUrl"] = url
        for v in snap["versions"]:
            v["id"] = f"ver-{v['version']}" if ids else None
        html = build_studio.build([snap])
        return probed(html, embedded(html)["datasets"][0]["id"], self.JS)

    def test_a_bar_and_a_forest_row_open_the_versions_code_in_a_new_tab(self) -> None:
        got = self.page(self.BASE)
        self.assertTrue(got["ranked"] and got["forest"], got)
        for link in got["ranked"] + got["forest"]:
            self.assertRegex(link["href"], "^" + re.escape(self.BASE) + r"/versions/ver-\d+$")
            self.assertEqual((link["target"], link["rel"]), ("_blank", "noopener"))
            self.assertRegex(link["label"], r"^Open v\d+'s code change in Artemis \(new tab\)$")
        self.assertTrue(got["focused"], "a version link must take keyboard focus")
        self.assertEqual(got["stops"], got["rows"], "one Tab stop per version: its label, not its mark too")

    def test_no_link_without_the_run_url_or_the_version_id(self) -> None:
        for url, ids in ((None, True), (self.BASE, False), ("https://evil.example/projects/p/discover/r", True), ("http://testing.artemis.turintech.ai/projects/p/discover/r", True), ("https://artemis.turintech.ai.evil.example/projects/p/discover/r", True), (self.BASE + "/versions", True)):
            with self.subTest(url=url, ids=ids):
                got = self.page(url, ids)
                self.assertEqual((got["ranked"], got["forest"]), ([], []))
                self.assertTrue(all(got["rows"]), f"a card drew no rows, so there was nothing to link: {got['rows']}")


if __name__ == "__main__":
    unittest.main()
