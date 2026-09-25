#!/usr/bin/env python3
"""Check that every `artemis` command and flag in the skills exists in a real CLI.

Usage: check_cli.py [path-to-artemis]   (default: `artemis` on PATH)
Reads each command's --help, so no login or network is needed.
"""
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile

SKILLS = pathlib.Path(__file__).resolve().parent.parent / "plugins/artemis/skills"
CLI = sys.argv[1] if len(sys.argv) > 1 else "artemis"
HOME = tempfile.mkdtemp()
_help = {}
VALUED = {"--output-format", "--config", "--ssl-cert-file"}


def help_for(path):
    key = tuple(path)
    if key not in _help:
        out = subprocess.run([CLI, *path, "--help"], capture_output=True, text=True,
                             env={**os.environ, "HOME": HOME}).stdout
        # Commands are listed after "Usage:", in "Available Commands:" or grouped sections, before "Flags:".
        listing = out.rsplit("Usage:", 1)[-1].split("Flags:", 1)[0]
        subs = set(re.findall(r"^  ([a-z][a-z0-9-]*)\s+[A-Z]", listing, re.M))
        flags = set(re.findall(r"^\s+(?:-\w, )?(--[a-z][a-z0-9-]*)", out, re.M))
        _help[key] = (subs, flags)
    return _help[key]


def commands(text):
    """Yield `artemis ...` invocations from fenced code blocks and inline code."""
    for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.S):
        for line in block.replace("\\\n", " ").splitlines():
            for part in re.split(r"\|\||&&|[|;]|\$\(", line):
                m = re.search(r"(?:^|\s)(artemis\s.*)", part)
                if m:
                    yield m.group(1)
    roots = help_for([])[0]
    for m in re.finditer(r"`([a-z][^`]*)`", text):
        words = m.group(1).split()
        if words[0] == "artemis" and len(words) > 1:
            yield m.group(1)
        elif words[0] in roots and len(words) > 1 and words[0] not in ("help", "version"):
            yield "artemis " + m.group(1)


def check(cmd):
    cmd = re.split(r"\s[12]?>|\s<\s|\)", cmd)[0]
    try:
        toks = shlex.split(cmd)
    except ValueError:
        toks = cmd.split()
    # Drop global flags that take a value, so the value is not read as a command.
    toks = [t for i, t in enumerate(toks)
            if t not in VALUED and (i == 0 or toks[i - 1] not in VALUED)]
    path, flags, i = [], [], 1
    while i < len(toks):
        t = toks[i]
        if t.startswith("--"):
            flags.append(t.split("=", 1)[0])
        elif not t.startswith("-") and t in help_for(path)[0]:
            path.append(t)
        i += 1
    if not path:
        rest = [t for t in toks[1:] if not t.startswith("-")]
        return [f"unknown command {rest[0]!r}"] if rest and re.fullmatch(r"[a-z][a-z-]+", rest[0]) else []
    known = help_for(path)[1] | help_for([])[1]
    return [f for f in flags if f not in known and f != "--help"]


failures, checked = [], []
for skill in sorted(SKILLS.iterdir()):
    for f in sorted(skill.rglob("*.md")):
        for cmd in set(commands(f.read_text())):
            checked.append(cmd)
            for flag in check(cmd):
                failures.append(f"{f.relative_to(SKILLS)}: {flag} unknown in: {cmd[:90]}")

version = subprocess.run([CLI, "--version"], capture_output=True, text=True).stdout.strip()
for f in sorted(set(failures)):
    print("FAIL", f)
print(f"{len(checked)} commands checked against {version}: {'OK' if not failures else str(len(set(failures))) + ' problems'}")
sys.exit(1 if failures else 0)
