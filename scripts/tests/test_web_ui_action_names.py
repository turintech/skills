"""Skills name a Maintain action the way the Web UI does: False positive, never dismiss."""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"


class WebUiActionNames(unittest.TestCase):
    def test_no_skill_says_dismiss(self):
        for path in sorted(SKILLS.rglob("*.md")):
            for n, line in enumerate(path.read_text().splitlines(), 1):
                with self.subTest(f"{path.relative_to(SKILLS)}:{n}"):
                    self.assertIsNone(re.search(r"\bdismiss", line, re.I), line)

    def test_maintain_names_the_false_positive_command(self):
        text = (SKILLS / "maintain/SKILL.md").read_text()
        self.assertIn("artemis maintain issues false-positive <id>...", text)


if __name__ == "__main__":
    unittest.main()
