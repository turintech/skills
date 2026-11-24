---
name: benchmark-review
description: "Review whether a Discovery benchmark measures the user's goal and can be gamed, on request only, starting from the goal and ending with a few simple choices for each of the top gaps. Use when the user asks to review a benchmark, asks whether it measures the right thing or can be gamed, or says yes to the review offer from repo-command-setup or discovery-inspect. Any goal, SQL included. Not for setup readiness (artemis), starting runs (discovery-start) or writing or fixing a harness (repo-command-setup)."
compatibility: Requires Artemis CLI 1.1.20+ (below 1.2.0) and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.20"
  artemis-cli-max: "1.2.0"
  artemis-platform-min: "3.1.0"
---

# Review a benchmark

## At a glance

- **Problem:** Discovery optimises whatever the benchmark rewards, and only the user knows what they want to achieve. This skill settles their goal first, turns it into what a benchmark needs to measure it, shows what theirs has and what's missing, then plans the next step with them: a few choices per gap, the simplest trustworthy one recommended.
- **Must be available:** The user's goal, from them, and a benchmark in a checkout. A correctness check and the project Script help but aren't required.
- **Requirements:** `artemis --version` is at least `artemis-cli-min` (1.1.20, where `discovery metrics --stats` covers every version, not one page); if it is older, load the skill and follow `cli-setup` first.
- **Use / don't use:** Only when the user asks, or says yes to the offer from `repo-command-setup` or from `discovery-inspect` after a suspicious result. Never start it on your own, and never treat it as a gate: Discovery can always go ahead. Changing the harness is `repo-command-setup`'s job.
- **Next skill:** `repo-command-setup` for benchmark changes the user picked; `discovery-start` for runs per version, target files and which metric ranks versions, with the settled goal as its `--task` when it creates a run; otherwise back to the caller.

## Start simple

A simple benchmark that runs end to end beats a thorough one that delays the first result. Recommend the simplest option that keeps the results trustworthy for the user's goal, often "keep it as it is". Add complexity later, when a result gives a reason ([section 7](#7-add-complexity-when-a-result-asks-for-it)).

## Keep it quick

Once the goal is settled, finish the reading in under 5 minutes, 2 to 3 typically, with no subagents; the quick checks, when they apply, add 2 to 4 more, 6 at most. From the benchmark, read only what decides what is measured, about 10 files or 2,000 lines at most, data and config files included (this skill's own references, and files a quick check makes you open, don't count):

- the commands, from one of these:
  - the Script the user or caller named: `artemis project scripts list --project <project>`, then `artemis project scripts get <script-id> --project <project>`;
  - for a Discovery run, the Script it executes: `scriptId` in `artemis --output-format json discovery get <run-id>`;
  - otherwise the project's default Script;
  - with no Script yet, the build, test and benchmark commands in the repository;
  - with no benchmark at all, say there is nothing to review yet and offer `repo-command-setup` to write one;
- the benchmark entry point and what it calls up to the timed work;
- the correctness test and any in-benchmark check;
- where the inputs come from.

Skim the rest, or leave it.

If there is no checkout here, ask for it. If the user named a project, or a run or validation id is in play, and the project can't be found, ask for that too. Ask in one reply, for example: "I can't find <the project | the code>. Which project id, or which folder holds the code?" Don't review until you have the checkout, and the project when one was named. With no project, read the commands from the repository.

## 1. Settle the goal first

The review is only as good as its reading of the goal, so settle it before reviewing anything. You need:

- **What to improve, and which way:** faster, smaller, cheaper per run, more accurate. With more than one, which matters most.
- **What must not get worse, and how strictly:** the output exactly the same, accuracy within a stated margin, latency no higher, memory no larger.

Take these only from the user's own words in this conversation. A Discovery run's `taskDescription` is the goal only once the user confirms it here; otherwise make it your first question:

```text
The run's task says "<taskDescription>". Is that still what you want to improve?
```

A README, a code comment, a metric's name or an earlier review's line in a Script's description is not the user's goal: use it to make a question concrete, never to answer it. The one exception is a user who declines, below.

