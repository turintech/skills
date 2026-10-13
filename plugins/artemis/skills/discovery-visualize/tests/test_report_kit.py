#!/usr/bin/env python3
"""Checks for the HTML report kit, the page builder and the report checker."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_report  # noqa: E402
import check_report  # noqa: E402
import collect_discovery  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "synthetic"

PAGE = """const R = ArtemisReport;
R.header(document.getElementById('header'), { title: 'A finding', prov: ['run r'] });
const f = R.figure(document.getElementById('page'), { n: 1, question: 'How much?' });
R.rankedBars(f.chart, [{ label: 'v1', value: 10, text: '+10%' }], {});
f.finding('It went up.', 'By ten percent.');
"""

DEFAULT_PAGE = """const R = ArtemisReport;
R.header(document.getElementById('header'), { title: 'v2 is 10% faster', chips: [{ text: 'Better (falcon)', strong: true }, { text: '3 runs each' }] });
const page = document.getElementById('page');
const f1 = R.figure(page, { question: 'Every run' });
R.headline(f1.top, { left: { k: 'Baseline', v: '2.71' }, mid: { big: '+10%' }, right: { k: 'Best', v: '3.01' } });
R.compareRuns(f1.chart, { label: 'Baseline', runs: [2.70, 2.71, 2.72], mean: 2.71 }, { label: 'v2', runs: [2.96, 3.03, 3.04], mean: 3.01, color: '#16a34a' }, { pctText: 'Artemis: +10%  (better)', axisLabel: 'fps' });
f1.bullets(['<b>No overlap:</b> all 3 runs', 'a <script> stays text']);
const f2 = R.figure(page, { question: 'Which changes were real?' });
R.forest(f2.chart, [
  { label: 'v2', pct: 10, lo: 7, hi: 14, verdict: 'better', n: 5, hero: true },
  { label: 'v1', pct: 1, lo: -7, hi: 9, verdict: 'noise', n: 5, color: '#dc2626' },
  { label: 'v3', pct: -9, lo: -12, hi: -6, verdict: 'worse', n: 5 },
  { label: 'v4', pct: 2, lo: null, hi: null, note: 'n = 1, no interval' },
]);
f2.bullets(['<b>Really faster:</b> v2']);
R.bullets(page, ['Verdicts from Artemis'], { quiet: true });
R.footer(page, { prov: ['run r'], link: { href: '#' } });
"""


class KitTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_kit_parses(self) -> None:
        subprocess.run(["node", "--check", str(ROOT / "assets" / "report-kit.js")], check=True)

    def test_build_fills_every_placeholder(self) -> None:
        html = build_report.build({"run": {"id": "r"}, "note": "</script>"}, PAGE, "Title")
        for key in ("__TITLE__", "__KIT__", "__SNAPSHOT__", "__PAGE__"):
            self.assertNotIn(key, html)
        self.assertIn("window.ArtemisReport", html)
        # Data cannot close its own script element.
        self.assertNotIn('"</script>"', html)

    def test_built_page_passes_static_checks(self) -> None:
        self.assertEqual(check_report.static_checks(build_report.build({}, PAGE, "Title")), [])

    def test_static_checks_catch_known_faults(self) -> None:
        bad = build_report.build({}, "const top = 1;\nfetch('x');\n// an em dash — here\n// font: monospace", "Title")
        problems = " ".join(check_report.static_checks(bad))
        self.assertIn("RESERVED NAME", problems)
        self.assertIn("LIVE FETCH", problems)
        self.assertIn("DASH", problems)
        self.assertIn("MONOSPACE", problems)

    def test_default_figures_pass_static_checks(self) -> None:
        self.assertEqual(check_report.static_checks(build_report.build({}, DEFAULT_PAGE, "Title")), [])

    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_default_figures_render(self) -> None:
        html = build_report.build({}, DEFAULT_PAGE, "Title")
        self.assertEqual(check_report.render_checks(html, check_report.find_chrome()), [])

    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_rendered_page_has_no_problems(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = build_report.build({}, PAGE, "Title")
            self.assertEqual(check_report.render_checks(html, check_report.find_chrome()), [])


class RecipeTests(unittest.TestCase):
    """The default page in references/report-kit.md repeats falcon's verdict; it never re-judges it."""

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_headline_words_follow_falcons_verdict(self) -> None:
        recipe = (ROOT / "references" / "report-kit.md").read_text(encoding="utf-8")
        line = next(l for l in recipe.splitlines() if l.startswith("const verdict = "))
        script = "const out = [];\n" + "".join(
            "{ const t = " + t + "; " + line + " out.push(verdict); }\n"
            for t in ("{verdict: 'better'}", "{verdict: 'worse'}", "{verdict: 'noise'}", "{verdict: 'pending'}", "null")
        ) + "console.log(JSON.stringify(out));"
        result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
        self.assertEqual(
            __import__("json").loads(result.stdout),
            [", a real gain", ", a real loss", ", within the noise", ", too few runs to tell yet", ""],
        )

    def test_recipe_stops_when_there_is_no_best_version(self) -> None:
        recipe = (ROOT / "references" / "report-kit.md").read_text(encoding="utf-8")
        self.assertIn("if (!BL) throw new Error('No best version for ' + key + ': ' + S.perMetricWinners[key].reason", recipe)

    def test_recipe_never_prints_null_runs(self) -> None:
        recipe = (ROOT / "references" / "report-kit.md").read_text(encoding="utf-8")
        self.assertNotIn("{ text: t.readings + ' runs vs '", recipe)
        self.assertNotIn("fmt.p", recipe.replace("fmt.pct", ""))

    # ART-2547 (a): the default page charts the Composite score per version on its own axis, without a zero line.
    def test_recipe_charts_the_composite_score_per_version(self) -> None:
        recipe = (ROOT / "references" / "report-kit.md").read_text(encoding="utf-8")
        figure = recipe.split("// The Composite score per version", 1)[1].split("// Method note.", 1)[0]
        self.assertIn("R.trajectory(fc.chart, S.versions.map(v => ({ label: v.label, y: v.fitness, gapText", figure)
        self.assertIn("fits.length >= 3 && new Set(fits).size > 1", recipe)
        self.assertNotIn("zero:", figure)



