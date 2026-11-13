"""benchmark-review: an opt-in, few-minute review that shows what a benchmark measures and its gaps against the goal.

Each rule is pinned by a short phrase that carries it, plus a scan for wording that would weaken or invert it,
so rewording a sentence keeps passing and turning a rule around fails.
"""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"
REVIEW = SKILLS / "benchmark-review"
README = SKILLS.parents[2] / "README.md"

# Wording that would turn the review into a gate on Discovery.
GATE = re.compile(
    r"must wait|\bwait(s|ing)? (for|until)\b|until (this|the) (benchmark )?review passes|required before|"
    r"blocks? (a |the )?(run|Discovery)|before (every|any|the first) Discovery|review passed|readiness verdict|"
    r"until .{0,60}review|do not (start|launch) Discovery|don't (start|launch) (a )?Discovery|"
    r"must (run|use) .?benchmark-review|run .?benchmark-review.? before|hold (off |the )?(on )?(Discovery|launch|run)|"
    r"only (then|after) .{0,40}Discovery|(create|start) the run until|until the benchmark has been reviewed|"
    r"need your answer before|until the goal is (settled|clear)|(let|allow) Discovery (start|go ahead) only|"
    r"(start|run) (this|the) review yourself|\byourself before\b|offer (it )?again|ask once more|"
    r"(always|automatically) before", re.I)

# Wording that would turn the on-request review into a default step.
NOT_ON_REQUEST = re.compile(r"(?i)\balways\b|automatically|\bbefore (the first|every|any)\b")

# Wording that would let the README or a guess stand in for the user's goal.
README_AS_GOAL = re.compile(
    r"(?i)\b(use|take|adopt|go with)\b[^.\n]{0,30}\bREADME|or (the|a) README|fall back to .{0,40}README|"
    r"README.{0,60}without asking|start from it|(answer|settle)s? (it|the question) when|most likely reading|"
    r"best guess|unless the README|README's\b(?![^.]{0,20}only when)")

# Wording that would let the review write to Artemis or start work outside the one note after a yes.
WRITES = re.compile(
    r"(?i)changeset (create|validate)\b|discovery (create|update)\b|metrics-schema set|scripts (create|update|delete)\b|"
    r"\b(start|run|launch|create) (one |a |another )?(new )?validation|\bvalidate (the |this )?Script\b|"
    r"\b(record|note|write|store|add|append|put|save)\b[^,.]{0,40}(Script's description|in its description)")

# Wording that would let the quick checks run where they shouldn't, or install or retry their way past a limit.
SHORTCUTS = re.compile(r"(?i)shared database is fine|clean it up|unless a smaller input|rerun with .?timeout|\binstall (it|the|a)\b")

# Wording that would turn the one round into several.
MORE_ROUNDS = re.compile(r"(?i)ask once more|ask again whether|second (review )?round|another round")

# Jargon the reply to the user must not carry.
JARGON = re.compile(r"(?i)p99|multiset|summarised|ranking metric|hard gate|eval run")

# Wording that would turn an edit guard into a list of files a version may change.
ALLOWLIST = re.compile(r"(?i)allowlist|only the target files|limits versions to|beyond (its|the|their) target files|"
                       r"outside (its|their) target files|are the write boundary|touched nothing")


def read(rel):
    return (SKILLS / rel).read_text(encoding="utf-8")


def section(text, pattern):
    """The body under the first `## ` heading matching pattern, up to the next `## ` heading."""
    m = re.search(rf"^## {pattern}.*$", text, re.M)
    if not m:
        raise AssertionError(f"no '## {pattern}' heading")
    return text[m.end():].split("\n## ", 1)[0]


def between(text, start, end=None):
    """The text after the first `start`, up to the first `end` after it; fails by name when either is missing."""
    if start not in text:
        raise AssertionError(f"missing {start!r}")
    rest = text.split(start, 1)[1]
    if end is None:
        return rest
    if end not in rest:
        raise AssertionError(f"missing {end!r} after {start!r}")
    return rest.split(end, 1)[0]


def first_line(text, test, what):
    """The first line passing `test`; fails by `what` rather than raising StopIteration."""
    line = next((l for l in text.splitlines() if test(l)), None)
    if line is None:
        raise AssertionError(f"missing {what}")
    return line


def must_search(pattern, text, flags=0):
    """re.search that fails by pattern rather than crashing on a None match."""
    m = re.search(pattern, text, flags)
    if not m:
        raise AssertionError(f"missing {pattern!r}")
    return m


