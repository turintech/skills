"""A built page reaches the user before its render check, and a check that can't run never stops the hand-over."""
import pathlib
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"
VISUALIZE = SKILLS / "discovery-visualize"


def between(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i + len(start))]


class PathBeforeCheck(unittest.TestCase):
    def assert_path_first(self, where, text, check):
        self.assertIn("path", text, where)
        self.assertLess(text.index("path"), text.index(check), f"{where}: the page's path comes after {check}")
        self.assertRegex(text, r"never stops the (flow|hand-over)", f"{where}: a skipped or blocked check must not stop the hand-over")

    def test_skill_step_6(self):
        skill = (VISUALIZE / "SKILL.md").read_text()
        self.assert_path_first("SKILL.md step 6", between(skill, "6. Build the page", "\n7. "), "`check_report.py`")

    def test_skill_studio_section(self):
        studio = between((VISUALIZE / "SKILL.md").read_text(), "## Interactive studio", "\n## ")
        bullets = studio[studio.index("Give the user the built page's path"):]
        self.assertLess(0, bullets.index("`check_report.py --studio` needs Chrome"), "the studio's path bullet comes before its check")
        self.assertIn("never stop before the page is published and handed over", bullets)

    def test_report_kit(self):
        kit = (VISUALIZE / "references/report-kit.md").read_text()
        self.assert_path_first("report-kit.md", between(kit, "Give the user the page's path", "\n\n"), "`check_report.py`")

    def test_maintain_board_report(self):
        board = (SKILLS / "maintain/references/board-report.md").read_text()
        self.assert_path_first("board-report.md", between(board, "Give the user the built page's path", "\n\n"), "Fix everything the checker reports")


if __name__ == "__main__":
    unittest.main()
