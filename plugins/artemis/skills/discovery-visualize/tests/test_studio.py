#!/usr/bin/env python3
"""Checks for the checker's --studio mode on built chart studio pages."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_studio  # noqa: E402
import check_report  # noqa: E402
import collect_discovery  # noqa: E402
from studio_fixtures import CHROME, dump, embedded, late, probed, project_snapshot, run_snapshot, with_data  # noqa: E402


class StaticCheckTests(unittest.TestCase):
    def test_built_page_passes(self) -> None:
        self.assertEqual(check_report.studio_static_checks(build_studio.build([run_snapshot()])), [])

    def test_unbuilt_template_fails(self) -> None:
        template = build_studio.TEMPLATE.read_text(encoding="utf-8")
        self.assertTrue(any(p.startswith("NOT BUILT") for p in check_report.studio_static_checks(template)))

    def test_a_data_fetch_fails_but_the_font_fetch_passes(self) -> None:
        html = build_studio.build([run_snapshot()])
        self.assertIn('fetch("https://fonts.googleapis.com/', html)
        bad = html.replace("var fontCss = null;", 'var fontCss = null; fetch("https://example.com/snap.json");')
        self.assertTrue(any(p.startswith("LIVE FETCH") for p in check_report.studio_static_checks(bad)))
        bad = html.replace("var fontCss = null;", "var fontCss = null; fetch(url);")
        self.assertTrue(any(p.startswith("LIVE FETCH") for p in check_report.studio_static_checks(bad)))

    def test_any_monospace_fails(self) -> None:
        html = build_studio.build([run_snapshot()])
        for bad in ('--mono: "Courier New", monospace;', "IBM Plex Mono"):
            with self.subTest(bad=bad):
                mutant = html.replace("var fontCss = null;", "var fontCss = null; /* " + bad + " */", 1)
                self.assertTrue(any(p.startswith("MONOSPACE") for p in check_report.studio_static_checks(mutant)))

    def test_a_moved_font_loader_fails(self) -> None:
        html = build_studio.build([run_snapshot()]).replace("function exportFonts()", "function loadFonts()")
        html = html.replace("var fontCss = null;", 'var fontCss = null; var url = "https://evil.example"; fetch(url);', 1)
        self.assertTrue(any("font loader" in p for p in check_report.studio_static_checks(html)))

    def test_a_spaced_fetch_fails(self) -> None:
        html = build_studio.build([run_snapshot()]).replace("var fontCss = null;", 'var fontCss = null; fetch ("https://example.com/x");', 1)
        self.assertTrue(any(p.startswith("LIVE FETCH") for p in check_report.studio_static_checks(html)))

    def test_no_datasets_is_no_data(self) -> None:
        html = with_data(build_studio.build([run_snapshot()]), lambda d: d.update(datasets=[]))
        self.assertIn("NO DATA: the page holds no snapshot to draw", check_report.studio_static_checks(html))

    def test_an_xhr_fails(self) -> None:
        html = build_studio.build([run_snapshot()]).replace("var fontCss = null;", "var fontCss = null; new XMLHttpRequest();", 1)
        self.assertTrue(any(p.startswith("LIVE FETCH") for p in check_report.studio_static_checks(html)))

    def test_unreadable_data_says_why(self) -> None:
        html = build_studio.build([run_snapshot()])
        broken = html.replace('id="studio-data">{', 'id="studio-data">{,', 1)
        self.assertTrue(any(p.startswith("NO DATA: studio-data does not parse") for p in check_report.studio_static_checks(broken)))
        no_id = re.sub(r'"id":"r-[^"]*"', '"id":""', html, count=1)
        self.assertIn("NO DATA: dataset 1 in studio-data has no id", check_report.studio_static_checks(no_id))

    def test_a_dash_fails(self) -> None:
        html = build_studio.build([run_snapshot()]).replace(">Reset<", ">Reset \u2014 now<")
        self.assertTrue(any(p.startswith("DASH") for p in check_report.studio_static_checks(html)))

    def test_every_dataset_and_session_is_a_view(self) -> None:
        html = build_studio.build([run_snapshot(), project_snapshot(2)])
        self.assertEqual([s for _, s in check_report.studio_views(html)], [0, 0, 1])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_the_checkers_own_probe_parses(self) -> None:
        # A syntax slip in the probe makes every page fail as "did not finish rendering", with no cause.
        script = re.search(r"<script>(.*)</script>", check_report.studio_probe(), re.S).group(1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "probe.js"
            path.write_text(script, encoding="utf-8")
            subprocess.run(["node", "--check", str(path)], check=True, capture_output=True)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_page_script_parses(self) -> None:
        html = build_studio.build([run_snapshot()])
        script = max(re.findall(r"<script>(.*?)</script>", html, re.S), key=len)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "studio.js"
            path.write_text(script, encoding="utf-8")
            subprocess.run(["node", "--check", str(path)], check=True)


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class RenderTests(unittest.TestCase):
    def test_every_view_renders_clean_with_no_label_overlapping_or_cut(self) -> None:
        # The checker measures every label in every chart, view and control state, at 1000px and 390px.
        html = build_studio.build([run_snapshot(), project_snapshot(3)], failed=["2:2:1"])
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])

    def test_a_note_about_a_missing_reading_is_shown_word_for_word(self) -> None:
        snap = run_snapshot()
        best = snap["bestLines"]
        note = f"{best['label']} has no reading on build_size; v1 is best on it"
        best["notes"] = dict(best.get("notes") or {}, build_size=note)
        html = build_studio.build([snap])
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
        # Drop the line that shows it, and the checker must say so.
        hidden = html.replace("noReading(D.best)", "[]")
        self.assertNotEqual(hidden, html)
        problems = check_report.studio_render_checks(hidden, CHROME)
        self.assertTrue(any("MISSING BEST NOTE" in p and "no reading on build_size" in p for p in problems), problems)

    def test_a_page_that_never_says_how_best_was_chosen_fails(self) -> None:
        html = build_studio.build([run_snapshot()])
        self.assertIn('"Best = highest Composite score across all metrics."', html)
        problems = check_report.studio_render_checks(html.replace('"Best = highest Composite score across all metrics."', '""'), CHROME)
        self.assertTrue(any(p.startswith("MISSING BEST RULE") for p in problems), problems)

    def test_many_sessions_fit_a_phone(self) -> None:
        html = build_studio.build([project_snapshot(6)])
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
        # Buttons for every session are wider than a phone; the checker sees it at 390px.
        wide = html.replace("ds.sessions.length > 4 ?", "ds.sessions.length > 40 ?").replace("String(i + 1), false,", "\"Discovery session \" + (i + 1), false,")
        self.assertNotEqual(wide, html)
        problems = check_report.studio_render_checks(wide, CHROME)
        self.assertTrue(any("WIDER THAN THE WINDOW" in p and "390px" in p for p in problems), problems)

    def test_six_sessions_rank_each_sessions_top_version_until_show_all(self) -> None:
        probe = """<script>setTimeout(function () {
  var card = function () { return document.querySelector('[data-card="sessions"]'); };
  var bars = function () { return [].filter.call(card().querySelectorAll("tspan"), function (t) { return /^version /.test(t.textContent); }).length; };
  var out = { top: bars(), labels: [].map.call(card().querySelectorAll('.seg[aria-label="Show"] button'), function (b) { return b.textContent; }) };
  var all = [].filter.call(card().querySelectorAll('.seg[aria-label="Show"] button'), function (b) { return /^All /.test(b.textContent); })[0];
  if (all) all.click();
  setTimeout(function () { out.all = bars(); var p = document.createElement("pre"); p.id = "tops"; p.textContent = JSON.stringify(out); document.body.appendChild(p); }, 800);
}, 1500);</script>"""
        project = project_snapshot(6)
        per_run = len(project["runs"][0]["rankings"][project["runs"][0]["metrics"][0]["key"]])
        self.assertGreater(per_run, 1)
        found = re.search(r'<pre id="tops">(.*?)</pre>', dump(build_studio.build([project]), "p-proj-1", 0, probe))
        self.assertIsNotNone(found)
        got = json.loads(found.group(1).replace("&quot;", '"'))
        self.assertEqual(got["top"], 6)
        self.assertEqual(got["labels"], ["Each Discovery session's top", f"All {6 * per_run} versions"])
        self.assertEqual(got["all"], 6 * per_run)
        # Five sessions keep every version and no Show control.
        five = re.search(r'<pre id="tops">(.*?)</pre>', dump(build_studio.build([project_snapshot(5)]), "p-proj-1", 0, probe))
        self.assertIsNotNone(five)
        got5 = json.loads(five.group(1).replace("&quot;", '"'))
        self.assertEqual((got5["top"], got5["labels"]), (5 * per_run, []))

    def test_three_sessions_each_get_a_line_and_a_summary(self) -> None:
        html = build_studio.build([project_snapshot(3)])
        click = '<script>setTimeout(function () { [].filter.call(document.querySelectorAll("button"), function (b) { return b.textContent === "Over time"; })[0].click(); }, 1500);</script>'
        dom = dump(html, "p-proj-1", 0, click)
        for text in ("Discovery session 3 (dotted)", "session 3"):
            self.assertIn(text, dom)
        self.assertRegex(dom.replace("'", "&#39;"), r'session 3&#39;s top on [^:<]+: <span class="num">')

    def test_end_labels_stay_inside_the_plot_when_lines_end_low(self) -> None:
        project = project_snapshot(5)
        for snap in project["runs"][1:]:
            for v in snap["versions"]:
                for stat in (v.get("metrics") or {}).values():
                    if stat and stat.get("pctBetter") is not None:
                        stat["pctBetter"] = -40.0
        html = build_studio.build([project])
        probe = """<script>setTimeout(function () {
  [].filter.call(document.querySelectorAll("button"), function (b) { return b.textContent === "Over time"; })[0].click();
  setTimeout(function () {
    var grid = document.querySelector(".recharts-cartesian-grid").getBoundingClientRect(), out = [];
    [].forEach.call(document.querySelectorAll("text"), function (t) { if (/^Discovery session \\d+$/.test(t.textContent)) { var r = t.getBoundingClientRect(); out.push([t.textContent, Math.round(r.top), Math.round(r.bottom)]); } });
    var p = document.createElement("pre"); p.id = "ends"; p.textContent = JSON.stringify({ top: grid.top, bottom: grid.bottom, labels: out }); document.body.appendChild(p);
  }, 800);
}, 1500);</script>"""
        found = re.search(r'<pre id="ends">(.*?)</pre>', dump(html, "p-proj-1", 0, probe))
        self.assertIsNotNone(found)
        ends = json.loads(found.group(1).replace("&quot;", '"'))
        self.assertEqual(len(ends["labels"]), 5)
        spans = sorted((top, bottom) for _, top, bottom in ends["labels"])
        for top, bottom in spans:
            self.assertGreaterEqual(top, ends["top"] - 12)
            self.assertLessEqual(bottom, ends["bottom"] + 2)
        for (_, b1), (t2, _) in zip(spans, spans[1:]):
            self.assertLessEqual(b1, t2 + 1)

    def test_a_view_behind_a_control_is_drawn_too(self) -> None:
        a = 'useCard(props.scope, "time", { mode: "pct" }), c = cs[0], hd = c.hidden || {};'
        html = build_studio.build([run_snapshot()])
        self.assertEqual(html.count(a), 1)
        problems = check_report.studio_render_checks(html.replace(a, a + ' if (c.mode === "mean") throw new Error("mean view broke");'), CHROME)
        self.assertTrue(any(p.startswith("SCRIPT ERROR: mean view broke (after ") for p in problems), problems)
        dark = html.replace("function App() {", 'function App() { if (document.documentElement.getAttribute("data-theme") === "dark") throw new Error("dark broke");', 1)
        self.assertTrue(any(p.startswith("SCRIPT ERROR: dark broke (after Theme > Dark)") for p in check_report.studio_render_checks(dark, CHROME)))

    def test_an_unknown_family_or_profile_falls_back_to_the_default(self) -> None:
        # An unknown family on every metric, or an unknown run profile: the default layout, never the model one
        # (which would move the trade-off card up among the lead cards).
        for family, profile in (("speech", None), (None, "speech")):
            with self.subTest(family=family, profile=profile):
                snap = run_snapshot()
                if profile:
                    snap["profile"] = profile
                for m in snap["metrics"]:
                    if family:
                        m["family"] = family
                html = build_studio.build([snap])
                self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
                order = probed(html, embedded(html)["datasets"][0]["id"], "return [].map.call(document.querySelectorAll('.page > section.card'), function (c) { return c.getAttribute('data-card'); });")
                self.assertEqual(order[:3], ["best", "ranked", "forest"])

    def test_sessions_of_different_tasks_say_their_changes_do_not_compare(self) -> None:
        def card(html):
            probe = '<script>setTimeout(function () { var c = document.querySelector("[data-card=sessions]"); var d = document.createElement("pre"); d.id = "s"; d.textContent = c.querySelector("h2").textContent + " || " + c.querySelector(".means").textContent; document.body.appendChild(d); }, 2500);</script>'
            found = re.search(r'<pre id="s">(.*?)</pre>', dump(html, "p-proj-1", 0, probe), re.S)
            return found.group(1).replace("&#39;", "'")
        same = card(build_studio.build([project_snapshot(2)]))
        self.assertIn("How did each Discovery session do on", same)
        self.assertNotIn("different task", same)
        task = project_snapshot(2)
        task["runs"][0]["run"]["taskDescription"] = "Rewrite query A, faster."
        task["runs"][1]["run"]["taskDescription"] = "Rewrite query B, faster."
        text = card(build_studio.build([task]))
        self.assertIn("Discovery sessions in this project (each against its own original)", text)
        self.assertIn("Each Discovery session here is a different task", text)
        self.assertIn("Discovery session 2's top on ", text)
        bench = project_snapshot(2)  # same task text, but originals far apart: another benchmark
        for stat in bench["runs"][1]["baseline"]["metrics"].values():
            if isinstance(stat, dict) and stat.get("mean"):
                stat["mean"] *= 5
        self.assertIn("Discovery sessions in this project", card(build_studio.build([bench])))

    def test_a_one_card_page_passes_with_its_card_heading_as_title(self) -> None:
        html = build_studio.build([run_snapshot()], only="ranked")
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])

    def test_a_lone_run_with_marks_keeps_the_run_layout(self) -> None:
        html = build_studio.build([run_snapshot()], failed=["1:1:2"])
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
        dom = dump(html, embedded(html)["datasets"][0]["id"])
        self.assertIn("Failed your correctness check", dom.split("<script")[0] + "".join(p.split("</script>", 1)[-1] for p in dom.split("<script")[1:]))
        for sessions_only in ("How did each Discovery session do", "Discovery session 1</span>", "different task"):
            self.assertNotIn(sessions_only, re.sub(r"<script.*?</script>", "", dom, flags=re.S))

    def test_a_menu_option_and_a_hidden_series_are_drawn_too(self) -> None:
        snap = run_snapshot()
        for m in snap["metrics"]:
            if m["key"] == "compile_runtime":
                m["kind"] = "target"  # a second ranked metric, so the forest's menu has another option
        html = build_studio.build([snap])
        forest = 'useCard(props.scope, "forest", { scale: "lin" }), c = cs[0], hd = c.hidden || {};'
        best = 'useCard(props.scope, "best", { offM: derived }), c = cs[0], hd = c.hidden || {};'
        self.assertEqual((html.count(forest), html.count(best)), (1, 1))
        menu = html.replace(forest, forest + ' if (c.metric && c.metric !== D.primary) throw new Error("other metric broke");')
        problems = check_report.studio_render_checks(menu, CHROME)
        self.assertTrue(any(p.startswith("SCRIPT ERROR: other metric broke (after How sure is each change") for p in problems), problems)
        legend = html.replace(best, best + ' if (Object.keys(hd).some(function (k) { return hd[k]; })) throw new Error("hidden series broke");')
        problems = check_report.studio_render_checks(legend, CHROME)
        self.assertTrue(any(p.startswith("SCRIPT ERROR: hidden series broke (after ") and "> legend " in p for p in problems), problems)

    def test_a_walk_over_the_cap_says_so(self) -> None:
        with mock.patch.object(check_report, "STUDIO_PROBE", check_report.STUDIO_PROBE.replace("MAX = 400", "MAX = 2")):
            problems = check_report.studio_render_checks(build_studio.build([run_snapshot()]), CHROME)
        self.assertTrue(any(p.startswith("WALK CUT SHORT: ") and "only the first 2 were drawn" in p for p in problems), problems)

    def test_a_phone_sees_the_whole_table_or_a_cue(self) -> None:
        snap = run_snapshot()
        snap["versions"][0]["experimentTitle"] = "Use bucket_time_keys_before_probing_hash_join_partitions in query_planner.optimize"
        html = build_studio.build([snap])
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
        css = "table.sum .wide { display: none; }"
        self.assertEqual(html.count(css), 1)
        hidden = html.replace(css, "", 1).replace("table.sum { min-width: 0; font-size: 15px; }", "", 1)
        problems = check_report.studio_render_checks(hidden, CHROME)
        self.assertTrue(any(p.startswith("HIDDEN BEHIND A SIDEWAYS SCROLL, NO CUE: Every version on") and "390px" in p for p in problems), problems)

    def test_every_change_axis_shows_zero(self) -> None:
        # One version far worse than the rest: the axis runs further left than right, and 0 must still be labelled.
        snap = run_snapshot()
        key = next(m["key"] for m in snap["metrics"] if m["kind"] == "target")
        for r in snap["rankings"][key][-1:]:
            r["pctBetter"] = -440.0
        html = build_studio.build([snap])
        probe = '<script>setTimeout(function () { var out = [].map.call(document.querySelectorAll(".card"), function (c) { var h = c.querySelector("h2"), xs = [].map.call(c.querySelectorAll("svg text"), function (t) { return t.textContent; }); return (h ? h.textContent : "") + "=" + xs.join("|"); }); var d = document.createElement("pre"); d.id = "ax"; d.textContent = JSON.stringify(out); document.body.appendChild(d); }, 2500);</script>'
        found = re.search(r'<pre id="ax">(.*?)</pre>', dump(html, embedded(html)["datasets"][0]["id"], 0, probe))
        cards = json.loads(found.group(1).replace("&quot;", '"'))
        ranked = [c for c in cards if c.startswith("Which versions moved")]
        self.assertTrue(ranked and "|0%|" in "|" + ranked[0].split("=", 1)[1] + "|", cards)

    def test_the_ranked_box_never_ties_a_leader_to_a_regression(self) -> None:
        # "Artemis can't separate v1 from v2" is only true when the two share a verdict.
        snap = run_snapshot()
        key = next(m["key"] for m in snap["metrics"] if m["kind"] == "target")
        ranks = snap["rankings"][key]
        self.assertGreaterEqual(len(ranks), 2)
        by = {v["label"]: v for v in snap["versions"]}
        for r, verdict in ((ranks[0], "noise"), (ranks[1], "worse")):
            by[r["label"]]["metrics"][key].setdefault("vsBaseline", {})["verdict"] = verdict
        visible = re.sub(r"<script.*?</script>", "", dump(build_studio.build([snap]), "r-" + snap["run"]["id"]), flags=re.S)
        self.assertIn('Top: <span class="num">' + ranks[0]["label"] + ",", visible)
        self.assertNotIn("be told apart from " + ranks[1]["label"], visible)
        by[ranks[1]["label"]]["metrics"][key]["vsBaseline"]["verdict"] = "noise"
        visible = re.sub(r"<script.*?</script>", "", dump(build_studio.build([snap]), "r-" + snap["run"]["id"]), flags=re.S)
        self.assertIn("be told apart from " + ranks[1]["label"], visible)

    def test_without_the_layout_pass_labels_overlap_and_the_checker_says_where(self) -> None:
        html = build_studio.build([run_snapshot(), project_snapshot(3)])
        raw = html.replace("function scheduleDeclutter() { clearTimeout(declutterT); declutterT = setTimeout(declutter, 30); }", "function scheduleDeclutter() {}")
        self.assertNotEqual(raw, html)
        problems = check_report.studio_render_checks(raw, CHROME)
        self.assertTrue(any(p.startswith("LABEL CUT OFF:") and "390px" in p for p in problems), problems)
        self.assertTrue(any(p.startswith("LABELS OVERLAP:") for p in problems), problems)

    def test_an_empty_versions_filter_says_so(self) -> None:
        html = build_studio.build([run_snapshot()])
        probe = """<script>setTimeout(function () {
  var card = document.querySelector('[data-card="ranked"]');
  [].filter.call(card.querySelectorAll("button"), function (b) { return b.textContent === "Versions"; })[0].click();
  setTimeout(function () {
    [].filter.call(card.querySelectorAll("button"), function (b) { return b.textContent === "None"; })[0].click();
    setTimeout(function () { var d = document.createElement("pre"); d.id = "empty"; d.textContent = card.querySelector(".plot").textContent + " | " + card.querySelector(".means").textContent; document.body.appendChild(d); }, 400);
  }, 400);
}, 1500);</script>"""
        found = re.search(r'<pre id="empty">(.*?)</pre>', dump(html, embedded(html)["datasets"][0]["id"], 0, probe))
        self.assertIsNotNone(found)
        self.assertEqual(found.group(1).count("No versions shown. Pick some under Versions."), 2, found.group(1))
        self.assertNotIn("highest", found.group(1))

    def test_a_tick_cut_by_the_chart_edge_is_moved_inside_or_hidden(self) -> None:
        # At 390px the last commit label of a box plot hung past the chart's right edge.
        html = build_studio.build([run_snapshot()])
        probe = """<script>setTimeout(function () {
  var ns = "http://www.w3.org/2000/svg", root = document.getElementById("root"), host = document.createElement("div");
  host.innerHTML = '<svg class="recharts-surface" width="200" height="60"><g class="recharts-cartesian-axis-tick-labels"><g class="recharts-cartesian-axis-tick-label"><text x="20" y="20" text-anchor="middle" font-size="14">5760917</text></g><g class="recharts-cartesian-axis-tick-label"><text x="196" y="20" text-anchor="middle" font-size="14">9595b39</text></g></g></svg>';
  root.appendChild(host);
  setTimeout(function () {
    var svg = host.querySelector("svg").getBoundingClientRect(), t = host.querySelectorAll("text")[1], r = t.getBoundingClientRect();
    var d = document.createElement("pre"); d.id = "edge"; d.textContent = JSON.stringify({ inside: r.right <= svg.right + 0.5 && r.left >= svg.left - 0.5, hidden: getComputedStyle(t).visibility === "hidden" || getComputedStyle(t.parentNode).visibility === "hidden" });
    document.body.appendChild(d);
  }, 600);
}, 1500);</script>"""
        found = re.search(r'<pre id="edge">(.*?)</pre>', dump(html, embedded(html)["datasets"][0]["id"], 0, probe))
        state = json.loads(found.group(1).replace("&quot;", '"'))
        self.assertTrue(state["inside"], state)  # there is room, so it moves rather than hides

    def test_a_request_of_any_kind_fails_at_run_time(self) -> None:
        html = build_studio.build([run_snapshot()])
        calls = {
            "LIVE FETCH: fetch https://example.com/x.json": 'window["fe" + "tch"]("https://example.com/x.json").catch(function () {});',
            "LIVE FETCH: WebSocket wss://example.com": 'try { new WebSocket("wss://example.com"); } catch (e) {}',
            "LIVE FETCH: sendBeacon https://example.com/b": 'navigator.sendBeacon("https://example.com/b", "x");',
            "LIVE FETCH: EventSource https://example.com/e": 'try { new EventSource("https://example.com/e"); } catch (e) {}',
            "LIVE FETCH: loaded https://example.com/pixel.gif": 'new Image().src = "https://example.com/pixel.gif";',
        }
        # One page makes every request; the checker must name each.
        page = html.replace("var fontCss = null;", "var fontCss = null; " + " ".join(calls.values()), 1)
        problems = check_report.render_checks(page, CHROME, "", check_report.studio_probe(), 8000)
        for expected in calls:
            with self.subTest(expected=expected):
                self.assertTrue(any(p.startswith(expected) for p in problems), problems)

    def test_only_the_pinned_libraries_load(self) -> None:
        html = build_studio.build([run_snapshot()])
        for url in check_report.STUDIO_SCRIPTS:
            self.assertIn(f'<script src="{url}"', html)
        other = html.replace("var fontCss = null;", 'var fontCss = null; var s = document.createElement("script"); s.src = "https://unpkg.com/htm@3.1.0/dist/htm.umd.js"; document.head.appendChild(s);', 1)
        problems = check_report.studio_render_checks(other, CHROME)
        self.assertTrue(any(p.startswith("LIVE FETCH: loaded https://unpkg.com/htm@3.1.0") for p in problems), problems)

    def test_a_comment_opener_in_the_data_still_draws(self) -> None:
        snap = run_snapshot()
        snap["run"]["projectName"] = "A <!-- B"
        html = build_studio.build([snap])
        self.assertEqual(check_report.studio_static_checks(html), [])
        self.assertEqual(len(check_report.studio_views(html)), 1)
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
        self.assertIn("A &lt;!-- B", dump(html, embedded(html)["datasets"][0]["id"]))

    def test_a_drawing_error_says_why_instead_of_a_blank_page(self) -> None:
        html = build_studio.build([run_snapshot()]).replace('"perMetricWinners":', '"perMetricWinnersGone":', 1)
        problems = check_report.studio_render_checks(html, CHROME)
        self.assertTrue(any(p.startswith("SCRIPT ERROR") for p in problems), problems)
        self.assertIn('<div class="err">The studio failed to draw this snapshot', dump(html, embedded(html)["datasets"][0]["id"]))

    def test_unreadable_data_shows_the_parse_error(self) -> None:
        html = build_studio.build([run_snapshot()]).replace('id="studio-data">{', 'id="studio-data">{,', 1)
        self.assertRegex(dump(html, "x"), r"This snapshot did not load: [^<.]+")

    def test_a_phone_frame_that_never_reports_is_a_render_line(self) -> None:
        with mock.patch.object(check_report, "studio_probe", return_value=""):
            self.assertEqual(check_report.phone_checks(build_studio.build([run_snapshot()]), CHROME, ""), ["RENDER: the page did not finish rendering at 390px"])

    def test_every_session_is_opened_not_just_the_first(self) -> None:
        html = with_data(build_studio.build([project_snapshot(2)]), lambda d: d["datasets"][0]["sessions"][1].pop("perMetricWinners"))
        problems = check_report.studio_render_checks(html, CHROME)
        self.assertTrue(any("SCRIPT ERROR" in p and "[p-proj-1, session 2]" in p for p in problems), problems)
        self.assertFalse([p for p in problems if "session 1" in p], problems)

    def test_the_probe_catches_a_blank_title_hidden_charts_and_missing_libraries(self) -> None:
        html = build_studio.build([run_snapshot()])
        probe = check_report.studio_probe()
        blank = check_report.render_checks(html + late('document.querySelector("h1").textContent = "";'), CHROME, "", probe, 8000)
        self.assertIn("EMPTY TITLE", blank)
        hidden = check_report.render_checks(html + late('[].forEach.call(document.querySelectorAll(".recharts-surface, table.sum, .plot .sparse, .plot .missing"), function (s) { s.remove(); });'), CHROME, "", probe, 8000)
        self.assertIn("NO CHART RENDERED", hidden)
        no_lib = re.sub(r'<script src="[^"]*Recharts\.min\.js"[^>]*></script>', "", html)
        self.assertNotEqual(no_lib, html)
        self.assertTrue(any(p.startswith("RENDER: the chart libraries did not load") for p in check_report.render_checks(no_lib, CHROME, "", probe, 8000)))

    def test_charts_under_more_are_checked_and_one_broken_chart_keeps_the_rest(self) -> None:
        html = build_studio.build([project_snapshot(2)])
        broken = html.replace("function TimeCard(props) {", 'function TimeCard(props) { throw new Error("time card broke");', 1)
        self.assertNotEqual(broken, html)
        problems = check_report.studio_render_checks(broken, CHROME)
        self.assertIn("SCRIPT ERROR: time card broke [p-proj-1, session 1]", problems)
        self.assertNotIn("NO CHART RENDERED [p-proj-1, session 1]", problems)
        # Opened by a reader, More shows that one chart's message and the rest of the page stays.
        opened = dump(broken.replace("START && START.more ? true :", "true ? true :", 1), "p-proj-1", 0)
        self.assertIn('<div class="err">This chart failed to draw: time card broke</div>', opened)
        self.assertNotIn('<div class="err">The studio failed to draw', opened)
        self.assertIn("<h1", opened)

    def test_a_section_left_closed_fails(self) -> None:
        html = build_studio.build([project_snapshot(2)]).replace("START && START.more ? true :", "false ? true :", 1)
        problems = check_report.studio_render_checks(html, CHROME)
        self.assertTrue(any(p.startswith("CLOSED SECTION, NOT CHECKED: More charts") for p in problems), problems)

    def test_the_checker_keeps_the_page_in_standards_mode(self) -> None:
        mode = "<script>setTimeout(function () { var d = document.createElement('pre'); d.id = '__ar_probe'; d.textContent = document.compatMode; document.body.appendChild(d); }, 300);</script>"
        self.assertEqual(check_report.render_checks(build_studio.build([run_snapshot()]), CHROME, "", mode), ["CSS1Compat"])

    def test_main_runs_the_studio_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "studio.html"
            page.write_text(build_studio.build([copy.deepcopy(run_snapshot())]), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as said:
                self.assertEqual(check_report.main(["--studio", str(page)]), 0)
            self.assertEqual(said.getvalue().strip(), "OK")


class NoChromeTests(unittest.TestCase):
    def test_a_missing_page_is_refused_cleanly(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(check_report.main(["--studio", "/nonexistent/studio.html"]), 2)
        self.assertIn("No such file", err.getvalue())
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "latin1.html"
            page.write_bytes("<title>caf\u00e9</title>".encode("latin-1"))
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(check_report.main(["--studio", str(page)]), 2)
            self.assertIn("codec can't decode", err.getvalue())

    def test_studio_without_chrome_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "studio.html"
            page.write_text(build_studio.build([run_snapshot()]), encoding="utf-8")
            out = io.StringIO()
            with mock.patch.object(check_report, "find_chrome", return_value=None), contextlib.redirect_stdout(out):
                self.assertEqual(check_report.main(["--studio", str(page)]), 1)
            self.assertIn("NOT RENDERED", out.getvalue())
            self.assertNotIn("\nOK", "\n" + out.getvalue())

    def test_chrome_keeps_its_temp_files_in_the_runs_own_folder(self) -> None:
        # Each headless launch copies its built-in extensions into TMPDIR; in /tmp they pile up by the gigabyte.
        seen = {}
        def fake(cmd, **kw):
            seen.update(env=kw.get("env") or {}, profile=next(a for a in cmd if a.startswith("--user-data-dir=")))
            return subprocess.CompletedProcess(cmd, 0, stdout='<pre id="__ar_probe">OK</pre>', stderr="")
        with mock.patch.object(check_report.subprocess, "run", side_effect=fake):
            check_report.render_checks("<title>t</title>", "chrome")
        self.assertTrue(seen["env"].get("TMPDIR"))
        self.assertEqual(str(Path(seen["profile"].split("=", 1)[1]).parent), seen["env"]["TMPDIR"])

    def test_a_chrome_timeout_or_crash_is_a_render_line(self) -> None:
        with mock.patch.object(check_report.subprocess, "run", side_effect=subprocess.TimeoutExpired("chrome", 120)):
            self.assertEqual(check_report.render_checks("<title>t</title>", "chrome"), ["RENDER: the page timed out after 120 s in headless Chrome"])
        crashed = subprocess.CompletedProcess([], 1, stdout="", stderr="boom")
        with mock.patch.object(check_report.subprocess, "run", return_value=crashed):
            self.assertIn("Chrome exit 1: boom", check_report.render_checks("<title>t</title>", "chrome")[0])


NEMO = Path(__file__).resolve().parent / "fixtures" / "bench" / "nemo-speech.json"


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class RealRunTests(unittest.TestCase):
    """A real run, not just the synthetic fixture: tests/fixtures/bench/nemo-speech.json is a NeMo speech run's snapshot cut
    to v1, v4 and v5 (Best, and the best on each metric) with all 11 metrics: two readings a side on each measured metric
    (AI Metrics have one), and the fields today's collector adds (units read from names, bestLines.metric). Every id, link,
    runner and description is scrubbed, experiment titles are filler of the same word lengths, and numbers are rounded to
    four figures. The shape of the data is what shapes the page, so the fixture keeps the shape and nothing else. It has
    the suite's only unitless targets (rtfx, der_long) and AI Metrics from a real judge."""

    @staticmethod
    def snapshot() -> dict:
        return json.loads(NEMO.read_text(encoding="utf-8"))

    def test_the_fixture_carries_nothing_from_the_real_run(self) -> None:
        # The repo is public: commits are fakes (one letter, then zeros) and file paths are neutral.
        raw = NEMO.read_text(encoding="utf-8")
        shas = set(re.findall(r'"([0-9a-f]{40})"', raw))
        self.assertTrue(shas)
        for sha in shas:
            self.assertRegex(sha, r"^([a-f])\1{6}0{32}\d$")
        self.assertEqual(json.loads(raw)["run"]["targetFiles"], ["src/a.cpp", "src/b.cpp", "src/c.cpp"])

    def test_the_fixture_is_what_todays_collector_writes(self) -> None:
        snap = self.snapshot()
        fresh = run_snapshot()  # what build_snapshot writes today, on the synthetic run
        self.assertLessEqual(set(fresh), set(snap))
        self.assertLessEqual(set(fresh["bestLines"]), set(snap["bestLines"]))
        vs = lambda s: next(st["vsBaseline"] for v in s["versions"] for st in v["metrics"].values() if isinstance(st, dict) and st.get("vsBaseline"))
        self.assertLessEqual(set(vs(fresh)), set(vs(snap)))
        self.assertIn("metric", snap["bestLines"])
        for m in snap["metrics"]:
            if not m.get("platformUnit"):
                self.assertEqual(m["unit"], collect_discovery.infer_unit(m["key"]), m["key"])
        for v in snap["versions"]:
            for m in snap["metrics"]:
                if m["kind"] == "quality" and m["key"] in v["metrics"]:
                    self.assertIsNone(v["metrics"][m["key"]]["timesBetter"], (v["label"], m["key"]))

    def test_a_real_run_passes_every_check(self) -> None:
        # Its 13-letter experiment-title words pushed the summary table past a 390px phone.
        self.assertEqual(check_report.studio_render_checks(build_studio.build([self.snapshot()]), CHROME), [])

    def test_ai_metrics_stay_out_of_the_measured_cards(self) -> None:
        snap = self.snapshot()
        html = build_studio.build([snap])
        js = """var out = {}; ["best", "ranked", "forest", "time", "box", "table"].forEach(function (id) {
  var c = document.querySelector('[data-card="' + id + '"]'); if (!c) return;
  out[id] = [].map.call(c.querySelectorAll('select option, .ptitle'), function (o) { return o.textContent.trim(); });
}); return { cards: out, names: window.STUDIO_LABELS };"""
        got = probed(html, embedded(html)["datasets"][0]["id"], js)
        ai = {got["names"][m["key"]] for m in snap["metrics"] if m["kind"] == "quality"}
        self.assertEqual(len(ai), 6)
        self.assertEqual(set(got["cards"]), {"best", "ranked", "forest", "time", "box", "table"})
        for card, shown in got["cards"].items():
            self.assertTrue(shown, card)
            self.assertFalse(ai & set(shown), (card, ai & set(shown)))


if __name__ == "__main__":
    unittest.main()
