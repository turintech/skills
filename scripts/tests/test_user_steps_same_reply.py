"""A step the user must take is shown in the reply that announces it, never held for a later message."""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"


def skill(name):
    return (SKILLS / name / "SKILL.md").read_text()


class UserStepsSameReply(unittest.TestCase):
    def test_no_skill_sends_a_user_step_as_its_own_message(self):
        # "Send the step as its own message" made an agent end its turn after "the next message has the three steps".
        for path in sorted(SKILLS.rglob("*.md")):
            for n, line in enumerate(path.read_text().splitlines(), 1):
                self.assertNotRegex(line, r"(?i)\b(its|their) own message|separate message",
                                    f"{path.relative_to(SKILLS)}:{n}")

    def test_cli_setup_shows_the_login_boxes_in_the_same_reply(self):
        text = skill("cli-setup")
        start = text.index("## Authenticate")
        step = text[start:text.index("````text", start)]
        self.assertIn("in the same reply", step)
        self.assertIn("never end your turn before the user can see what they must do", step)
        # "Its own block" read as one fence merges box and command, and the command loses its copy button.
        self.assertIn("each fence exactly as shown and no text between them", step)

    def test_quickstart_shows_a_users_step_before_waiting(self):
        text = skill("quickstart")
        setup = text[text.index("## 5. Setup"):text.index("## 6.")]
        self.assertRegex(setup, r"show what they must do .* in the same reply, then wait")
        self.assertIn("in the same turn, ask the next step with the host's question tool", text)


if __name__ == "__main__":
    unittest.main()
