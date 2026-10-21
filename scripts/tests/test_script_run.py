"""`script-run` owns running a Script on a branch, and `artemis/references/waiting.md` owns starting and waiting."""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"
WAITING = SKILLS / "artemis/references/waiting.md"
CALLERS = ("quickstart/SKILL.md", "repo-command-setup/SKILL.md", "runner-setup/SKILL.md",
           "change-validate/SKILL.md", "discovery-start/FAST_TRACK.md", "discovery-start/SKILL.md")


def skill_files():
    return sorted(SKILLS.rglob("*.md"))


class ScriptRun(unittest.TestCase):
    def test_the_router_sends_validation_to_script_run(self):
        routes = (SKILLS / "artemis/SKILL.md").read_text().split("## 6. Route to the owning skill", 1)[1]
        self.assertIn("(the Validation workflow): `script-run`", routes)
        self.assertNotIn("and validation: `repo-command-setup`", routes)

    def test_the_start_takes_the_version_the_caller_chose(self):
        # A hardcoded `original` would measure the starting commit on both sides of a comparison.
        self.assertIn('--version "<version>"', (SKILLS / "script-run/SKILL.md").read_text())

    def test_the_loop_ends_on_a_validation_s_end_states(self):
        text = (SKILLS / "script-run/SKILL.md").read_text()
        self.assertIn('case "$s" in success|failed|cancelled) break ;; esac', text)

    def test_values_fall_back_to_the_logs_and_a_series_posts_one_block(self):
        text = (SKILLS / "script-run/SKILL.md").read_text()
        self.assertIn("read the values in the logs as below", text)
        self.assertIn("read them in the logs, after `artemis_results.json content:`", text)
        self.assertIn("the caller posts one block at its start; skip it here", text)

    def test_both_blocks_are_run_as_written(self):
        # Agents that retyped the loop, or rebuilt it by filtering the skill file, waited on the wrong word.
        self.assertIn("Run this block and §3's loop as written, filling in only the `<...>` values; "
                      "never retype them or rebuild them by filtering this file", (SKILLS / "script-run/SKILL.md").read_text())

    def test_callers_hand_the_run_to_script_run(self):
        for name in CALLERS:
            self.assertIn("`script-run`", (SKILLS / name).read_text(), name)

    def test_only_script_run_carries_the_validation_loop(self):
        loops = [p.relative_to(SKILLS).as_posix() for p in skill_files()
                 if re.search(r"for i in \$\(seq \d+\); do\n\s+out=\$\(artemis [^\n]*changeset validation get", p.read_text())]
        self.assertEqual(loops, ["script-run/SKILL.md"])
        word = [p.relative_to(SKILLS).as_posix() for p in skill_files() if "a Discovery run's word" in p.read_text()]
        self.assertEqual(word, ["script-run/SKILL.md"], "the `success`, not `completed` rule lives in one place")

    def test_no_validation_waits_with_wait(self):
        found = [f"{p.relative_to(SKILLS)}: {line.strip()[:80]}" for p in skill_files()
                 for line in p.read_text().replace("\\\n", " ").splitlines()
                 if re.search(r"artemis [^`]*changeset validate [^`]*--wait", line)]
        self.assertEqual(found, [], "a validation that times out under --wait loses its id")


class Waiting(unittest.TestCase):
    text = WAITING.read_text()

    def test_one_page_holds_the_start_block_the_lines_and_the_limit(self):
        for heading in ("## Start block", "## Waiting out loud", "## Bounded waits"):
            self.assertIn(heading, self.text)
        self.assertIn("at most 16 checks (8 minutes)", self.text)
        self.assertIn("10-minute shell timeout", self.text)
        self.assertIn("the CLI exits without printing the validation's id", self.text)
        self.assertIn("leave out `· LLM council …` when no review models were passed", self.text)
        self.assertFalse((SKILLS / "artemis/references/start-block.md").exists())

    def test_callers_read_it_by_path_not_by_copy(self):
        anchors = {re.sub(r"[^a-z0-9 -]", "", h.lower()).replace(" ", "-") for h in re.findall(r"^#+ (.+)$", self.text, re.M)}
        for p in skill_files():
            text = p.read_text()
            self.assertNotIn("`artemis`'s *Start block*", text, p)
            self.assertNotIn("carried here because", text, p)
            for target, anchor in re.findall(r"\]\(([^)#]*waiting\.md)(?:#([^)]+))?\)", text):
                self.assertEqual((p.parent / target).resolve(), WAITING.resolve(), p)
                if anchor:
                    self.assertIn(anchor, anchors, f"{p}: #{anchor}")


if __name__ == "__main__":
    unittest.main()
