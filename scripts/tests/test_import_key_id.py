"""project-import passes only a key id that `key list` returned, and stops when there is none."""
import pathlib
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"


class ImportKeyId(unittest.TestCase):
    def test_no_placeholder_key_id_and_no_import_without_a_key(self):
        text = (SKILLS / "project-import/SKILL.md").read_text()
        credential = text[text.index("## 3. Select a Git credential"):text.index("## 4. Import once")]
        self.assertIn("`--key-id` takes only a UUID that `key list` returned", credential)
        self.assertIn("Never pass a placeholder or made-up value", credential)
        self.assertIn("If `key list` is still empty after the user has tried a route above, stop", credential)


if __name__ == "__main__":
    unittest.main()
