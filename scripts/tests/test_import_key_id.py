"""project-import passes only a key id that `key list` returned, and stops when there is none."""
import pathlib
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"
TEXT = (SKILLS / "project-import/SKILL.md").read_text()


class ImportKeyId(unittest.TestCase):
    def test_no_placeholder_key_id_and_no_import_without_a_key(self):
        credential = TEXT[TEXT.index("## 3. Select a Git credential"):TEXT.index("## 4. Import once")]
        self.assertIn("`--key-id` takes only a UUID that `key list` returned", credential)
        # The placeholders agents passed in user tests, named so they are recognised.
        self.assertIn("Never pass a placeholder or made-up value such as `<key-uuid>` or `UNKNOWN-KEY`", credential)
        self.assertIn("If `key list` still has no key that can read the repository after the user has tried "
                      "the routes above, including the demo's fallback, do not import", credential)
        self.assertIn('ask them to say "done" once one is saved, then re-run `artemis key list`', credential)
        self.assertIn("return to any calling skill without a project UUID", credential)

    def test_the_checklist_carries_the_key_id_rule(self):
        checklist = TEXT[TEXT.index("## Checklist"):]
        self.assertIn("`--key-id` is a UUID from `key list`, never a placeholder", checklist)


if __name__ == "__main__":
    unittest.main()
