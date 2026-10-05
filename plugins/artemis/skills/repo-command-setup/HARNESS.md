# Author a Discovery-ready benchmark harness

Use this companion when the repository lacks a suitable correctness-gated benchmark that writes Artemis metrics, or needs benchmark tiers or measurement conditions for Fast-track Discovery. After the harness exists and has been verified locally, return to [SKILL.md](SKILL.md) to wire and verify the three commands.

## What Artemis needs

From the repository root, Artemis runs **compile → test → benchmark** on a fresh checkout. The benchmark must:

- be **headless** (no GUI, prompts, or display);
- time only the optimization target (warmup and setup outside the timed region);
- use **deterministic, representative** inputs;
- write numeric metrics to exactly `artemis_results.json` or `artemis_results.csv` in the command working directory;
- return non-zero on failure;
- leave metric names, units, and direction stable across baseline and candidates.

Stdout is for diagnostics. Metrics come only from the results file. See SKILL.md §4 for accepted JSON/CSV shapes.

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

Confirm the results file contains the ranking metric as a number. Then return to SKILL.md §2–§6 to record the three commands and complete runner verification when available.

## Long benchmarks: small, medium and full tiers

Fast-track Discovery minimizes time to trustworthy results using benchmark tiers and parallel runners; `discovery-start` owns the choice and launch. Keep fast benchmarks on a single Discovery. Prepare tiers when staging has been chosen. Reuse existing workload-selection options where possible; a custom harness could accept `--tier small`, `--tier medium` and `--tier full`. These are harness options, not Artemis CLI flags.

- Use fixed, representative inputs nested small ⊆ medium ⊆ full. Preserve the behavior being optimized; fewer tasks or samples must still exercise the target path.
- Keep metric names, units, definitions and directions identical across tiers. Keep the correctness gate at every tier with the same acceptance criteria; reducing benchmark coverage must not disable tests or relax quality tolerances.
- Save one project validation script per tier with its workload fixed in the benchmark command and the build/test gate included. Record each script ID, workload and measured duration, and verify each through [SKILL.md](SKILL.md). Keep harness, workload selection and gates outside the candidate agent's edit scope.

Treat the smaller tiers as screening evidence. Nested inputs do not guarantee the same ranking; `discovery-start` owns promotion and the final full-benchmark comparison.

## Parallel runners: measurement conditions

Speed and memory measurements from different machines are not comparable. A runner pool sharing one name assigns tasks to any member and a Discovery measures its baseline once, so pool members must be interchangeable (same hardware, OS, toolchain and load) for timing or memory benchmarks. Machines that differ need separate runner names and separate runs, each with its own baseline. Accuracy-only benchmarks can use any machine with the required environment. Keep workloads, metric definitions and correctness gates fixed across instances.

Record machine identity and measurement conditions alongside each execution, outside the numeric results file. A shared runner name identifies a group, not a machine; verify the pool members really are interchangeable before trusting timing results from it, and fall back to one machine or separately named runners when they are not. Apply this rule to tier screening and final full-benchmark validation alike.

`discovery-start` owns approval before starting or reusing additional runners and verification of active instances; `runner-setup` owns registration. More capacity does not relax the harness contract.

## Minimal JSON example

```json
{"simulation_fps": 23.6}
```

Do not put strings, booleans, nested objects, or identifiers in the results file.

## Out of scope here

Language-specific framework tutorials, statistical methodology beyond a stable ranking metric, and Discovery task/budget design belong in product docs or a worked example—not in the wiring skill.
