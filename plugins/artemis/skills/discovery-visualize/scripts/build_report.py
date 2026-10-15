#!/usr/bin/env python3
"""Build one self-contained report page from the template, the report kit, a snapshot, and a page script.

Stdlib only. The page script uses ArtemisReport (see assets/report-kit.js) and the global SNAPSHOT.

    python3 build_report.py --snapshot snap.json --page page.js --title "Particle Life run" --output report.html
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets" / "report-template.html"
KIT = ROOT / "assets" / "report-kit.js"


def build(snapshot: object, page_js: str, title: str) -> str:
    # Escape "</" so data can never close the script element it sits in.
    data = json.dumps(snapshot, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8")
    for key, value in (("__TITLE__", title), ("__KIT__", KIT.read_text(encoding="utf-8")), ("__SNAPSHOT__", data), ("__PAGE__", page_js)):
        if html.count(key) != 1:
            raise ValueError(f"template placeholder {key} must appear exactly once")
        html = html.replace(key, value)
    return html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", required=True, help="Snapshot JSON (one collector snapshot, or any JSON the page script expects)")
    parser.add_argument("--page", required=True, help="Page script using ArtemisReport and SNAPSHOT")
    parser.add_argument("--title", required=True, help="Short page title for the browser tab")
    parser.add_argument("--output", required=True, help="Where to write the HTML")
    args = parser.parse_args(argv)
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    html = build(snapshot, Path(args.page).read_text(encoding="utf-8"), args.title)
    Path(args.output).write_text(html, encoding="utf-8")
    print(f"wrote {args.output} ({len(html) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
