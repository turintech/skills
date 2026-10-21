"""discovery-start blocks a Discovery until the benchmark review has passed."""
import pathlib
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"


class BenchmarkReviewGate(unittest.TestCase):
    def test_discovery_start_requires_a_passed_review(self):
        text = (SKILLS / "discovery-start/SKILL.md").read_text()
        requirements = text[text.index("## Requirements"):text.index("\n## ", text.index("## Requirements") + 1)]
        self.assertIn("HARNESS.md#pre-discovery-benchmark-review) passed", requirements)
        self.assertIn("anything else blocks", requirements)

    def test_the_review_writes_the_line_discovery_start_reads(self):
        text = (SKILLS / "repo-command-setup/HARNESS.md").read_text()
        self.assertIn("## Pre-Discovery benchmark review", text)
        self.assertIn("`Benchmark review passed <date>", text)


if __name__ == "__main__":
    unittest.main()