def skill():
    return read("benchmark-review/SKILL.md")


def quick():
    return read("benchmark-review/references/quick-checks.md")


def step4():
    return between(skill(), "4. **Three quick checks**", "\n## ")


def bullet(text, start):
    """The bullet or numbered item that starts with `start`, up to the next item at the same depth."""
    return re.split(r"\n\s*(?:- |\d+\. )", start + between(text, start), maxsplit=1)[0]


def after():
    return section(skill(), r"6\. After the answer")


def offer():
    return section(read("repo-command-setup/SKILL.md"), r"7\. Offer a benchmark review")


def inspect_item():
    return bullet(read("discovery-inspect/SKILL.md"), "- **A result that looks too good is a benchmark question.**")


def router():
    return bullet(read("artemis/SKILL.md"), "- Reviewing a benchmark on request").strip()


def readme_row():
    return first_line(README.read_text(encoding="utf-8"), lambda l: "`benchmark-review`" in l, "README row for benchmark-review")


def bash_blocks(text):
    return re.findall(r"```bash\n(.*?)```", text, re.S)


class NeverAGate(unittest.TestCase):
    def test_on_request_only(self):
        self.assertIn("on request only", must_search(r"^description: (.*)$", skill(), re.M).group(1))
        glance = section(skill(), "At a glance")
        for rule in (r"never start it on your own", r"never treat it as a gate", r"Discovery can always go ahead"):
            self.assertRegex(glance, f"(?i){rule}")
        self.assertRegex(section(skill(), r"7\. Add complexity"), r"(?i)start only on the user's yes")
        self.assertRegex(section(skill(), "Checklist"), r"(?i)started only because the user asked or said yes")

    def test_no_gate_wording_anywhere(self):
        texts = {p.name: p.read_text(encoding="utf-8") for p in REVIEW.rglob("*.md")}
        texts.update({"repo-command-setup §7": offer(), "discovery-inspect": inspect_item(), "router": router(),
                      "README": readme_row()})
        for rel in ("repo-command-setup/SKILL.md", "repo-command-setup/HARNESS.md", "discovery-start/SKILL.md",
                    "quickstart/SKILL.md", "discovery-inspect/SKILL.md"):
            texts[rel] = "\n".join(l for l in read(rel).splitlines() if re.search(r"(?i)benchmark.review|(this|the) review", l))
        for name, text in texts.items():
            m = GATE.search(text)
            self.assertIsNone(m, f"{name}: {m.group(0) if m else ''}")

    def test_the_gate_scan_catches_common_gate_wording(self):
        for line in ("Don't start Discovery until the review is done.", "Run `benchmark-review` before Discovery.",
                     "You must run benchmark-review first.", "Hold Discovery until the user has picked.",
                     "Until they pick, hold the Discovery launch.", "Only then may Discovery be started.",
                     "If it has never been reviewed, start this review yourself before `discovery-start`.",
                     "On no, explain why it matters and offer again.", "ask once more before going on",
                     "Don't steer until the user has been through `benchmark-review`.",
                     "Discovery should wait until the user has picked.", "always before the first Discovery run"):
            self.assertRegex(line, GATE)

    def test_router_and_readme_stay_on_request(self):
        for name, text in (("router", router()), ("README", readme_row())):
            self.assertRegex(text, r"(?i)on request", name)
            self.assertNotRegex(text, NOT_ON_REQUEST, name)
        self.assertTrue(router().endswith(": `benchmark-review`"), router())

    def test_discovery_start_and_quickstart_do_not_route_through_it(self):
        for rel in ("discovery-start/SKILL.md", "quickstart/SKILL.md"):
            self.assertNotIn("benchmark-review", read(rel), rel)
            self.assertNotRegex(read(rel), r"(?i)until .{0,40}review|has been reviewed|review(ed)? (it )?(first|before)", rel)

    def test_writes_only_the_note_and_only_after_a_yes(self):
        a = after()
        note = between(a, "if a Script exists, ask once", "Stop once")
        self.assertRegex(note, r"Only on yes")
        # An empty description file would otherwise wipe the Script's description.
        self.assertIn("grep -q '[^[:space:]]'", note)
        self.assertNotRegex(note, r"(?i)anyway|without (a|an) (yes|answer)|unless .{0,20}\bno\b|no answer")
        for p in REVIEW.rglob("*.md"):
            text = p.read_text(encoding="utf-8").replace(note, "")
            m = WRITES.search(text)
            self.assertIsNone(m, f"{p.name}: {m.group(0) if m else ''}")
        self.assertRegex(section(skill(), "Checklist"), r"noted on the Script only if the user said yes")

    def test_the_other_scans_catch_common_rewordings(self):
        for pattern, lines in ((SHORTCUTS, ("A shared database is fine for one run.", "Install the missing tool, then go on.",
                                            "If it times out, rerun with `timeout 300`.")),
                               (MORE_ROUNDS, ("Then ask again whether anything else matters.", "Offer a second review round.")),
                               (JARGON, ("The ranking metric is p99.", "Each version must pass a hard gate."))):
            for line in lines:
                self.assertRegex(line, pattern)

    def test_the_write_scan_catches_common_rewordings(self):
        for line in ("Add the goal and choices to the Script's description as well.", "Validate the Script once more.",
                     "run `artemis discovery metrics-schema set`", "start a new validation", "scripts update"):
            self.assertRegex(line, WRITES)


