"""Fix in Discovery starts in one call from the board, so the skill teaches no agent turn and names each refusal's way out."""
import pathlib
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"


def fix_in_discovery():
    text = (SKILLS / "maintain/SKILL.md").read_text()
    start = text.index("### Fix in Discovery")
    return text[start:text.index("\n### ", start + 1)]


class FixInDiscovery(unittest.TestCase):
    def test_no_agent_turn(self):
        section = fix_in_discovery()
        for stale in ("--timeout", "question card", "chat answer", "exit 6"):
            self.assertNotIn(stale, section, f"Fix in Discovery still describes the agent turn ({stale})")
        self.assertIn("`Discovery Run ID`", section)
        self.assertIn("`discoveryRunId`", section)

    def test_each_refusal_has_a_way_out(self):
        section = fix_in_discovery()
        for remedy in ("`--script` or `--runner`", "stop it (§6)", "re-sync it (§8)", "drop it", "all from one project", "runner-setup"):
            self.assertIn(remedy, section)

    def test_ids_accept_uuids(self):
        text = (SKILLS / "maintain/SKILL.md").read_text()
        self.assertNotIn("the maintain agent reads only display ids", text)


if __name__ == "__main__":
    unittest.main()
