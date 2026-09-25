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
        bad = build_report.build({}, "const top = 1;\nfetch('x');\n// an em dash — here", "Title")
        problems = " ".join(check_report.static_checks(bad))
        self.assertIn("RESERVED NAME", problems)
        self.assertIn("LIVE FETCH", problems)
        self.assertIn("DASH", problems)

    @unittest.skipUnless(check_report.find_chrome(), "no Chrome or Chromium")
    def test_rendered_page_has_no_problems(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = build_report.build({}, PAGE, "Title")
            self.assertEqual(check_report.render_checks(html, check_report.find_chrome()), [])


if __name__ == "__main__":
    unittest.main()
