"""Skills that run code pick the user's own runner, never any runner that happens to be online."""
import pathlib
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"


class OwnRunner(unittest.TestCase):
    def test_change_validate_uses_the_users_own_runner(self):
        requirements = (SKILLS / "change-validate/SKILL.md").read_text().split("## Requirements")[1].split("\n## ")[0]
        self.assertIn("*Whose runner is that?*", requirements)
        self.assertNotIn("An online runner: `artemis runner list`.", requirements)


if __name__ == "__main__":
    unittest.main()
