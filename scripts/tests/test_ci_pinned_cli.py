"""CI checks the skills only against exact CLI releases, each verified by its checksum: never latest/ or the newest listed."""
import pathlib
import re
import unittest

import yaml

WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/check-skills.yml"


class PinnedCliInCi(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text()
        self.job = yaml.safe_load(self.text)["jobs"]["check"]

    def test_the_pin_is_one_exact_release(self):
        self.assertRegex(str(self.job["env"]["ARTEMIS_CLI_PINNED"]), r"^\d+\.\d+\.\d+$")

    def test_no_moving_version(self):
        self.assertNotIn("artemis-cli/latest", self.text)
        self.assertIsNone(re.search(r"sort -uV \| tail", self.text), "picks whatever release is newest")

    def test_every_cli_download_is_checked_against_its_checksums(self):
        for step in self.job["steps"]:
            run = step.get("run", "")
            if "artemis-cli-linux-amd64" in run and "curl" in run:
                self.assertIn("checksums.txt", run, step["name"])
                self.assertIn("sha256sum -c", run, step["name"])


if __name__ == "__main__":
    unittest.main()
