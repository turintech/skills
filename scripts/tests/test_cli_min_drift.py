"""check_cli.py fails a skill whose own or linked files use a command its declared minimum CLI lacks."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

CHECK = pathlib.Path(__file__).resolve().parents[1] / "check_cli.py"
ROOT_HELP = "Usage:\n  artemis [command]\n\nAvailable Commands:\n  project     Manage projects\n\nFlags:\n  -h, --help   help\n"
PROJECT_HELP = "Usage:\n  artemis project [command]\n\nAvailable Commands:\n  list        List projects\n\nFlags:\n  -h, --help   help\n"


class MinimumDrift(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        cli = self.root / "artemis"
        cli.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "--version" ]; then echo "Artemis CLI 1.1.14"; exit 0; fi\n'
            f'case " $* " in *" project "*) printf %s "{PROJECT_HELP}" ;; *) printf %s "{ROOT_HELP}" ;; esac\n')
        cli.chmod(0o755)
        self.cli = str(cli)
        self.skills = self.root / "skills"

    def skill(self, name, body, minimum="1.1.14"):
        folder = self.skills / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(f'---\nname: {name}\nmetadata:\n  artemis-cli-min: "{minimum}"\n---\n\n{body}\n')

    def run_check(self):
        env = {**os.environ, "ARTEMIS_SKILLS_DIR": str(self.skills), "ARTEMIS_CLI_STRICT": ""}
        return subprocess.run([sys.executable, str(CHECK), self.cli], capture_output=True, text=True, env=env)

    def test_a_command_newer_than_the_minimum_fails_even_with_a_fallback_named(self):
        self.skill("uses-get", "Read it with `artemis project get <id>` (CLI 1.1.16+), or `artemis project list` before.")
        r = self.run_check()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FAIL uses-get (uses-get/SKILL.md): command 'project get' unknown", r.stdout)

    def test_a_linked_file_in_another_skill_counts_against_the_linking_skill(self):
        self.skill("owner", "See the reference.", minimum="1.1.16")
        (self.skills / "owner/REF.md").write_text("Run `artemis project get <id>`.\n")
        self.skill("linker", "Follow [the reference](../owner/REF.md#part).")
        r = self.run_check()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FAIL linker (owner/REF.md): command 'project get' unknown", r.stdout)
        self.assertIn("SKIP owner: needs CLI 1.1.16", r.stdout)

    def test_commands_the_minimum_has_pass(self):
        self.skill("lists", "Run `artemis project list`.")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
