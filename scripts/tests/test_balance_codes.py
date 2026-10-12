"""Skills never ask a user to pay for the model provider's empty account."""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"


def paragraphs():
    """Every paragraph or list item in the skills' Markdown, with where it is."""
    for path in sorted(SKILLS.rglob("*.md")):
        for block in re.split(r"\n\s*\n|\n(?=\s*[-*] )", path.read_text()):
            yield path.relative_to(SKILLS), block


class BalanceCodes(unittest.TestCase):
    def test_top_up_advice_tells_the_provider_code_apart(self):
        # ERR_LLM_PROVIDER_INSUFFICIENT_BALANCE contains INSUFFICIENT_BALANCE, but it is the
        # provider's account: the backend says consumers must not prompt for payment on it.
        for where, text in paragraphs():
            if "INSUFFICIENT_BALANCE" in text and re.search(r"top up|balance at the bottom", text):
                self.assertIn("ERR_LLM_PROVIDER_INSUFFICIENT_BALANCE", text,
                              f"{where}: top-up advice on INSUFFICIENT_BALANCE without the provider's code")
                self.assertRegex(text, r"never ask the user to pay",
                                 f"{where}: the provider's code must say not to ask the user to pay")


if __name__ == "__main__":
    unittest.main()
