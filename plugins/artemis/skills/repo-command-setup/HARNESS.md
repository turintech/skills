# Author a Discovery-ready benchmark harness

Use this companion when the repository lacks a suitable correctness-gated microbenchmark that writes Artemis metrics. After the harness exists and has been verified locally, return to [SKILL.md](SKILL.md) to wire and verify the three commands.

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
   - writes a fresh numeric results file atomically in the directory from which
     Artemis invoked the command. If measurement runs elsewhere, capture the
     invocation directory before changing directories and publish the completed
     file back there.
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

Run the benchmark a second time after deleting the first result. Confirm its
mtime/content is new and the metric is comparable. Also prove one representative
semantic fault makes the test command fail; a benchmark without a functioning
correctness gate is not Discovery-ready.

## Minimal JSON example

```json
{"simulation_fps": 23.6}
```

Do not put strings, booleans, nested objects, or identifiers in the results file.

## Out of scope here

Language-specific framework tutorials, statistical methodology beyond a stable ranking metric, and Discovery task/budget design belong in product docs or a worked example—not in the wiring skill.
