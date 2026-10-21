"""maintain owns the Maintain board chart and draws it with discovery-visualize's kit by path."""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"
REPORT = SKILLS / "maintain/references/board-report.md"


def frontmatter_description(name):
    text = (SKILLS / name / "SKILL.md").read_text()
    return re.search(r"^description: (.*)$", text, re.M).group(1)


class MaintainBoardReport(unittest.TestCase):
    def test_maintain_reads_the_board_report_when_it_summarises(self):
        board = (SKILLS / "maintain/SKILL.md").read_text().split("## 4. Read the board", 1)[1].split("\n## ", 1)[0]
        self.assertIn("without being asked, draw the board's chart", board)
        self.assertIn("(references/board-report.md)", board)
        self.assertTrue(REPORT.is_file())

    def test_discovery_visualize_no_longer_owns_it(self):
        self.assertFalse((SKILLS / "discovery-visualize/references/maintain-report.md").exists())
        self.assertNotIn("Maintain", frontmatter_description("discovery-visualize"))
        self.assertNotIn("maintain-report.md", (SKILLS / "discovery-visualize/SKILL.md").read_text())

    def test_maintain_claims_the_chart(self):
        self.assertIn("chart or graph the Maintain board", frontmatter_description("maintain"))
        self.assertIn("publish or chart code-health issues", (SKILLS / "artemis/SKILL.md").read_text())

    def test_each_skill_points_at_the_other(self):
        self.assertIn("Use `maintain` to chart a project's Maintain issues.", (SKILLS / "discovery-visualize/SKILL.md").read_text())
        self.assertIn("The board chart also needs `discovery-visualize` installed beside this skill", (SKILLS / "maintain/SKILL.md").read_text())

    def test_the_kit_paths_resolve_from_maintain(self):
        text = REPORT.read_text()
        self.assertIn('KIT="<maintain-dir>/../discovery-visualize/scripts"', text)
        maintain = SKILLS / "maintain"
        for script in ("build_report.py", "check_report.py"):
            self.assertTrue((maintain / "../discovery-visualize/scripts" / script).resolve().is_file(), script)
        for link, anchor in re.findall(r"\]\((\.\./[^)#]+)(?:#([^)]+))?\)", text):
            target = (REPORT.parent / link).resolve()
            self.assertTrue(target.is_file(), link)
            if anchor:
                slugs = {re.sub(r"[^a-z0-9 -]", "", h.lower()).replace(" ", "-")
                         for h in re.findall(r"^#{1,6} (.+)$", target.read_text(), re.M)}
                self.assertIn(anchor, slugs, link + "#" + anchor)

    def test_a_missing_kit_falls_back_to_text(self):
        self.assertIn("answer in text and say the chart needs `discovery-visualize` installed too", REPORT.read_text())


if __name__ == "__main__":
    unittest.main()
