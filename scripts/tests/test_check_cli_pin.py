"""check_cli_pin.py checks the skills' CLI range against the CI pin and against the CLI production runs."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CHECK = ROOT / "scripts/check_cli_pin.py"


class PinnedCli(unittest.TestCase):
    def setUp(self):
        self.skills = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.skills)
        for name, low in (("old", "1.1.8"), ("new", "1.1.16")):
            (self.skills / name).mkdir()
            (self.skills / name / "SKILL.md").write_text(
                f'---\nname: {name}\nmetadata:\n  artemis-cli-min: "{low}"\n  artemis-cli-max: "1.2.0"\n---\n')

    def run_check(self, *args, strict="", actions=""):
        env = {**os.environ, "ARTEMIS_SKILLS_DIR": str(self.skills), "ARTEMIS_CLI_FLOOR_STRICT": strict,
               "GITHUB_ACTIONS": actions}
        return subprocess.run([sys.executable, str(CHECK), *args], capture_output=True, text=True, env=env)

    def run_production(self, version, strict="1", actions=""):
        floor = self.skills / "production-cli-version"
        floor.write_text(version + "\n")
        return self.run_check("--production", str(floor), strict=strict, actions=actions)

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

    def test_a_minimum_above_the_production_cli_fails_in_strict_mode(self):
        r = self.run_production("1.1.15")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FAIL new: artemis-cli-min 1.1.16 is above 1.1.15, the CLI production runs", r.stdout)
        self.assertNotIn("old:", r.stdout)

    def test_a_minimum_equal_to_or_below_the_production_cli_passes(self):
        for version in ("1.1.16", "1.1.18"):
            with self.subTest(version):
                r = self.run_production(version)
                self.assertEqual(r.returncode, 0, r.stdout)
                self.assertIn(f"OK: no skill needs a CLI newer than {version}", r.stdout)

    def test_outside_strict_mode_a_minimum_above_the_production_cli_only_warns(self):
        r = self.run_production("1.1.15", strict="")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("WARN new: artemis-cli-min 1.1.16 is above 1.1.15", r.stdout)
        self.assertNotIn("::warning::", r.stdout)

    def test_on_github_actions_the_warning_is_a_pr_annotation(self):
        r = self.run_production("1.1.15", strict="", actions="true")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("::warning::WARN new: artemis-cli-min 1.1.16 is above 1.1.15", r.stdout)
        strict = self.run_production("1.1.15", actions="true")
        self.assertNotIn("::warning::", strict.stdout)

    def test_a_production_file_without_one_exact_version_fails(self):
        for text in ("", "latest", "1.1"):
            with self.subTest(text):
                r = self.run_production(text)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("must hold one X.Y.Z version", r.stderr)

    def test_a_missing_production_file_fails_cleanly(self):
        missing = self.skills / "no-such-file"
        r = self.run_check("--production", str(missing), strict="1")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"FAIL {missing} missing: the CLI version production runs", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_ci_is_strict_about_the_production_cli_only_for_main(self):
        workflow = (ROOT / ".github/workflows/check-skills.yml").read_text()
        self.assertIn("types: [opened, synchronize, reopened, edited]", workflow)
        self.assertIn("ARTEMIS_CLI_FLOOR_STRICT: ${{ (github.base_ref || github.ref_name) == 'main' && '1' || '' }}", workflow)
        self.assertIn('check_cli_pin.py" --production "$ROOT/.github/production-cli-version" || fail=1',
                      (ROOT / "scripts/check-skills.sh").read_text())


if __name__ == "__main__":
    unittest.main()
