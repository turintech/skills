#!/usr/bin/env python3
"""Check that the CLI release CI pins is one every skill declares it works with.

Usage: check_cli_pin.py X.Y.Z
Passes when the highest artemis-cli-min <= X.Y.Z < the lowest artemis-cli-max.
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
    """Every skill's metadata.<field> as a version tuple."""
    found = []
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        m = re.search(rf'^  {field}: "([^"]+)"', path.read_text(), re.M)
        if m and version_tuple(m.group(1)):
            found.append(version_tuple(m.group(1)))
    return found


if len(sys.argv) != 2 or not version_tuple(sys.argv[1]):
    sys.exit(__doc__)
pin = version_tuple(sys.argv[1])
low, high = max(declared("artemis-cli-min")), min(declared("artemis-cli-max"))
low_text, high_text = ".".join(map(str, low)), ".".join(map(str, high))
if not low <= pin < high:
    sys.exit(f"FAIL pinned CLI {sys.argv[1]} is outside the skills' range: {low_text} up to, not including, {high_text}")
print(f"OK: pinned CLI {sys.argv[1]} is within {low_text} up to, not including, {high_text}")
