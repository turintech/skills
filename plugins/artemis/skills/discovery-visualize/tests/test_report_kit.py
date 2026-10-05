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
R.headline(f1.top, { left: { k: 'Original', v: '2.71' }, mid: { big: '+10%' }, right: { k: 'Best', v: '3.01' } });
R.compareRuns(f1.chart, { label: 'Original', runs: [2.70, 2.71, 2.72], mean: 2.71 }, { label: 'v2', runs: [2.96, 3.03, 3.04], mean: 3.01, color: '#16a34a' }, { pctText: '+10%  (p = 0.005)', axisLabel: 'fps' });
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


if __name__ == "__main__":
    unittest.main()
