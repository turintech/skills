"""Fix in Discovery starts in one call from the board, so the skill teaches no agent turn and names each refusal's way out."""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"


def maintain():
    return (SKILLS / "maintain/SKILL.md").read_text()


def section_checklist():
    text = maintain()
    return text[text.index("## Checklist"):]


def fix_in_discovery():
    text = maintain()
    start = text.index("### Fix in Discovery")
    return text[start:text.index("\n### ", start + 1)]


# Each refusal the board or CLI can give, and the way out the skill must name after it.
REFUSALS = (("(422)", "`--script` or `--runner`"), ("A fix already running", "wait for it"), ("`outdated`", "re-sync it (§8)"), ("`obsolete`", "drop it"), ("Archived or dismissed", "`unarchive`"), ("Any other reason", "the CLI's words"), ("offline-runner warning", "`runner-setup`"), ("the project's own runner", "`artemis runner list`"), ("unknown `--runner` name", "fix the name or the ids"), ("A 422 that names neither", "the CLI's words"))


class FixInDiscovery(unittest.TestCase):
    def test_no_agent_turn(self):
        section = fix_in_discovery()
        for stale in ("--timeout", "question card", "chat answer", "exit 6"):
            self.assertNotIn(stale, section, f"Fix in Discovery still describes the agent turn ({stale})")
        for fact in ("`Discovery Run ID`", "`discoveryRunId`", "10 versions", "`--focus`", "`in_progress`",
                     "/discover/<run-id>`", "`Status: closed`", "`--model`"):
            self.assertIn(fact, section)

    def test_each_refusal_has_a_way_out(self):
        section = fix_in_discovery()
        self.assertIn("Then run the rest again", section[section.index("(409"):])
        for refusal, remedy in REFUSALS:
            self.assertIn(refusal, section)
            start = section.index(refusal)
            # The remedy belongs to this refusal: it sits in the same sentence or the one after, before the next refusal's.
            later = [section.index(r, start + 1) for r, _ in REFUSALS if r != refusal and r in section[start + 1:]]
            following = section[start:min(later, default=len(section))]
            self.assertIn(remedy, following, f"{refusal} has no way out after it")

    def test_a_running_discovery_fix_is_cancelled_by_its_run(self):
        section = fix_in_discovery()
        self.assertIn("`artemis discovery cancel <run-id>`", section)
        self.assertIn("`artemis discovery cancel <run-id>`, which stops it for every Issue in that run and moves them back to `triaged`", section)
        self.assertRegex(section, r"(?m)^- A fix already running \(also a 409\): wait for it")
        # isActive marks the latest attempt, which may be the fix agent's: no discovery run id then.
        self.assertIn("jq -r '.runs[] | select(.isActive and .discoveryRunId)", section)
        self.assertNotIn("select(.isActive) |", section)
        stop = next((line for line in maintain().splitlines() if "artemis maintain issues cancel" in line), None)
        self.assertIsNotNone(stop, "the fix agent's Stop line is gone")
        self.assertIn("Fix in Discovery", stop, "the Stop line no longer sends a Fix in Discovery to its run")

    def test_the_start_and_its_checks(self):
        section = fix_in_discovery()
        for fact in ("each Issue is confirmed", "takes the project's own settings", "Up to 5 Issues per run, all from one project",
                     "a 400 (an id that isn't an Issue, or Issues from two projects)",
                     "archived (`Status: closed`), out of date or obsolete (`Sync Status`) or already being fixed (`Fix Status` `pending` or `in_progress`) refuses the call",
                     "read its name from `artemis project get <p>` (its default runner) and check `artemis runner list` shows it online"):
            self.assertIn(fact, section)
        self.assertIn("(§6; a Fix in Discovery by cancelling its run)", maintain())
        self.assertIn("`issues cancel`, `discovery cancel` and `rules delete`", section_checklist())
        for fact in ("the `Web UI` lines the command prints are the Issues' pages", "the board's endpoint has no switch for them",
                     "use `--execution-mode skip` only if the user agreed to an unmeasured run"):
            self.assertIn(fact, section)

    def test_section_refs_name_real_headings(self):
        for number in re.findall(r"§(\d+)", maintain()):
            self.assertRegex(maintain(), rf"\n## {number}\. ", f"§{number} names no heading")

    def test_ids(self):
        text = maintain()
        self.assertNotIn("the maintain agent reads only display ids", text)
        self.assertNotIn("`-p` is also needed when `--script` is a name", text)
        ids = next(line for line in text.splitlines() if line.startswith("**Ids.**"))
        self.assertIn("accepts a UUID", ids)
        self.assertIn("a `--script` name is looked up in the Issues' own project", text)
        self.assertIn("need `-p` either way", ids)
        # 1.1.16 and 1.1.17 refuse -p on a plain `fix`; 1.1.18 (artemis-cli #256) takes it. The caveat goes with the min bump.
        minimum = tuple(int(n) for n in re.search(r'artemis-cli-min: "([\d.]+)"', text).group(1).split("."))
        if minimum < (1, 1, 18):
            self.assertIn("a plain `fix` from CLI 1.1.18", ids)
        else:
            self.assertNotIn("from CLI 1.1.18", ids, "artemis-cli-min is past 1.1.18, so drop the caveat")
        self.assertIn("artemis maintain issues fix <issue-id>...", text)


if __name__ == "__main__":
    unittest.main()
