# Author a Discovery-ready benchmark harness

Use this companion when the repository lacks a suitable correctness-gated benchmark that writes Artemis metrics, or needs benchmark tiers for Fast-track Discovery. After the harness exists and has been verified locally, return to [SKILL.md](SKILL.md) to record and verify the Script's build, test and benchmark.

## What a Discovery-ready harness needs

From the repository root, a validation runs the setup commands (build, then test), then the benchmark, on a fresh checkout. The benchmark must:

- be **headless** (no GUI, prompts, or display);
- time only the optimization target (warmup and setup outside the timed region);
- use **representative** inputs generated from a logged seed, sizes varied per run (review step 3);
- write numeric metrics to exactly `artemis_results.json` or `artemis_results.csv` in the command working directory;
- return non-zero on failure;
- leave metric names, units, and direction stable across baseline and versions.

Stdout is for diagnostics. Metrics come only from the results file. See SKILL.md §4 for accepted JSON/CSV shapes.

## Pre-Discovery benchmark review

Run this while writing or adopting the harness, before any Discovery, with or without a runner; repeat step 9 on the runner. Report pass or block to the user, with evidence per step. How-tos are in [ADVANCED.md](ADVANCED.md#benchmark-review-how-tos).

1. **Objective and floors.** Write down the user's objective, constraints and priority cases. Floors are what the user needs, never "today minus a margin"; a broken baseline must fail them. Gate each above the floor by an agreed margin, on a set the agent never sees, and per class, as [benchmark-review](../benchmark-review/SKILL.md#2-check-the-floors) checks. If today's quality comes from a side effect (early stopping, a fixed iteration count), gate on held-out quality at several sizes, not on the training objective.
2. **Complete objectives.** Ask the user what could get worse while the target improves; measure it or say why it cannot change. Compression: a round trip or quality floor (for a model, decision agreement), ratio and both speeds. Training: held-out quality and time to target.
3. **Fresh, varied input every scored run.** Before the timed child starts, generate inputs from a run-time seed (logged), or sample the user's data afresh, at a new path. Vary sizes and shapes per run, with one small case, one off-shape case and one above the largest expected size, and vary every field the real data varies. Rank on a per-unit rate (such as MB/s). Check outputs against a reference computed in that run, not a stored hash.
4. **Gate beyond the generator.** Also gate on real samples and written edge cases the generator never emits: rare valid shapes (raw-unit scales, rare methods); torn, joined or misquoted records; and malformed, negative, infinite and empty input. A lossy or approximate mode that misses its floor fails; never score it at a fallback's size or speed.
5. **Isolate, verify apart, time from outside.** Run the benchmark in a container, as a separate user or under `bwrap`; block only if none works; kill its process group before reading results. Cap it at the agreed cores with a cpuset and measure memory across its whole process tree ([how](ADVANCED.md#make-metrics-comparable-across-runs)). Verify each output in its own fresh process that sees only that output and its decoder or scorer, and give every repetition a fresh, empty working directory. Time the child from outside with a monotonic clock around a blocking wait, not polling; check every repetition and report the first or slowest beside the median. The harness computes every metric.
6. **Tamper guard.** Write `bench/manifest.sha256` over the harness, generators, references and tests, and pin its own hash in the Script's benchmark command, which the repo cannot change: `echo "<sha256>  bench/manifest.sha256" | sha256sum -c --quiet - && sha256sum -c --quiet bench/manifest.sha256 || exit 1` (`shasum -a 256 -c` on macOS). Only a new review rewrites either.
7. **Per-case results** beside the aggregate (geometric mean).
8. **Holdout.** Keep real user data, and any seed for it, outside the repository and the agent's reach, and gate shortlisted versions on it after Discovery with a holdout Script that reads it by absolute path, as in [Compare outside a run](../discovery-start/FAST_TRACK.md#compare-outside-a-run). Never tune against it.
9. **Baseline and noise.** Repeat the unchanged code as scored (`--eval-runs`, SKILL.md §5b) and compute the target's coefficient of variation (CV); every version draws sizes the same way, so the CV includes input variance. Block if it is above half the smallest gain the user cares about; repeat after any harness fix. Record runner, CPU, OS and toolchain.
10. **Independent review.** Hand off to `benchmark-review`; fix each hole it finds here, with a new manifest, then hand back.
11. **Scoring tiers.** Agree with the user: the target `high`, few others; gated guards and per-case metrics `none`.

Write `bench/REVIEW.md`, outside the manifest: objective, cases, metrics (unit, direction, tier), floors, CV, the holdout Script's id, the manifest's sha256, and the reviewer's verdict per attempt. The review passes only when every step passed, `benchmark-review`'s verdict is passed or reused, and the holdout, sha256 and verdict are recorded. Then read the Script's description (`artemis project scripts get <script-id> --project <p>`) and append `Benchmark review passed <date> at <harness gitHash>: holdout <holdout-script-id>, manifest <sha256>, reviewer <verdict>` with `project scripts update <script-id> --project <p> --description "..."` (it replaces the description, not the commands). Otherwise append `Benchmark review open: steps <n>` and do not start a Discovery. Any change to the harness, inputs or gate needs a new review.

## Authoring steps

1. **Choose the metric and direction** with the user when unclear (for example maximize `simulation_fps`, minimize `median_ms`).
2. **Keep or add a correctness gate** (unit/integration test) that fails if optimized behavior changes. The timed path must not weaken that gate.
3. **Create a repository-owned script** (prefer `tools/` or `benchmarks/`) that:
   - removes any stale `artemis_results.json` / `.csv` before measuring;
   - runs or invokes the timed workload;
   - writes a fresh numeric results file atomically when practical.
4. **Prefer wrapping an existing timed binary** when one already prints timing to stdout; do not reinvent timers unless necessary. The harness's job is the Artemis results channel.
5. **Verify locally** from a clean checkout:

```bash
<compile-command>
<test-command>
rm -f artemis_results.json artemis_results.csv
<benchmark-command>
test -f artemis_results.json || test -f artemis_results.csv
```

Confirm the results file contains every intended metric as a number. Then return to SKILL.md §2–§6 to record the build, test and benchmark in a Script and complete runner verification when available.

## Long benchmarks: small, medium and full tiers

Prepare tiers once the user has chosen [Fast-track Discovery](../discovery-start/FAST_TRACK.md). Reuse existing workload-selection options where possible; a custom harness could accept `--tier small`, `--tier medium` and `--tier full`. These are harness options, not Artemis CLI flags.

- Use representative inputs whose sizes nest small ⊆ medium ⊆ full. Preserve the behavior being optimized; fewer tasks or samples must still exercise the target path.
- Keep metric names, units, definitions and directions identical across tiers. Keep the correctness gate at every tier with the same acceptance criteria; reducing benchmark coverage must not disable tests or relax quality tolerances.
- Save one Script per tier with its workload fixed in the benchmark command and the build/test gate included. Record each Script ID, workload and measured duration, and verify each through [SKILL.md](SKILL.md). Keep harness, workload selection and gates outside the Discovery agent's edit scope.

A smaller tier only screens versions: nested inputs do not guarantee the same ranking. Promotion and the final comparison are in [Fast-track Discovery](../discovery-start/FAST_TRACK.md).

## Minimal JSON example

```json
{"simulation_fps": 23.6}
```

Do not put strings, booleans, nested objects, or identifiers in the results file.

## Out of scope here

Language-specific framework tutorials and Discovery task/budget design belong in product docs or a worked example, not in the wiring skill.
