"""check_cli.py against a CLI older than the skills need: a skip normally, a failure in the release gate."""
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

CHECK = pathlib.Path(__file__).resolve().parents[1] / "check_cli.py"


def fake_cli(test, version):
    """An `artemis` that reports `version` and lists no commands, removed after the test."""
    folder = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, folder)
    path = pathlib.Path(folder) / "artemis"
    path.write_text(f'#!/bin/sh\nif [ "$1" = "--version" ]; then echo "Artemis CLI {version}"; else echo "Usage:\n  artemis [command]"; fi\n')
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def run(cli, strict):
    env = {**os.environ, "ARTEMIS_CLI_STRICT": "1" if strict else ""}
    return subprocess.run([sys.executable, str(CHECK), cli], capture_output=True, text=True, env=env)


class TooOldCli(unittest.TestCase):
    def test_skills_needing_a_newer_cli_are_skipped_by_default(self):
        r = run(fake_cli(self, "1.0.11"), strict=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("SKIP quickstart: needs CLI", r.stdout)
        self.assertIn("skills skipped: they need a newer CLI", r.stdout)

    def test_the_release_gate_fails_instead_of_skipping(self):
        r = run(fake_cli(self, "1.0.11"), strict=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FAIL quickstart: needs CLI", r.stdout)
        self.assertIn("the CLI checked is Artemis CLI 1.0.11", r.stdout)
        self.assertNotIn("SKIP", r.stdout)
        # The skills' commands are still checked, so missing flags are listed too.
        self.assertRegex(r.stdout, r"(?m)^[1-9]\d* commands checked")

    def test_a_source_build_is_never_too_old(self):
        r = run(fake_cli(self, "0.1.0"), strict=True)
        self.assertNotIn("needs CLI", r.stdout)
        self.assertIn("commands checked against Artemis CLI 0.1.0", r.stdout)


if __name__ == "__main__":
    unittest.main()
