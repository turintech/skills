"""cli-setup's cli_meets_min: a release by its number, a dev build by the day the minimum was published."""
import pathlib
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills/cli-setup/SKILL.md"


def copies():
    """Every cli_meets_min definition in the skill, as written."""
    return re.findall(r"^cli_meets_min\(\) \{.*?^\}$", SKILL.read_text(), re.S | re.M)


class CliMeetsMin(unittest.TestCase):
    def run_check(self, version, minimum="1.1.16", last_modified="Fri, 09 Oct 2026 07:30:24 GMT"):
        """Run the skill's function with a curl that answers HEAD with `last_modified`, or fails when it is None."""
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        curl = pathlib.Path(folder) / "curl"
        log = pathlib.Path(folder) / "curl.log"
        answer = "exit 22" if last_modified is None else f"printf 'HTTP/2 200\\r\\nlast-modified: {last_modified}\\r\\n\\r\\n'"
        curl.write_text(f'#!/bin/sh\necho "$@" >> {log}\n{answer}\n')
        curl.chmod(curl.stat().st_mode | stat.S_IEXEC)
        script = copies()[0] + f'\ncli_meets_min "Artemis CLI {version}" "{minimum}"\n'
        out = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                             env={"PATH": f"{folder}:/usr/bin:/bin"}).stdout.strip()
        return out, log.read_text() if log.exists() else ""

    def test_both_copies_are_the_same(self):
        found = copies()
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0], found[1])

    def test_releases_compare_by_number(self):
        self.assertEqual(self.run_check("1.1.16")[0], "ok")
        self.assertEqual(self.run_check("1.1.17")[0], "ok")
        self.assertEqual(self.run_check("1.1.15")[0], "old")

    def test_a_dev_build_from_on_or_after_the_release_day_passes(self):
        out, log = self.run_check("dev-20261012-102045-33c18ce4")
        self.assertEqual(out, "ok")
        self.assertIn("/public/artemis-cli/1.1.16/checksums.txt", log)
        self.assertEqual(self.run_check("dev-20261009-000000-aaaaaaa")[0], "ok")

    def test_a_dev_build_from_before_the_release_is_old(self):
        self.assertEqual(self.run_check("dev-20260929-091931-f61e0c7")[0], "old")

    def test_an_unreadable_release_date_is_unknown(self):
        self.assertEqual(self.run_check("dev-20261012-102045-33c18ce4", last_modified=None)[0], "unknown")


if __name__ == "__main__":
    unittest.main()
