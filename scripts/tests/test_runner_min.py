"""A reused runner must be new enough for the platform: older runners 404 on every validation."""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"


def skill(name):
    return (SKILLS / name / "SKILL.md").read_text()


def runner_min():
    match = re.search(r'^  artemis-runner-min: "(\d+)\.(\d+)\.(\d+)"$', skill("runner-setup"), re.M)
    return tuple(int(part) for part in match.groups()) if match else None


class RunnerMinimum(unittest.TestCase):
    def test_runner_setup_declares_a_minimum_the_platform_accepts(self):
        self.assertIsNotNone(runner_min(), "runner-setup declares no artemis-runner-min")
        self.assertGreaterEqual(runner_min(), (5, 3, 0), "runners before 5.3.0 404 on validation")

    def test_runner_setup_checks_the_version_before_reusing_a_runner(self):
        section = skill("runner-setup").split("## Whose runner is that?")[1].split("\n## ")[0]
        self.assertIn("artemis-runner-min", section)
        self.assertIn("--version", section)
        self.assertIn("*Update or restart*", section)

    def test_quickstart_reuses_only_a_runner_at_the_minimum(self):
        row = next(line for line in skill("quickstart").splitlines() if line.startswith("| Runner |"))
        self.assertIn("artemis-runner-min", row)


if __name__ == "__main__":
    unittest.main()