class Requirements(unittest.TestCase):
    def test_an_older_cli_goes_to_cli_setup_first(self):
        glance = section(skill(), "At a glance")
        need = must_search(r"- \*\*Requirements:\*\*[^\n]*", glance).group(0)
        self.assertIn("`artemis --version` is at least `artemis-cli-min`", need)
        self.assertIn("`cli-setup` first", need)
        self.assertIn(must_search(r'artemis-cli-min: "([\d.]+)"', skill()).group(1), need)


class GoalFirst(unittest.TestCase):
    def goal(self):
        return section(skill(), r"1\. Settle the goal first")

    def test_sections_run_goal_then_needs_then_reading(self):
        self.assertRegex(skill(), r"## 1\. Settle the goal first[\s\S]*## 2\. Turn the goal into what to measure"
                                  r"[\s\S]*## 3\. Read the benchmark[\s\S]*## 5\. Show it and ask")
        self.assertRegex(section(skill(), r"2\. Turn the goal"), r"(?i)before reading what the benchmark does")

    def test_the_goal_comes_from_the_user_never_the_readme_or_a_guess(self):
        goal = self.goal()
        self.assertRegex(goal, r"(?i)only from the user's own words")
        self.assertRegex(goal, r"`taskDescription` is the goal only once the user confirms it")
        self.assertRegex(goal, r"(?i)never to answer it")
        self.assertRegex(goal, r"(?i)never fold a guess in as a default")
        for name, text in (("SKILL", skill()), ("checklist", read("benchmark-review/references/checklist.md"))):
            m = README_AS_GOAL.search(text)
            self.assertIsNone(m, f"{name}: {m.group(0) if m else ''}")
        self.assertNotRegex(skill(), r"(?i)(taking|take|use) the run's `taskDescription`|`taskDescription` as the goal")

    def test_the_scans_pass_harmless_rewordings(self):
        for line in ("the README's goal, only when the user declined", "the installed toolchain"):
            self.assertNotRegex(line, README_AS_GOAL)
            self.assertNotRegex(line, r"(?i)\binstall (it|the|a)\b")

    def test_the_readme_scan_catches_common_rewordings(self):
        for line in ("If the goal isn't stated, use the README's.", "If neither has it, take it from the README.",
                     "unless the README makes it obvious", "If it stays unclear, go with the most likely reading.",
                     "When the answer is vague, fall back to what the README states.",
                     "If the README states a clear goal, start from it without asking."):
            self.assertRegex(line, README_AS_GOAL)

    def test_one_short_question_per_reply(self):
        goal = self.goal()
        self.assertRegex(goal, r"(?i)one short question per reply")
        self.assertRegex(goal, r"(?i)never ask what the user already said")
        self.assertRegex(goal, r"(?i)review nothing and run nothing in the same reply as a goal question")
        for sentence in re.findall(r"[^.\n]*\bquestions?\b[^.\n]*", goal):
            self.assertNotRegex(sentence, r"(?i)all (three|3|the) questions|at once|together|in (a single|one) reply|"
                                          r"\bask\b[^.]{0,40}\bsame (message|reply)", sentence)
        self.assertNotRegex(goal, r"(?i)\bask\b[^.]{0,40}\bsame (message|reply)|both (questions )?at once")
        questions = [q.split("```", 1)[0].strip() for q in goal.split("```text\n")[1:]]
        asks = [q for q in questions if q.endswith(", or something else?")]
        self.assertEqual(len(asks), 2, questions)
        for q in asks:
            self.assertNotIn("\n", q)
            self.assertFalse("improve" in q and "get worse" in q, q)

    def test_the_readme_goal_only_after_the_user_declines(self):
        goal = self.goal()
        decline = between(goal, "If, after a goal question, the user declines")
        self.assertRegex(decline, r"(?i)review against the goal the README states, and say so first")
        self.assertRegex(decline, r"I need your goal to review this")
        self.assertRegex(decline, r"go to `discovery-start`")
        self.assertRegex(section(skill(), "Checklist"), r"(?i)the README's goal only when the user declined")

    def test_a_missing_project_or_checkout_is_asked_for(self):
        quick_budget = section(skill(), "Keep it quick")
        self.assertRegex(quick_budget, r"(?i)no checkout here, ask for it")
        self.assertRegex(quick_budget, r"(?i)can't be found[^.]{0,120}\bask\b")
        self.assertRegex(quick_budget, r"(?i)don't review until you have the checkout")

    def test_section_seven_settles_the_goal_like_section_one(self):
        again = section(skill(), r"7\. Add complexity")
        self.assertRegex(again, r"(?i)reuse it; otherwise settle it as in section 1")

    def test_the_goal_becomes_target_guards_and_workload(self):
        needs = section(skill(), r"2\. Turn the goal")
        for rule in (r"\*\*Target metric:\*\*.*direction and importance", r"hard gate a version has to pass",
                     r"guard metric reported on every run", r"\*\*Workload:\*\* inputs that exercise"):
            self.assertRegex(needs, rule)
        self.assertNotRegex(needs, r"(?i)optional|if you like|when cheap|instead of a gate|weighted|combined (score|into)|"
                                   r"sum of|existing inputs")


