"""Every skill declares a CLI ceiling (exclusive), cli-setup warns at or above it, and the check enforces min < max."""
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS = ROOT / "plugins/artemis/skills"


def below_max(version, maximum="1.2.0"):
    text = (SKILLS / "cli-setup/SKILL.md").read_text()
    function = re.search(r"^cli_below_max\(\) \{.*?^\}$", text, re.S | re.M).group(0)
    script = function + f'\ncli_below_max "Artemis CLI {version}" "{maximum}"\n'
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout.strip()


class CliCeiling(unittest.TestCase):
    def test_every_skill_declares_the_ceiling(self):
        for path in sorted(SKILLS.glob("*/SKILL.md")):
            text = path.read_text()
            self.assertIn('\n  artemis-cli-max: "1.2.0"\n', text, path.parent.name)
            sentence = re.search(r"^compatibility: (.*)$", text, re.M).group(1)
            if "Requires Artemis CLI" in sentence:
                self.assertRegex(sentence, r"Requires Artemis CLI [0-9.]+\+ \(below 1\.2\.0\)", path.parent.name)

    def test_cli_below_max_compares_releases_and_passes_dev_builds(self):
        self.assertEqual(below_max("1.1.18"), "ok")
        self.assertEqual(below_max("1.2.0"), "above")
        self.assertEqual(below_max("1.2.1"), "above")
        self.assertEqual(below_max("1.10.0"), "above")
        self.assertEqual(below_max("dev-20261012-102045-33c18ce4"), "ok")

    def test_the_ceiling_is_one_rule_in_cli_setup_that_quickstart_points_to(self):
        rule = (SKILLS / "cli-setup/SKILL.md").read_text()
        self.assertIn("**The ceiling.**", rule)
        self.assertIn("`above` is a warning, not a stop", rule)
        self.assertIn("`cli-setup`'s *The ceiling*", (SKILLS / "quickstart/SKILL.md").read_text())

    def check_skills_with(self, old, new):
        """Run check-skills.sh on a copy of the repository with one front-matter line changed."""
        root = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        for part in ("plugins", "scripts"):
            shutil.copytree(ROOT / part, root / part)
        skill = root / "plugins/artemis/skills/maintain/SKILL.md"
        skill.write_text(skill.read_text().replace(old, new, 1))
        return subprocess.run(["bash", str(root / "scripts/check-skills.sh")], capture_output=True, text=True,
                              env={"PATH": "/usr/bin:/bin"})

    def test_check_skills_requires_the_ceiling(self):
        r = self.check_skills_with('  artemis-cli-max: "1.2.0"\n', "")
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL maintain: missing metadata.artemis-cli-max", r.stdout)

    def test_check_skills_requires_min_below_max(self):
        r = self.check_skills_with('artemis-cli-max: "1.2.0"', 'artemis-cli-max: "1.1.16"')
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL maintain: artemis-cli-min 1.1.16 is not below artemis-cli-max 1.1.16", r.stdout)


if __name__ == "__main__":
    unittest.main()
