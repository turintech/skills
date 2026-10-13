"""quickstart asks the credits question at step 7, before it hands the demo run to discovery-start."""
import pathlib
import unittest

QUICKSTART = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills/quickstart/SKILL.md"
QUESTION = '"Setup is done. Start the Particle Life run now? It uses account credits."'


class CreditsGate(unittest.TestCase):
    def test_step_7_asks_before_handing_over_to_discovery_start(self):
        text = QUICKSTART.read_text()
        gate, handover = text.find("**Credits check, for the demo"), text.find("**Then hand these to `discovery-start`:**")
        self.assertTrue(0 <= gate < handover, "the credits check must come before the handover")
        self.assertIn(QUESTION, text[gate:handover])
        self.assertIn(QUESTION, text[: text.find("## 7.")], "section 6 asks the same question")


if __name__ == "__main__":
    unittest.main()