class Quick(unittest.TestCase):
    def test_budget(self):
        budget = section(skill(), "Keep it quick")
        for phrase in ("under 5 minutes", "no subagents", "about 10 files or 2,000 lines"):
            self.assertIn(phrase, budget)
        read_it = section(skill(), r"3\. Read the benchmark")
        self.assertRegex(read_it, r"(?i)don't start (extra|new) runs")
        # a std is only "within a run" where the CLI pools it so; how much runs vary is the spread of per-run means
        self.assertRegex(read_it, r"(?i)the `--stats` std is pooled within runs")
        self.assertIn("discovery metrics <run-id> --stats", read_it)
        self.assertRegex(read_it, r"(?i)how much runs vary is the spread of per-run means \(the largest minus the smallest")
        self.assertRegex(between(skill(), "metadata:", "\n---"), r'artemis-cli-min: "1\.1\.20"')

    def test_quick_checks_only_when_short_and_runnable_here(self):
        head = step4().split("\n   - **worse", 1)[0]
        for rule in (r"under 40 seconds", r"has the toolchain", r"no command writes where it can't be moved \(a shared database",
                     r"(?i)otherwise,? skip them|if not,? skip them"):
            self.assertRegex(head, rule)
        self.assertNotRegex(step4() + quick(), SHORTCUTS)
        self.assertRegex(section(skill(), "Checklist"), r"(?i)finish within 40 seconds")
        self.assertRegex(head, r"(?i)runtime, `/usr/bin/time`[^;]*or `bash`")

    def test_a_skipped_check_says_why(self):
        # Five different causes print the same words, so the reply carries which one.
        self.assertRegex(step4(), r'not checked by running \(<reason>\)')
        self.assertIn("| not checked by running (<reason>)", self.template_line())
        self.assertIn("not checked by running (<reason>)>", between(skill(), "The line reads `Benchmark review", "`."))
        self.assertRegex(quick(), r"(?i)with its reason in brackets")

    def template_line(self):
        return first_line(skill(), lambda l: l.startswith("- Checked by running:"), "'- Checked by running:' line")

    def test_all_three_checks_stay_and_must_fail(self):
        for name, rule in (("worse", r"metric must move the right way"),
                           ("wrong", r"correctness check must fail"),
                           ("cheat", r"gate must fail it")):
            for where, text in (("SKILL", step4()), ("quick-checks", quick())):
                item = bullet(text, f"- **{name}:**")
                self.assertRegex(item, f"(?i){rule}", f"{where} {name}")
                self.assertNotRegex(item, r"(?i)optional|skip it", f"{where} {name}")
        self.assertRegex(bullet(quick(), "- **cheat:**"), r"(?i)with noise not measured, any gain counts as the cheat winning")
        wrong = between(quick(), "- **wrong:**", "- **cheat:**")
        self.assertRegex(wrong, r"(?i)wrong in every option it can choose")
        self.assertRegex(wrong, r"(?i)the gate missed a wrong answer: that's the surprise")

    def test_a_runtime_metric_is_timed_not_read_from_a_results_file(self):
        # A Script that measures the benchmark's runtime writes no artemis_results file, so its run must not require one.
        timed = [b for b in bash_blocks(section(quick(), r"2\. Run the untouched copy")) if "/usr/bin/time -p" in b]
        self.assertEqual(len(timed), 1, "one timed form of cmds.sh")
        self.assertNotIn("artemis_results", timed[0])
        self.assertRegex(section(quick(), r"2\. Run the untouched copy"), r"(?i)ranking metric is the benchmark command's runtime")
        self.assertIn('2> "<work>/time.txt"', timed[0])
        self.assertRegex(section(quick(), r"2\. Run the untouched copy"), r"bash -c 'time -p sh \"<work>/bench.sh\"' 2> \"<work>/time.txt\"")
        # A stale results file from the checkout must not pass for this run's output.
        plain = [b for b in bash_blocks(section(quick(), r"2\. Run the untouched copy")) if "artemis_results" in b]
        self.assertTrue(plain, "no cmds.sh block writes artemis_results")
        self.assertIn("rm -f artemis_results.json artemis_results.csv &&", plain[0])

    def test_checks_compare_against_a_saved_baseline(self):
        baseline = section(quick(), r"2\. Run the untouched copy")
        self.assertRegex(baseline, r"(?i)every later run overwrites what it writes")
        self.assertRegex(baseline, r"(?i)output files[^.]{0,60}to `<work>/reference-out` now")
        self.assertIn("`<work>/reference-out`", between(quick(), "- **wrong:**", "- **cheat:**"))
        self.assertIn("`<work>/reference-out`", bullet(quick(), "- **cheat:**"))

    def test_runs_leave_the_shell_where_it_was(self):
        for block in bash_blocks(quick()):
            for line in block.splitlines():
                if re.match(r"\s*cd ", line):
                    raise AssertionError(f"bare cd outside a subshell: {line}")
        self.assertRegex(section(quick(), r"3\. One check at a time"), r"(?i)same way, in a subshell")

    def test_every_stop_cleans_up(self):
        q = quick()
        self.assertRegex(section(q, r"4\. Clean up"), r"(?i)early stops included,.{0,10}delete `<work>`")
        self.assertRegex(q, r"(?i)nothing runs in the user's checkout")
        self.assertRegex(q, r"(?i)work folder for the whole review outside the checkout")
        self.assertRegex(q, r"(?i)undo the edit before the next check")
        self.assertRegex(q, r"(?i)once 6 minutes have passed since the copy, stop")
        self.assertNotRegex(q, r"(?i)keep the edit|run (them|it) in the user's checkout")
        for sentence in re.findall(r"[^.\n]*\b[Ss]top\b[^.\n]*\.", q):
            self.assertIn("delete `<work>`", sentence, sentence)
        self.assertRegex(q, r"(?i)times? out is \"not checked by running\"")
        self.assertIn("timeout 40", q)
        self.assertRegex(q, r"(?i)`timeout` set to 90 seconds or the time left before the 6 minutes, whichever is less")

    def test_shell_snippets_fail_loudly_and_quote_paths(self):
        for name, text in (("SKILL", skill()), ("quick-checks", quick())):
            for block in bash_blocks(text):
                self.assertNotRegex(block, r"(?<![\"/])<(checkout|work|scratch|description-file|script-id|project)>", name)
                self.assertNotRegex(block, r"\|\s*rsync", name)
                self.assertNotRegex(block, r"&&[^{}\n]*\|\|\s*echo", name)  # a failed command reported as the fallback

    def test_only_tested_defences_are_credited(self):
        s = skill()
        self.assertRegex(s, r"(?i)credit a defence only when a check you ran shows (that )?it works")
        self.assertRegex(s, r"(?i)never tell the user it stops something")
        self.assertRegex(s, r"(?i)marked not tested")
        self.assertNotRegex(s, r"(?i)(comment|review note|report|description)s?\b.{0,60}\b(counts|credit(ed)?|as working|already works)")
        self.assertRegex(section(s, "Checklist"), r"(?i)no defence credited that a check didn't test")

    def test_a_skipped_worse_check_leads_the_later_line(self):
        self.assertRegex(step4(), r'put the "worse" check first on the "Later" line')
        self.assertRegex(section(skill(), "Checklist"), r'(?i)the "worse" check leads the Later line')


