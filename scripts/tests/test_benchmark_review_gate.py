"""discovery-start blocks a Discovery until the benchmark review has passed, and benchmark-review owns the reviewer."""
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS = ROOT / "plugins/artemis/skills"


def section(text, title):
    """The `## ` section with this title, numbered or not."""
    match = re.search(rf"^## (?:\d+\. )?{re.escape(title)}$", text, re.M)
    assert match, f"no section titled {title!r}"
    start = match.start()
    end = text.find("\n## ", start + 1)
    return text[start:end if end != -1 else len(text)]


class BenchmarkReviewGate(unittest.TestCase):
    def test_discovery_start_requires_a_passed_review(self):
        requirements = section((SKILLS / "discovery-start/SKILL.md").read_text(), "Requirements")
        self.assertRegex(requirements, r"(?m)^- For a run that scores the benchmark \(`--execution-mode benchmark`, the default; `test` and `skip` score none\), its \[pre-Discovery benchmark review\]\(\.\./repo-command-setup/HARNESS\.md#pre-discovery-benchmark-review\) passed")
        self.assertIn("the latest review line naming the manifest sha256 its benchmark command pins says passed", requirements)
        self.assertIn("names the holdout and verdict", requirements)
        self.assertIn("anything else blocks", requirements)
        checklist = section((SKILLS / "discovery-start/SKILL.md").read_text(), "Checklist")
        self.assertIn("For a run that scores the benchmark, the Script's review line for its pinned manifest says passed", checklist)
        self.assertIn("Once the baseline has finalized (section 2), set the tiers", requirements)
        self.assertIn("`discovery metrics-schema set <run-id> --file <schema.json>`", requirements)
        self.assertIn("Finish a missing or open review with `repo-command-setup`'s benchmark review", requirements)
        self.assertIn("The file replaces the whole schema, so start from the run's own", (SKILLS / "discovery-start/SKILL.md").read_text())
        self.assertIn("match each entry's `metricId` to its name with `artemis --output-format json discovery metrics \"<run_id>\" --all`", (SKILLS / "discovery-start/SKILL.md").read_text())

    def test_fix_in_discovery_needs_the_same_review(self):
        text = (SKILLS / "maintain/SKILL.md").read_text()
        self.assertIn("except for Fix in Discovery; one that scores the benchmark needs its script's benchmark review passed, as `discovery-start` requires", text)
        self.assertIn("For a Fix in Discovery that scores the benchmark, its script's review line for its pinned manifest says passed", section(text, "Checklist"))

    def test_the_review_writes_the_line_discovery_start_reads(self):
        text = (SKILLS / "repo-command-setup/HARNESS.md").read_text()
        self.assertRegex(text, r"`Benchmark review passed <date> at <harness gitHash>: holdout <holdout-script-id>, manifest <sha256>, reviewer <verdict>`")
        self.assertIn("`benchmark-review`'s verdict is passed or reused", text)
        # Reuse picks the latest line naming the manifest, so an open line must name it too.
        self.assertIn("`Benchmark review open <date>: steps <n>, manifest <sha256>` and do not start a Discovery", text)
        self.assertIn("The review passes only when every step passed", text)
        self.assertIn("record each step in `bench/REVIEW.md` as it finishes", text)

    def test_the_steps_other_skills_cite_keep_their_numbers(self):
        review = section((SKILLS / "repo-command-setup/HARNESS.md").read_text(), "Pre-Discovery benchmark review")
        steps = dict(re.findall(r"(?m)^(\d+)\. \*\*(.+?)\.?\*\*", review))
        self.assertEqual(len(steps), 11)
        for n, title in (("1", "Objective and floors"), ("5", "Isolate, verify apart, time from outside"), ("3", "Fresh, varied input every scored run"), ("6", "Tamper guard"), ("9", "Baseline and noise"),
                         ("10", "Independent review"), ("11", "Scoring tiers")):
            self.assertEqual(steps[n], title)

    def test_the_unlisted_files_guard_runs(self):
        advanced = (SKILLS / "repo-command-setup/ADVANCED.md").read_text()
        line = next(l for l in advanced.splitlines() if l.startswith("- **Unlisted files:**"))
        guard = " && ".join(re.findall(r"`([^`]*(?:find|for f in)[^`]*)`", line))
        self.assertEqual(guard.count("`"), 0)
        self.assertEqual(len(re.findall(r"find |for f in", guard)), 3)
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            for f in ("bench/h.py", "tests/test_a.py"):
                (root / f).parent.mkdir(exist_ok=True)
                (root / f).write_text("x = 1\n")
            (root / "bench/REVIEW.md").write_text("review\n")
            (root / "pytest.ini").write_text("")
            writer = re.search(r"^- \*\*Write the manifest\*\*.*?: `([^`]+)`", advanced, re.M)[1]
            subprocess.run(["sh", "-c", writer], cwd=root, check=True)
            subprocess.run(["sh", "-c", writer], cwd=root, check=True)  # a rewrite must not list the old manifest
            listed = (root / "bench/manifest.sha256").read_text()
            self.assertEqual([line[66:] for line in listed.splitlines()], ["bench/h.py", "pytest.ini", "tests/test_a.py"])
            guard = 'sha256sum -c --quiet bench/manifest.sha256 && ' + guard
            (root / "tests/__pycache__").mkdir()
            (root / "tests/__pycache__/test_a.cpython-310.pyc").write_text("cache")
            run = lambda: subprocess.run(["sh", "-c", guard], cwd=root).returncode
            self.assertEqual(run(), 0, "a clean harness with bytecode caches fails the guard")
            self.assertFalse((root / "tests/__pycache__").exists(), "a planted bytecode cache survives the guard")
            for new in ("tests/conftest.py", "tox.ini", "pytest.toml", ".pytest.toml"):
                (root / new).write_text("")
                self.assertNotEqual(run(), 0, f"a new {new} passes the guard")
                (root / new).unlink()
            (root / "pytest.ini").write_text("[pytest]\naddopts = --co\n")
            self.assertNotEqual(run(), 0, "an edited pytest.ini passes the guard")
            (root / "pytest.ini").write_text("")
            self.assertEqual(run(), 0)
            (root / "src").mkdir()
            (root / "src/evil.py").write_text("")
            (root / "tests/conftest.py").symlink_to("../src/evil.py")
            self.assertNotEqual(run(), 0, "a symlinked conftest.py passes the guard")

    def test_the_manifest_hash_is_pinned_outside_the_repo(self):
        review = section((SKILLS / "repo-command-setup/HARNESS.md").read_text(), "Pre-Discovery benchmark review")
        self.assertIn("pin its own hash in the Script's test and benchmark commands, which the repo cannot change, in front of each", review)
        self.assertIn("keep build outputs, generated inputs and working directories outside them", review)
        self.assertIn("tests inside the package also need every `conftest.py` and pytest config file from the root down to them listed and checked", review)
        self.assertIn('echo "<sha256>  bench/manifest.sha256" | sha256sum -c --quiet - && sha256sum -c --quiet bench/manifest.sha256 || exit 1', review)
        self.assertIn("Also fail on any file in those directories the manifest does not list", review)
        self.assertIn("the test runner's config (for pytest, a root `pytest.ini`, which overrides any pytest settings in `pyproject.toml`, `setup.cfg` or `tox.ini`, and a root `conftest.py`; the guard also fails on a new `pytest.toml` or `.pytest.toml`)", review)
        self.assertIn("With no user data, the holdout is a seed range or generator parameters", review)
        advanced = (SKILLS / "repo-command-setup/ADVANCED.md").read_text()
        self.assertIn("- **Unlisted files:**", advanced)
        self.assertIn("for f in conftest.py pytest.toml .pytest.toml pytest.ini tox.ini;", advanced)
        self.assertIn("With pytest, write a root `pytest.ini` even if empty", advanced)
        self.assertIn("time it from outside (review step 5); never score timings it prints",
                      (SKILLS / "repo-command-setup/HARNESS.md").read_text())

    def test_only_a_calling_skill_with_a_known_good_benchmark_skips_it(self):
        self.assertIn("only a calling skill with a known-good benchmark, such as the demo's, may.",
                      (SKILLS / "repo-command-setup/SKILL.md").read_text())
        self.assertIn("tell it to skip its own verification and its benchmark review, since the demo's benchmark is known-good",
                      (SKILLS / "quickstart/SKILL.md").read_text())

    def test_the_harness_review_hands_the_reviewer_to_benchmark_review(self):
        review = section((SKILLS / "repo-command-setup/HARNESS.md").read_text(), "Pre-Discovery benchmark review")
        self.assertRegex(review, r"10\. \*\*Independent review\.\*\* Hand off to `benchmark-review`")
        self.assertNotIn("Hack list", (SKILLS / "repo-command-setup/ADVANCED.md").read_text())
        self.assertIn("../benchmark-review/SKILL.md#2-check-the-floors", review)
        self.assertRegex((SKILLS / "benchmark-review/SKILL.md").read_text(), r"(?m)^## 2\. Check the floors$")


