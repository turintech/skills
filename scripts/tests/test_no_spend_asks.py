"""Agent work the user asked for starts without a credits question; steer still asks how many versions to add."""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"
SPEND_GATE = re.compile(r"spends? credits|\bbefore credits\b", re.IGNORECASE)


def skill(name):
    return (SKILLS / name / "SKILL.md").read_text()


def section(text, heading):
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start:end if end != -1 else None]


class NoSpendAsks(unittest.TestCase):
    def test_maintain_runs_what_the_user_asked_for_without_a_credits_question(self):
        text = skill("maintain")
        self.assertNotRegex(text, SPEND_GATE, "maintain gates agent runs on credits")
        self.assertIn("without asking about credits", text)
        self.assertNotIn("after the user's yes:", text, "a Scan or Re-sync waits on a yes")

    def test_browser_skills_stop_for_plan_and_state_not_for_credits(self):
        for name in ("platform-tour", "cli-follow-along"):
            with self.subTest(name):
                text = skill(name)
                self.assertNotRegex(text, SPEND_GATE, f"{name} stops before a click because it spends credits")
                self.assertIn("no credits question", text)

    def test_quickstart_retries_a_model_failure_once_without_asking(self):
        row = next(line for line in section(skill("quickstart"), "## 10. ").splitlines() if "model error" in line)
        self.assertIn("start one fresh run", row)
        self.assertNotIn("yes", row, "the retry after a model failure waits on a yes")

    def test_steer_still_asks_how_many_versions_to_add(self):
        self.assertIn("ask how many versions to add", skill("discovery-steer"))


if __name__ == "__main__":
    unittest.main()
