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

Run this while writing or adopting the harness, before any Discovery on it, whether or not a runner is set up yet; repeat step 8 on the runner once the Script passes there. A Discovery agent will exploit any gap, and a benchmark's author rarely finds the gaps that win. Report pass or block to the user, with evidence for each step.

1. **Objective and cases.** Write down the user's objective, constraints and priority cases, at the sizes and shapes they run most, plus one pathological size. Floors are what the user needs, never "today minus a margin": a broken baseline must fail them. Add missing cases, or agree exclusions with the user.
2. **Complete objectives.** Ask the user what could get worse while the target improves, starting from the table below, and measure it or say why it cannot change. Record each metric's unit and direction.
3. **Fresh input every scored run.** Generate each case's content from a seed chosen at run time, at a new path, with fixed sizes and distributions; log the seed. Check the output against a reference computed in that run (a round trip, or the unchanged reference code), not a stored hash, so caches and answers keyed on the input fail.
4. **Verify apart, time from outside.** Verify the produced artefact in a separate clean process that sees only the artefact, never the repo's models, data or reference outputs. Time the whole child process from outside until its output exists. Check the output on every timed repetition, and report the first or slowest beside the median. The harness computes every metric; never record a number the code reports about itself. Include adversarial input in the gate (malformed, negative, infinite, empty), not only realistic input.
5. **Tamper guard.** Write `bench/manifest.sha256` over the harness, generators, references and tests, and start the benchmark command with `sha256sum -c bench/manifest.sha256 || exit 1` (`shasum -a 256 -c` on macOS). Do not pass those files to `discovery create --target-files`. Only a new review rewrites the manifest.
6. **Per-case results.** Write each case's metric beside the aggregate (geometric mean), in absolute units, so one case's regression shows.
7. **Holdout.** Keep a holdout from the user's real data, not the same generator, and gate shortlisted versions on it after Discovery with a holdout Script in place of the tier Script, as in [Compare outside a run](../discovery-start/FAST_TRACK.md#compare-outside-a-run). Never tune against it.
8. **Baseline and noise.** Repeat the unchanged code (`--eval-runs` on the runner, SKILL.md §5b) and compute the target's coefficient of variation (CV). Block if it is above half the smallest gain the user cares about: add runs or steady the runner ([ADVANCED.md](ADVANCED.md)). Record runner, CPU, OS and toolchain.
9. **Independent adversarial review.** A separate reviewer (a subagent or fresh session), allowed to edit only the code under optimization, gets the brief "raise the score without doing the work" and must try each of: in-process and on-disk caches; answers keyed on the input's name, size, shape or hash; reading the repo's models, data or reference outputs; work deferred past the timer (lazy results, import time); looser handling of input the gate lacks; tuning to the selection inputs; empty or NaN output. Each must fail the gate or lose score. If one wins, fix the harness and repeat steps 8 and 9.
10. **Scoring tiers.** Agree with the user: the target `high`, few others (the composite is a weighted sum); gated guards and per-case metrics `none`. `discovery-start` sets them with `discovery metrics-schema set`.

Write `bench/REVIEW.md`, outside the manifest: objective, cases, metrics (unit, direction, tier), floors, CV, the holdout's path, the manifest's sha256, and the reviewer's verdict with each attempt's result. The review passes only when every step passed and those three items are filled in. Then read the Script's description with `artemis project scripts get <script-id> --project <p>` and append `Benchmark review passed <date> at <gitHash>: holdout <path>, manifest <sha256>, reviewer <verdict>` with `project scripts update <script-id> --project <p> --description "..."`, which replaces the description but leaves the commands. Otherwise append `Benchmark review open: steps <n>` and do not start a Discovery. Any change to the harness, inputs or gate needs a new review.

| Domain | Gate (in the scored run) | Ranked | Recorded only |
|---|---|---|---|
| Lossless compression | fresh input decompresses to itself, byte for byte | ratio; compression and decompression speed | peak memory, per-file ratio |
| Lossy compression | quality at or above the user's floor on two metrics, one perceptual (for a model: agreement with the original's decisions) | size at fixed quality, at 2-3 operating points | per-input quality |
| ML training | held-out quality at or above the target | time to target | final loss |
| Kernels | outputs within tolerance across shapes and distributions | time at the user's shapes | time per shape |

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