class Decisions(unittest.TestCase):
    def decide(self):
        return section(skill(), r"4\. Pick the decisions")

    def test_start_simple(self):
        body = section(skill(), "Start simple")
        self.assertRegex(body, r"(?i)recommend the simplest option that keeps the results trustworthy")
        self.assertNotRegex(body, r"(?i)most thorough|never .keep it as it is")

    def test_ranking(self):
        rank = between(self.decide(), "Rank them:", "A surprise and")
        items = re.findall(r"^(\d)\. (.*)$", rank, re.M)
        self.assertEqual([n for n, _ in items], ["1", "2", "3", "4"])
        self.assertRegex(items[0][1], r"^a cheat that passes with a better metric")
        self.assertRegex(items[1][1], r"^a need from section 2 the benchmark doesn't meet")

    def test_a_winning_cheat_stays_first(self):
        self.assertRegex(step4(), r"(?i)a cheat that passes with a better metric always does")
        self.assertNotRegex(step4(), r"(?i)always does,? (unless|except|but)")
        won = must_search(r"A cheat that won in the quick checks[^.]*\.", self.decide()).group(0)
        self.assertRegex(won, r"never one of these")
        self.assertRegex(won, r"first decision")
        self.assertRegex(section(skill(), "Checklist"), r"a winning cheat is the first decision")

    def test_few_decisions_few_choices_one_recommended(self):
        decide = self.decide()
        self.assertRegex(decide, r"(?i)at most the top 3")
        self.assertRegex(decide, r"(?i)2 or 3 concrete choices, simplest first")
        self.assertRegex(decide, r"(?i)exactly one\b.{0,40}recommended")
        self.assertRegex(decide, r"(?i)recommended[^.]{0,40}\bsimplest\b.{0,40}trustworthy")
        self.assertRegex(decide, r"(?i)can't make Discovery report a gain that isn't real, or hide a loss .{0,40}never a decision")
        self.assertNotRegex(decide, r"(?i)\bor two\b|one or two|two (when|if)|more when|or more|up to [4-9]|"
                                    r"never recommend .keep it as it is|recommend the (most thorough|fullest)")
        checklist = section(skill(), "Checklist")
        self.assertRegex(checklist, r"At most 3 decisions")
        self.assertRegex(checklist, r"exactly one recommended")


