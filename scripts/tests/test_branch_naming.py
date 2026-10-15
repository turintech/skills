"""Prose says "branch", as the Web UI does; `changeset` stays only in commands, ids and JSON keys."""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"
# The one glossary line that maps the two names, and the label older deployments showed.
ALLOWED = ("the CLI calls it a **changeset**", "the changeset's Validations tab")


def prose_lines(path):
    fenced = False
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            yield number, re.sub(r"<[^>]*>", "", re.sub(r"`[^`]*`", "", line)), line


class BranchNaming(unittest.TestCase):
    def test_prose_says_branch_not_changeset(self):
        found = [
            f"{path.relative_to(SKILLS)}:{number}"
            for path in sorted(SKILLS.rglob("*.md"))
            for number, prose, line in prose_lines(path)
            if re.search(r"\bchangesets?\b", prose, re.I) and not any(a in line for a in ALLOWED)
        ]
        self.assertEqual(found, [], "prose says changeset where the Web UI says Branch")


if __name__ == "__main__":
    unittest.main()
