#!/usr/bin/env python3
"""Check that section and skill references in the skills resolve."""
import pathlib
import re
import sys

SKILLS = pathlib.Path(__file__).resolve().parent.parent / "plugins/artemis/skills"
names = sorted(d.name for d in SKILLS.iterdir() if (d / "SKILL.md").is_file())
texts = {n: (SKILLS / n / "SKILL.md").read_text() for n in names}
sections = {n: set(re.findall(r"^#{2,3} (\d+[a-z]?)\.", t, re.M)) for n, t in texts.items()}

NUM = r"\d+[a-z]?"
REF = re.compile(
    rf"(?:`([a-z][a-z0-9-]+)`(?:'s)?,?\s+)?(?:§\s?|\b[Ss]ections?\s+)({NUM}(?:(?:,\s*|,?\s+(?:and|or|to)\s+){NUM})*)"
)
NAMED = re.compile(r"`([a-z][a-z0-9-]+)`'s \*([^*]+)\*")

failures = []
for name, text in texts.items():
    for line_no, line in enumerate(text.splitlines(), 1):
        where = f"{name}/SKILL.md:{line_no}"
        for m in REF.finditer(line):
            target = m.group(1) if m.group(1) in texts else name
            if m.group(1) and m.group(1) not in texts and not line[m.start():m.end()].startswith("`artemis"):
                # A backticked word before "section" that is not a skill, e.g. a command: check this file.
                target = name
            for num in re.findall(NUM, m.group(2)):
                if num not in sections[target]:
                    failures.append(f"{where}: section {num} not found in {target}")
        for m in NAMED.finditer(line):
            skill, label = m.groups()
            if skill not in texts:
                failures.append(f"{where}: `{skill}` is not a skill")
            elif label.lower() not in texts[skill].replace(m.group(0), "").lower():
                failures.append(f"{where}: *{label}* not found in {skill}")

for f in failures:
    print("FAIL", f)
sys.exit(1 if failures else 0)
