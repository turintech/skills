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

Run this once the Script has passed on the intended runner, before the first Discovery on that benchmark. A benchmark that runs is not yet one that represents the user's problem, and a Discovery agent will exploit any gap in it. Report pass or block to the user, with the evidence for each step.

1. **Objective and cases.** Write down the user's objective, constraints and priority cases. Map each case to fixed inputs that reach the optimized path at the sizes and shapes the user runs most, plus one pathological size. Draw inputs from more than one distribution, and avoid cases whose output is nearly constant. Add missing cases, or agree exclusions with the user.
2. **Complete objectives.** Ask the user what could get worse while the target improves, starting from the domain table below, and measure it or say why it cannot change. Record each metric's unit and direction.
3. **The scored run checks itself.** The benchmark command verifies every output it times (round trip, or expected output within a stated tolerance) and exits non-zero on a mismatch, so a fast wrong answer scores nothing. The harness computes every metric from what the code produced (output sizes, decoded output, time measured outside the code); never record a number the code under test reports about itself.
4. **Tamper guard.** Write `bench/manifest.sha256` over the harness, inputs, expected outputs and tests, and start the benchmark command with `sha256sum -c bench/manifest.sha256 || exit 1` (`shasum -a 256 -c` on macOS). Do not pass those files to `discovery create --target-files`. Only a new review rewrites the manifest.
5. **Per-case results.** Write each case's metric as well as the aggregate (geometric mean across cases), in absolute units, so a regression on one case shows.
6. **Selection and holdout.** Freeze the selection inputs. Keep a fixed holdout from the user's real data, not the same generator, to check shortlisted versions after Discovery with a holdout Script in place of the tier Script, as in [Compare outside a run](../discovery-start/FAST_TRACK.md#compare-outside-a-run). Never tune against holdout scores.
7. **Baseline and noise.** Repeat the unchanged code with `--eval-runs` (SKILL.md §5b), in fresh processes with consistent warmup, and compute the target's coefficient of variation (CV). Block if the CV is above half the smallest gain the user cares about: add runs or steady the runner ([ADVANCED.md](ADVANCED.md)). Record the runner, CPU, OS and toolchain.
8. **Independent adversarial review.** Give a separate reviewer (a subagent or a fresh session) the harness and the brief "raise the score without doing the work", with this list: skip work, return cached or reference outputs, lose quality, break the timing, edit inputs or tests, produce empty or NaN output. Each attempt must fail the gate or lose score. If one wins, fix the harness and repeat steps 7 and 8.
9. **Scoring tiers.** Agree with the user which metrics are scored: the target `high`, few others, because the composite score is a weighted sum. Gated guard metrics and per-case metrics stay measured but unscored (`none`). `discovery-start` sets them with `discovery metrics-schema set`.

Write `bench/REVIEW.md` (objective, cases, metrics with unit, direction and tier, gates, CV, holdout) and cover it with the manifest. Start the Discovery only after every step passes. Record the pass in the Script's description so later sessions can reuse it: read it with `artemis project scripts get <script-id> --project <p>`, then append `Benchmark review passed <date> at <gitHash>` with `project scripts update <script-id> --project <p> --description "..."`, which replaces the description but leaves the commands. Any later change to the benchmark, its inputs or the gate needs a new review.

| Domain | Gate (in the scored run) | Ranked | Recorded only |
|---|---|---|---|
| Lossless compression | decompressed output equals the input, byte for byte | ratio; compression and decompression speed | peak memory, per-file ratio |
| Lossy compression | quality at or above the agreed floor on two metrics, one perceptual | size at fixed quality, or quality at fixed size, at 2-3 operating points | per-input quality |
| ML training | held-out accuracy at or above the target | time to target | final loss |
| Kernels | outputs within tolerance across shapes and distributions | time at the user's shapes | time per shape |
| Query engine | result sets equal the reference | latency over the user's query mix at real data scale | cold versus warm cache |

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
