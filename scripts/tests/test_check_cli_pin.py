"""check_cli_pin.py passes a pinned CLI inside the skills' range and fails one outside it."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

CHECK = pathlib.Path(__file__).resolve().parents[1] / "check_cli_pin.py"


class PinnedCli(unittest.TestCase):
    def setUp(self):
        self.skills = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.skills)
        for name, low in (("old", "1.1.8"), ("new", "1.1.16")):
            (self.skills / name).mkdir()
            (self.skills / name / "SKILL.md").write_text(
                f'---\nname: {name}\nmetadata:\n  artemis-cli-min: "{low}"\n  artemis-cli-max: "1.2.0"\n---\n')

    def run_check(self, pin):
        env = {**os.environ, "ARTEMIS_SKILLS_DIR": str(self.skills)}
        return subprocess.run([sys.executable, str(CHECK), pin], capture_output=True, text=True, env=env)

    def test_a_pin_from_the_highest_minimum_up_to_the_ceiling_passes(self):
        for pin in ("1.1.16", "1.1.18", "1.1.99"):
            with self.subTest(pin):
                r = self.run_check(pin)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_pin_below_a_minimum_or_at_the_ceiling_fails(self):
        for pin in ("1.1.15", "1.0.11", "1.2.0", "1.10.0"):
            with self.subTest(pin):
                r = self.run_check(pin)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("outside the skills' range: 1.1.16 up to, not including, 1.2.0", r.stderr)


if __name__ == "__main__":
    unittest.main()
