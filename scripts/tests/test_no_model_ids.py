"""Skills name no model: each deployment's catalogue differs, so the CLI's listing decides."""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"
MODEL_ID = re.compile(
    r"\b(?:gpt|claude|gemini|o\d|qwen\d*|llama|mistral|deepseek|grok)-[\w.-]*\d[\w.-]*", re.I
)


class NoModelIds(unittest.TestCase):
    def test_no_skill_hard_codes_a_model_id(self):
        found = [
            f"{path.relative_to(SKILLS)}:{n}: {m.group()}"
            for path in sorted(SKILLS.rglob("*.md"))
            for n, line in enumerate(path.read_text().splitlines(), 1)
            for m in MODEL_ID.finditer(line)
        ]
        self.assertEqual(found, [], "use `artemis model list` instead of naming a model")


if __name__ == "__main__":
    unittest.main()
