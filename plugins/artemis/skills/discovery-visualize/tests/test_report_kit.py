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
        self.assertIn("if (!win) throw new Error('No best version for ' + key + ': ' + S.perMetricWinners[key].reason", recipe)

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