class AfterTheAnswer(unittest.TestCase):
    def test_discovery_settings_go_to_discovery_start(self):
        item = bullet(after(), "- **A choice about how Discovery runs**")
        self.assertRegex(item, r"pass it to `discovery-start`")
        self.assertNotIn("repo-command-setup", item)
        handoff = must_search(r"[^.\n]*`discovery-start` for runs per version[^.\n]*", section(skill(), "At a glance")).group(0)
        for choice in ("target files", "ranks versions", "`--task`"):
            self.assertIn(choice, handoff)
        self.assertNotRegex(offer(), r"(?i)runs per version|--eval-runs|target files")
        # discovery-start owns how a ranking choice is set
        ranking = between(read("discovery-start/SKILL.md"), "names which metric ranks versions", "\n\n")
        for rule in (r"once the baseline has finalized", r"the ranking metric `high`", r"every other `worker` metric `none`",
                     r"`agent` metrics as they are", r"metrics-schema set"):
            self.assertRegex(ranking, rule)
        self.assertNotRegex(ranking, r"(?i)ranking metric `(low|none|medium)`|other `worker` metric `(high|medium)`")

    def test_benchmark_changes_go_to_repo_command_setup(self):
        item = bullet(after(), "- **A choice that changes the benchmark")
        self.assertRegex(item, r"Let `repo-command-setup` make and verify the changes, and tell it this is a return from a review")
        self.assertRegex(section(skill(), "At a glance"), r"Changing the harness is `repo-command-setup`'s job")
        # the new-Script rule lives once, in repo-command-setup
        self.assertNotRegex(skill(), r"(?i)create a new Script")
        self.assertRegex(offer(), r"(?i)create a new Script")

    def test_an_edit_guard_protects_what_measures_not_a_file_allowlist(self):
        self.assertRegex(after(), r"guard against edits follows \[HARNESS\.md\]\([^)]*#rules-that-close-common-gaps\), \*Keep the scorer out of reach\*")
        guard = bullet(section(read("repo-command-setup/HARNESS.md"), "Rules that close common gaps"),
                       "- **Keep the scorer out of reach.**")
        for rule in (r"never which other files a version may change", r"since target files don't stop edits",
                     r"target files are guidance for Discovery, not a write boundary", r"honest change anywhere"):
            self.assertRegex(guard, rule)
        for name, text in (("HARNESS guard", guard), ("SKILL §6", after())):
            self.assertNotRegex(text, ALLOWLIST, name)

    def test_one_round(self):
        self.assertRegex(after(), r"(?i)stop once the user (has )?picked")
        self.assertNotRegex(after(), MORE_ROUNDS)