When any of them isn't clear, ask the user before reviewing, in plain words, one short question per reply, and end the reply with it. Keep it to a sentence or two, with at most three likely answers. To find those, read the README and the metric names the benchmark writes (the few lines that build `artemis_results`, or the Script's commands), nothing more; leave the references for section 3. What must not get worse belongs to the second question, even when the benchmark already holds a floor. For example, the first question, then the second once the first is answered:

```text
Before I look at the benchmark: what do you want Discovery to improve? It reports parse_ms, so faster parsing, faster start-up, or something else?
```

```text
And what must not get worse while it does that: the parsed counts staying exactly the same, memory no higher than today, or something else?
```

Ask the next question only when the last answer leaves it open. Two questions are usually enough. Ask a third only when the user named two things to improve and not which matters more, or a guard whose strictness is open ("accuracy unchanged" on a float score: exactly, or within a margin?). If one of your offered answers named a strictness ("agreement no lower than today's 95%", say) and the user picks it, that settles the strictness. Never ask what the user already said. Never fold a guess in as a default ("I'll assume speed unless you say otherwise"). Beyond that short read and finding the project, review nothing and run nothing in the same reply as a goal question.

If, after a goal question, the user declines to answer or tells you to go on without answering, review against the goal the README states, and say so first: "I'm reviewing against <goal>, from the README. Tell me if that's wrong." If the README states no goal either, say "I need your goal to review this; you can start Discovery without a review." and stop. If they ask to start Discovery instead, go to `discovery-start`.

## 2. Turn the goal into what to measure

Before reading what the benchmark does, write down what measuring this goal needs. These needs are what the rest of the review checks against:

