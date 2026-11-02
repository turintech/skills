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
        # A comment in a command block is prose too, whole-line or after a command; the commands are not.
        if fenced and not line.lstrip().startswith("#"):
            parts = re.split(r"\s#\s", line, maxsplit=1)
            if len(parts) < 2:
                continue
            line = parts[1]
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

    def test_both_fix_labels_go_together(self):
        # Every released CLI prints `Changeset ID`; only the CLI wording change prints `Branch ID`, for the same id.
        lines = [line for path in sorted(SKILLS.rglob("*.md")) for line in path.read_text().splitlines() if "`Branch ID`" in line]
        self.assertTrue(lines, "no skill names the `Branch ID` newer CLIs print")
        for line in lines:
            self.assertIn("`Changeset ID`", line, "a skill names `Branch ID` without the `Changeset ID` every release prints")

    def test_glossary_keeps_changeset_for_commands_and_json(self):
        glossary = next((line for line in (SKILLS / "maintain/SKILL.md").read_text().splitlines() if "the CLI calls it a **changeset**" in line), None)
        self.assertIsNotNone(glossary, "maintain's Branch/changeset glossary line is gone")
        self.assertIn("`changesetId`", glossary)

    def test_no_skill_says_original_code(self):
        found = [str(path.relative_to(SKILLS)) for path in sorted(SKILLS.rglob("*.md"))
                 if re.search(r"\boriginal code\b", path.read_text(), re.I)]
        self.assertEqual(found, [], "a skill says original code where the Web UI says starting commit (a Branch) or baseline (a run)")

    def test_version_original_is_the_starting_commit(self):
        lines = [line for line in (SKILLS / "repo-command-setup/SKILL.md").read_text().splitlines() if "`--version original`" in line and "resolves" in line]
        self.assertTrue(lines)
        for line in lines:
            self.assertIn("starting commit", line)

    def test_discovery_start_wait_names_an_adopted_baseline(self):
        text = (SKILLS / "discovery-start/SKILL.md").read_text()
        wait = [line for line in text.splitlines() if "*Waiting out loud*" in line and "metricsSchema" in line]
        self.assertTrue(wait, "discovery-start's baseline wait is gone")
        self.assertIn("the baseline", wait[0])
        self.assertIn("adopted", wait[0])

if __name__ == "__main__":
    unittest.main()
