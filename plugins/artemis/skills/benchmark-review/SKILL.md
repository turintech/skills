---
name: benchmark-review
description: "Review a Discovery benchmark with the user, on request only, as a few-minute planning session: what it measures, then simple choices per gap. Use when the user asks to review a benchmark, whether it measures the right thing or can be gamed, accepts the offer from repo-command-setup, or from discovery-inspect after a suspicious result. Any goal, SQL included. Not for setup readiness (artemis), optimising code (discovery-start) or writing a harness (repo-command-setup)."
compatibility: Requires Artemis CLI 1.1.14+ (below 1.2.0) and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.14"
  artemis-cli-max: "1.2.0"
  artemis-platform-min: "3.1.0"
---

# Review a benchmark

## At a glance

- **Problem:** Discovery optimises whatever the benchmark rewards. Only the user knows their goal and how much measuring is worth to them. This skill shows them what their benchmark will really measure, then plans the next step with them: a few choices per gap, the simplest trustworthy one recommended.
- **Must be available:** A benchmark and its correctness check in a checkout. The project Script helps but isn't required.
- **Use / don't use:** Only when the user asks, or says yes to the offer from `repo-command-setup` or from `discovery-inspect` after a suspicious result. Never start it on your own, and never treat it as a gate: Discovery can always go ahead. Changing the harness is `repo-command-setup`'s job.
- **Next skill:** `repo-command-setup` to make the choices the user picked; otherwise back to the caller or `discovery-start`.

## Start simple

A simple benchmark that runs end to end beats a thorough one that delays the first result. Recommend the simplest option that keeps the results trustworthy for the user's goal, often "keep it as it is". Add complexity later, when a result gives a reason ([section 5](#5-add-complexity-when-a-result-asks-for-it)).

## Keep it quick

Finish the reading in under 5 minutes, 2 to 3 typically, with no subagents; the quick checks, when they apply, add up to about 4 more. From the benchmark, read only what decides what is measured, about 10 files or 2,000 lines at most (this skill's own references don't count):

- the commands: the Script's (`artemis project scripts list --project <project>`, then `artemis project scripts get <script-id> --project <project>`), or with no Script yet, the build, test and benchmark commands in the repository;
- the benchmark entry point and what it calls up to the timed work;
- the correctness test and any in-benchmark check;
- where the inputs come from.

Skim the rest, or leave it.

## 1. Read the benchmark