class Output(unittest.TestCase):
    LABELS = ["Target", "Must not get worse", "Workload", "Timed", "Benchmark runs per version", "Discovery may change",
              "Checked by running"]

    def blocks(self):
        blocks = section(skill(), r"5\. Show it and ask").split("```text\n")[1:]
        if len(blocks) < 2:
            raise AssertionError("section 5 needs a template and an example ```text block")
        return blocks

    def template(self):
        return self.blocks()[0].split("```", 1)[0]

    def example(self):
        return self.blocks()[1].split("```", 1)[0]

    @staticmethod
    def needs(text):
        return between(text, "Here's what you have:\n\n", "\n\n")

    def test_goal_then_needs_then_decisions(self):
        for name, text in (("template", self.template()), ("example", self.example())):
            self.assertRegex(text, r"^Your goal: ", name)
            self.assertIn("Decisions, most important first:", between(text, "Here's what you have:"), name)
            self.assertEqual(re.findall(r"^- ([A-Z][^:]+):", self.needs(text), re.M), self.LABELS, name)
            for need in ("Target", "Must not get worse", "Workload"):
                line = first_line(self.needs(text), lambda l: l.startswith(f"- {need}:"), f"'- {need}:' line")
                self.assertIn("You have:", line, f"{name} {need}")
                self.assertRegex(line, r"(Matches\.|Missing: )", f"{name} {need}")
            for line in ('"go with the recommendations"', "anything else you want your benchmark to capture?",
                         "Later, if a result asks for it:"):
                self.assertIn(line, text, name)

    def test_every_missing_need_in_the_example_is_a_decision_or_later(self):
        ex = self.example()
        later = must_search(r"^Later, if a result asks for it: (.*)$", ex, re.M).group(1)
        self.assertIn("real log lines in the timed file", later)
        self.assertEqual(len(re.findall(r"Missing: ", self.needs(ex))), 2)

    def test_the_example_is_filled_in_with_one_recommendation_each(self):
        ex = self.example()
        self.assertNotIn("<", ex)
        decisions = re.findall(r"^\d+\. ", ex, re.M)
        self.assertEqual(len(re.findall(r"^   Recommended: [a-c], ", ex, re.M)), len(decisions))
        self.assertIn("a) Keep it as it is", ex)
        self.assertRegex(self.template(), r"(?m)^   Recommended: <letter>, ")

    def test_the_example_question_names_only_metrics_the_example_has(self):
        first_q = between(between(section(skill(), r"1\. Settle the goal first"), "```text\n"), "```text\n", "```")
        target = first_line(self.needs(self.example()), lambda l: l.startswith("- Target:"), "'- Target:' line in the example")
        for metric in re.findall(r"\b[a-z]+_[a-z]+\b", first_q):
            self.assertIn(metric, target, metric)

    def test_plain_words(self):
        self.assertRegex(section(skill(), r"5\. Show it and ask"), r"(?i)leave out checklist row numbers, trait names")
        for text in (self.template(), self.example()):
            self.assertNotRegex(text, JARGON)


class Harness(unittest.TestCase):
    def rules(self):
        return section(read("repo-command-setup/HARNESS.md"), "Rules that close common gaps")

    def test_gap_rules_are_not_default_steps(self):
        self.assertRegex(self.rules(), r"(?i)none of these is a default step: add one only when the user picks it")
        self.assertNotRegex(self.rules(), r"(?i)by default|always apply")

    def test_inputs_stay_deterministic(self):
        harness = read("repo-command-setup/HARNESS.md")
        self.assertIn("**deterministic, representative** inputs", harness)
        self.assertRegex(self.rules(), r"fixed, logged seed, never literals in the timed code")
        self.assertNotIn("never literals", harness.split("## Rules", 1)[0])
        sql = read("benchmark-review/references/sql.md")
        self.assertRegex(sql, r"fixed parameter set generated from a logged seed")
        for name, text in (("sql.md", sql), ("traits.md", read("benchmark-review/references/traits.md")),
                           ("HARNESS rules", self.rules())):
            self.assertNotRegex(text, r"(?i)drawn at run time(?!.*logs?)|(fresh|new) (random )?(inputs|data) "
                                      r"(each|every|for every) (repetition|run)|random(ised|ized)? (inputs|data)(?!.*logged)", name)


