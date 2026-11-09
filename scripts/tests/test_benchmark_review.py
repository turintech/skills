"""benchmark-review: an opt-in, few-minute review that shows what a benchmark measures and its gaps against the goal.

Each test pins a clause that carries a rule and, where a rule could be inverted next to it, scans for the inversion.
"""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"
REVIEW = SKILLS / "benchmark-review"

# Wording that would turn the review into a gate on Discovery.
GATE = re.compile(r"must wait|waits? (for|until)|until (this|the) (benchmark )?review passes|required before|"
                  r"blocks? (a |the )?(run|Discovery)|before every Discovery|review passed|readiness verdict", re.I)


def read(rel):
    return (SKILLS / rel).read_text(encoding="utf-8")


def section(text, pattern):
    """The body under the first `## ` heading matching pattern, up to the next `## ` heading."""
    m = re.search(rf"^## {pattern}.*$", text, re.M)
    if not m:
        raise AssertionError(f"no '## {pattern}' heading")
    return text[m.end():].split("\n## ", 1)[0]


def skill():
    return read("benchmark-review/SKILL.md")


def bullet(text, start):
    """The bullet or numbered item that starts with `start`, up to the next item at the same depth."""
    i = text.index(start)
    return re.split(r"\n\s*(?:- |\d+\. )", text[i:], maxsplit=1)[0]


class NeverAGate(unittest.TestCase):
    def test_on_request_only(self):
        self.assertIn("on request only", re.search(r"^description: (.*)$", skill(), re.M).group(1))
        self.assertIn("Never start it on your own, and never treat it as a gate: Discovery can always go ahead.", skill())
        self.assertIn("or from `discovery-inspect` after a suspicious result", skill())
        self.assertIn("start only on the user's yes", section(skill(), r"5\. Add complexity"))
        self.assertIn("- [ ] Started only because the user asked or said yes to an offer.", section(skill(), "Checklist"))
        self.assertNotRegex(skill(), r"(?i)sends the user here|or a (Discovery )?result looks? suspicious\.")

    def test_no_gate_wording_anywhere(self):
        texts = {p.name: p.read_text() for p in REVIEW.rglob("*.md")}
        texts["repo-command-setup §7"] = section(read("repo-command-setup/SKILL.md"), r"7\. Offer a benchmark review")
        texts["discovery-inspect"] = bullet(read("discovery-inspect/SKILL.md"),
                                            "- **A result that looks too good is a benchmark question.**")
        for name, text in texts.items():
            m = GATE.search(text)
            self.assertIsNone(m, f"{name}: {m.group(0) if m else ''}")

    def test_discovery_start_and_quickstart_do_not_route_through_it(self):
        for rel in ("discovery-start/SKILL.md", "quickstart/SKILL.md"):
            self.assertNotIn("benchmark-review", read(rel), rel)

    def test_a_winning_cheat_is_the_users_decision(self):
        step = skill().split("5. **Three quick checks", 1)[1].split("\n## ", 1)[0]
        self.assertIn("a cheat that passes with a better metric always does", step)
        self.assertIn("It is still the user's decision: Discovery can go ahead.", step)
        self.assertIn("- [ ] Discovery never blocked.", section(skill(), "Checklist"))


class Offer(unittest.TestCase):
    def offer(self):
        return section(read("repo-command-setup/SKILL.md"), r"7\. Offer a benchmark review")

    def test_offered_in_passing(self):
        offer = self.offer()
        self.assertIn("Want me to review this benchmark against your goal before Discovery? It takes a few minutes.", offer)
        self.assertIn("in the reply that proposes the next step and before running it", offer)
        self.assertIn("offer it once per session", offer)
        self.assertIn("If the user's next message doesn't take it up, carry on", offer)
        self.assertIn("Discovery can always go ahead", offer)
        self.assertNotRegex(offer, r"(?i)wait for the answer|do not offer|never offer|skip this section")

    def test_skipped_only_when_the_caller_verifies_and_on_return(self):
        offer = self.offer()
        self.assertIn("Skip the offer when the caller verifies the commands itself or tells you to skip verification", offer)
        self.assertIn("on a return from `benchmark-review`", offer)
        self.assertIn("When the commands are verified and Discovery is next, `benchmark-review` offered at most once",
                      section(read("repo-command-setup/SKILL.md"), "Completion checklist"))

    def test_discovery_inspect_offers_it_on_a_suspicious_result(self):
        item = bullet(read("discovery-inspect/SKILL.md"), "- **A result that looks too good is a benchmark question.**")
        self.assertIn("offer `benchmark-review`", item)
        self.assertNotRegex(item, r"(?i)never offer|do not offer|ignore")
        self.assertIn("`discovery-inspect` offers this review", section(skill(), r"5\. Add complexity"))