1. **The goal.** Take it from the user's words, the Discovery brief or the README. If it isn't stated, form your best reading; the final question asks the user to correct it.
2. **The traits** in [traits.md](references/traits.md) that apply. They tell you which checks matter; don't show them. For SQL work, also read [sql.md](references/sql.md).
3. **What will be measured:**
   - the ranking metric, its unit and direction, and how runs are combined;
   - any other metrics;
   - the inputs;
   - the correctness rule, against the [equivalence rules](references/traits.md#equivalence-rules);
   - the runs per version, if chosen (Discovery's default is one);
   - the files Discovery may change.
4. **How much results vary, from runs that already exist:**
   - validations of this Script whose ids are already in the conversation: `artemis changeset validation get <validation-id> --project <project>` for each command's runtime and each metric's n and std, `artemis changeset validation logs <validation-id> --project <project>` for the raw values;
   - repeats in the benchmark's own output.

   Don't start extra runs for it. With none, say "not measured".
5. **Three quick checks, only when a measured validation or local run shows build, test and benchmark together taking under a minute, and this machine has the toolchain those commands need.** Otherwise skip them.
   1. Copy the checkout's files to a scratch folder:
      ```bash
      git -C <checkout> ls-files -co --exclude-standard | rsync -a --ignore-missing-args --files-from=- <checkout>/ <scratch>/
      ```
   2. Run the build, test and benchmark commands once on the untouched copy: that is the baseline the checks compare against. If it already fails (a generated or ignored input missing, say), stop here and say "not checked by running" rather than blame the benchmark.
   3. One check at a time, edit only the target code in the copy, run the commands, then undo the edit before the next:
      - **worse:** make it clearly slower, or worse on the goal. The metric must move the right way.
      - **wrong:** return a wrong answer. The correctness check must fail. Skip this one when the ranking metric *is* the correctness measure, such as accuracy: "worse" already covers it.
      - **cheat:** make the target return the answer for exactly the scored inputs without doing the work: a stored or hardcoded result keyed on the input's size, shape or name, or the scored data itself embedded in the target. Aim it at the defence the benchmark relies on most (a perturbed or fresh copy, a holdout, a sandbox). The gate must fail it, or the metric must show no gain beyond its noise. Keep it to one small edit and one run.
   4. Delete the copy. The checks take up to four runs of under a minute each, on top of the reading; say so in one line before starting them.

   A surprise in any check becomes the first decision, and a cheat that passes with a better metric always does, whatever the goal. It is still the user's decision: Discovery can go ahead.

   Credit a defence only when a check you ran shows it works. One you only read about, in its code comments, a review note or a report that says a hole is closed, is "not tested": say so, and never tell the user it stops something. If you skipped the checks, say "not checked by running", and put the "worse" check first on the "Later" line: slow the target once in a validation to prove the timed run reaches it.

## 2. Pick the decisions

Walk every row of [checklist.md](references/checklist.md). A row matters only when it matters for **this** goal: tie each one to the goal in one line, never as general best practice.

Rank them:

1. rows marked "first";
2. then by how badly they would mislead Discovery for this goal.

Turn at most the top 3 into decisions. Anything smaller goes on one "Later, if a result asks for it:" line.

For each decision, offer 2 or 3 concrete choices, simplest first:

- **keep it as it is**, saying what that risks;
- **the simplest fix that makes results trustworthy** (a correctness check on real samples, more runs per version, one larger input);
- at most one **fuller option** (real data kept outside the repository, first and repeat runs timed apart), saying when it's worth it.

Name exactly one choice as recommended, on its own line: the simplest one that keeps the results trustworthy for this goal. That is "keep it as it is" whenever the gap can't make Discovery report a gain that isn't real. Each choice is a few words in the user's terms, and says roughly what it costs to set up. The checklist's fix column is a hint, not text to paste.

Holes only the platform can close (a holdout Discovery can't read, inputs it can't predict, a scorer it can't edit) get one line at most, not a decision.

## 3. Show it and ask

Reply in this shape, in plain words. Leave out checklist numbers, trait names, scores and statistics jargon.

```text
Here's what this benchmark will measure for Discovery:

- Ranks versions by: <name> (<unit>, <lower|higher> is better, <how repeats are combined, such as the median of 5 repeats in one run>), from <script name or command>
- Timed: <what the clock covers>; outside it: <what isn't timed, such as start-up, loading or the check>
- Also measured: <other metrics> | nothing else
- Inputs: <what they are, how many, sizes, where they come from>
- Counts as correct: <the check in plain words>, checked on <which outputs and inputs>
- Runs per version: <n | not set yet, so one>; runs vary by about <x>% | not measured
- Discovery may change: <target files | the whole repository>
- Checked by running: slowing <target> made <metric> <x>% worse; a wrong answer <failed | passed | was skipped, the metric is the correctness measure> the check; a cheat (<what it did>) <was rejected | gained nothing beyond noise | won by x%> | not checked by running

For your goal (<goal in one line>), a few decisions, most important first:

1. <What's missing, in one line>. <Why it matters for this goal>.
   a) Keep it as it is: <what that risks>
   b) <Simplest fix>: <what changes, rough effort>
   c) <Fuller option>: <what changes>, worth it when <condition>
   Recommended: <letter>, <why in a few words>
2. ...

Later, if a result asks for it: <short list>

Pick a letter for each, or say "go with the recommendations".
Is there anything else you want your benchmark to capture?
```

Two special cases:

- **No goal was stated:** put "I read your goal as: <goal>" above the decisions, and add "Is that right?" to the question.
- **No decisions needed:** say "This benchmark is fine to start with." Then ask the same "anything else" question.

For example, a log parser whose goal is "parse our nginx logs faster":

```text
Here's what this benchmark will measure for Discovery:

- Ranks versions by: parse_ms (milliseconds, lower is better, the median of 5 repeats in one run), from "bench"
- Timed: parsing the file already in memory; outside it: reading the file from disk, start-up and the check
- Also measured: nothing else
- Inputs: one 50 MB file generated by tools/gen.py, the same file every run
- Counts as correct: the parsed counts match the original parser's, checked on that file and on a second one tools/gen.py makes from a fresh, logged seed
- Runs per version: not set yet, so one; runs vary by about 4%
- Discovery may change: the whole repository
- Checked by running: slowing parse_line made parse_ms 38% worse; a wrong answer failed the check; a cheat that returns stored counts for the generated file's size was rejected by the check

For your goal (parse your nginx logs faster), a few decisions, most important first:

1. The check only uses generated files, which have none of your real logs' oddities (IPv6, quoted user agents, broken lines). A parser that only handles the generated format would pass.
   a) Keep it as it is: a parser fitted to the generated format could win and then break on your logs
   b) Add a sample of your real logs to the check: about 10 minutes, no slower runs
   c) Also keep a set of real logs outside the repository to check the best versions: worth it once you rely on the result
   Recommended: b, the smallest change that keeps a win real
2. Each version runs once, and runs vary by about 4%, so a small win could be noise.
   a) Keep it as it is: Discovery may report a gain of a few percent that isn't real
   b) 3 runs per version: about 3 times the benchmark time per version
   Recommended: b, so a win has to clear the noise

Later, if a result asks for it: a larger log file, name the file holding parse_line as the target

Pick a letter for each, or say "go with the recommendations".
Is there anything else you want your benchmark to capture?
```

## 4. After the answer

- **Every choice is "keep it as it is":** if a Script exists, ask whether to note the choices in its description. Only on yes, add one line, keeping what was there. Write the new description to a file outside the checkout first, so the shell expands nothing in it:
  ```bash
  artemis project scripts update "<script-id>" --project "<project>" --description "$(cat <description-file>)"
  ```
  The line reads `Benchmark review <YYYY-MM-DD>: <choices made>; ran on <runner, toolchain>; left for later: <list|none>`. With no Script yet, say the line is added once there is one. Then go back to the caller, or to `discovery-start`.
- **Any choice that changes the benchmark, recommended or not, or something to add:** list the concrete harness changes. A new wish ("also memory", "p99 too") becomes a metric or a check. A guard against edits protects only what measures: the benchmark, its checks, their expected outputs and the guard itself. It never limits which other files a version may change, because target files are guidance for Discovery, not a write boundary: an honest change anywhere in the code must still pass. Then:
  1. Let `repo-command-setup` make and verify the changes, and tell it this is a return from a review, so it doesn't offer one again.
  2. Show only the lines of the summary that changed, then go back to the caller or `discovery-start`.
- **Stop once the user has picked.** Don't ask again or push further rounds.

## 5. Add complexity when a result asks for it

Start simple, and come back when a Discovery result gives a reason. Any of these signs:

- a gain far larger than expected;
- a winner whose code special-cases the benchmark's inputs, sizes or file names;
- a winner that loses on real data or new inputs;
- rankings that flip between reruns.

`discovery-inspect` offers this review when it sees one; start only on the user's yes. Start this review again with that result as the goal's evidence. Lead with the "Later" item that explains it, and recommend the smallest change that would have caught it.

## Checklist

- [ ] Started only because the user asked or said yes to an offer.
- [ ] Reading under 5 minutes (quick checks about 4 more), no subagents, at most about 10 benchmark files read.
- [ ] What will be measured: all eight lines shown, in plain words, including what the clock covers and what it doesn't.
- [ ] At most 3 decisions tied to the user's goal, each with 2 or 3 choices and exactly one recommended: the simplest that keeps results trustworthy.
- [ ] Smaller gaps left on the "Later" line, not pushed now.
- [ ] Quick checks (worse, wrong, cheat) only with a measured full run under a minute and the toolchain here; otherwise "not checked by running"; the "worse" check leads the Later line when skipped.
- [ ] No defence credited that a check didn't test; a winning cheat is the first decision.
- [ ] Ended with "pick a letter or go with the recommendations" and "anything else?".
- [ ] Choices noted on the Script only if the user said yes; changes made through `repo-command-setup`.
- [ ] Discovery never blocked.
