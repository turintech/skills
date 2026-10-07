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
        # Only the flag lists count: a flag named in an example is not proof it exists.
        sections = re.findall(r"^(?:Global )?Flags:\n(.*?)(?:\n\n|\Z)", out, re.M | re.S)
        flags = set(re.findall(r"^\s+(?:-\w, )?(--[a-z][a-z0-9-]*)", "\n".join(sections), re.M))
        _help[key] = (subs, flags)
    return _help[key]


def alias_of(path, word):
    """The command `word` names under `path` when it is an alias the listing does not show, else None."""
    out = subprocess.run([CLI, *path, word, "--help"], capture_output=True, text=True,
                         env={**os.environ, "HOME": HOME}).stdout
    m = re.search(r"^Aliases:\n\s+(.+)$", out, re.M)
    if not m or word not in [a.strip() for a in m.group(1).split(",")]:
        return None
    return m.group(1).split(",")[0].strip()


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
        if re.search(r"\b(?:no|not)\s+$", text[max(0, m.start() - 5):m.start()]):
            continue  # "There is no `...`" names a command that must not be used.
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
    path, flags, problems, i = [], [], [], 1
    while i < len(toks):
        t = toks[i]
        subs = help_for(path)[0]
        if t.startswith("--"):
            flags.append(t.split("=", 1)[0])
        elif not t.startswith("-") and t in subs:
            path.append(t)
        elif not t.startswith("-") and subs and alias_of(path, t):
            path.append(alias_of(path, t))
        elif path and subs and re.fullmatch(r"[a-z][a-z-]+", t) and not toks[i - 1].startswith("-"):
            # A word where the CLI expects one of its subcommands, not a value or a placeholder.
            problems.append(f"command {' '.join(path + [t])!r}")
            break
        i += 1
    if not path:
        rest = [t for t in toks[1:] if not t.startswith("-")]
        return [f"unknown command {rest[0]!r}"] if rest and re.fullmatch(r"[a-z][a-z-]+", rest[0]) else []
    known = help_for(path)[1] | help_for([])[1]
    return problems + [f for f in flags if f not in known and f != "--help"]


def version_tuple(text):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(n) for n in m.groups()) if m else None


def cli_min(skill):
    """metadata.artemis-cli-min as a (major, minor, patch) tuple, or None."""
    path = skill / "SKILL.md"
    m = path.exists() and re.search(r'^  artemis-cli-min: "([^"]+)"', path.read_text(), re.M)
    return version_tuple(m.group(1)) if m else None


version = subprocess.run([CLI, "--version"], capture_output=True, text=True).stdout.strip()
# The release gate sets this: a CLI too old for a skill is a failure there, not a skip.
STRICT = os.environ.get("ARTEMIS_CLI_STRICT") == "1"
have = version_tuple(version)
# A build from source reports 0.1.0 and has everything on main, so it checks every skill.
if have and have[0] == 0:
    have = None

failures, checked, skipped = [], [], []
for skill in sorted(SKILLS.iterdir()):
    need = cli_min(skill)
    if have and need and have < need:
        if STRICT:
            failures.append(f"{skill.name}: needs CLI {'.'.join(map(str, need))}, the CLI checked is {version}")
        else:
            print(f"SKIP {skill.name}: needs CLI {'.'.join(map(str, need))}, checking against {version}")
            skipped.append(skill.name)
            continue
    for f in sorted(skill.rglob("*.md")):
        for cmd in set(commands(f.read_text())):
            checked.append(cmd)
            for flag in check(cmd):
                failures.append(f"{f.relative_to(SKILLS)}: {flag} unknown in: {cmd[:90]}")

for f in sorted(set(failures)):
    print("FAIL", f)
note = f" ({len(skipped)} skills skipped: they need a newer CLI)" if skipped else ""
print(f"{len(checked)} commands checked against {version}: {'OK' if not failures else str(len(set(failures))) + ' problems'}{note}")
sys.exit(1 if failures else 0)
