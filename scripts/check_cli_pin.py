#!/usr/bin/env python3
"""Check the skills' CLI range against the CLI CI pins and the CLI production runs.

Usage: check_cli_pin.py X.Y.Z
         Passes when the highest artemis-cli-min <= X.Y.Z < the lowest artemis-cli-max.
       check_cli_pin.py --production FILE
         Passes when no skill's artemis-cli-min is above the version in FILE, the CLI
         production runs. A skill above it is a warning, or a failure with
         ARTEMIS_CLI_FLOOR_STRICT=1 (CI sets it for main, which production users install).
"""
import os
import pathlib
import re
import sys

SKILLS = pathlib.Path(os.environ.get("ARTEMIS_SKILLS_DIR") or pathlib.Path(__file__).resolve().parent.parent / "plugins/artemis/skills")


def version_tuple(text):
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", text)
    return tuple(int(n) for n in m.groups()) if m else None


def declared(field):
    """Every skill's metadata.<field>, as (skill name, version text, version tuple)."""
    found = []
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        m = re.search(rf'^  {field}: "([^"]+)"', path.read_text(), re.M)
        if m and version_tuple(m.group(1)):
            found.append((path.parent.name, m.group(1), version_tuple(m.group(1))))
    return found


def check_pin(text):
    pin = version_tuple(text)
    low = max(declared("artemis-cli-min"), key=lambda d: d[2])
    high = min(declared("artemis-cli-max"), key=lambda d: d[2])
    if not low[2] <= pin < high[2]:
        sys.exit(f"FAIL pinned CLI {text} is outside the skills' range: {low[1]} up to, not including, {high[1]}")
    print(f"OK: pinned CLI {text} is within {low[1]} up to, not including, {high[1]}")


def check_production(path):
    if not pathlib.Path(path).is_file():
        sys.exit(f"FAIL {path} missing: the CLI version production runs")
    text = pathlib.Path(path).read_text().strip()
    floor = version_tuple(text)
    if not floor:
        sys.exit(f"FAIL {path} must hold one X.Y.Z version, not {text!r}")
    above = [(name, low) for name, low, version in declared("artemis-cli-min") if version > floor]
    if not above:
        print(f"OK: no skill needs a CLI newer than {text}, the one production runs")
        return
    strict = os.environ.get("ARTEMIS_CLI_FLOOR_STRICT") == "1"
    # On GitHub Actions a warning becomes a PR annotation, so it is seen before the release PR fails.
    annotate = "::warning::" if not strict and os.environ.get("GITHUB_ACTIONS") == "true" else ""
    for name, low in above:
        print(f"{annotate}{'FAIL' if strict else 'WARN'} {name}: artemis-cli-min {low} is above {text}, the CLI production runs")
    if strict:
        sys.exit(1)


if len(sys.argv) == 3 and sys.argv[1] == "--production":
    check_production(sys.argv[2])
elif len(sys.argv) == 2 and version_tuple(sys.argv[1]):
    check_pin(sys.argv[1])
else:
    sys.exit(__doc__)