class BenchmarkReviewSkill(unittest.TestCase):
    text = (SKILLS / "benchmark-review/SKILL.md").read_text()

    def test_the_hack_list_covers_the_attacks_that_won_user_tests(self):
        hacks = section(self.text, "Brief the reviewer")
        items = re.findall(r"(?m)^- (.+?)[;.]$", hacks.split("Hack list:", 1)[1])
        self.assertEqual(items, [
            "in-process and on-disk caches",
            "answers keyed on the input's name, size, shape or hash",
            "reading the repo's models, data or references",
            "work deferred past the timer (lazy results, import time)",
            "fast paths for the benchmark's exact shapes",
            "fast paths outside the scored size range",
            "parsing or validation fitted to the generator, looser on input the gate lacks",
            "tuning to the inputs the benchmark scores rather than the user's data",
            "quality tuned to sit just above the floor",
            "dropping rare classes or outputs",
            "more cores or memory than the baseline used",
            "a process that outlives the gate and rewrites the results",
            "state shared between outputs or repetitions",
            "empty or NaN output",
        ])
        self.assertIn("Complete one full pass", hacks)
        self.assertIn("Never read the floor set or holdout", hacks)
        self.assertIn("A pass that skips an item or ends early is not complete", hacks)

    def test_floors_need_a_margin_unrebuildable_inputs_and_every_class(self):
        floors = section(self.text, "Check the floors")
        for rule in ("**Margin.**", "**Inputs the code cannot rebuild.**", "**Every class stays.**"):
            self.assertIn(rule, floors)

    def test_a_blocked_reviewer_keeps_the_review_open(self):
        blocked = section(self.text, "When the reviewer cannot run")
        self.assertIn("never record it as passed", blocked)
        self.assertIn("Use the Artemis benchmark-review skill on <checkout path>", blocked)
        self.assertIn("is the separate reviewer", blocked)

    def test_a_second_round_needs_a_reviewer_that_did_not_fix(self):
        second = section(self.text, "Fix, then a second round")
        self.assertIn("never the one that fixed it", second)
        self.assertIn("one the time box cuts short is `open: reviewer did not complete`", second)
        self.assertIn("the second round needs another subagent", section(self.text, "When the reviewer cannot run"))

    def test_the_floor_set_is_not_the_holdout(self):
        self.assertIn("It is separate from the holdout", section(self.text, "Check the floors"))

    def test_missing_or_early_open_reviews_go_to_the_harness_review(self):
        self.assertIn("A missing review, or one open on steps 1-9, goes to `repo-command-setup`", section(self.text, "At a glance"))

    def test_reuse_needs_the_same_pinned_manifest(self):
        reuse = section(self.text, "Reuse an unchanged review")
        self.assertIn("the latest review line (by date, then the later line) naming the manifest sha256 this Script's benchmark command pins says passed", reuse)
        self.assertIn('echo "<pinned sha256>  bench/manifest.sha256" | sha256sum -c --quiet -', reuse)
        self.assertIn("this Script's own guard passes in the checkout", reuse)
        self.assertIn("the objective and floors in `bench/REVIEW.md` equal those recorded beside that passed verdict", reuse)

    def test_its_verdicts_are_the_ones_the_harness_line_accepts(self):
        verdict = section(self.text, "Verdict")
        for value in ("- `passed`: a complete pass found no win, or a complete round after the fixes found none;", "- `reused <date>`:", "- `open: <reason>`:", "`Benchmark review open <date>: steps 1,10, manifest <sha256>`",
                      "Then finish HARNESS step 11 (scoring tiers)",
                      "`steps 10, manifest <sha256>` otherwise"):
            self.assertIn(value, verdict)

    def test_both_skills_write_the_same_open_line(self):
        harness = (SKILLS / "repo-command-setup/HARNESS.md").read_text()
        template = re.search(r"`(Benchmark review open <date>: steps )<n>(, manifest <sha256>)`", harness)
        assert template, "no open-line template in HARNESS.md"
        self.assertIn(f"`{template[1]}1,10{template[2]}`", self.text)

    def test_smaller_tiers_take_the_full_tiers_review(self):
        tiers = section((SKILLS / "repo-command-setup/HARNESS.md").read_text(), "Long benchmarks: small, medium and full tiers")
        self.assertIn("Review the full tier", tiers)
        self.assertIn("smaller Fast-track tiers take the full tier's review", section(self.text, "Reuse an unchanged review"))
        self.assertIn("or for a smaller Fast-track tier the full tier's Script", section(self.text, "Reuse an unchanged review"))

    def test_the_router_and_readme_name_it(self):
        router = section((SKILLS / "artemis/SKILL.md").read_text(), "Route to the owning skill")
        self.assertIn("`benchmark-review`", router)
        readiness = (SKILLS / "artemis/SKILL.md").read_text()
        self.assertIn("| Benchmark review | For a Discovery that scores the benchmark, the Script's latest review line for its pinned manifest says passed, unless a calling skill supplied a known-good benchmark | `repo-command-setup`, then `benchmark-review`", readiness)
        self.assertIn("| `benchmark-review` |", (ROOT / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()