- **Target metric:** for each thing to improve, the number that shows it, with its unit, direction and importance: one ranks versions, any other is secondary. Best in the Web UI follows the Composite score, which blends every metric by importance, so the ranking metric counts most there; a secondary set to `none` doesn't count at all. "Faster" is the time of the work the user cares about; "smaller files" is the size of the files they ship; "cheaper per run" is that run's cost.
- **Guards:** each thing that must not get worse becomes a hard gate a version has to pass to count, and, when the guard is a single score (accuracy, memory, latency, size), a guard metric reported on every run so a drift shows before it fails. An exact match on the outputs themselves needs no extra metric. "Accuracy unchanged" is a check against the original's outputs, exact or within the margin the user named, plus accuracy reported alongside; "same decisions" is every decision matching the original's. Pick the rule for each output type from the [equivalence rules](references/traits.md#equivalence-rules).
- **Workload:** inputs that exercise what the goal is about: the user's real sizes and shapes, the situation they named (the first call, a busy server, the largest file), each configuration they run.

## 3. Read the benchmark

1. **The traits** in [traits.md](references/traits.md) that apply. They tell you which checks matter. For SQL work, also read [sql.md](references/sql.md).
2. **What it has, against each need from section 2:**
   - the metric that ranks versions, its unit and direction, and how runs are combined; when the Script writes several metrics and nothing sets which ranks (no run's metrics schema yet), say so: that is a gap against the target;
   - any other metrics, and which guard each could serve;
   - the correctness rule, against each guard and the [equivalence rules](references/traits.md#equivalence-rules);
   - the inputs, against the workload. When the benchmark scores situations or variants the user may judge apart (small and large, first call and repeat, several sizes or settings of the output) and the goal doesn't say which counts, ask that one question as soon as you see it, alone in its reply and in the same short style as section 1, before the quick checks, then go on with the answer;
   - what the clock covers;
   - the Benchmark runs per version, if chosen (Discovery's default is one);
   - the files Discovery may change.
3. **How much results vary, from runs that already exist:**
   - validations of this Script whose ids are already in the conversation: `artemis changeset validation get <validation-id> --project <project>` for each command's runtime and, where it reports them ([repo-command-setup 5b](../repo-command-setup/SKILL.md#5b-verify-via-the-runner)), each metric's mean (use the means; don't report its std); `artemis changeset validation logs <validation-id> --project <project>` for the raw values, on any CLI;
   - a Discovery run whose id is in the conversation: `artemis discovery metrics <run-id> --stats` for each metric's n and std, and `artemis discovery metrics <run-id> --all` without `--stats` for the raw samples;
   - n counts every value the results file wrote. The `--stats` std is pooled within runs: use the "repeats within a run" wording below for it. How much runs vary is the spread of per-run means (the largest minus the smallest, as a percentage of their median), from 2 or more validations, or from the raw samples grouped by Benchmark run when a run has more than one (`artemis --output-format json discovery metrics <run-id> --all`: one `observationId` per Benchmark run of a version);
   - repeats in the benchmark's own output. These are within one run, so they usually understate how much runs vary: report them as "repeats within a run vary by about <x>%; between runs not measured", and treat that as a lower bound when choosing runs per version.

   Don't start extra runs for it. With none, say "not measured".
4. **Three quick checks**, only when all of these hold:
   - this machine has the toolchain those commands need, rsync 3.1 or newer (`rsync --version`) and `timeout` (`gtimeout` on macOS), and, when the ranking metric is the benchmark's runtime, `/usr/bin/time` (the `time` package on Debian and Ubuntu) or `bash`;
   - no command writes where it can't be moved (a shared database, files under the home folder). A write you can point at the scratch folder doesn't count, and copying an existing cache there first is fine;
   - build, test and benchmark together take under 40 seconds, from a measured validation or else from the baseline run in the checks, cut off at 40 seconds.

   Otherwise skip them and say "not checked by running (<reason>)": the condition that failed. Run them as [quick-checks.md](references/quick-checks.md) says, on a scratch copy:
   - **worse:** make the target clearly worse for the user's goal; the metric must move the right way.
   - **wrong:** return a wrong answer just past the user's guard; the correctness check must fail.
   - **cheat:** score better without doing the work (stored answers for the scored inputs, or an edit to a scorer Discovery can change); the gate must fail it, or the metric must show no gain beyond its noise.

   A surprise in any check becomes the first decision, and a cheat that passes with a better metric always does, whatever the goal.

   Credit a defence only when a check you ran shows it works. One you only read about, in its code comments, a review note, another Script's description or a report that says a hole is closed, is "not tested": say so, and never tell the user it stops something. Mention another Script only when it claims to close this hole; you may offer it as a choice, marked not tested. When you skipped the checks, put the "worse" check first on the "Later" line: make the target worse once in a validation to prove the measured run reaches it.

## 4. Pick the decisions

Walk every row of [checklist.md](references/checklist.md). A row matters only when it matters for **this** goal: tie each one to the goal in one line, never as general best practice.

Rank them:

1. a cheat that passes with a better metric, then any other surprise from the quick checks;
2. a need from section 2 the benchmark doesn't meet: the target isn't what ranks versions, a guard has no gate, the workload misses what the goal is about;
3. rows marked "first";
4. then by how badly they would mislead Discovery for this goal.

A surprise and an unmet need with one cause are one decision. Turn at most the top 3 into decisions. A gap that can't make Discovery report a gain that isn't real, or hide a loss the user would mind, is never a decision. It and anything below the top 3 go on one "Later, if a result asks for it:" line.

For each decision, offer 2 or 3 concrete choices, simplest first:

- **keep it as it is**, saying what that risks;
- **the simplest fix that makes results trustworthy** (rank by the goal's own number, a gate on the guard, a correctness check on real samples, more runs per version, one larger input);
- at most one **fuller option** (real data kept outside the repository, first and repeat runs timed apart), saying when it's worth it.

Name exactly one choice as recommended, on its own line: the simplest one that keeps the results trustworthy for this goal. Each choice is a few words in the user's terms, and says roughly what it costs to set up; a rough guess is fine. The checklist's fix column is a hint, not text to paste.

Holes only the platform can close (a holdout Discovery can't read, inputs it can't predict) get one line at most, not a decision: put it on the "Later" line. A cheat that won in the quick checks is never one of these: it stays the first decision, with a harness fix such as a check on fresh inputs. A scorer Discovery can edit is not one of them either: a check on its contents closes it here.

## 5. Show it and ask

Reply in this shape, in plain words: the goal, what measuring it needs and what this benchmark has against each need, then the decisions. Leave out checklist row numbers, trait names and statistics jargon (std, confidence intervals).

```text
Your goal: <what to improve, which way>, with <what must not get worse, how strictly>.<With two to improve: <which> matters most.>

To measure that, Discovery needs these. Here's what you have:

- Target: <the goal's own number, unit, direction>, ranking versions<; <second>, secondary>. You have: <what ranks versions now, its unit, direction and how repeats are combined, such as the median of 5 repeats in one run>, from <script name or command>; also measured: <other metrics | nothing else>. <Matches. | Missing: <what>>
- Must not get worse: <each guard>, with a check on every version that fails when it changes (<exact match | within <margin>> on <which outputs and inputs>)<, plus <guard metric> reported every run>. You have: <the check in plain words, on which outputs and inputs | no check>. <Matches. | Missing: <what>>
- Workload: <inputs that exercise the goal>. You have: <what they are, how many, sizes, where they come from>. <Matches. | Missing: <what>>
- Timed: <what the clock covers>; outside it: <what isn't timed, such as start-up, loading or the check>
- Benchmark runs per version: <n | not set yet, so one>; <runs vary by about <x>%, from <where> | repeats within a run vary by about <x>%; between runs not measured | not measured>
- Discovery may change: <target files | the whole repository>
- Checked by running: <making <target> worse (<how>) made <metric> <x>% worse>; a wrong answer <failed | passed> the check, or: the wrong-answer check was skipped, since <metric> is the correctness measure; a cheat (<what it did>) <was rejected | gained nothing beyond noise | won by <x>%> | not checked by running (<reason>)<; ran on <short-sha>, not <short-sha> the run measured><; ran with uncommitted changes>

Decisions, most important first:

1. <What's missing, in one line>. <Why it matters for this goal>.
   a) Keep it as it is: <what that risks>
   b) <Simplest fix>: <what changes, rough effort>
   c) <Fuller option>: <what changes, rough effort>, worth it when <condition>
   Recommended: <letter>, <why in a few words>
2. ...

Later, if a result asks for it: <short list>

Pick a letter for each, or say "go with the recommendations".
Is there anything else you want your benchmark to capture?
```

Special cases:

- **No guard named** (declined, or the user said nothing must stay the same): end the "Your goal" line after the improvement, and the "Must not get worse" line reads "none named, so nothing is guarded".
- **No decisions needed:** say "This benchmark measures your goal as it is." in place of the decisions. Keep the "Later" line when it has anything, a skipped "worse" check included. Then ask the same "anything else" question.
- **Nothing left for later:** leave the "Later" line out.
- **The ranking metric isn't a time** (a size, a score): on the "Timed" line, say that no ranked number is timed and what computes the metric. On "Benchmark runs per version", a metric computed from fixed or seeded inputs is still "not measured"; add that it should come out the same each run, and why.

For example, a log parser whose user said "parse our nginx logs faster, and the counts must stay exactly the same":

```text
Your goal: parse your nginx logs faster, with every count exactly the same as today's parser gives.

To measure that, Discovery needs these. Here's what you have:

- Target: parsing time per file, in milliseconds (lower is better), ranking versions. You have: parse_ms (milliseconds, lower is better, the median of 5 repeats in one run), from "bench"; also measured: nothing else. Matches.
- Must not get worse: the counts, with a check on every version that fails when any count changes (exact match, on logs like yours). You have: the counts compared with the original parser's on the generated file and on a second one tools/gen.py makes from a fresh, logged seed. Missing: none of your real logs' oddities are checked.
- Workload: logs with your real lines and sizes. You have: one 50 MB file generated by tools/gen.py, the same file every run. Missing: real lines (IPv6, quoted user agents, broken lines).
- Timed: parsing the file already in memory; outside it: reading the file from disk, start-up and the check
- Benchmark runs per version: not set yet, so one; runs vary by about 4%, from 3 earlier validations
- Discovery may change: the whole repository
- Checked by running: making parse_line worse (twice the work per line) made parse_ms 38% worse; a wrong answer failed the check; a cheat (stored counts keyed on the generated file's size) was rejected

Decisions, most important first:

1. The counts are only checked on generated files, which have none of your real logs' oddities. A parser that only handles the generated format would pass and win.
   a) Keep it as it is: a parser fitted to the generated format could win and then break on your logs
   b) Add a sample of your real logs to the check: about 10 minutes, no slower runs
   c) Also keep a set of real logs outside the repository to check the best versions: about half an hour, worth it when you rely on the result
   Recommended: b, the smallest change that keeps a win real
2. Each version runs once, and runs vary by about 4%, so a small win could be noise.
   a) Keep it as it is: Discovery may report a gain of a few percent that isn't real
   b) 3 Benchmark runs per version: about 3 times the benchmark time per version
   Recommended: b, so a win has to clear the noise

Later, if a result asks for it: real log lines in the timed file, a larger log file, name the file holding parse_line as the target

Pick a letter for each, or say "go with the recommendations".
Is there anything else you want your benchmark to capture?
```

## 6. After the answer

Act on each choice by its kind; one answer can mix all three.

- **A choice that changes the benchmark, recommended or not, or something to add:** list the concrete harness changes, each tied to the need it meets: a new target metric, a gate for a guard, a guard metric, an input. A new wish ("also memory", "p99 too") becomes a metric or a check. A guard against edits follows [HARNESS.md](../repo-command-setup/HARNESS.md#rules-that-close-common-gaps), *Keep the scorer out of reach*. Let `repo-command-setup` make and verify the changes, and tell it this is a return from a review. When it returns, repeat only the lines of your section 5 reply that changed.
- **A choice about how Discovery runs** (Benchmark runs per version, target files, which metric ranks versions and in which direction): pass it to `discovery-start`: on an existing run, a change to runs per version or target files means a new run, so every version is measured the same way.
- **A step by hand** (confirm the best versions on real data, say): say when to do it. **"Keep it as it is"** needs nothing.

Once those are done, if a Script exists, ask once whether to note the goal and choices in the description of the Script Discovery will use (the new one, if `repo-command-setup` made one). Only on yes, add one line, keeping what was there. Write the new description to a file outside the checkout first, so the shell expands nothing in it:

```bash
if [ ! -f "<description-file>" ]; then
  echo "description file missing; not updated"
elif grep -q '[^[:space:]]' "<description-file>"; then
  artemis project scripts update "<script-id>" --project "<project>" --description "$(cat "<description-file>")"
else
  echo "description file empty; not updated"
fi
```

The line reads `Benchmark review <YYYY-MM-DD>: goal <goal>; <choices made>; quick checks <ran here | not checked by running (<reason>)>; left for later: <list|none>`. Then go back to the caller, or to `discovery-start` with the Discovery choices.

Stop once the user has picked. Don't ask again or push further rounds.

## 7. Add complexity when a result asks for it

When `discovery-inspect` flags a result that looks too good and offers this review, start only on the user's yes. If this conversation already settled the goal, reuse it; otherwise settle it as in section 1. Then take that result as evidence. Lead with the gap that explains it (the earlier review's "Later" item, if there was one), and recommend the smallest change that would have caught it.

## Checklist

- [ ] Started only because the user asked or said yes to an offer.
- [ ] Checkout found, and the project when one was named, or asked for before reviewing.
- [ ] Goal settled before reviewing: what to improve, what must not get worse and how strictly, from the user's own words; one short question per reply when it wasn't clear, never a guess; the README's goal only when the user declined, said so first.
- [ ] The goal turned into needs: target metric with direction and importance, a hard gate and guard metric per guard, a workload that exercises the goal.
- [ ] Reading under 5 minutes (quick checks 2 to 4 more, 6 at most), no subagents, at most about 10 benchmark files read.
- [ ] How much results vary taken only from existing runs, otherwise "not measured".
- [ ] Reply led with the goal, then each need with what the benchmark has and what's missing, in plain words, including what the clock covers and what it doesn't.
- [ ] At most 3 decisions tied to the user's goal, each with 2 or 3 choices and exactly one recommended: the simplest that keeps results trustworthy.
- [ ] Smaller gaps left on the "Later" line, not pushed now.
- [ ] Quick checks (worse, wrong, cheat) only when build, test and benchmark finish within 40 seconds (a measured validation, or the baseline run here), with the toolchain here and nothing written where it can't be moved; otherwise "not checked by running" with its reason, and the "worse" check leads the Later line.
- [ ] No defence credited that a check didn't test; a winning cheat is the first decision.
- [ ] After a suspicious result: the goal reused or settled first, and the gap that explains the result leads.
- [ ] Ended with "pick a letter or go with the recommendations" when there are decisions, and always with "anything else?".
- [ ] Benchmark changes made through `repo-command-setup`; runs per version, target files, ranking and the settled goal (as `--task`) passed to `discovery-start`; choices noted on the Script only if the user said yes; stopped once the user picked.
- [ ] Discovery never blocked.
