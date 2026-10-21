---
name: benchmark-review
description: "Review a Discovery benchmark for ways to game it before any Discovery runs. Checks that quality floors have a margin, are scored on inputs the code cannot rebuild and keep every class, then has a separate reviewer attack the benchmark from a fixed hack list, with a second round after fixes. Reuses a passed review while the pinned manifest is unchanged, and keeps the review open when the reviewer cannot run. Use after repo-command-setup has built or adopted a harness, when a benchmark review is open, or when asked whether a benchmark can be gamed."
compatibility: Requires Artemis CLI 1.1.14+ (below 1.2.0) and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.14"
  artemis-cli-max: "1.2.0"
  artemis-platform-min: "3.1.0"
---

# Review a benchmark before Discovery

## At a glance

- **Problem:** Discovery optimizes whatever the benchmark rewards. Before any Discovery, a separate reviewer tries the known ways to score better without a real gain, so a gameable benchmark is fixed first.
- **Must be available:** A harness that passes steps 1-9 of `repo-command-setup`'s [benchmark review](../repo-command-setup/HARNESS.md#pre-discovery-benchmark-review), its `bench/REVIEW.md`, and the project Script whose benchmark command pins `bench/manifest.sha256`.
- **Use / don't use:** Use for step 10 of that review, to finish an open review, or to answer "can this benchmark be gamed?". Not for a benchmark a calling skill supplies as known-good, such as the demo's. To build or fix the harness, use `repo-command-setup`.
- **Next skill:** `repo-command-setup` records the verdict in the Script's review line; then `discovery-start`.

## Requirements

- The project and Script id, and the Script's commands and description: `artemis project scripts get <script-id> --project <p>`.
- The harness checkout, with `bench/REVIEW.md` holding the objective, floors, cases and metrics.
- A way to start a separate reviewer: a subagent or a fresh session. Otherwise section 5.

## 1. Reuse an unchanged review

A passed review holds while what it reviewed is unchanged. Reuse it only when all of these hold:

- a `Benchmark review passed` line, on this Script or another Script in the project with the same commands, names the manifest sha256 pinned in this Script's benchmark command;
- `sha256sum -c --quiet bench/manifest.sha256` passes in the checkout (`shasum -a 256 -c` on macOS);
- the objective and floors in `bench/REVIEW.md` are the ones that review checked.

Then the verdict is `reused <that line's date>`: go to section 6. A different benchmark command, tier or size range needs a new review, and so does any doubt.

## 2. Check the floors

Before the reviewer starts, check the floors in `bench/REVIEW.md` against the harness. A miss is a harness fix in `repo-command-setup`:

- **Margin.** The gate demands a margin above the user's floor, agreed with the user and recorded, so a version cannot win by sitting just above it.
- **Inputs the code cannot rebuild.** The floor is also scored on inputs whose distribution lives outside the repository, as the holdout does (HARNESS step 8), not only on a generator the code can read.
- **Every class stays.** Every class or output kind the original produces must remain producible. A per-class floor covers rare classes too, with no minimum sample count.

## 3. Brief the reviewer

Warn the user first: this is the slow part of setup. Start one separate reviewer, a subagent or a fresh session, that reads the harness and edits only the code under optimization. It completes one full pass over every item below; it never skips one or cuts the pass short. Each item must fail the gate or lose score. Record each item's result in `bench/REVIEW.md`.

Hack list:

- in-process and on-disk caches;
- answers keyed on the input's name, size, shape or hash;
- reading the repo's models, data or references;
- work deferred past the timer (lazy results, import time);
- fast paths for the benchmark's exact shapes;
- fast paths outside the scored size range;
- parsing or validation fitted to the generator, looser on input the gate lacks;
- tuning to the selection inputs;
- quality tuned to sit just above the floor;
- dropping rare classes or outputs;
- more cores or memory than the baseline used;
- a process that outlives the gate and rewrites the results;
- state shared between outputs or repetitions;
- empty or NaN output.

## 4. Fix, then a second round

Each win is a hole in the harness: fix it with `repo-command-setup` (a new manifest and a new pinned hash) and record it. After any fix, run a second, time-boxed round with a fresh reviewer, aimed at the fixes and at what the first round reached least. A win in the second round keeps the review open: fix it and run another round, or stop and report the review open.

## 5. When the reviewer cannot run

A safety check, a missing subagent tool or a stopped session can end the reviewer before its pass completes. The review then stays open; never record it as passed. Record `open: reviewer did not complete`, and give the user the next step to run in a fresh session on the same checkout:

```text
Use the Artemis benchmark-review skill on <checkout path> for Script <script-id> in project <project-id>.
```

## 6. Verdict

Write the verdict for this attempt in `bench/REVIEW.md`:

- `passed`: a completed pass found no win, or a completed round after the fixes found none;
- `reused <date>`: section 1;
- `open: <reason>`: anything else.

Then return to `repo-command-setup` to write the Script's review line. Only `passed` or `reused` lets it write passed; `discovery-start` blocks on anything else.