class References(unittest.TestCase):
    def test_checklist_has_fourteen_rows_seven_first(self):
        rows = re.findall(r"^\| (\d+) \| [^|]+ \| (yes|no[^|]*) \|", read("benchmark-review/references/checklist.md"), re.M)
        self.assertEqual([int(n) for n, _ in rows], list(range(1, 15)))
        self.assertEqual([int(n) for n, first in rows if first == "yes"], list(range(1, 8)))

    def test_traits_and_equivalence_rules(self):
        text = read("benchmark-review/references/traits.md")
        for t in range(1, 8):
            self.assertIn(f"| T{t} ", text)
        self.assertRegex(text, r"Never branch on a task's name, with one exception: SQL work also reads \[sql\.md\]")
        rules = section(text, "Equivalence rules")
        for rule in ("identical", "canonicalising", "tolerance", "statistically equivalent", "quality floor"):
            self.assertIn(rule, rules)

    def test_sql_path(self):
        text = read("benchmark-review/references/sql.md").lower()
        for phrase in ("what may discovery change", "duplicates", "nulls", "plan stability", "prepared statements",
                       "cold and warm are two metrics", "tested equivalent, not proven", "is never the gate",
                       "use them only with the user's yes"):
            self.assertIn(phrase, text, phrase)

    def test_every_reference_is_linked_and_every_link_resolves(self):
        def slugs(path):
            return {re.sub(r"[^a-z0-9 -]", "", h.lower()).replace(" ", "-")
                    for h in re.findall(r"^#+ (.+)$", path.read_text(encoding="utf-8"), re.M)}
        for ref in (REVIEW / "references").glob("*.md"):
            self.assertIn(f"](references/{ref.name}", skill(), ref.name)
        for md in REVIEW.rglob("*.md"):
            for target, anchor in re.findall(r"\]\(([^)#\s]*\.md)?(?:#([^)\s]+))?\)", md.read_text(encoding="utf-8")):
                if not target and not anchor:
                    continue
                path = (md.parent / target) if target else md
                self.assertTrue(path.is_file(), f"{md.name} -> {target}")
                if anchor:
                    self.assertIn(anchor, slugs(path), f"{md.name} -> {target}#{anchor}")


class Wiring(unittest.TestCase):
    def test_repo_command_setup_offers_it_once_in_passing(self):
        o = offer()
        self.assertRegex(o, r"(?i)offer it once per session")
        self.assertRegex(o, r"(?i)doesn't take it up, carry on")
        self.assertRegex(o, r"(?i)already asked to start Discovery, skip the offer")
        self.assertRegex(o, r"(?i)skip the offer when the caller verifies the commands itself")
        self.assertRegex(o, r"(?i)on a return from `benchmark-review`")
        self.assertRegex(between(o, "When the review comes back"), r"(?i)return to `benchmark-review`")
        self.assertEqual(between(o, "```text\n", "```").count("\n"), 1)
        nxt = bullet(read("repo-command-setup/SKILL.md"), "- **Next skill:**")
        self.assertRegex(nxt, r"`benchmark-review`[^.\n]{0,40}§7")
        self.assertRegex(nxt, r"`discovery-start`")
        self.assertRegex(section(read("repo-command-setup/SKILL.md"), "Completion checklist"),
                         r"`benchmark-review` offered once, except when")

    def test_discovery_inspect_offers_it_on_a_suspicious_result(self):
        item = inspect_item()
        self.assertRegex(item, r"offer `benchmark-review`")
        self.assertRegex(item, r"run id")
        for sign in ("far larger than expected", "flip between reruns"):
            self.assertIn(sign, item)
        self.assertNotRegex(item, r"(?i)never offer|do not offer|ignore|\b(any|every) (finished )?run\b|always|until|yourself")

    def test_validation_get_facts_live_in_repo_command_setup(self):
        pin = r"on CLI \d+\.\d+\.\d+ or newer each metric's mean"
        self.assertRegex(read("repo-command-setup/SKILL.md"), pin)
        self.assertNotRegex(skill(), pin)
        self.assertIn("](../repo-command-setup/SKILL.md#5b-verify-via-the-runner)", section(skill(), r"3\. Read the benchmark"))
        self.assertNotRegex(after(), r"(?i)once the baseline has finalized")


if __name__ == "__main__":
    unittest.main()
