#!/usr/bin/env python3
"""Report where each skill could be shorter. Informational: never fails.

For each skill: its size, its largest sections, and sentences it shares with
other skills (a fact written in two places should live in one).
"""
import collections
import pathlib
import re

SKILLS = pathlib.Path(__file__).resolve().parent.parent / "plugins/artemis/skills"
names = sorted(d.name for d in SKILLS.iterdir() if (d / "SKILL.md").is_file())
texts = {n: (SKILLS / n / "SKILL.md").read_text() for n in names}


def prose(text):
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    return re.sub(r"```.*?```", "", text, flags=re.S)


def sentences(text):
    for s in re.split(r"(?<=[.!?])\s+|\n", prose(text)):
        s = re.sub(r"[`*|>#-]", "", s).strip().lower()
        if len(s.split()) >= 8:
            yield re.sub(r"\s+", " ", s)


owners = collections.defaultdict(set)
for n, t in texts.items():
    for s in sentences(t):
        owners[s].add(n)

rows = []
for n, t in texts.items():
    words = len(t.split())
    code = sum(len(b.split()) for b in re.findall(r"```.*?```", t, re.S))
    parts = re.split(r"^(#{2,3} .+)$", t, flags=re.M)
    secs = sorted(((len(body.split()), head.strip("# ").strip()) for head, body in zip(parts[1::2], parts[2::2])), reverse=True)
    shared = sorted(s for s in set(sentences(t)) if len(owners[s]) > 1)
    rows.append((words, n, code, secs[:3], shared))

print(f"{'skill':<22}{'words':>7}{'code':>6}  largest sections")
for words, n, code, secs, shared in sorted(rows, reverse=True):
    top = ", ".join(f"{h[:28]} ({w})" for w, h in secs)
    print(f"{n:<22}{words:>7}{code:>6}  {top}")
print()
for words, n, code, secs, shared in sorted(rows, reverse=True):
    for s in shared:
        others = ", ".join(sorted(owners[s] - {n}))
        print(f"{n}: also in {others}: {s[:110]}")
