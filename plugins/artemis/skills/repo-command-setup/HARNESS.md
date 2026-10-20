# Author a Discovery-ready benchmark harness

Use this companion when the repository lacks a suitable correctness-gated benchmark that writes Artemis metrics, or needs benchmark tiers for Fast-track Discovery. After the harness exists and has been verified locally, return to [SKILL.md](SKILL.md) to record and verify the Script's build, test and benchmark.

## What a Discovery-ready harness needs

From the repository root, a validation runs the setup commands (build, then test), then the benchmark, on a fresh checkout. The benchmark must:

- be **headless** (no GUI, prompts, or display);
- time only the optimization target (warmup and setup outside the timed region);
- use **deterministic, representative** inputs;
- write numeric metrics to exactly `artemis_results.json` or `artemis_results.csv` in the command working directory;
- return non-zero on failure;
- leave metric names, units, and direction stable across baseline and versions.

Stdout is for diagnostics. Metrics come only from the results file. See SKILL.md §4 for accepted JSON/CSV shapes.

## Pre-Discovery benchmark review

Run this once the Script has passed on the intended runner, before the first Discovery on that benchmark: a benchmark that runs is not yet one that represents the user's problem. Report pass or block to the user, with the evidence for each step.

1. **Objective and cases.** Write down the user's objective, constraints and priority cases. Map each case to fixed inputs and check that they reach the optimized path at realistic sizes, hard cases included. Add missing cases, or agree exclusions with the user.
2. **Missing outcomes.** Ask the user what could get worse while the ranking metrics improve, and measure each essential outcome or say why it cannot change. Lossy compression needs output quality against the original as well as size or speed, with an agreed quality floor when quality is a constraint. Record each metric's unit, direction and how readings are aggregated.
3. **Gate versus ranking.** Correctness tests and quality floors belong in the build/test gate: failing rejects a version, passing earns nothing. Rank valid versions only by benchmark metrics. Keep the inputs that choose a version apart from those that judge it: freeze the selection inputs, and keep a fixed holdout of the user's cases to check shortlisted versions after Discovery with a holdout Script in place of the tier Script, as in [Compare outside a run](../discovery-start/FAST_TRACK.md#compare-outside-a-run). Never tune against holdout scores or change either set to favor a version. Never pass harness, input or gate files to `discovery create --target-files`.
4. **Real baseline and noise.** Run the unchanged code repeatedly on the fixed inputs on the intended runner, in fresh processes with consistent warmup (`--eval-runs`, SKILL.md §5b). Record each reading, the spread and the runner conditions; investigate drift rather than keep a favorable reading.
5. **Adversarial try.** Try at least one shortcut: skipped work, cached answers, lost quality, or an empty, failed or NaN result. Confirm the gate rejects it or the metrics expose it. If it would win, fix the benchmark and repeat steps 4 and 5.

Start the Discovery only after every step passes. Record the pass in the Script's description so later sessions can reuse it: read it with `artemis project scripts get <script-id> --project <p>`, then append `Benchmark review passed <date> at <gitHash>` with `project scripts update <script-id> --project <p> --description "..."`, which replaces the description but leaves the commands. Any later change to the benchmark, its inputs or the gate needs a new review.

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

Confirm the results file contains every intended metric as a number. Then return to SKILL.md §2–§6 to record the build, test and benchmark in a Script and complete runner verification when available; run the [pre-Discovery benchmark review](#pre-discovery-benchmark-review) once that Script passes on the runner.

## Long benchmarks: small, medium and full tiers

Prepare tiers once the user has chosen [Fast-track Discovery](../discovery-start/FAST_TRACK.md). Reuse existing workload-selection options where possible; a custom harness could accept `--tier small`, `--tier medium` and `--tier full`. These are harness options, not Artemis CLI flags.

- Use fixed, representative inputs nested small ⊆ medium ⊆ full. Preserve the behavior being optimized; fewer tasks or samples must still exercise the target path.
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
