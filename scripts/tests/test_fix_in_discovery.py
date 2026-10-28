"""Fix in Discovery starts in one call from the board, so the skill teaches no agent turn and names each refusal's way out."""
import pathlib
import re
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

    def test_states_what_the_backend_does(self):
        section = fix_in_discovery()
        for fact in ("a budget of 10 versions", "(execution mode, script, runner, model, Benchmark runs)",
                     "once the `Discovery Run ID` prints", "about 5 minutes", "refuses the whole call (409",
                     "Then run the rest again", "Up to 5 Issues per run, all from one project", "(422)"):
            self.assertIn(fact, section)

    def test_each_refusal_has_a_way_out(self):
        section = fix_in_discovery()
        for remedy in ("`--script` or `--runner`", "`artemis discovery cancel <run-id>`", "`discoveryRunId` from `issues fix-runs`",
                       "wait for it", "re-sync it (§8)", "`unarchive` it", "dismissed as a false positive drop it", "runner-setup", "only if the user agreed to an unmeasured run"):
            self.assertIn(remedy, section)

    def test_section_refs_name_real_headings(self):
        text = (SKILLS / "maintain/SKILL.md").read_text()
        for number in re.findall(r"§(\d+)", fix_in_discovery()):
            self.assertRegex(text, rf"\n## {number}\. ", f"§{number} names no heading")

    def test_ids_accept_uuids(self):
        text = (SKILLS / "maintain/SKILL.md").read_text()
        self.assertNotIn("the maintain agent reads only display ids", text)
        self.assertIn("Every `issues` command accepts a UUID, or a display id", text)
        self.assertIn("`-p` is also needed when `--script` is a name", text)
        self.assertIn("artemis maintain issues fix <issue-id>...", text)

    def test_issues_cancel_points_a_discovery_fix_at_its_run(self):
        text = (SKILLS / "maintain/SKILL.md").read_text()
        self.assertIn("refuses a local attempt and a Fix in Discovery (cancel its run instead)", text)


if __name__ == "__main__":
    unittest.main()
