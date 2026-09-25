#!/usr/bin/env python3
"""Check a built report before sharing it.

Static checks always run. With Chrome or Chromium installed, the page is also rendered headlessly
and checked for script errors, labels drawn outside their chart, and empty titles or findings.
Exit status is non-zero when anything fails.

    python3 check_report.py report.html
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Browser globals that a top-level `const`/`let` cannot redeclare; doing so stops the whole script.
RESERVED = ("top", "name", "parent", "status", "length", "origin", "self", "frames", "history", "location")

PROBE = """
<script>
setTimeout(function () {
  var out = (window.__AR_ERRORS || []).slice();
  document.querySelectorAll('svg').forEach(function (svg) {
    var vb = svg.viewBox && svg.viewBox.baseVal;
    if (!vb || !vb.width) return;
    svg.querySelectorAll('text').forEach(function (t) {
      if (t.getAttribute('transform')) return;
      var b = t.getBBox();
      if (b.x < -1 || b.x + b.width > vb.width + 1 || b.y < -1 || b.y + b.height > vb.height + 1)
        out.push('OUTSIDE CHART: ' + t.textContent.slice(0, 60));
    });
  });
  var h1 = document.querySelector('h1');
  if (!h1 || !h1.textContent.trim()) out.push('EMPTY TITLE');
  document.querySelectorAll('section h2').forEach(function (h2) {
    var f = h2.parentElement.querySelector('.ar-finding, .finding');
    if (f && !f.textContent.trim()) out.push('EMPTY FINDING under: ' + h2.textContent.slice(0, 60));
  });
  if (!document.querySelector('svg')) out.push('NO CHART RENDERED');
  var d = document.createElement('pre'); d.id = '__ar_probe'; d.textContent = out.join('\\n') || 'OK';
  document.body.appendChild(d);
}, 1200);
</script>
"""
CATCHER = '<script>window.__AR_ERRORS=[];window.addEventListener("error",function(e){window.__AR_ERRORS.push("SCRIPT ERROR: "+e.message+" (line "+e.lineno+")")});</script>'


def static_checks(html: str) -> list[str]:
    problems = []
    if re.search(r"[–—]|&(ndash|mdash|#8211|#8212);", html):
        problems.append("DASH: an en or em dash is in the page; use a comma, colon or 'to'")
    for name in RESERVED:
        if re.search(rf"^\s*(const|let)\s+{name}\s*=", html, re.M):
            problems.append(f"RESERVED NAME: a top-level `{name}` clashes with a browser global and stops the script")
    if re.search(r"\bfetch\(|XMLHttpRequest", html):
        problems.append("LIVE FETCH: the page must embed its data, not fetch it")
    if "<title>" not in html[:8192]:
        problems.append("NO <title> in the first 8KB")
    return problems


def find_chrome() -> str | None:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    return mac if os.path.exists(mac) else None


def render_checks(html: str, chrome: str) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "probe.html"
        page.write_text(CATCHER + html + PROBE, encoding="utf-8")
        profile = Path(tmp) / "profile"
        result = subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={profile}",
             "--window-size=1000,900", "--virtual-time-budget=4000", "--dump-dom", page.as_uri()],
            capture_output=True, text=True, timeout=120, check=False,
        )
    match = re.search(r'<pre id="__ar_probe">(.*?)</pre>', result.stdout, re.S)
    if not match:
        return ["RENDER: the page did not finish rendering in headless Chrome"]
    text = match.group(1).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()
    return [] if text == "OK" else text.splitlines()


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: check_report.py report.html", file=sys.stderr)
        return 2
    html = Path(args[0]).read_text(encoding="utf-8")
    problems = static_checks(html)
    chrome = find_chrome()
    if chrome:
        problems += render_checks(html, chrome)
    else:
        print("note: no Chrome or Chromium found, so only static checks ran; open the page and look at it")
    for p in problems:
        print("FAIL", p)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
