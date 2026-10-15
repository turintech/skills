"""runner-setup finds the newest runner in its version folder, not among the older flat files."""
import pathlib
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills/runner-setup/SKILL.md"


class RunnerDownloadFolders(unittest.TestCase):
    def test_download_names_the_version_folders(self):
        text = SKILL.read_text()
        get = text[text.index("## Get the runner"):]
        self.assertIn(".../artemis-runner/<version>/<file>", get)
        self.assertIn("the newest flat file is not the newest version", get)


if __name__ == "__main__":
    unittest.main()
