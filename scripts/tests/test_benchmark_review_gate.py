"""discovery-start blocks a Discovery until the benchmark review has passed, and benchmark-review owns the reviewer."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS = ROOT / "plugins/artemis/skills"


def section(text, heading):
    start = text.index(heading)
    end = text.find("\n## ", start + 1)
    return text[start:end if end != -1 else len(text)]


class BenchmarkReviewGate(unittest.TestCase):
    def test_discovery_start_requires_a_passed_review(self):
        requirements = section((SKILLS / "discovery-start/SKILL.md").read_text(), "## Requirements")
        self.assertIn("HARNESS.md#pre-discovery-benchmark-review) passed", requirements)
        self.assertIn("anything else blocks", requirements)
        self.assertIn("`benchmark-review`", requirements)

    def test_the_review_writes_the_line_discovery_start_reads(self):
        text = (SKILLS / "repo-command-setup/HARNESS.md").read_text()
        self.assertIn("## Pre-Discovery benchmark review", text)
        self.assertIn("`Benchmark review passed <date>", text)
        self.assertIn("`benchmark-review`'s verdict is passed or reused", text)

    def test_the_harness_review_hands_the_reviewer_to_benchmark_review(self):
        review = section((SKILLS / "repo-command-setup/HARNESS.md").read_text(), "## Pre-Discovery benchmark review")
        self.assertRegex(review, r"10\. \*\*Independent review\.\*\* Hand off to `benchmark-review`")
        self.assertNotIn("Hack list", (SKILLS / "repo-command-setup/ADVANCED.md").read_text())


class BenchmarkReviewSkill(unittest.TestCase):
    text = (SKILLS / "benchmark-review/SKILL.md").read_text()

    def test_the_hack_list_covers_the_attacks_that_won_user_tests(self):
        hacks = section(self.text, "## 3. Brief the reviewer")
        for item in ("in-process and on-disk caches", "work deferred past the timer",
                     "fast paths outside the scored size range", "quality tuned to sit just above the floor",
                     "dropping rare classes or outputs", "more cores or memory than the baseline used"):
            self.assertIn(item, hacks)
        self.assertIn("never skips one or cuts the pass short", hacks)

    def test_floors_need_a_margin_unrebuildable_inputs_and_every_class(self):
        floors = section(self.text, "## 2. Check the floors")
        for rule in ("**Margin.**", "**Inputs the code cannot rebuild.**", "**Every class stays.**"):
            self.assertIn(rule, floors)

    def test_a_blocked_reviewer_keeps_the_review_open(self):
        blocked = section(self.text, "## 5. When the reviewer cannot run")
        self.assertIn("The review then stays open; never record it as passed", blocked)
        self.assertIn("Use the Artemis benchmark-review skill on <checkout path>", blocked)

    def test_reuse_needs_the_same_pinned_manifest(self):
        reuse = section(self.text, "## 1. Reuse an unchanged review")
        self.assertIn("names the manifest sha256 pinned in this Script's benchmark command", reuse)
        self.assertIn("sha256sum -c --quiet bench/manifest.sha256", reuse)

    def test_the_router_and_readme_name_it(self):
        router = section((SKILLS / "artemis/SKILL.md").read_text(), "## 6. Route to the owning skill")
        self.assertIn("`benchmark-review`", router)
        self.assertIn("| `benchmark-review` |", (ROOT / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()