class Quick(unittest.TestCase):
    def test_budget(self):
        quick = section(skill(), "Keep it quick")
        for phrase in ("under 5 minutes", "no subagents", "about 10 files or 2,000 lines"):
            self.assertIn(phrase, quick)
        self.assertIn("Don't start extra runs for it.", skill())

    def test_quick_checks_only_when_short_and_runnable_here(self):
        step = skill().split("5. **Three quick checks", 1)[1].split("\n## ", 1)[0]
        self.assertIn("build, test and benchmark together taking under a minute", step)
        self.assertIn("this machine has the toolchain those commands need", step)
        self.assertIn("Run the build, test and benchmark commands once on the untouched copy", step)
        self.assertIn("If it already fails", step)
        self.assertIn("undo the edit before the next", step)
        self.assertIn('"not checked by running"', step)

    def test_all_three_checks_stay(self):
        step = skill().split("5. **Three quick checks", 1)[1].split("\n## ", 1)[0]
        for name, rule in (("worse", "The metric must move the right way."),
                           ("wrong", "The correctness check must fail."),
                           ("cheat", "The gate must fail it")):
            item = bullet(step, f"- **{name}:**")
            self.assertIn(rule, item, name)
            self.assertNotRegex(item, r"(?i)optional|skip it", name)

    def test_only_tested_defences_are_credited(self):
        s = skill()
        self.assertIn("Credit a defence only when a check you ran shows it works.", s)
        self.assertIn('is "not tested"', s)
        self.assertIn("never tell the user it stops something", s)
        self.assertIn("No defence credited that a check didn't test", section(s, "Checklist"))

    def test_a_skipped_worse_check_leads_the_later_line(self):
        self.assertIn('put the "worse" check first on the "Later" line', section(skill(), r"1\. Read the benchmark"))
        self.assertIn('the "worse" check leads the Later line when skipped', section(skill(), "Checklist"))


class StartSimple(unittest.TestCase):
    def test_start_simple_recommends_the_simplest_option(self):
        body = section(skill(), "Start simple")
        self.assertIn("Recommend the simplest option that keeps the results trustworthy", body)
        self.assertIn('often "keep it as it is"', body)
        self.assertNotRegex(body, r"(?i)most thorough|never .keep it as it is")

    def test_decisions(self):
        decide = section(skill(), r"2\. Pick the decisions")
        self.assertIn("Turn at most the top 3 into decisions.", decide)
        self.assertIn("offer 2 or 3 concrete choices, simplest first", decide)
        self.assertIn("Name exactly one choice as recommended", decide)
        self.assertIn('That is "keep it as it is" whenever the gap can\'t make Discovery report a gain that isn\'t real.',
                      decide)
        self.assertNotRegex(decide, r"(?i)never recommend .keep it as it is|recommend the (most thorough|fullest)")

    def test_an_edit_guard_protects_what_measures_not_a_file_allowlist(self):
        after = section(skill(), r"4\. After the answer")
        self.assertIn("A guard against edits protects only what measures", after)
        self.assertIn("It never limits which other files a version may change", after)
        self.assertIn("an honest change anywhere in the code must still pass", after)
        self.assertNotRegex(after, r"(?i)outside the target|allowlist|only the target files|limits versions to")


class AfterTheAnswer(unittest.TestCase):
    def test_the_script_note_needs_a_yes(self):
        after = section(skill(), r"4\. After the answer")
        self.assertIn("ask whether to note the choices in its description. Only on yes", after)
        self.assertIn("ran on <runner, toolchain>", after)

    def test_recommended_changes_are_made(self):
        after = section(skill(), r"4\. After the answer")
        self.assertIn('- **Every choice is "keep it as it is":**', after)
        self.assertIn("- **Any choice that changes the benchmark, recommended or not", after)
        self.assertNotIn("- **The recommendations, or", after)

    def test_one_round(self):
        after = section(skill(), r"4\. After the answer")
        self.assertIn("Stop once the user has picked.", after)
        self.assertNotRegex(after, r"(?i)ask once more|ask again whether")


class Output(unittest.TestCase):
    def block(self):
        return section(skill(), r"3\. Show it and ask").split("```text\n", 1)[1].split("```", 1)[0]

    def example(self):
        return section(skill(), r"3\. Show it and ask").split("```text\n")[2].split("```", 1)[0]

    def test_a_filled_in_example(self):
        self.assertNotIn("<", self.example())
        self.assertTrue(self.example().startswith("Here's what this benchmark will measure for Discovery:"))
        decisions = re.findall(r"^\d+\. ", self.example(), re.M)
        self.assertEqual(self.example().count("Recommended:"), len(decisions))  # exactly one per decision
        self.assertIn("a) Keep it as it is", self.example())
        self.assertIn("- Timed: parsing the file already in memory; outside it:", self.example())
        # a cheat the example calls rejected needs a check that could reject it
        self.assertIn("a second one tools/gen.py makes from a fresh, logged seed", self.example())
        for line in ("For your goal (", "Later, if a result asks for it:", '"go with the recommendations"',
                     "anything else you want your benchmark to capture?"):
            self.assertIn(line, self.example(), line)

    def test_eight_measure_lines(self):
        labels = re.findall(r"^- ([A-Z][^:]+):", self.block().split("\n\n", 1)[1].split("\n\n", 1)[0], re.M)
        self.assertEqual(labels, ["Ranks versions by", "Timed", "Also measured", "Inputs", "Counts as correct",
                                  "Runs per version", "Discovery may change", "Checked by running"])

    def test_choices_against_the_goal_and_the_two_questions(self):
        block = self.block()
        self.assertIn("For your goal (<goal in one line>)", block)
        self.assertIn("a) Keep it as it is: <what that risks>", block)
        self.assertIn("Recommended: <letter>", block)
        self.assertIn('"go with the recommendations"', block)
        self.assertIn("anything else you want your benchmark to capture?", block)

    def test_plain_words(self):
        self.assertIn("Leave out checklist numbers, trait names, scores and statistics jargon.", skill())
        self.assertNotRegex(self.block(), r"(?i)p99|multiset|summarised|ranking metric")


