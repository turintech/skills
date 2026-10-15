"""Starting a Discovery run never waits on a credits yes: users know runs spend credits."""
import pathlib
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"


def skill(name):
    return (SKILLS / name / "SKILL.md").read_text()


def section(text, heading):
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start:end if end != -1 else None]


class NoCreditGates(unittest.TestCase):
    def test_discovery_start_dispatches_without_a_credits_question(self):
        text = skill("discovery-start")
        dispatch = text[text.index("Before the command that dispatches the agent"):text.index("```bash\nartemis --output-format json discovery create")]
        self.assertNotRegex(dispatch.lower(), r"credit", "discovery-start asks about credits before dispatching")
        self.assertNotRegex(section(text, "## Checklist").lower(), r"credit", "discovery-start's checklist gates on credits")

    def test_quickstart_hands_the_demo_over_without_a_credits_question(self):
        text = skill("quickstart")
        for heading in ("## 6. Rules for this flow", "## Checklist"):
            self.assertNotRegex(section(text, heading).lower(), r"credit", f"quickstart {heading} gates on credits")
        self.assertRegex(text, r"for the demo, that these settings are fixed, so `discovery-start` does not ask")


if __name__ == "__main__":
    unittest.main()
