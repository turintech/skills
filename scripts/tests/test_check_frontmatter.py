"""check_frontmatter.py fails a skill whose name or description is empty, as a skill loader would have nothing to show or match."""
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

CHECK = pathlib.Path(__file__).resolve().parents[1] / "check_frontmatter.py"


def check(test, front):
    """Run the check on one skill whose front matter is `front`."""
    folder = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, folder)
    skill = pathlib.Path(folder) / "demo"
    skill.mkdir()
    (skill / "SKILL.md").write_text(f"---\n{front}---\n\n# Demo\n")
    return subprocess.run([sys.executable, str(CHECK), folder], capture_output=True, text=True)


class EmptyFields(unittest.TestCase):
    def test_a_filled_name_and_description_pass(self):
        r = check(self, "name: demo\ndescription: Shows the check.\n")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_an_empty_or_blank_name_or_description_fails(self):
        cases = {
            "empty description": 'name: demo\ndescription: ""\n',
            "blank description": 'name: demo\ndescription: "   "\n',
            "empty name": 'name: ""\ndescription: Shows the check.\n',
            "blank name": "name: ' '\ndescription: Shows the check.\n",
        }
        for case, front in cases.items():
            with self.subTest(case):
                r = check(self, front)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("is empty", r.stdout)

    def test_a_missing_description_still_fails(self):
        r = check(self, "name: demo\n")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("needs a name and a description string", r.stdout)


class CliRange(unittest.TestCase):
    FRONT = 'name: demo\ndescription: Shows the check.\nmetadata:\n  artemis-cli-min: "{low}"\n  artemis-cli-max: "{high}"\n'

    def test_a_ceiling_above_the_floor_passes(self):
        r = check(self, self.FRONT.format(low="1.1.16", high="1.2.0"))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_a_ceiling_at_or_below_the_floor_fails(self):
        for high in ("1.1.16", "1.1.9", "1.0.0"):
            with self.subTest(high):
                r = check(self, self.FRONT.format(low="1.1.16", high=high))
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("must be above artemis-cli-min", r.stdout)


if __name__ == "__main__":
    unittest.main()
