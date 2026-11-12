#!/usr/bin/env python3
"""What each studio card draws and says on awkward data: clamped and open values, missing comparisons,
reference metrics, and the Best ring. Each test reads the drawn page in headless Chrome."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
import unittest.mock
import contextlib
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_studio  # noqa: E402
import check_report  # noqa: E402
import collect_discovery  # noqa: E402
from studio_fixtures import CHROME, VISIBLE, embedded, late, low_then_high, probed, project_snapshot, run_snapshot, with_intervals  # noqa: E402

KEY = "latency_ms"


def ds(html: str) -> str:
    return embedded(html)["datasets"][0]["id"]


def by_label(snap: dict) -> dict:
    return {v["label"]: v for v in snap["versions"]}


def click(card: str, text: str) -> str:
    """Press the button with this text inside one card."""
    return ("[].filter.call(document.querySelector('[data-card=\"" + card + "\"]').querySelectorAll('button'), "
            "function (b) { return b.textContent.trim() === " + json.dumps(text) + "; })[0].click();")


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class AIScoreCardTests(unittest.TestCase):
    def test_a_score_past_100_percent_prints_its_value_and_a_clip_arrow(self) -> None:
        snap = run_snapshot()
        by_label(snap)["v4"]["metrics"]["quality_score"]["pctBetter"] = 300.0
        html = build_studio.build([snap])
        js = VISIBLE + "return { values: [].filter.call(card('ai').querySelectorAll('.recharts-label-list text, .recharts-bar text'), vis).map(function (t) { return t.textContent; }), arrows: card('ai').querySelectorAll('.clip-arrow').length };"
        got = probed(html, ds(html), js, more=True)
        self.assertIn("+300%", got["values"])
        self.assertNotIn("+100%", got["values"])
        self.assertEqual(got["arrows"], 1)


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class SessionsCardTests(unittest.TestCase):
    def test_ranked_ticks_follow_the_ranked_bars_not_the_line_chart(self) -> None:
        # One far outlier: the ranked axis is clipped to the rest, so the line chart's ticks (up to 2000%) would leave only 0%.
        project = project_snapshot(2)
        first = project["runs"][0]
        by_label(first)["v2"]["metrics"][KEY]["pctBetter"] = 2000.0
        for row in first["rankings"][KEY]:
            if row["label"] == "v2":
                row["pctBetter"] = 2000.0
        html = build_studio.build([project])
        got = probed(html, ds(html), VISIBLE + "return [].filter.call(card('sessions').querySelectorAll('.recharts-xAxis-tick-labels text'), vis).map(function (t) { return t.textContent; });")
        self.assertIn("0%", got)
        self.assertGreaterEqual(len(got), 3, got)


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class LeadMetricTests(unittest.TestCase):
    H1 = "return document.querySelector('h1').textContent;"

    def test_a_reference_metric_never_leads(self) -> None:
        snap = run_snapshot()
        next(m for m in snap["metrics"] if m["key"] == KEY)["importance"] = "medium"  # so only the role keeps the control from leading
        snap["metrics"].append(dict(next(m for m in snap["metrics"] if m["key"] == KEY), key="cublas_ms", label="cublas_ms", role="reference", importance="high"))
        for v in snap["versions"]:
            if KEY in v["metrics"]:
                v["metrics"]["cublas_ms"] = dict(v["metrics"][KEY])
        snap["baseline"]["metrics"]["cublas_ms"] = dict(snap["baseline"]["metrics"][KEY])
        snap["rankings"]["cublas_ms"] = [dict(r) for r in snap["rankings"][KEY]]
        snap["perMetricWinners"]["cublas_ms"] = dict(snap["perMetricWinners"][KEY])
        snap["bestLines"].pop("metric", None)  # an older snapshot: the page must still skip the control
        html = build_studio.build([snap])
        h1 = probed(html, ds(html), self.H1)
        self.assertIn("Latency (ms)", h1)
        self.assertNotIn("Cublas", h1)

    def test_the_page_leads_with_the_collectors_metric(self) -> None:
        snap = run_snapshot()
        self.assertEqual(snap["bestLines"]["metric"], KEY)
        for m in snap["metrics"]:
            if m["key"] == "compile_runtime":
                m.update(kind="target", importance="high")
            elif m["key"] == KEY:
                m["importance"] = "medium"  # by importance alone, compile_runtime would lead
        html = build_studio.build([snap])
        self.assertIn("Latency (ms)", probed(html, ds(html), self.H1))


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class BestCardTests(unittest.TestCase):
    def test_a_panel_names_the_best_on_its_metric_alone(self) -> None:
        snap = run_snapshot()
        for m in snap["metrics"]:
            if m["key"] == "compile_runtime":
                m["kind"] = "target"
        snap["bestLines"] = collect_discovery.best_lines({m["key"]: m for m in snap["metrics"]}, snap["versions"], snap["perMetricWinners"], snap["webUiBest"])
        self.assertIn("compile_runtime", snap["bestLines"]["notes"])
        html = build_studio.build([snap])
        text = probed(html, ds(html), "return document.querySelector('[data-card=\"best\"]').textContent;")
        self.assertRegex(text, r"Best on this metric alone: v4, [^,]+, (significantly|no significant|needs)")


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class TimeCardTests(unittest.TestCase):
    def test_the_composite_view_rings_the_web_uis_best(self) -> None:
        snap = run_snapshot()
        by = by_label(snap)
        for label, fitness in (("v2", 0.9), ("v4", 0.7)):
            by[label].update(fitness=fitness, displayStatus="scored")
        snap["webUiBest"] = {"version": 2, "label": "v2", "fitness": 0.9}
        snap["bestLines"].update(version=4, label="v4", byComposite=False)
        html = build_studio.build([snap])
        got = probed(html, ds(html), VISIBLE + "return texts('time').filter(function (t) { return /Best /.test(t); });", act=click("time", "Overall score"))
        self.assertEqual(got, ["Web UI Best 0.900"])  # the page's Best is v4 here, so the ring says whose Best it is


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class FooterLinkTests(unittest.TestCase):
    JS = "return [].map.call(document.querySelectorAll('footer a'), function (a) { return a.getAttribute('href'); });"

    def test_only_an_artemis_link_is_a_link(self) -> None:
        for url, links in (("javascript:alert(1)", []), ("https://example.com/projects/p/discover/r", []),
                           ("https://artemis.turintech.ai/projects/p/discover/r", ["https://artemis.turintech.ai/projects/p/discover/r"])):
            with self.subTest(url=url):
                snap = run_snapshot()
                snap["run"]["webUrl"] = url
                html = build_studio.build([snap])
                self.assertEqual(probed(html, ds(html), self.JS), links)


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class ForestCardTests(unittest.TestCase):
    def test_an_open_low_end_draws_its_whisker_to_the_axis_edge(self) -> None:
        snap = with_intervals(run_snapshot())
        next(m for m in snap["metrics"] if m["key"] == KEY)["higherIsBetter"] = True
        by_label(snap)["v1"]["metrics"][KEY]["vsBaseline"].update(ciLowPct=-150.0, ciHighPct=60.0, verdict="noise")
        html = build_studio.build([snap])
        js = ("var c = document.querySelector('[data-card=\"forest\"]'), area = c.querySelector('.recharts-reference-area-rect').getBoundingClientRect();"
              "var xs = [].map.call(c.querySelectorAll('.recharts-errorBar line'), function (l) { return l.getBoundingClientRect().left; });"
              "return { edge: area.left, left: Math.min.apply(null, xs) };")
        got = probed(html, ds(html), js, act=click("forest", "Log (×)"))
        self.assertLess(abs(got["left"] - got["edge"]), 3, got)

    def test_a_version_with_no_comparison_is_listed_and_counted(self) -> None:
        snap = with_intervals(run_snapshot())
        by_label(snap)["v4"]["metrics"][KEY]["vsBaseline"] = None
        html = build_studio.build([snap])
        text = probed(html, ds(html), "return document.querySelector('[data-card=\"forest\"]').textContent;")
        self.assertIn("No Artemis comparison: v4", text)
        self.assertRegex(text, r"\d of 3 ")
        self.assertNotRegex(text, r"\d of 2 ")


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class RankedCardTests(unittest.TestCase):
    def test_no_comparison_is_not_called_needs_more_runs(self) -> None:
        snap = run_snapshot()
        by_label(snap)["v4"]["metrics"][KEY]["vsBaseline"] = None
        html = build_studio.build([snap])
        got = probed(html, ds(html), VISIBLE + "return { text: card('ranked').textContent, bars: texts('ranked') };")
        self.assertIn("2 need more runs", got["text"])
        self.assertNotIn("3 need more runs", got["text"])
        self.assertIn("1 with no Artemis comparison", got["text"])
        self.assertTrue(any("No Artemis comparison" in t for t in got["bars"]), got["bars"])


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class ExportTests(unittest.TestCase):
    CAPTURE = ("URL.createObjectURL = function (b) { b.text().then(function (t) { window.__saved = t; }); return 'about:blank'; };"
               "HTMLAnchorElement.prototype.click = function () {};")

    def test_the_svg_legend_draws_needs_more_runs_as_a_dashed_outline(self) -> None:
        snap = with_intervals(run_snapshot())  # v1 improved, the rest no difference
        by_label(snap)["v4"]["metrics"][KEY]["vsBaseline"]["verdict"] = "pending"  # and one that needs more runs, so the legend shows
        html = build_studio.build([snap])
        act = self.CAPTURE + click("ranked", "Download") + " setTimeout(function () { " + click("ranked", "SVG") + " }, 200);"
        svg = probed(html, ds(html), "return window.__saved || '';", act=act)
        legend = svg[:svg.index("Needs more runs")]
        swatch = legend[legend.rfind("<rect"):]
        self.assertIn('fill="none"', swatch)
        self.assertIn('stroke-dasharray="3 2"', swatch)  # the legend's dash; the bars use 5 3

    def test_a_plain_browser_save_never_claims_it_saved(self) -> None:
        html = build_studio.build([run_snapshot()])
        act = self.CAPTURE + click("ranked", "Download") + " setTimeout(function () { " + click("ranked", "CSV of the plotted data") + " }, 200);"
        toast = probed(html, ds(html), "var t = document.querySelector('.toast'); return t ? t.textContent : null;", act=act)
        self.assertIsNotNone(toast)
        self.assertFalse(toast.startswith("Saved"), toast)
        self.assertIn(".csv", toast)


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class MetricNameTests(unittest.TestCase):
    def test_a_unit_in_the_name_reads_once(self) -> None:
        snap = run_snapshot()
        base = next(m for m in snap["metrics"] if m["key"] == KEY)
        snap["metrics"] += [dict(base, key="ms_per_chunk", label="ms_per_chunk", unit="ms"), dict(base, key="proc_wall_s", label="proc_wall_s", unit="s")]
        html = build_studio.build([snap])
        names = probed(html, ds(html), "return window.STUDIO_LABELS;")
        self.assertEqual((names["ms_per_chunk"], names["proc_wall_s"]), ("Time per chunk (ms)", "Proc wall (s)"))


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class CheckerTests(unittest.TestCase):
    def problems(self, html: str) -> list[str]:
        return check_report.render_checks(html, CHROME, "", check_report.studio_probe(), 8000)

    def test_an_unhandled_promise_rejection_fails(self) -> None:
        html = build_studio.build([run_snapshot()]).replace("var fontCss = null;", 'var fontCss = null; Promise.reject(new Error("lost save"));', 1)
        self.assertIn("UNHANDLED REJECTION: lost save", self.problems(html))

    def test_one_empty_card_fails_while_the_others_draw(self) -> None:
        html = build_studio.build([run_snapshot()])
        empty = html + late('var c = document.querySelector("[data-card=ranked] .plot"); c.innerHTML = "";')
        problems = self.problems(empty)
        self.assertTrue(any(p.startswith("EMPTY CARD: Which versions moved") for p in problems), problems)
        self.assertNotIn("NO CHART RENDERED", problems)

    def test_a_value_label_the_layout_pass_hid_fails(self) -> None:
        html = build_studio.build([run_snapshot()])
        hide = html + late('[].forEach.call(document.querySelectorAll("[data-card=ranked] .recharts-label-list text"), function (t) { t.style.visibility = "hidden"; });')
        problems = self.problems(hide)
        self.assertTrue(any(p.startswith("LABEL HIDDEN: ") and "Which versions moved" in p for p in problems), problems)

    def test_a_hidden_name_on_a_category_axis_fails(self) -> None:
        html = build_studio.build([run_snapshot()])
        hide = html + late('var t = document.querySelector("[data-card=ranked] .recharts-yAxis-tick-labels text"); t.style.visibility = "hidden";')
        problems = self.problems(hide)
        self.assertTrue(any(p.startswith("NAME HIDDEN: ") and "Which versions moved" in p for p in problems), problems)

    def test_a_project_view_without_its_sessions_card_fails(self) -> None:
        html = build_studio.build([project_snapshot(2)])
        gone = html.replace("function SessionsCard(props) {", "function SessionsCard(props) { return null;", 1)
        self.assertNotEqual(gone, html)
        self.assertTrue(any(p.startswith("NO SESSIONS CARD") for p in check_report.studio_render_checks(gone, CHROME)))

    def test_a_best_note_with_the_wrong_version_fails(self) -> None:
        snap = run_snapshot()
        for m in snap["metrics"]:
            if m["key"] == "compile_runtime":
                m["kind"] = "target"
        snap["bestLines"] = collect_discovery.best_lines({m["key"]: m for m in snap["metrics"]}, snap["versions"], snap["perMetricWinners"], snap["webUiBest"])
        html = build_studio.build([snap])
        self.assertFalse([p for p in self.problems(html) if "BEST NOTE" in p])
        # The header's line names v1 where the note says v4; v4 still appears elsewhere in the same bullet.
        swapped = html.replace('return x ? x[1] + " on " + mlabel(D.byKey[k]) : null;', 'return x ? "v1 on " + mlabel(D.byKey[k]) + " (not " + x[1] + ")" : null;', 1)
        self.assertNotEqual(swapped, html)
        self.assertTrue(any(p.startswith("MISSING BEST NOTE") for p in self.problems(swapped)))

    def test_a_shortened_value_label_fails(self) -> None:
        html = build_studio.build([run_snapshot()])
        # The layout pass squeezed into 30px, as a crowded chart would: the value labels are cut to "1,2..." and must fail.
        squeeze = "if (r.width > lim.right - lim.left && leaf(x)) {"
        self.assertEqual(html.count(squeeze), 1)
        cut = html.replace(squeeze, "if (x.closest('.recharts-label-list')) lim = { left: lim.left, top: lim.top, bottom: lim.bottom, right: lim.left + 30 }; " + squeeze, 1)
        self.assertTrue(any(p.startswith("LABEL SHORTENED: ") for p in self.problems(cut)))

    def test_an_empty_note_is_not_a_drawn_card(self) -> None:
        html = build_studio.build([run_snapshot()])
        empty = html + late('document.querySelector("[data-card=ranked] .plot").innerHTML = "<p class=\'missing\'></p>";')
        self.assertTrue(any(p.startswith("EMPTY CARD: Which versions moved") for p in self.problems(empty)))

    def test_a_control_that_vanishes_mid_walk_is_said(self) -> None:
        html = build_studio.build([run_snapshot()])
        # Once the walk starts clicking, the forest's buttons stop being found where the walk listed them.
        gone = html + late('document.addEventListener("click", function () { [].forEach.call(document.querySelectorAll("[data-card=forest] .seg"), function (s) { s.className = "gone"; }); }, true);')
        problems = check_report.studio_render_checks(gone, CHROME)
        self.assertTrue(any(p.startswith("WALK: the control for ") for p in problems), problems)

    def test_a_snapshot_without_best_lines_says_the_best_checks_did_not_run(self) -> None:
        html = build_studio.build([run_snapshot()]).replace('"bestLines":', '"bestLinesGone":', 1)
        self.assertIn("NO BEST LINES: the snapshot has no bestLines key, so the Best checks did not run", " ".join(self.problems(html)))


def no_pct(snap: dict, label: str) -> None:
    """Falcon kept its verdict but gave no % for this version on the lead metric (an original of 0, say)."""
    st = by_label(snap)[label]["metrics"][KEY]
    st["pctBetter"] = None
    st["vsBaseline"]["improvementPct"] = None


def renamed_targets(project: dict) -> dict:
    """The second session measures under other keys, so no target metric is shared."""
    run = project["runs"][1]
    rename = lambda k: "renamed_" + k if k == KEY else k
    for m in run["metrics"]:
        m["key"] = rename(m["key"])
    for v in run["versions"]:
        v["metrics"] = {rename(k): x for k, x in v["metrics"].items()}
    run["baseline"]["metrics"] = {rename(k): x for k, x in run["baseline"]["metrics"].items()}
    run["rankings"] = {rename(k): x for k, x in run["rankings"].items()}
    run["perMetricWinners"] = {rename(k): x for k, x in run["perMetricWinners"].items()}
    return project


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class MissingValueTests(unittest.TestCase):
    def test_no_percent_is_said_never_printed_as_zero(self) -> None:
        snap = run_snapshot()
        no_pct(snap, "v2")
        html = build_studio.build([snap])
        got = probed(html, ds(html), "return { h1: document.querySelector('h1').textContent, best: document.querySelector('[data-card=\"best\"] .psub').textContent };")
        self.assertIn("v2 has no % change from Artemis on Latency (ms)", got["h1"])
        self.assertNotIn("0.0%", got["h1"] + got["best"])
        self.assertIn("no % change from Artemis", got["best"])

    def test_a_version_measured_but_not_compared_is_named(self) -> None:
        snap = run_snapshot()
        st = by_label(snap)["v1"]["metrics"][KEY]
        st.update(pctBetter=None, vsBaseline=None)
        snap["rankings"][KEY] = [r for r in snap["rankings"][KEY] if r["label"] != "v1"]
        html = build_studio.build([with_intervals(snap)])
        got = probed(html, ds(html), "var t = function (id) { return document.querySelector('[data-card=\"' + id + '\"]').textContent; }; return { ranked: t('ranked'), forest: t('forest'), table: t('table') };")
        for card in ("ranked", "forest"):
            self.assertIn("No Artemis comparison: v1", got[card], card)
        self.assertNotIn("Not measured: v1", got["ranked"])
        self.assertIn("v1 no Artemis comparison", got["table"])

    def test_the_ai_count_ignores_the_legend_and_a_score_with_no_percent_is_named(self) -> None:
        snap = run_snapshot()
        by_label(snap)["v1"]["metrics"]["quality_score"]["pctBetter"] = None
        html = build_studio.build([snap])
        js = "var c = document.querySelector('[data-card=\"ai\"]'); return { means: c.querySelector('.means').textContent, text: c.textContent };"
        shown = probed(html, ds(html), js, more=True)
        hidden = probed(html, ds(html), js, act=click("ai", "Worse than the original's score"), more=True)
        self.assertEqual(shown["means"], hidden["means"])
        self.assertIn("1 of 2", shown["means"])  # v2 down, v4 up; v1 and v5 have a score but no %
        self.assertIn("No % from Artemis: v1", shown["text"])

    def test_the_trade_off_names_versions_it_cannot_place(self) -> None:
        snap = run_snapshot()
        by_label(snap)["v4"]["metrics"]["quality_score"]["mean"] = None
        html = build_studio.build([snap])
        text = probed(html, ds(html), "return document.querySelector('[data-card=\"pareto\"]').textContent;", more=True)
        self.assertRegex(text, r"Not on this chart \(no .+?\): [^.]*v4")

    def test_a_machine_group_skips_a_missing_reading(self) -> None:
        snap = run_snapshot()
        snap["baseline"]["metrics"][KEY]["runs"] = [{"value": 10.0, "runner": "a"}, {"value": None, "runner": "b"}]
        for label, value, runner in (("v1", 8.0, "a"), ("v2", 6.0, "b"), ("v4", 7.0, "a")):
            by_label(snap)[label]["metrics"][KEY]["runs"] = [{"value": value, "runner": runner}]
        html = build_studio.build([snap])
        dots = probed(html, ds(html), "return document.querySelectorAll('[data-card=\"box\"] .recharts-bar circle').length;", act=click("box", "Machine"), more=True)
        self.assertEqual(dots, 4)


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class ClippedIntervalTests(unittest.TestCase):
    def test_an_interval_past_the_axis_ends_in_an_arrow(self) -> None:
        snap = with_intervals(run_snapshot())
        by_label(snap)["v1"]["metrics"][KEY]["vsBaseline"].update(ciLowPct=-10.0, ciHighPct=130.0)  # past the +100% cap of a time
        html = build_studio.build([snap])
        got = probed(html, ds(html), "var c = document.querySelector('[data-card=\"forest\"]'); return c.querySelectorAll('.ci-open').length;")
        self.assertEqual(got, 1)


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class ProjectTests(unittest.TestCase):
    def test_sessions_with_no_shared_metric_say_so(self) -> None:
        project = renamed_targets(project_snapshot(2))
        html = build_studio.build([project])
        text = probed(html, ds(html), "var c = document.querySelector('[data-card=\"sessions\"]'); return c ? c.textContent : null;")
        self.assertIsNotNone(text)
        self.assertIn("No target metric with a direction is shared by every session", text)
        with self.assertRaisesRegex(ValueError, "share no target metric"):
            build_studio.build([renamed_targets(project_snapshot(2))], only="sessions")

    def test_a_run_left_out_is_named_on_the_page(self) -> None:
        project = project_snapshot(2)
        failed = run_snapshot()
        failed["run"].update(id="dead-run-9", status="failed")
        failed.update(versions=[], bestLines=None)
        project["runs"].insert(0, failed)
        project["skipped"] = [{"id": "gone-run-1", "status": "cancelled", "reason": "no comparison"}]
        html = build_studio.build([project])
        text = probed(html, ds(html), "return document.querySelector('header').textContent;")
        self.assertIn("Not shown: run gone-run (cancelled, no comparison); run dead-run (failed, no measured version).", text)

    def test_the_sessions_card_leads_with_the_lead_metric_not_a_control(self) -> None:
        project = project_snapshot(2)
        for run in project["runs"]:
            base = next(m for m in run["metrics"] if m["key"] == KEY)
            base["importance"] = "medium"  # with no bestLines.metric, only the role keeps the high-importance control from leading
            run["bestLines"].pop("metric")
            run["metrics"].insert(0, dict(base, key="cublas_ms", label="cublas_ms", role="reference", importance="high"))
            for v in run["versions"]:
                if KEY in v["metrics"]:
                    v["metrics"]["cublas_ms"] = dict(v["metrics"][KEY])
            run["baseline"]["metrics"]["cublas_ms"] = dict(run["baseline"]["metrics"][KEY])
            run["rankings"]["cublas_ms"] = [dict(r) for r in run["rankings"][KEY]]
            run["perMetricWinners"]["cublas_ms"] = dict(run["perMetricWinners"][KEY])
        html = build_studio.build([project])
        self.assertIn("Latency (ms)", probed(html, ds(html), "return document.querySelector('[data-card=\"sessions\"] h2').textContent;"))

    def test_a_one_run_project_still_names_the_runs_left_out(self) -> None:
        project = project_snapshot(1)
        failed = run_snapshot()
        failed["run"].update(id="dead-run-9", status="failed")
        failed.update(versions=[], bestLines=None)
        project["runs"].insert(0, failed)
        project["skipped"] = [{"id": "gone-run-1", "status": "cancelled", "reason": "no comparison"}]
        html = build_studio.build([project])
        self.assertEqual([r["id"] for r in embedded(html)["datasets"][0]["leftOut"]], ["gone-run-1", "dead-run-9"])
        self.assertIn("Not shown: run gone-run (", probed(html, ds(html), "return document.querySelector('header').textContent;"))

    def test_a_downloaded_file_is_named_by_its_session(self) -> None:
        html = build_studio.build([project_snapshot(2)])
        act = ("HTMLAnchorElement.prototype.click = function () { window.__name = this.download; };" + click("ranked", "Download")
               + " setTimeout(function () { " + click("ranked", "CSV of the plotted data") + " }, 200);")
        name = probed(html, ds(html), "return window.__name || null;", act=act, session=1)
        self.assertRegex(name or "", r"-s2-ranked\.csv$")

    def test_reset_clears_a_pick_and_a_pick_after_it_is_saved_again(self) -> None:
        html = build_studio.build([run_snapshot()])
        legend = "document.querySelector('[data-card=best] .legend button')"
        keys = "(function () { var k = []; for (var i = 0; i < localStorage.length; i++) k.push(localStorage.key(i)); return k.filter(function (x) { return /:best$/.test(x); }); })()"
        act = (legend + ".click(); setTimeout(function () { window.__hidden = " + legend + ".getAttribute('aria-pressed'); window.__saved = " + keys + ".length;"
               " [].filter.call(document.querySelectorAll('.bar button'), function (b) { return b.textContent === 'Reset'; })[0].click();"
               " setTimeout(function () { window.__reset = [" + legend + ".getAttribute('aria-pressed'), " + keys + ".length]; " + legend + ".click(); }, 300); }, 300);")
        got = probed(html, ds(html), "return { hidden: window.__hidden, saved: window.__saved, reset: window.__reset, again: " + keys + ".length };", act=act)
        self.assertEqual(got, {"hidden": "false", "saved": 1, "reset": ["true", 0], "again": 1})

    def test_a_one_card_page_checks_and_draws_only_its_first_view(self) -> None:
        project = project_snapshot(2)
        for v in project["runs"][1]["versions"]:
            v["metrics"].pop("quality_score", None)
        html = build_studio.build([project], only="ai")
        self.assertEqual(len(check_report.studio_views(html)), 1)
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
        # A remembered session from the full studio never changes what a one-card page draws.
        remembered = html.replace('var DATA = readSnap("studio-data")', 'try { localStorage.setItem("dv-studio:v1:session", "1"); } catch (e) {} var DATA = readSnap("studio-data")', 1)
        self.assertNotEqual(remembered, html)
        # Opened as a reader opens it: no start view from the checker, so only the page decides what it draws.
        probe = "<script>setTimeout(function () { var d = document.createElement('pre'); d.id = '__ar_probe'; d.textContent = document.querySelector('[data-card=ai]') ? 'AI CARD' : 'NO AI CARD'; document.body.appendChild(d); }, 3000);</script>"
        self.assertEqual(check_report.render_checks(remembered, CHROME, "", probe, 8000), ["AI CARD"])


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class MoreWordingTests(unittest.TestCase):
    def test_the_mean_view_legend_says_mean(self) -> None:
        snap = run_snapshot()
        snap["steering"] = {"points": [{"firstVersion": 2, "firstLabel": "v2", "guidance": "Try a cache."}]}  # a steer, so the legend shows
        html = build_studio.build([snap])
        legend = probed(html, ds(html), "return document.querySelector('[data-card=time] .legend').textContent;", act=click("time", "Mean"))
        self.assertIn("Latency (ms), mean", legend)
        self.assertNotIn("% better", legend)

    def test_the_trade_off_leads_with_the_most_important_target(self) -> None:
        # No bestLines.metric (an older snapshot) and a low-importance target listed first: the trade-off's x axis is still the lead.
        snap = run_snapshot()
        snap["bestLines"].pop("metric")
        base = next(m for m in snap["metrics"] if m["key"] == KEY)
        snap["metrics"].insert(0, dict(base, key="size_kb", label="size_kb", unit="kB", importance="low"))
        for v in snap["versions"]:
            if KEY in v["metrics"]:
                v["metrics"]["size_kb"] = dict(v["metrics"][KEY], mean=v["metrics"][KEY]["mean"] * 3 + v["version"])
        snap["baseline"]["metrics"]["size_kb"] = dict(snap["baseline"]["metrics"][KEY])
        html = build_studio.build([snap])
        self.assertIn("Which versions trade Latency (ms) against", probed(html, ds(html), "return document.querySelector('[data-card=pareto] h2').textContent;", more=True))

    def test_a_rate_reads_its_unit_once(self) -> None:
        snap = run_snapshot()
        base = next(m for m in snap["metrics"] if m["key"] == KEY)
        snap["metrics"].append(dict(base, key="decode_tokens_per_s", label="decode_tokens_per_s", unit="tokens/s"))
        html = build_studio.build([snap])
        self.assertEqual(probed(html, ds(html), "return window.STUDIO_LABELS.decode_tokens_per_s;"), "Decode tokens (tokens/s)")

    def test_a_project_link_is_the_footers_fallback(self) -> None:
        snap = run_snapshot()
        snap["run"].update(webUrl="https://example.com/x", projectUrl="https://artemis.turintech.ai/projects/p-1/")
        html = build_studio.build([snap])
        self.assertEqual(probed(html, ds(html), FooterLinkTests.JS), ["https://artemis.turintech.ai/projects/p-1"])

    def test_a_one_series_export_has_no_legend(self) -> None:
        html = build_studio.build([run_snapshot()])
        act = ExportTests.CAPTURE + click("time", "Download") + " setTimeout(function () { " + click("time", "SVG") + " }, 200);"
        svg = probed(html, ds(html), "return window.__saved || '';", act=act)
        self.assertTrue(svg.startswith("<svg"), svg[:80])
        self.assertNotIn('y="-9" width="10"', svg)


NEMO = Path(__file__).resolve().parent / "fixtures" / "bench" / "nemo-speech.json"


def nemo() -> dict:
    return json.loads(NEMO.read_text(encoding="utf-8"))


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class GappedVersionTests(unittest.TestCase):
    """A snapshot cut to v1, v4 and v5 keeps those numbers: nothing is drawn as v2 or v3, and nothing is dropped."""

    def test_the_sessions_line_uses_the_real_version_numbers(self) -> None:
        a, b = nemo(), nemo()
        b["run"]["id"] = "22222222-2222-4222-8222-222222222222"
        html = build_studio.build([{"schemaVersion": 2, "kind": "project", "projectId": "p-nemo", "runs": [a, b], "skipped": []}])
        js = VISIBLE + "return { ticks: [].map.call(card('sessions').querySelectorAll('.recharts-xAxis-tick-labels text'), function (t) { return t.textContent; }), dots: card('sessions').querySelectorAll('.recharts-line-dots circle, .recharts-line circle').length };"
        got = probed(html, ds(html), js, act=click("sessions", "Over time"))
        self.assertEqual(got["ticks"], ["v1", "v4", "v5"])
        self.assertEqual(got["dots"], 6)

    def test_the_over_time_count_names_the_version_made_not_its_place_in_the_cut(self) -> None:
        html = build_studio.build([nemo()])
        text = probed(html, ds(html), "return document.querySelector('[data-card=time] .means').textContent;")
        self.assertIn("It was the 5th version made; this snapshot holds 3 versions", text)


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class CheckerProbeTests(unittest.TestCase):
    def test_a_page_that_draws_another_view_than_asked_fails(self) -> None:
        html = build_studio.build([run_snapshot(), project_snapshot(2)])
        wrong = html.replace("var d = START ? START.dataset :", "var d = START ? FIRST :", 1)
        self.assertNotEqual(wrong, html)
        problems = check_report.studio_render_checks(wrong, CHROME)
        self.assertTrue(any(p.startswith("WRONG VIEW: asked p-proj-1 s2") for p in problems), problems)

    def test_a_probe_that_throws_says_why(self) -> None:
        html = build_studio.build([run_snapshot()]) + late("window.STUDIO_LABELS = { compile_runtime: 1, latency_ms: 1 };")
        problems = check_report.render_checks(html, CHROME, "", check_report.studio_probe(), 8000)
        self.assertTrue(any(p.startswith("PROBE ERROR: ") for p in problems), problems)


class DashTests(unittest.TestCase):
    def test_dashes_in_the_data_are_swapped_and_the_page_passes(self) -> None:
        snap = run_snapshot()
        snap["versions"][0]["experimentTitle"] = "Cache keys \u2014 skip rehash for 3\u20135 joins"
        html = build_studio.build([snap])
        self.assertEqual(check_report.studio_static_checks(html), [])
        self.assertIn("Cache keys, skip rehash for 3 to 5 joins", html)
        self.assertEqual(snap["versions"][0]["experimentTitle"], "Cache keys \u2014 skip rehash for 3\u20135 joins")  # the caller's snapshot is untouched
        raw = html.replace("Cache keys, skip", "Cache keys \u2014 skip", 1)
        self.assertIn("DASH IN DATA", " ".join(check_report.studio_static_checks(raw)))

    def test_only_sessions_refuses_sessions_that_share_only_controls(self) -> None:
        project = project_snapshot(2)
        for run in project["runs"]:
            for m in run["metrics"]:
                if m["kind"] == "target":
                    m["role"] = "reference"
        with self.assertRaisesRegex(ValueError, "share no target metric"):
            build_studio.build([project], only="sessions")


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class OneCardPageAndHeadlineTests(unittest.TestCase):
    def test_a_one_card_table_page_passes(self) -> None:
        self.assertEqual(check_report.studio_render_checks(build_studio.build([run_snapshot()], only="table"), CHROME), [])

    def test_a_one_card_page_carries_a_no_reading_note(self) -> None:
        snap = run_snapshot()
        snap["bestLines"]["notes"]["compile_runtime"] = "v2 has no reading on compile_runtime; v4 is best on it"
        self.assertEqual(check_report.studio_render_checks(build_studio.build([snap], only="ranked"), CHROME), [])

    def test_no_best_version_says_why_never_that_none_beat_the_original(self) -> None:
        snap = run_snapshot()
        for v in snap["versions"]:
            st = v["metrics"].get(KEY)
            if st:
                st.update(pctBetter=None, vsBaseline=None)
        snap["rankings"][KEY] = []
        snap["perMetricWinners"][KEY] = {"raw": None, "eligible": None, "reason": "no change from Artemis yet", "unranked": []}
        snap["bestLines"] = None
        html = build_studio.build([snap])
        h1 = probed(html, ds(html), "return document.querySelector('h1').textContent;")
        self.assertEqual(h1, "No Best version on Latency (ms) yet: no change from Artemis yet")

    def test_a_target_with_no_direction_never_leads(self) -> None:
        snap = low_then_high()
        next(m for m in snap["metrics"] if m["key"] == "latency_ms")["higherIsBetter"] = None
        next(m for m in snap["metrics"] if m["key"] == "db_size_mb")["importance"] = "low"
        snap["bestLines"]["metric"] = "latency_ms"  # an older collector's pick
        html = build_studio.build([snap])
        got = probed(html, ds(html), "return { h1: document.querySelector('h1').textContent, ranked: document.querySelector('[data-card=ranked] h2').textContent };")
        self.assertNotIn("Latency", got["h1"] + got["ranked"])

    def test_long_group_names_are_cut_to_fit_never_hidden(self) -> None:
        snap = run_snapshot()
        names = ["gpu-runner-a100-eu-west-0%d" % i for i in range(1, 9)]
        snap["baseline"]["metrics"][KEY]["runs"] = [{"value": 10.0 + i / 10, "runner": n} for i, n in enumerate(names)]
        html = build_studio.build([snap], only="box")
        problems = check_report.studio_render_checks(html, CHROME)
        self.assertEqual(problems, [])
        hidden = html.replace("function fitName(s, slot) {", "function fitName(s, slot) { return s;", 1)
        self.assertNotEqual(hidden, html)
        self.assertTrue(any(p.startswith("NAME HIDDEN: ") for p in check_report.studio_render_checks(hidden, CHROME)))


class BuilderRuleTests(unittest.TestCase):
    def test_a_run_with_only_ai_scores_is_left_out(self) -> None:
        project = project_snapshot(3)
        dead = project["runs"][1]
        dead["run"]["status"] = "failed"
        for v in dead["versions"]:
            v["executionStatus"] = "failed"
            v["metrics"] = {k: x for k, x in v["metrics"].items() if k == "quality_score"}
        data = embedded(build_studio.build([project]))["datasets"][0]
        self.assertEqual(len(data["sessions"]), 2)
        self.assertEqual([r["id"] for r in data["leftOut"]], ["run-1"])

    def test_a_one_card_page_embeds_only_the_snapshot_it_draws(self) -> None:
        second = run_snapshot()
        second["run"]["id"] = "second-run"
        html = build_studio.build([run_snapshot(), second], only="ranked")
        self.assertEqual(len(embedded(html)["datasets"]), 1)


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class RealRunAndEdgeCaseTests(unittest.TestCase):
    def test_every_one_card_page_of_a_real_run_passes(self) -> None:
        for card in ("best", "ranked", "forest", "time", "box", "table", "pareto", "ai"):
            with self.subTest(card=card):
                self.assertEqual(check_report.studio_render_checks(build_studio.build([nemo()], only=card), CHROME), [])

    def test_a_session_hidden_over_time_stays_in_ranked(self) -> None:
        html = build_studio.build([project_snapshot(2)])
        bars = "document.querySelectorAll('[data-card=sessions] .recharts-bar-rectangle').length"
        act = (click("sessions", "Over time") + " setTimeout(function () { " + click("sessions", "Discovery session 2 (dashed)")
               + " setTimeout(function () { " + click("sessions", "Ranked") + " }, 300); }, 300);")
        self.assertEqual(probed(html, ds(html), "return " + bars + ";", act=act), 6)

    def test_rate_names_read_as_throughput(self) -> None:
        snap = run_snapshot()
        base = next(m for m in snap["metrics"] if m["key"] == KEY)
        for key, unit in (("mb_per_s", "MB/s"), ("throughput_mb_per_s", "MB/s"), ("tok_s", "tokens/s")):
            snap["metrics"].append(dict(base, key=key, label=key, unit=unit))
        html = build_studio.build([snap])
        names = probed(html, ds(html), "return window.STUDIO_LABELS;")
        self.assertEqual([names[k] for k in ("mb_per_s", "throughput_mb_per_s", "tok_s")], ["Throughput (MB/s)", "Throughput (MB/s)", "Throughput (tokens/s)"])

    def test_the_ai_card_says_when_no_metric_is_selected(self) -> None:
        html = build_studio.build([run_snapshot()])
        act = click("ai", "Metrics") + " setTimeout(function () { document.querySelector('[data-card=ai] .pop input[type=checkbox]').click(); }, 200);"
        text = probed(html, ds(html), "return document.querySelector('[data-card=ai]').textContent;", act=act, more=True)
        self.assertIn("No AI Metric is selected.", text)
        self.assertNotIn("0 of 0", text)

    def test_a_csv_cell_never_runs_as_a_formula(self) -> None:
        snap = run_snapshot()
        by_label(snap)["v1"]["experimentTitle"] = "=HYPERLINK(\"x\")"
        html = build_studio.build([snap])
        act = ExportTests.CAPTURE + click("table", "Download") + " setTimeout(function () { " + click("table", "CSV of the data") + " }, 200);"
        csv = probed(html, ds(html), "return window.__saved || '';", act=act)
        self.assertIn("'=HYPERLINK", csv)

    def test_a_metric_with_no_original_reading_is_named(self) -> None:
        snap = run_snapshot()
        for m in snap["metrics"]:
            if m["key"] == "compile_runtime":
                m["kind"] = "target"
        del snap["baseline"]["metrics"]["compile_runtime"]
        html = build_studio.build([snap])
        self.assertIn("No reading on the original: Compile runtime (s)", probed(html, ds(html), "return document.querySelector('[data-card=best]').textContent;"))

    def test_a_missing_version_count_falls_back_to_the_versions_drawn(self) -> None:
        snap = run_snapshot()
        snap["run"]["versionCount"] = None
        html = build_studio.build([snap])
        header = probed(html, ds(html), "return document.querySelector('header').textContent;")
        self.assertIn("completed, 5 versions", header)
        self.assertNotIn("null", header)


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class CheckerViewTests(unittest.TestCase):
    def test_a_page_that_never_says_which_view_it_drew_fails(self) -> None:
        html = build_studio.build([run_snapshot(), project_snapshot(2)])
        silent = html.replace("window.STUDIO_VIEW_DRAWN = { dataset: dataset, session: si };", "", 1)
        self.assertNotEqual(silent, html)
        self.assertTrue(any(p.startswith("WRONG VIEW: the page did not report") for p in check_report.studio_render_checks(silent, CHROME)))

    def test_a_card_that_goes_blank_behind_a_control_fails(self) -> None:
        html = build_studio.build([run_snapshot()])
        blank = html + late('document.addEventListener("click", function (e) { if (e.target.textContent === "Mean") setTimeout(function () { document.querySelector("[data-card=time] .plot").innerHTML = ""; }, 50); }, true);')
        problems = check_report.studio_render_checks(blank, CHROME)
        self.assertTrue(any(p.startswith("EMPTY CARD: How did the search go") and "(after " in p for p in problems), problems)


class StaticAndBuilderTests(unittest.TestCase):
    def test_text_about_fetch_in_the_data_is_not_a_fetch(self) -> None:
        snap = run_snapshot()
        snap["versions"][0]["experimentTitle"] = "Batch the fetch() calls in the loader"
        snap["versions"][1]["experimentConclusion"] = "Replaced XMLHttpRequest polling with a cache"
        self.assertEqual(check_report.studio_static_checks(build_studio.build([snap])), [])

    def test_a_run_with_only_build_timings_is_left_out(self) -> None:
        project = project_snapshot(3)
        dead = project["runs"][1]
        for v in dead["versions"]:
            v["metrics"] = {k: x for k, x in v["metrics"].items() if k == "compile_runtime"}
        data = embedded(build_studio.build([project]))["datasets"][0]
        self.assertEqual([r["id"] for r in data["leftOut"]], ["run-1"])

    def test_dashes_keep_identifiers_and_split_ranges_cleanly(self) -> None:
        got = build_studio.no_dashes({"title": "1\u20132\u20133 joins \u2014 fast", "key": "a\u2013b", "metrics": {"x\u2013y": {"label": "p\u2013q"}}})
        self.assertEqual(got, {"title": "1 to 2 to 3 joins, fast", "key": "a\u2013b", "metrics": {"x\u2013y": {"label": "p, q"}}})

    def test_a_bad_run_inside_a_project_is_named_by_position_and_id(self) -> None:
        project = project_snapshot(3)
        project["runs"][2]["schemaVersion"] = 1
        with self.assertRaisesRegex(ValueError, r"snapshot 1, run 3 \(run-2\): schemaVersion is 1"):
            build_studio.build([project])


class BrokenDataTests(unittest.TestCase):
    def test_a_nan_in_the_data_is_refused_and_named(self) -> None:
        snap = run_snapshot()
        by_label(snap)["v1"]["metrics"][KEY]["std"] = float("nan")
        with self.assertRaisesRegex(ValueError, "NaN or Infinity"):
            build_studio.build([snap])
        html = build_studio.build([run_snapshot()]).replace('"mean":', '"nan":NaN,"mean":', 1)
        self.assertTrue(any(p.startswith("NO DATA: studio-data does not parse: NaN is not JSON") for p in check_report.studio_static_checks(html)))

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_the_pages_own_failure_message_reaches_the_report(self) -> None:
        html = build_studio.build([run_snapshot()]).replace("function App() {", 'function App() { throw new Error("start broke");', 1)
        problems = check_report.render_checks(html, CHROME, "", check_report.studio_probe(), 8000)
        self.assertTrue(any(p.startswith("RENDER: The studio failed to draw this snapshot: start broke") for p in problems), problems)

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_card_names_what_its_saved_picks_hide(self) -> None:
        snap = run_snapshot()
        snap["metrics"].append(dict(next(m for m in snap["metrics"] if m["key"] == KEY), key="speedup_x", label="speedup_x", unit=None, higherIsBetter=True))
        html = build_studio.build([snap])
        act = click("ranked", "Versions") + " setTimeout(function () { document.querySelector('[data-card=ranked] .pop input[type=checkbox]').click(); }, 200);"
        got = probed(html, ds(html), "var t = function (id) { return document.querySelector('[data-card=' + id + ']').textContent; }; return { ranked: t('ranked'), best: t('best') };", act=act)
        self.assertRegex(got["ranked"], r"Hidden here: v\d \(Versions\)")
        self.assertIn("Hidden here: Speedup x (Metrics)", got["best"])  # the default: a ratio of the same timing says it twice


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class CsvTests(unittest.TestCase):
    def csv(self, html: str, card: str, act: str = "") -> str:
        act = ExportTests.CAPTURE + act + " setTimeout(function () { " + click(card, "Download") + " setTimeout(function () { " + click(card, "CSV of the plotted data") + " }, 200); }, 300);"
        return probed(html, ds(html), "return window.__saved || '';", act=act)

    def test_the_forest_csv_leaves_out_a_series_hidden_in_the_legend(self) -> None:
        html = build_studio.build([with_intervals(run_snapshot())])
        shown = self.csv(html, "forest")
        hidden = self.csv(html, "forest", act=click("forest", "\u2248 No significant difference"))
        self.assertIn("No significant difference", shown)
        self.assertNotIn("No significant difference", hidden)
        self.assertIn("Significantly improved", hidden)

    def test_the_over_time_csv_is_empty_when_its_dots_are_hidden(self) -> None:
        snap = run_snapshot()
        snap["steering"] = {"points": [{"firstVersion": 2, "firstLabel": "v2", "guidance": "Try a cache."}]}  # two series, so a legend
        html = build_studio.build([snap])
        act = (click("time", "Latency (ms), % better") + " setTimeout(function () { " + click("time", "Download")
               + " setTimeout(function () { " + click("time", "CSV of the plotted data") + " }, 200); }, 300);")
        toast = probed(html, ds(html), "var t = document.querySelector('.toast'); return t ? t.textContent : null;", act=act)
        self.assertEqual(toast, "Nothing plotted to export")

    def test_a_tab_or_carriage_return_cell_is_kept_as_text(self) -> None:
        snap = run_snapshot()
        by_label(snap)["v1"]["experimentTitle"] = "\tcmd"
        by_label(snap)["v2"]["experimentTitle"] = "line\rbreak"
        html = build_studio.build([snap])
        act = ExportTests.CAPTURE + click("table", "Download") + " setTimeout(function () { " + click("table", "CSV of the data") + " }, 200);"
        csv = probed(html, ds(html), "return window.__saved || '';", act=act)
        self.assertIn("'\tcmd", csv)
        self.assertIn('"line\rbreak"', csv)


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class HiddenPickTests(unittest.TestCase):
    def test_the_best_conclusion_leaves_out_a_hidden_lead_metric(self) -> None:
        html = build_studio.build([run_snapshot()])
        act = click("best", "Metrics") + " setTimeout(function () { document.querySelector('[data-card=best] .pop input[type=checkbox]').click(); }, 200);"
        means = probed(html, ds(html), "var m = document.querySelector('[data-card=best] .means'); return m ? m.textContent : '';", act=act)
        self.assertNotIn("Latency", means)

    def test_a_tie_never_names_a_hidden_version(self) -> None:
        html = build_studio.build([run_snapshot()])
        act = click("ranked", "Versions") + " setTimeout(function () { [].filter.call(document.querySelectorAll('[data-card=ranked] .pop label'), function (l) { return l.textContent === 'v4'; })[0].querySelector('input').click(); }, 200);"
        means = probed(html, ds(html), "return document.querySelector('[data-card=ranked] .means').textContent;", act=act)
        self.assertIn("Can't be told apart from v1", means)
        self.assertNotIn("from v4", means)

    def test_a_failed_session_row_breaks_over_lines_on_a_phone(self) -> None:
        html = build_studio.build([project_snapshot(2)], failed=["1:1:2"])
        lines = probed(html, "p-proj-1", "var t = [].filter.call(document.querySelectorAll('[data-card=sessions] .recharts-yAxis-tick-labels text'), function (x) { return /^\u2715/.test(x.textContent); })[0]; return t ? t.querySelectorAll('tspan').length : 0;", phone=True)
        self.assertEqual(lines, 3)


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class DirectionWarningAndVerdictTests(unittest.TestCase):
    CHECK = "latency_ms is set as higher-is-better on this project; check Settings > Metrics."

    def test_a_direction_warning_reaches_every_page_and_the_checker_requires_it(self) -> None:
        snap = run_snapshot()
        snap["bestLines"]["checks"] = [self.CHECK]
        snap["directionChecks"] = [self.CHECK]
        for only in (None, "ranked"):
            with self.subTest(only=only):
                html = build_studio.build([snap], only=only)
                self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
        dropped = build_studio.build([snap]).replace("noReading(D.best), checks) };", "noReading(D.best)) };", 1)
        self.assertTrue(any(p.startswith("MISSING DIRECTION CHECK") for p in check_report.studio_render_checks(dropped, CHROME)))

    def test_a_comparison_with_no_verdict_never_prints_undefined(self) -> None:
        snap = run_snapshot()
        by_label(snap)["v2"]["metrics"][KEY]["vsBaseline"].update(verdict=None, readings=5)
        html = build_studio.build([snap])
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
        self.assertIn("no Artemis comparison", probed(html, ds(html), "return document.querySelector('h1').textContent;"))

    def test_the_checker_fails_a_visible_undefined(self) -> None:
        html = build_studio.build([run_snapshot()]) + late('document.querySelector("h1").textContent += ", undefined";')
        self.assertTrue(any(p.startswith("BROKEN VALUE: ") for p in check_report.render_checks(html, CHROME, "", check_report.studio_probe(), 8000)))

    def test_a_version_with_no_commit_keeps_its_label(self) -> None:
        snap = run_snapshot()
        by_label(snap)["v1"]["versionSha"] = None
        html = build_studio.build([snap])
        ticks = probed(html, ds(html), "return [].map.call(document.querySelectorAll('[data-card=box] .recharts-xAxis-tick-labels text'), function (t) { return t.textContent; });", act=click("box", "Commit"), more=True)
        self.assertIn("v1 (no commit)", " ".join(ticks))


class BuilderInputTests(unittest.TestCase):
    def test_the_title_loses_its_dashes_too(self) -> None:
        html = build_studio.build([run_snapshot()], title="NeMo \u2013 speech")
        self.assertIn("<title>NeMo, speech</title>", html)
        self.assertEqual(check_report.studio_static_checks(html), [])

    def test_a_nan_is_named_by_where_it_is(self) -> None:
        snap = run_snapshot()
        by_label(snap)["v1"]["metrics"][KEY]["std"] = float("nan")
        with self.assertRaisesRegex(ValueError, r"the snapshot's datasets\[0\]\.snapshot\.versions\[0\]\.metrics\.latency_ms\.std is NaN or Infinity"):
            build_studio.build([snap])


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class OlderSnapshotTests(unittest.TestCase):
    CHECK = DirectionWarningAndVerdictTests.CHECK

    def test_the_word_null_in_a_title_is_not_a_broken_value(self) -> None:
        snap = nemo()
        snap["versions"][0]["experimentTitle"] = "Skip null checks in the decode loop"
        self.assertEqual(check_report.studio_render_checks(build_studio.build([snap]), CHROME), [])

    def test_an_older_snapshot_keeps_its_direction_warning(self) -> None:
        snap = run_snapshot()
        snap["bestLines"]["lede"] += " " + self.CHECK
        snap["bestLines"].pop("checks", None)  # a snapshot from before bestLines.checks and directionChecks
        snap.pop("directionChecks", None)
        html = build_studio.build([snap])
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
        self.assertIn(self.CHECK, probed(html, ds(html), "return document.querySelector('header').textContent;"))
        dropped = html.replace("var checks = directionChecks(D.s, D.best);", "var checks = [];", 1)
        self.assertNotEqual(dropped, html)
        self.assertTrue(any(p.startswith("MISSING DIRECTION CHECK") for p in check_report.studio_render_checks(dropped, CHROME)))


class BuilderInputGuardTests(unittest.TestCase):
    def test_a_dash_used_as_a_minus_keeps_its_sign(self) -> None:
        self.assertEqual(build_studio.no_dashes(["latency \u201312%", "\u20130.5 ms", "x (\u20132.1%)"]), ["latency \u221212%", "\u22120.5 ms", "x (\u22122.1%)"])

    def test_fields_the_page_reads_without_a_guard_are_checked(self) -> None:
        no_readings = run_snapshot()
        del no_readings["baseline"]["readings"]
        listed = run_snapshot()
        listed["versions"][0]["metrics"] = []
        for snap, message in ((no_readings, "`baseline.readings` is missing"), (listed, "a version's `metrics` is not a JSON object")):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                build_studio.build([snap])

    def test_only_refuses_a_mark_on_a_snapshot_it_leaves_out(self) -> None:
        with self.assertRaisesRegex(ValueError, "--failed can mark only snapshot 1"):
            build_studio.build([run_snapshot(), run_snapshot()], failed=["2:1:1"], only="ranked")


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class CheckerResourceAndRenderTests(unittest.TestCase):
    def test_a_request_made_only_in_another_view_fails(self) -> None:
        html = build_studio.build([run_snapshot()]) + late('document.addEventListener("click", function (e) { if (e.target.textContent === "Mean") new Image().src = "https://example.com/mean.gif"; }, true);')
        problems = check_report.studio_render_checks(html, CHROME)
        self.assertTrue(any(p.startswith("LIVE FETCH: loaded https://example.com/mean.gif (after ") for p in problems), problems)

    def test_a_page_that_never_finishes_says_why_when_it_can(self) -> None:
        html = build_studio.build([run_snapshot()]).replace("function App() {", 'function App() { throw new Error("start broke");', 1)
        problems = check_report.render_checks(html, CHROME, "", "", 4000)
        self.assertEqual(problems, ["RENDER: the page did not finish rendering in headless Chrome: the page says 'The studio failed to draw this snapshot: start broke'"])


class OnlyOnAProjectTests(unittest.TestCase):
    def test_a_one_card_page_of_a_project_says_which_session_and_refuses_other_marks(self) -> None:
        with self.assertRaisesRegex(ValueError, "--failed can mark only session 1"):
            build_studio.build([project_snapshot(3)], failed=["1:3:1"], only="forest")
        build_studio.build([run_snapshot()], failed=["01:1:1"], only="forest")  # a padded snapshot number is still snapshot 1

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_the_page_names_the_session_it_draws(self) -> None:
        html = build_studio.build([project_snapshot(3)], only="forest")
        self.assertIn("Drawn from Discovery session 1 of 3", probed(html, "p-proj-1", "return document.querySelector('.page').textContent;"))
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])


class TradeOffBoxAndSaveTests(unittest.TestCase):
    def test_a_malformed_trade_off_block_is_refused_with_a_reason(self) -> None:
        for bad in ([], {"axes": ["x", "y"]}, {"axes": [{"key": "x"}]}):
            with self.subTest(pareto=bad):
                snap = run_snapshot()
                snap["pareto"] = bad
                with self.assertRaisesRegex(ValueError, "`pareto` is not"):
                    build_studio.build([snap], only="pareto")

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_save_refused_with_no_reason_still_says_so(self) -> None:
        stub = '<script>window.claude = { use: function () { return Promise.resolve({ save: function () { return Promise.reject(); } }); } };</script>'
        html = build_studio.build([run_snapshot()]).replace("<meta charset=\"utf-8\">", "<meta charset=\"utf-8\">" + stub, 1)
        act = click("ranked", "Download") + " setTimeout(function () { " + click("ranked", "CSV of the plotted data") + " }, 200);"
        toast = probed(html, ds(html), "var t = document.querySelector('.toast'); return t ? t.textContent : null;", act=act)
        self.assertEqual(toast, "Could not save r-11111111-1111-1111-1111-111111111111-ranked.csv")

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_version_whose_readings_are_all_null_is_named_under_the_box_plot(self) -> None:
        snap = run_snapshot()
        by_label(snap)["v2"]["metrics"][KEY]["runs"] = [None]
        html = build_studio.build([snap])
        self.assertRegex(probed(html, ds(html), "return document.querySelector('[data-card=box]').textContent;", more=True), r"No runs: [^.]*v2")


class SchemaAndAxisTests(unittest.TestCase):
    def test_the_builder_takes_the_collectors_schema_version_and_checks_the_card_first(self) -> None:
        self.assertIs(build_studio.SCHEMA_VERSION, collect_discovery.SCHEMA_VERSION)
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaisesRegex(ValueError, "--only must be one of"):
            build_studio.build([project_snapshot(2)], only="nope")
        self.assertEqual(err.getvalue(), "")

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_an_empty_target_file_list_is_unknown_not_another_task(self) -> None:
        project = project_snapshot(2)
        project["runs"][0]["run"]["targetFiles"] = ["src/a.cpp"]
        project["runs"][1]["run"]["targetFiles"] = []
        html = build_studio.build([project])
        self.assertNotIn("different task", probed(html, "p-proj-1", "return document.querySelector('[data-card=sessions]').textContent;"))

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_the_ai_axis_uses_the_minus_sign(self) -> None:
        html = build_studio.build([run_snapshot()])
        ticks = probed(html, ds(html), "return [].map.call(document.querySelectorAll('[data-card=ai] .recharts-xAxis-tick-labels text'), function (t) { return t.textContent; });", more=True)
        self.assertIn("\u2212100%", ticks)
        self.assertNotIn("-100%", ticks)


class MissingCardAndWordingTests(unittest.TestCase):
    def test_best_lines_that_are_not_an_object_are_refused(self) -> None:
        snap = run_snapshot()
        snap["bestLines"] = "v2 leads"
        with self.assertRaisesRegex(ValueError, "`bestLines` is not {label, lede, notes}"):
            build_studio.build([snap], only="pareto")

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_card_that_draws_nothing_at_all_fails(self) -> None:
        html = build_studio.build([run_snapshot()]).replace("function RankedCard(props) {", "function RankedCard(props) { return null;", 1)
        self.assertTrue(any(p.startswith("MISSING CARD: ranked") for p in check_report.studio_render_checks(html, CHROME)))

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_ranked_card_with_every_series_hidden_says_so(self) -> None:
        snap = with_intervals(run_snapshot())  # two series, so a legend
        html = build_studio.build([snap])
        act = click("ranked", "\u25b2 Significantly improved") + " setTimeout(function () { " + click("ranked", "\u2248 No significant difference") + " }, 200);"
        self.assertIn("Every series is hidden.", probed(html, ds(html), "return document.querySelector('[data-card=ranked] .plot').textContent;", act=act))

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_the_table_keeps_a_verdict_that_has_no_percent(self) -> None:
        snap = run_snapshot()
        no_pct(snap, "v2")
        html = build_studio.build([snap])
        text = probed(html, ds(html), "return document.querySelector('[data-card=table]').textContent;")
        self.assertIn("v2 no % change from Artemis", text)
        self.assertNotIn("v2 no Artemis comparison", text)

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_session_with_no_change_never_blames_a_check_that_did_not_run(self) -> None:
        project = project_snapshot(2)
        for v in project["runs"][1]["versions"]:
            if KEY in v["metrics"]:
                v["metrics"][KEY].update(pctBetter=None, vsBaseline=None)
        project["runs"][1]["rankings"][KEY] = []
        html = build_studio.build([project])
        text = probed(html, "p-proj-1", "return document.querySelector('[data-card=sessions]').textContent;")
        self.assertIn("Discovery session 2 has no version with a change on Latency (ms)", text)
        self.assertNotIn("no correct version", text)


class SessionsOnlyParityTests(unittest.TestCase):
    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_only_sessions_draws_what_the_studio_draws(self) -> None:
        project = project_snapshot(2)
        next(m for m in project["runs"][1]["metrics"] if m["key"] == KEY)["higherIsBetter"] = None  # only the first session's lead counts
        self.assertEqual(check_report.studio_render_checks(build_studio.build([project], only="sessions"), CHROME), [])

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_one_card_sessions_page_says_whose_best_it_names(self) -> None:
        html = build_studio.build([project_snapshot(3)], only="sessions")
        self.assertIn("The Best line below is Discovery session 1's; the chart ranks all 3 sessions.", probed(html, "p-proj-1", "return document.querySelector('.page').textContent;"))


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class WalkNoiseTests(unittest.TestCase):
    def test_one_broken_view_is_one_problem(self) -> None:
        html = build_studio.build([with_intervals(run_snapshot())]).replace("function ratioFromPct(p, hib) {", 'function ratioFromPct(p, hib) { throw new Error("log broke");', 1)
        problems = check_report.studio_render_checks(html, CHROME)
        self.assertTrue(any("log broke" in p for p in problems), problems)
        self.assertFalse([p for p in problems if p.startswith("WALK: the control for")], problems)

    def test_a_page_too_wide_is_said_once_per_view(self) -> None:
        html = build_studio.build([run_snapshot()]).replace(".page { max-width: 1240px;", ".page { min-width: 1100px; max-width: 1240px;", 1)
        problems = check_report.studio_render_checks(html, CHROME)
        wide = [p for p in problems if p.startswith("PAGE WIDER THAN THE WINDOW after")]
        self.assertTrue(wide, problems)  # said,
        self.assertLessEqual(len(wide), 2, wide)  # and at most once per pass (desktop, phone)


class NoPercentAndNoBestTests(unittest.TestCase):
    def test_a_reading_that_is_not_an_object_is_refused(self) -> None:
        snap = run_snapshot()
        snap["versions"][0]["metrics"]["quality_score"] = 0.5
        with self.assertRaisesRegex(ValueError, "a version's metric reading is not a JSON object"):
            build_studio.build([snap], only="ai")

    def test_best_lines_without_a_lede_are_refused(self) -> None:
        snap = run_snapshot()
        del snap["bestLines"]["lede"]
        with self.assertRaisesRegex(ValueError, "`bestLines` is not {label, lede, notes}"):
            build_studio.build([snap])

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_verdict_with_no_percent_keeps_its_verdict_everywhere(self) -> None:
        snap = with_intervals(run_snapshot())
        no_pct(snap, "v1")  # v1 is "better" in with_intervals
        snap["rankings"][KEY] = [r for r in snap["rankings"][KEY] if r["label"] != "v1"]
        html = build_studio.build([snap])
        got = probed(html, ds(html), "var t = function (id) { return document.querySelector('[data-card=' + id + ']').textContent; }; return { ranked: t('ranked'), forest: t('forest'), table: t('table') };")
        for card in ("ranked", "forest"):
            self.assertIn("No % change from Artemis: v1 (\u25b2 Significantly improved)", got[card], card)
            self.assertNotIn("No Artemis comparison: v1", got[card], card)
        self.assertIn("1 of 5 significantly improved: v1 no % change from Artemis", got["table"])

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_broken_value_in_a_conclusion_fails(self) -> None:
        html = build_studio.build([run_snapshot()])
        broken = html.replace('return r.label + " " + r.status; }).join(", ")', 'return r.label + " " + r.statu; }).join(", ")', 1)
        self.assertNotEqual(broken, html)
        self.assertTrue(any(p.startswith("BROKEN VALUE: ") for p in check_report.render_checks(broken, CHROME, "", check_report.studio_probe(), 8000)))

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_direction_warning_shows_when_no_version_leads(self) -> None:
        check = "latency_ms is set as higher-is-better on this project; check Settings > Metrics."
        snap = run_snapshot()
        snap["bestLines"] = None
        snap["directionChecks"] = [check]
        html = build_studio.build([snap])
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
        self.assertIn(check, probed(html, ds(html), "return document.querySelector('header').textContent;"))
        dropped = html.replace('if (s && Array.isArray(s.directionChecks)) return s.directionChecks;', 'if (s && Array.isArray(s.directionChecks)) return [];', 1)
        self.assertTrue(any(p.startswith("MISSING DIRECTION CHECK") for p in check_report.studio_render_checks(dropped, CHROME)))

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_values_artemis_sent_as_nan_are_named_on_the_page(self) -> None:
        snap = run_snapshot()
        snap["nonFinite"] = ["comparison.versions[2].metrics[0].improvementPct"]
        html = build_studio.build([snap])
        self.assertIn("Artemis sent 1 value that is not a number; read as missing: comparison.versions[2].metrics[0].improvementPct.", probed(html, ds(html), "return document.querySelector('header').textContent;"))


class DashDecodeAndExportTests(unittest.TestCase):
    def test_a_range_of_versions_reads_to(self) -> None:
        self.assertEqual(build_studio.no_dashes("Retry v2\u2013v5 tiling"), "Retry v2 to v5 tiling")
        for raw, plain in (("\u2014Fuse kernels", "Fuse kernels"), ("Fuse kernels \u2014", "Fuse kernels"), ("results: 5 \u2013 \u20133", "results: 5 to \u22123")):
            self.assertEqual(build_studio.no_dashes(raw), plain, raw)

    def test_a_probe_line_is_decoded_once(self) -> None:
        done = subprocess.CompletedProcess([], 0, stdout='<pre id="__ar_probe">LABEL HIDDEN: "a &amp;lt;b&amp;gt;"</pre>', stderr="")
        with unittest.mock.patch.object(check_report.subprocess, "run", return_value=done):
            self.assertEqual(check_report.render_checks("<title>t</title>", "chrome"), ['LABEL HIDDEN: "a &lt;b&gt;"'])

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_dashed_metric_key_never_shows_a_dash(self) -> None:
        snap = run_snapshot()
        rename = "p50\u2013p99_ms"
        for m in snap["metrics"]:
            if m["key"] == KEY:
                m.update(key=rename, label=None)
        for v in snap["versions"]:
            v["metrics"] = {rename if k == KEY else k: x for k, x in v["metrics"].items()}
        snap["baseline"]["metrics"] = {rename if k == KEY else k: x for k, x in snap["baseline"]["metrics"].items()}
        snap["baseline"]["readings"] = {rename if k == KEY else k: x for k, x in snap["baseline"]["readings"].items()}
        for d in ("rankings", "perMetricWinners"):
            snap[d] = {rename if k == KEY else k: x for k, x in snap[d].items()}
        snap["bestLines"]["metric"] = rename
        html = build_studio.build([snap])
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
        self.assertIn("P50 to p99 (ms)", probed(html, ds(html), "return document.querySelector('h1').textContent;"))
        raw = html.replace('.replace(/^\\s*[\\u2013\\u2014]\\s*|\\s*[\\u2013\\u2014]\\s*$/g, "").replace(/(\\w*\\d)\\s*\\u2013\\s*(?=[\\u2013\\u2212-]?\\w*\\d)/g, "$1 to ").replace(/\\s*[\\u2013\\u2014]\\s*/g, ", ")', "", 1)
        self.assertNotEqual(raw, html)
        self.assertTrue(any(p.startswith("DASH ON PAGE") for p in check_report.studio_render_checks(raw, CHROME)))

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_button_group_with_nothing_pressed_is_said(self) -> None:
        html = build_studio.build([run_snapshot()]) + late('var g = document.createElement("span"); g.className = "seg"; g.innerHTML = "<button>A</button><button>B</button>"; document.querySelector("[data-card=ranked] .tools").appendChild(g);')
        problems = check_report.render_checks(html, CHROME, "", check_report.studio_probe(), 30000)
        self.assertTrue(any(p.startswith("WALK: no button is pressed in Which versions moved") for p in problems), problems)

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_an_svg_export_that_fails_says_so(self) -> None:
        html = build_studio.build([run_snapshot()])
        act = "window.Blob = function () { throw new Error('no blob'); };" + click("ranked", "Download") + " setTimeout(function () { " + click("ranked", "SVG") + " }, 200);"
        toast = probed(html, ds(html), "var t = document.querySelector('.toast'); return t ? t.textContent : null;", act=act)
        self.assertEqual(toast, "SVG export failed (no blob)")


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class DashedNoteKeyTests(unittest.TestCase):
    def test_a_note_on_a_dashed_metric_key_still_pairs(self) -> None:
        snap = run_snapshot()
        rename = "p50\u2013p99_ms"
        for m in snap["metrics"]:
            if m["key"] == "compile_runtime":
                m.update(key=rename, label=None, kind="target")
        for v in snap["versions"]:
            v["metrics"] = {rename if k == "compile_runtime" else k: x for k, x in v["metrics"].items()}
        snap["baseline"]["metrics"] = {rename if k == "compile_runtime" else k: x for k, x in snap["baseline"]["metrics"].items()}
        snap["baseline"]["readings"] = {rename if k == "compile_runtime" else k: x for k, x in snap["baseline"]["readings"].items()}
        for d in ("rankings", "perMetricWinners"):
            snap[d] = {rename if k == "compile_runtime" else k: x for k, x in snap[d].items()}
        snap["bestLines"]["notes"] = {rename: "v4 is best on " + rename}
        self.assertEqual(check_report.studio_render_checks(build_studio.build([snap]), CHROME), [])


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class ExportNotesTests(unittest.TestCase):
    def test_a_saved_image_carries_the_cards_notes_and_hidden_series(self) -> None:
        html = build_studio.build([with_intervals(run_snapshot())])
        act = (ExportTests.CAPTURE + click("ranked", "\u25b2 Significantly improved") + " setTimeout(function () { " + click("ranked", "Download")
               + " setTimeout(function () { " + click("ranked", "SVG") + " }, 200); }, 300);")
        svg = probed(html, ds(html), "return window.__saved || '';", act=act)
        self.assertIn("Hidden in the legend: \u25b2 Significantly improved", svg)
        self.assertIn("Not measured: v3 (generation failed), v5 (execution failed)", svg)

    def test_a_save_that_throws_says_so_for_png_and_csv(self) -> None:
        html = build_studio.build([run_snapshot()])
        for item, words in (("PNG, 2x", "PNG export failed"), ("CSV of the plotted data", "CSV export failed")):
            with self.subTest(item=item):
                act = "URL.createObjectURL = function () { throw new Error('no url'); };" + click("ranked", "Download") + " setTimeout(function () { " + click("ranked", item) + " }, 200);"
                toast = probed(html, ds(html), "var t = document.querySelector('.toast'); return t ? t.textContent : null;", act=act)
                self.assertTrue(toast and toast.startswith(words), toast)

    def test_a_font_that_fails_to_download_is_said(self) -> None:
        html = build_studio.build([run_snapshot()])
        stub = ("var f0 = window.fetch; window.fetch = function (u) { return String(u).indexOf('fonts.gstatic.com') >= 0 ? Promise.resolve(new Response('', { status: 404 })) : f0.apply(this, arguments); };"
                + ExportTests.CAPTURE)
        act = stub + click("ranked", "Download") + " setTimeout(function () { " + click("ranked", "SVG") + " }, 200);"
        toast = probed(html, ds(html), "var t = document.querySelector('.toast'); return t ? t.textContent : null;", act=act)
        self.assertIn("the fonts did not load", toast or "")


class FailedMarkNoteTests(unittest.TestCase):
    def test_an_older_snapshot_is_said_on_stderr(self) -> None:
        snap = run_snapshot()
        snap["bestLines"].pop("metric")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            build_studio.build([snap])
        self.assertIn("collected by an older collect_discovery.py (no bestLines.metric)", err.getvalue())

    def test_a_mark_names_the_session_and_run_it_landed_on(self) -> None:
        project = project_snapshot(3)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            build_studio.build([project], failed=["1:2:1"])
        self.assertIn("--failed 1:2:1: marks v1 in Discovery session 2 (run run-1)", err.getvalue())


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class SaidOnThePageTests(unittest.TestCase):
    def test_a_correctness_mark_the_page_drops_fails(self) -> None:
        html = build_studio.build([run_snapshot()], failed=["1:1:2"])
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
        dropped = html.replace(": RUN_FAILED[dataset] || null;", ": null;", 1)
        self.assertNotEqual(dropped, html)
        self.assertTrue(any(p.startswith("MISSING CORRECTNESS MARK: v2") for p in check_report.studio_render_checks(dropped, CHROME)))

    def test_a_left_out_run_or_nan_note_the_page_drops_fails(self) -> None:
        project = project_snapshot(2)
        project["skipped"] = [{"id": "gone-run-1", "status": "cancelled", "reason": "no comparison"}]
        project["runs"][0]["nonFinite"] = ["v2 latency_ms improvementPct"]
        html = build_studio.build([project])
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
        dropped = html.replace("      ${leftOut}${nonFinite}", "      ", 1)
        self.assertNotEqual(dropped, html)
        problems = check_report.studio_render_checks(dropped, CHROME)
        self.assertTrue(any(p.startswith("MISSING LEFT-OUT RUN: run gone-run") for p in problems), problems)
        self.assertTrue(any(p.startswith("MISSING NON-FINITE NOTE: v2 latency_ms improvementPct") for p in problems), problems)

    def test_an_ai_metric_nobody_scored_says_so_and_unscored_versions_are_named(self) -> None:
        snap = run_snapshot()
        base = next(m for m in snap["metrics"] if m["key"] == "quality_score")
        snap["metrics"].append(dict(base, key="style_score", label="style_score"))
        snap["baseline"]["metrics"]["style_score"] = dict(snap["baseline"]["metrics"]["quality_score"])
        html = build_studio.build([snap])
        text = probed(html, ds(html), "return document.querySelector('[data-card=ai]').textContent;", more=True)
        self.assertIn("No version has a score on Style score.", text)
        self.assertIn("No score: v3", text)

    def test_a_best_with_no_reading_is_never_called_no_change(self) -> None:
        snap = run_snapshot()
        for m in snap["metrics"]:
            if m["key"] == "compile_runtime":
                m["kind"] = "target"
        del by_label(snap)["v2"]["metrics"]["compile_runtime"]
        html = build_studio.build([snap])
        text = probed(html, ds(html), "return document.querySelector('[data-card=best]').textContent;")
        self.assertIn("v2 has no reading on Compile runtime (s)", text)
        self.assertNotIn("no change from Artemis", text)


class FinalRoundTests(unittest.TestCase):
    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_every_one_card_page_says_which_versions_failed_the_users_check(self) -> None:
        for card in ("best", "ranked", "forest", "time", "box", "table", "pareto", "ai"):
            with self.subTest(card=card):
                html = build_studio.build([run_snapshot()], failed=["1:1:2"], only=card)
                self.assertEqual(check_report.studio_render_checks(html, CHROME), [])
                self.assertIn("Failed your correctness check: v2", probed(html, ds(html), "return document.querySelector('.page').innerText;"))

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_every_csv_says_which_rows_failed_the_users_check(self) -> None:
        html = build_studio.build([run_snapshot()], failed=["1:1:2"])
        act = ExportTests.CAPTURE + click("time", "Download") + " setTimeout(function () { " + click("time", "CSV of the plotted data") + " }, 200);"
        csv = probed(html, ds(html), "return window.__saved || '';", act=act)
        self.assertIn("failed_correctness_check", csv.split("\n")[0])
        self.assertTrue(any(line.startswith("v2,") and line.endswith(",true") for line in csv.split("\n")), csv)

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_skipped_run_with_no_id_is_named_as_such(self) -> None:
        project = project_snapshot(2)
        project["skipped"] = [{"id": None, "status": "cancelled", "reason": "no comparison"}]
        html = build_studio.build([project])
        self.assertIn("Not shown: a run with no id (cancelled, no comparison).", probed(html, "p-proj-1", "return document.querySelector('header').textContent;"))
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_missing_run_fields_read_plainly(self) -> None:
        snap = run_snapshot()
        snap["run"].pop("status", None)
        snap.pop("collectedAt", None)
        html = build_studio.build([snap])
        text = probed(html, ds(html), "return document.querySelector('header').textContent + ' | ' + document.querySelector('footer').textContent;")
        self.assertIn("no status, 5 versions", text)
        self.assertIn("Collection time not recorded", text)
        self.assertNotIn("undefined", text)

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_remembered_session_that_is_gone_is_said(self) -> None:
        html = build_studio.build([project_snapshot(2)])
        remembered = html.replace('var DATA = readSnap("studio-data")', 'try { localStorage.setItem("dv-studio:v1:session", "5"); } catch (e) {} var DATA = readSnap("studio-data")', 1)
        probe = "<script>setTimeout(function () { var d = document.createElement('pre'); d.id = '__ar_probe'; d.textContent = document.querySelector('header').textContent; document.body.appendChild(d); }, 3000);</script>"
        out = " ".join(check_report.render_checks(remembered, CHROME, "", probe, 8000))
        self.assertIn("The Discovery session you last opened is gone; showing session 2.", out)

    def test_a_chrome_that_cannot_start_is_a_render_line(self) -> None:
        with unittest.mock.patch.object(check_report.subprocess, "run", side_effect=OSError("No space left on device")):
            self.assertEqual(check_report.render_checks("<title>t</title>", "chrome"), ["RENDER: could not run Chrome in headless Chrome: No space left on device"])


class LastPassTests(unittest.TestCase):
    """The last confirming pass: what a reader sees and saves is true, and nothing is cut off."""

    def ranked_means(self, cis) -> str:
        snap = run_snapshot()
        by = by_label(snap)
        for label, (lo, hi) in zip(("v2", "v4"), cis):
            by[label]["metrics"][KEY]["vsBaseline"] = {"verdict": "better", "improvementPct": (lo + hi) / 2, "ciLowPct": lo, "ciHighPct": hi}
        html = build_studio.build([snap])
        return probed(html, ds(html), "return document.querySelector('[data-card=ranked] .means').textContent;")

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_two_versions_are_told_apart_when_their_intervals_do_not_overlap(self) -> None:
        self.assertNotIn("told apart", self.ranked_means(((38.0, 42.0), (15.0, 25.0))))
        self.assertIn("Can't be told apart from v4", self.ranked_means(((20.0, 42.0), (15.0, 25.0))))

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_the_box_range_comes_from_the_readings_it_draws(self) -> None:
        snap = run_snapshot()
        snap["baseline"]["metrics"][KEY].update(runs=[10.0, 12.0], min=5.0, max=20.0, count=5)
        html = build_studio.build([snap])
        text = probed(html, ds(html), "return document.querySelector('[data-card=box] .means').textContent;", more=True)
        self.assertRegex(text, r"Original: 10\.00 to 12\.00\D[^.]*over 2 iterations")

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_saved_ai_card_keeps_each_panels_scores_note(self) -> None:
        html = build_studio.build([nemo()])
        act = ExportTests.CAPTURE + click("ai", "Download") + " setTimeout(function () { " + click("ai", "SVG") + " }, 200);"
        svg = probed(html, ds(html), "return window.__saved || '';", act=act, more=True)
        self.assertTrue(svg.startswith("<svg"), svg[:80])
        words = re.sub(r"<[^>]+>", " ", svg)
        self.assertIn("No % from Artemis", " ".join(words.split()))

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_pop_ups_stay_on_a_phone_screen(self) -> None:
        html = build_studio.build([nemo()])
        for card in ("best", "ranked", "ai"):
            for menu in ("Metrics", "Download"):
                with self.subTest(card=card, menu=menu):
                    js = "var p = document.querySelector('[data-card=%s] .pop'); if (!p) return null; var r = p.getBoundingClientRect(); return [r.left, r.right, window.innerWidth];" % card
                    got = probed(html, ds(html), js, act=click(card, menu), phone=True, more=True)
                    if got is None and menu == "Metrics":
                        continue  # this card has no Metrics menu
                    self.assertIsNotNone(got)
                    self.assertGreaterEqual(got[0], 0, got)
                    self.assertLessEqual(got[1], got[2], got)

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_axis_titles_keep_their_direction_in_full(self) -> None:
        html = build_studio.build([nemo()])
        for phone in (False, True):
            with self.subTest(phone=phone):
                js = "var c = document.querySelector('[data-card=pareto]'); return { cut: [].map.call(c.querySelectorAll('[data-full]'), function (e) { return e.getAttribute('data-full'); }), text: c.textContent };"
                got = probed(html, ds(html), js, phone=phone, more=True)
                self.assertEqual(got["cut"], [])
                self.assertIn("higher is better", got["text"])

    @unittest.skipUnless(CHROME, "no Chrome or Chromium")
    def test_a_phone_box_plot_keeps_every_count_and_commit_readable(self) -> None:
        # Bench runs (cifar10, matmul-triton): 6 versions of 25 iterations hid every other "n=25" and cut commits to one letter at 390px.
        snap = run_snapshot()
        for n in (6, 7, 8):  # seven measured groups with the original, as on the bench's cifar10 run
            snap["versions"].append(json.loads(json.dumps(by_label(snap)["v1"])))
            snap["versions"][-1].update(version=n, label="v%d" % n, id="ver-%d" % n)
        snap["run"]["baselineVersionSha"] = "a1b2c3d" + "0" * 33
        for i, v in enumerate([snap["baseline"]] + snap["versions"]):
            st = v["metrics"].get(KEY)
            if not st:
                continue  # a version that failed to run has no readings
            st["runs"] = [st["mean"] + (k % 5) * 0.1 for k in range(25)]
            st.update(count=25, min=min(st["runs"]), max=max(st["runs"]))
            if i:
                v["versionSha"] = "%07x" % (0xb1b2c3d + i * 0x1111) + "0" * 33
        html = build_studio.build([snap], only="box")
        self.assertEqual(check_report.studio_render_checks(html, CHROME), [])


if __name__ == "__main__":
    unittest.main()


def without_web_font(html: str, family: str | None) -> str:
    """The page as a viewer sees it when Google Fonts is out of reach: the system's own sans, or the named one."""
    html = re.sub(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/[^"]*">', "", html)
    return html.replace("IBM Plex Sans", family) if family else html


def installed(family: str) -> bool:
    try:
        out = subprocess.run(["fc-match", "-f", "%{family}", family], capture_output=True, text=True, timeout=30, check=False).stdout
    except OSError:
        return False
    return family in out.split(",")  # fc-match names a substitute when the family is missing


@unittest.skipUnless(CHROME, "no Chrome or Chromium")
class FallbackFontTests(unittest.TestCase):
    def test_no_label_overlaps_in_a_fallback_font(self) -> None:
        # A viewer who cannot reach Google Fonts sees the system's sans: DejaVu Sans is wider than IBM Plex Sans and
        # Noto Sans taller, so text sized by counting characters ran into its neighbour (CI, 12 Nov).
        html = build_studio.build([project_snapshot(3)])
        for family in (None, "DejaVu Sans", "Noto Sans"):
            if family and not installed(family):
                continue  # the system default above still ran
            with self.subTest(family=family or "system default"):
                self.assertEqual(check_report.studio_render_checks(without_web_font(html, family), CHROME), [])