class Harness(unittest.TestCase):
    def test_inputs_stay_deterministic(self):
        harness = read("repo-command-setup/HARNESS.md")
        self.assertIn("**deterministic, representative** inputs", harness)
        self.assertIn("Use deterministic, representative inputs read from files or a fixed, logged seed",
                      read("repo-command-setup/SKILL.md"))
        self.assertIn("fixed, logged seed", section(harness, "Rules that close common gaps"))
        sql = read("benchmark-review/references/sql.md")
        self.assertIn("Score a fixed parameter set generated from a logged seed", sql)
        self.assertNotIn("seed chosen at run time, not a list", sql)
        for name, text in (("sql.md", sql), ("traits.md", read("benchmark-review/references/traits.md")),
                           ("HARNESS rules", section(harness, "Rules that close common gaps"))):
            self.assertNotRegex(text, r"(?i)drawn at run time(?!.*logs?)|fresh data each repetition", name)
        self.assertIn("run the original and the version on a second set from a fresh seed it logs, so both see the same values", sql)
        self.assertNotIn("as `quickstart` does (it may offer", read("repo-command-setup/SKILL.md"))

    def test_gap_rules_are_not_default_steps(self):
        rules = section(read("repo-command-setup/HARNESS.md"), "Rules that close common gaps")
        self.assertIn("None of these is a default step: add one only when the user picks it in a review", rules)


class References(unittest.TestCase):
    def test_checklist_has_fourteen_rows_seven_first(self):
        rows = re.findall(r"^\| (\d+) \| [^|]+ \| (yes|no[^|]*) \|", read("benchmark-review/references/checklist.md"), re.M)
        self.assertEqual([int(n) for n, _ in rows], list(range(1, 15)))
        self.assertEqual([int(n) for n, first in rows if first == "yes"], list(range(1, 8)))

    def test_every_configuration_the_user_runs_is_a_case(self):
        rows = {m.group(1): m.group(0) for m in re.finditer(r"^\| (\d+) \|.*$", read("benchmark-review/references/checklist.md"), re.M)}
        self.assertIn("thread counts, precisions or flags", rows["3"])
        self.assertIn("a fast path for one configuration that slows another", rows["11"])
        self.assertIn("| 4 | Correct means the same results as the original | yes |", rows["4"])

    def test_traits_and_equivalence_rules(self):
        text = read("benchmark-review/references/traits.md")
        for t in range(1, 8):
            self.assertIn(f"| T{t} ", text)
        rules = section(text, "Equivalence rules")
        for rule in ("identical", "canonicalising", "tolerance", "statistically equivalent", "quality floor"):
            self.assertIn(rule, rules)

    def test_sql_path(self):
        text = read("benchmark-review/references/sql.md")
        for phrase in ("What may Discovery change", "Duplicates", "NULLs", "Plan stability", "prepared statements",
                       "Cold and warm are two metrics", "tested equivalent, not proven", "is never the gate"):
            self.assertIn(phrase.lower(), text.lower(), phrase)
        self.assertIn("The regime the user chose to rank by", text)
        header = re.search(r"^\| +\|(.*)\|$", section(text, r"7\. Engines"), re.M).group(1)
        self.assertEqual([c.strip() for c in header.split("|")], ["Postgres", "MySQL", "SQL Server", "SQLite", "DuckDB"])

    def test_every_link_and_anchor_resolves(self):
        def slugs(path):
            return {re.sub(r"[^a-z0-9 -]", "", h.lower()).replace(" ", "-")
                    for h in re.findall(r"^#+ (.+)$", path.read_text(), re.M)}
        for md in REVIEW.rglob("*.md"):
            for target, anchor in re.findall(r"\]\(([^)#\s]*\.md)?(?:#([^)\s]+))?\)", md.read_text()):
                if not target and not anchor:
                    continue
                path = (md.parent / target) if target else md
                self.assertTrue(path.is_file(), f"{md.name} -> {target}")
                if anchor:
                    self.assertIn(anchor, slugs(path), f"{md.name} -> {target}#{anchor}")


class Wiring(unittest.TestCase):
    def test_router(self):
        self.assertIn("Reviewing a benchmark on request", read("artemis/SKILL.md"))

    def test_readme_lists_it(self):
        self.assertIn("| `benchmark-review` | On request,", (SKILLS.parents[2] / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()
