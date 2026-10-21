---
name: benchmark-review
description: "Have a separate reviewer try to game a Discovery benchmark before any Discovery runs: checks the quality floors, then attacks the benchmark from a fixed hack list, with a second round after fixes, and reuses a passed review while the pinned manifest is unchanged. Use at step 10 of repo-command-setup's benchmark review, to finish an open review, or when asked whether a benchmark can be gamed or reward-hacked. Not for a known-good benchmark a calling skill supplies, such as the demo's."
compatibility: Requires Artemis CLI 1.1.14+ (below 1.2.0) and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.14"
  artemis-cli-max: "1.2.0"
  artemis-platform-min: "3.1.0"
---

# Review a benchmark before Discovery

## At a glance

- **Problem:** Discovery optimizes whatever the benchmark rewards, including ways to score better without a real gain. A reviewer who did not build the benchmark looks for those ways first.
- **Must be available:** A harness that passes steps 1-9 of `repo-command-setup`'s [benchmark review](../repo-command-setup/HARNESS.md#pre-discovery-benchmark-review), with their evidence in `bench/REVIEW.md`.
- **Use / don't use:** Use for step 10 of that review, to finish an open review, or to answer "can this benchmark be gamed?". To build or fix the harness, use `repo-command-setup`.
- **Next skill:** `repo-command-setup` writes the Script's review line from this skill's verdict; then `discovery-start`.

## Requirements

- `artemis --version` meets `metadata.artemis-cli-min`. Otherwise `cli-setup`.
- The harness checkout, with `bench/REVIEW.md` holding the objective, floors, cases, metrics and the evidence for steps 1-9.
- The Script's commands and description: `artemis project scripts get <script-id> --project <p>`. With no Script yet (a local review before import), skip section 1 and keep the verdict in `bench/REVIEW.md`; `repo-command-setup` writes the line once the Script exists.
- A separate reviewer: a subagent, or this session when it was started fresh from section 5's line. Without one, the review stays open (section 5).

## 1. Reuse an unchanged review

Reuse a passed review only when all of these hold:

- a `Benchmark review passed` line, on this Script or another Script in the project with the same commands, names the manifest sha256 that this Script's benchmark command pins;
- this Script's own guard passes in the checkout: `echo "<pinned sha256>  bench/manifest.sha256" | sha256sum -c --quiet - && sha256sum -c --quiet bench/manifest.sha256` (`shasum -a 256 -c` on macOS);
- the objective and floors in `bench/REVIEW.md` equal those recorded beside that passed verdict.

Then the verdict is `reused <that line's date>`: go to section 6. A different command, tier or size range needs a new review, and so does any doubt.

## 2. Check the floors

Before the reviewer starts, check that the gate holds each floor in three ways:

- **Margin.** The gate demands a margin above the user's floor, agreed with the user and recorded, so a version cannot win by sitting just above it.
- **Inputs the code cannot rebuild.** Every run also scores the floor on a set the Discovery agent never sees: data, or a generator's parameters, kept on the runner outside the repository and read by the harness by absolute path. Report only pass or fail for it. The repo's generator and samples are readable, so they cannot be the only check.
- **Every class stays.** Every class or output kind the original produces must remain producible, with a per-class floor and no minimum sample count.

If any is missing, record `open: floors` and stop. Fix the harness with `repo-command-setup`, then run this skill again.

## 3. Brief the reviewer

Warn the user first: this is the slow part of setup. Give the reviewer a scratch copy of the checkout, and this brief:

```text
Try to make this benchmark score better without a real gain. Edit only <files under optimization>
in <scratch copy>; never the harness, bench/ or tests. Run the benchmark exactly as the Script
does: <benchmark command>. A win is a change that passes the gate and scores better while doing
the job worse for the user. Complete one full pass: try every item on the hack list below and
report each as item, what you tried, and the result (gate failed, score fell, or win).
```

Hack list:

- in-process and on-disk caches;
- answers keyed on the input's name, size, shape or hash;
- reading the repo's models, data or references;
- work deferred past the timer (lazy results, import time);
- fast paths for the benchmark's exact shapes;
- fast paths outside the scored size range;
- parsing or validation fitted to the generator, looser on input the gate lacks;
- tuning to the inputs the benchmark scores rather than the user's data;
- quality tuned to sit just above the floor;
- dropping rare classes or outputs;
- more cores or memory than the baseline used;
- a process that outlives the gate and rewrites the results;
- state shared between outputs or repetitions;
- empty or NaN output.

Record every row in `bench/REVIEW.md`. A pass that skips an item or ends early is not complete.

## 4. Fix, then a second round

Each win is a hole in the harness. Fix it with `repo-command-setup`, which rewrites the manifest and the pinned hash and repeats HARNESS step 9, then come back here. After any fix, a fresh reviewer runs a second round within a time box agreed with the user, aimed at the fixes and at the items the first round tested least. A win in the second round keeps the review open: record `open: win in round <n>`, then fix it and run another round, or stop.

## 5. When the reviewer cannot run

A safety check, a missing subagent tool or a stopped session can end the reviewer before its pass completes. The review then stays open; never record it as passed. Record `open: reviewer did not complete`, and give the user this line to start a fresh session on the same checkout:

```text
Use the Artemis benchmark-review skill on <checkout path> for Script <script-id> in project <project-id>. This session is the reviewer.
```

A session started from that line did not build the benchmark, so it is the separate reviewer: it runs sections 2-4 itself, then section 6.

## 6. Verdict

Write the verdict for this attempt in `bench/REVIEW.md`, with the date, the manifest sha256 and the floors as checked:

- `passed`: a complete pass found no win, or a complete round after the fixes found none;
- `reused <date>`: section 1;
- `open: <reason>`: anything else.

Then follow the closing paragraph of `repo-command-setup`'s [benchmark review](../repo-command-setup/HARNESS.md#pre-discovery-benchmark-review), with the evidence for steps 1-9 from `bench/REVIEW.md`. Only `passed` or `reused` lets it write the passed line; for `open`, it writes `Benchmark review open: steps 10`, and `discovery-start` blocks.

## Checklist

- [ ] Reuse checked against the pinned manifest, or a new review run.
- [ ] Floors have a margin, an unseen set and every class.
- [ ] One complete pass over the hack list, every row recorded.
- [ ] A second round after any fix.
- [ ] Verdict, manifest sha256 and floors written to `bench/REVIEW.md`.