class RecipeRenderTests(unittest.TestCase):
    """report-kit.md's own default page, run on the synthetic run, with and without each reading."""

    @staticmethod
    def recipe_page() -> str:
        recipe = (ROOT / "references" / "report-kit.md").read_text(encoding="utf-8")
        return recipe.split("```js\n", 1)[1].split("\n```", 1)[0]

    @staticmethod
    def relead(snapshot: dict) -> dict:
        """Recompute the collector's best lines after a test edits the snapshot."""
        defs = {m["key"]: m for m in snapshot["metrics"]}
        snapshot["bestLines"] = collect_discovery.best_lines(defs, snapshot["versions"], snapshot["perMetricWinners"], snapshot["webUiBest"])
        return snapshot

    @staticmethod
    def fixture_snapshot(with_readings: bool) -> dict:
        payloads = collect_discovery.load_from_dir(str(FIXTURE))
        if not with_readings:
            payloads["observations"] = None
        return collect_discovery.build_snapshot(payloads, collected_at="2026-01-01T00:00:00Z")

    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_recipe_renders_with_each_reading(self) -> None:
        html = build_report.build(self.fixture_snapshot(True), self.recipe_page(), "Title")
        self.assertEqual(check_report.render_checks(html, check_report.find_chrome()), [])

    # The synthetic run has one run per side, so this gives each side three to reach the per-metric bars,
    # the every-run figure and the forest.
    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_recipe_renders_with_several_runs_per_side(self) -> None:
        snapshot = self.fixture_snapshot(True)
        for side in [snapshot["baseline"]] + snapshot["versions"]:
            for m in side["metrics"].values():
                if m.get("mean") is not None:
                    m["count"] = 3
                    m["runs"] = [m["mean"] * 0.99, m["mean"], m["mean"] * 1.01]
                    if m.get("vsBaseline"):
                        m["vsBaseline"]["readings"] = 3
        snapshot["baseline"]["readings"] = {k: 3 for k in snapshot["baseline"]["readings"]}
        html = build_report.build(snapshot, self.recipe_page(), "Title")
        self.assertEqual(check_report.render_checks(html, check_report.find_chrome()), [])

    # One run per side has no verdict: the page draws every version against the baseline and skips the intervals.
    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_recipe_renders_with_one_run_per_side(self) -> None:
        snapshot = self.fixture_snapshot(True)
        for side in [snapshot["baseline"]] + snapshot["versions"]:
            for m in side["metrics"].values():
                m["count"] = 1
                if m.get("runs"):
                    m["runs"] = m["runs"][:1]
                if m.get("vsBaseline"):
                    m["vsBaseline"].update({"verdict": "pending", "ciLowPct": None, "ciHighPct": None})
        html = build_report.build(snapshot, self.recipe_page(), "Title")
        self.assertEqual(check_report.render_checks(html, check_report.find_chrome()), [])

    # Without readings the page threw "winM.runs is not iterable" and drew nothing.
    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_recipe_renders_without_readings(self) -> None:
        html = build_report.build(self.fixture_snapshot(False), self.recipe_page(), "Title")
        self.assertEqual(check_report.render_checks(html, check_report.find_chrome()), [])


    # The caption says the ring marks the winner, so the winner's point carries the ring (r=10) and no other does.
    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_recipe_rings_the_winner_on_the_composite_chart(self) -> None:
        html = build_report.build(self.fixture_snapshot(True), self.recipe_page(), "Title")
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "page.html"
            page.write_text(html, encoding="utf-8")
            dom = subprocess.run(
                [check_report.find_chrome(), "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={Path(tmp) / 'profile'}",
                 "--virtual-time-budget=4000", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, timeout=120, check=False,
            ).stdout
        self.assertIn("The ring marks", dom)
        self.assertEqual(dom.count('r="10"'), 1)

    @staticmethod
    def page_text(html: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "page.html"
            page.write_text(html, encoding="utf-8")
            dom = subprocess.run(
                [check_report.find_chrome(), "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={Path(tmp) / 'profile'}",
                 "--virtual-time-budget=4000", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, encoding="utf-8", timeout=120, check=False,
            ).stdout
        import html as html_lib
        import re
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", dom, flags=re.S)
        return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", text)))

    # The best version can still be behind the baseline: falcon's change is negative and its verdict "worse".
    def behind_snapshot(self, higher_is_better: bool) -> dict:
        snapshot = self.fixture_snapshot(True)
        key = "latency_ms"
        next(m for m in snapshot["metrics"] if m["key"] == key)["higherIsBetter"] = higher_is_better
        times = collect_discovery.times_better(-24.0, higher_is_better)
        snapshot["perMetricWinners"][key]["raw"].update({"pctBetter": -24.0, "timesBetter": times})
        win = next(v for v in snapshot["versions"] if v["version"] == snapshot["perMetricWinners"][key]["raw"]["version"])
        win["metrics"][key].update({"pctBetter": -24.0, "timesBetter": times})
        if win["metrics"][key].get("vsBaseline"):
            win["metrics"][key]["vsBaseline"]["verdict"] = "worse"
        return snapshot

    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_a_best_version_behind_the_baseline_reads_as_behind_when_lower_is_better(self) -> None:
        text = self.page_text(build_report.build(self.behind_snapshot(False), self.recipe_page(), "Title"))
        self.assertIn("v2 is 24.0% higher , a real loss", text)
        self.assertIn("1.24× worse than the baseline", text)
        self.assertNotIn("better than the baseline", text)

    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_a_best_version_behind_the_baseline_reads_as_behind_when_higher_is_better(self) -> None:
        text = self.page_text(build_report.build(self.behind_snapshot(True), self.recipe_page(), "Title"))
        self.assertIn("v2 is 24.0% slower , a real loss", text)
        self.assertIn("1.32× worse than the baseline", text)
        self.assertNotIn("better than the baseline", text)

    # The page leads with the Web UI's Best (highest Composite score), says so, and names a metric's own best when it differs.
    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_the_headline_is_the_web_uis_best_and_says_so(self) -> None:
        snapshot = self.fixture_snapshot(True)
        for v in snapshot["versions"]:
            v["fitness"] = 0.9 if v["label"] == "v4" else 0.3
        snapshot["webUiBest"] = collect_discovery.web_ui_best(snapshot["versions"])
        self.relead(snapshot)
        text = self.page_text(build_report.build(snapshot, self.recipe_page(), "Title"))
        self.assertIn("v4 is the Web UI’s Best: the highest Composite score", text)
        self.assertIn("Best on a single metric instead: v2 on latency_ms", text)
        self.assertIn("Best version · v4", text)
        # With several runs per side, each metric's panel shows v4 and notes the metric's own best.
        for side in [snapshot["baseline"]] + snapshot["versions"]:
            for m in side["metrics"].values():
                if m.get("mean") is not None:
                    m["count"] = 3
                    m["runs"] = [m["mean"] * 0.99, m["mean"], m["mean"] * 1.01]
        text = self.page_text(build_report.build(snapshot, self.recipe_page(), "Title"))
        self.assertIn("Artemis v4", text)
        self.assertIn("v2 is best on latency_ms", text)

    # The per-panel note, like the lede, names another best only on a measured metric, never an AI Metric.
    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_panel_notes_name_another_best_only_on_measured_metrics(self) -> None:
        snapshot = self.fixture_snapshot(True)
        for side in [snapshot["baseline"]] + snapshot["versions"]:
            for m in side["metrics"].values():
                if m.get("mean") is not None:
                    m["count"] = 3
                    m["runs"] = [m["mean"] * 0.99, m["mean"], m["mean"] * 1.01]
        notes = snapshot["bestLines"]["notes"]
        text = self.page_text(build_report.build(snapshot, self.recipe_page(), "Title"))
        for note in notes.values():
            self.assertIn(note, text)
        self.assertEqual(text.count(" is best on "), sum(" is best on " in n for n in notes.values()))

    # A metric the Web UI's Best has no reading for keeps its panel, on the metric's own best, and says why.
    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_a_metric_the_best_did_not_measure_keeps_its_panel(self) -> None:
        snapshot = self.fixture_snapshot(True)
        best = next(v for v in snapshot["versions"] if v["version"] == snapshot["webUiBest"]["version"])
        best["metrics"].pop("quality_score")
        self.relead(snapshot)
        for side in [snapshot["baseline"]] + snapshot["versions"]:
            for m in side["metrics"].values():
                if m.get("mean") is not None:
                    m["count"] = 3
                    m["runs"] = [m["mean"] * 0.99, m["mean"], m["mean"] * 1.01]
        text = self.page_text(build_report.build(snapshot, self.recipe_page(), "Title"))
        own = snapshot["perMetricWinners"]["quality_score"]["raw"]["label"]
        self.assertIn(best["label"] + " has no reading on quality_score; " + own + " is best on it", text)
        self.assertIn("quality_score", text.split("What changed")[0])
        self.assertIn("Artemis " + own, text)

    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_without_a_web_ui_best_the_page_says_why(self) -> None:
        snapshot = self.fixture_snapshot(True)
        snapshot["webUiBest"] = None
        self.relead(snapshot)
        text = self.page_text(build_report.build(snapshot, self.recipe_page(), "Title"))
        self.assertIn("The Web UI shows no Best, as no version’s Composite score is above the baseline", text)
        self.assertNotIn("is the Web UI’s Best", text)

    # A steer read from the run's chat is drawn on the Composite chart and named in the method note.
    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_a_steer_from_the_chat_is_marked(self) -> None:
        snapshot = self.fixture_snapshot(True)
        snapshot["steering"] = {"points": [{"at": "2026-10-13T12:35:39Z", "guidance": "Focus on memory now", "firstVersion": 4, "firstLabel": "v4"}],
                                "source": "artemis chat messages <chat-id>", "reason": None}
        text = self.page_text(build_report.build(snapshot, self.recipe_page(), "Title"))
        self.assertIn("Steered: Focus on memory now", text)
        self.assertIn("Steered before v4: “Focus on memory now”", text)
        snapshot["steering"] = {"points": [], "source": None, "reason": "the run's chat could not be read, so its steers are unknown"}
        text = self.page_text(build_report.build(snapshot, self.recipe_page(), "Title"))
        self.assertNotIn("Steered", text)
        self.assertIn("Steers not shown: the run's chat could not be read", text)

    # check_report fails a page that leaves out the collector's best lines, whatever script drew it.
    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_check_report_requires_the_best_lines(self) -> None:
        snapshot = self.fixture_snapshot(True)
        snapshot["bestLines"]["notes"]["compile_runtime"] = "v4 is best on compile_runtime"
        own_page = "ArtemisReport.header(document.getElementById('header'), { title: 'My own page' });\n" \
                   "ArtemisReport.trajectory(document.getElementById('page'), SNAPSHOT.versions.map(v => ({ label: v.label, y: v.fitness })));"
        problems = check_report.render_checks(build_report.build(snapshot, own_page, "Title"), check_report.find_chrome())
        self.assertTrue(any(p.startswith("MISSING BEST LINE") and "Web UI" in p for p in problems), problems)
        self.assertTrue(any("v4 is best on compile_runtime" in p for p in problems), problems)
        kept = own_page.replace("title: 'My own page'", "title: 'My own page', lede: SNAPSHOT.bestLines.lede + ' ' + Object.values(SNAPSHOT.bestLines.notes).join('. ')")
        problems = check_report.render_checks(build_report.build(snapshot, kept, "Title"), check_report.find_chrome())
        self.assertFalse([p for p in problems if p.startswith("MISSING BEST LINE")], problems)

    # Fewer than three Composite scores: the page leaves that figure out and still draws the rest.
    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_recipe_renders_without_composite_scores(self) -> None:
        snapshot = self.fixture_snapshot(True)
        for v in snapshot["versions"]:
            v["fitness"] = None
        html = build_report.build(snapshot, self.recipe_page(), "Title")
        self.assertEqual(check_report.render_checks(html, check_report.find_chrome()), [])


    # Every version on the same Composite score: no flat chart, one line in the method note instead.
    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_recipe_renders_with_equal_composite_scores(self) -> None:
        snapshot = self.fixture_snapshot(True)
        for v in snapshot["versions"]:
            v["fitness"] = 1
        html = build_report.build(snapshot, self.recipe_page(), "Title")
        self.assertEqual(check_report.render_checks(html, check_report.find_chrome()), [])


class MaintainReportTests(unittest.TestCase):
    """maintain-report.md's page, on a small synthetic board."""

    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_maintain_page_renders(self) -> None:
        page = (ROOT / "references" / "maintain-report.md").read_text(encoding="utf-8").split("```js\n", 1)[1].split("\n```", 1)[0]
        lanes = ["untriaged", "triaged", "in_progress", "done"]
        issues = [{"status": "open", "severity": sev, "lane": lanes[i % 4], "validity": "not_set"}
                  for i, sev in enumerate(["critical", "high", "high", "medium", "low", "low", "low"])]
        issues.append({"status": "closed", "severity": "low", "lane": "done", "validity": "false_positive"})
        snapshot = {"projectId": "p1234567", "projectName": "Smoke", "webUrl": "#", "issues": issues}
        html = build_report.build(snapshot, page, "Maintain")
        self.assertEqual(check_report.render_checks(html, check_report.find_chrome()), [])


if __name__ == "__main__":
    unittest.main()
