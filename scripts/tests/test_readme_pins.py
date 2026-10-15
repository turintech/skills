"""The README pins the release the manifests declare, for every agent, Claude Code included."""
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class ReadmePins(unittest.TestCase):
    def test_every_pinned_tag_is_the_manifests_version(self):
        version = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())["metadata"]["version"]
        readme = (ROOT / "README.md").read_text()
        pins = r"(?:releases/tag/|--git-ref |--ref |--pin |skills@|\[)(v\d+\.\d+\.\d+)\b"
        tags = set(re.findall(pins, readme))
        self.assertEqual(tags, {f"v{version}"}, "README pins a tag other than the manifests' version")

    def test_claude_code_can_pin_the_release(self):
        readme = (ROOT / "README.md").read_text()
        self.assertRegex(readme, r"/plugin marketplace add turintech/skills@v\d+\.\d+\.\d+")
        self.assertRegex(readme, r"claude plugin marketplace add turintech/skills@v\d+\.\d+\.\d+")


if __name__ == "__main__":
    unittest.main()
