# Author a Discovery-ready benchmark harness

Use this companion when the repository lacks a suitable correctness-gated benchmark that writes Artemis metrics, or needs benchmark tiers for Fast-track Discovery. After the harness exists and has been verified locally, return to [SKILL.md](SKILL.md) to record and verify the Script's build, test and benchmark.

## What a Discovery-ready harness needs

From the repository root, a validation runs the setup commands (build, then test), then the benchmark, on a fresh checkout. The benchmark must:

- be **headless** (no GUI, prompts, or display);
- time only the optimization target (warmup and setup outside the timed region);
- use **deterministic, representative** inputs: read from files, or generated from a fixed, logged seed;
- write numeric metrics to exactly `artemis_results.json` or `artemis_results.csv` in the command working directory;
- return non-zero on failure;
- leave metric names, units, and direction stable across baseline and versions.

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

Confirm the results file contains the ranking metric as a number. Then return to SKILL.md §2–§6 to record the build, test and benchmark in a Script and complete runner verification when available.

## Rules that close common gaps

Start with a simple benchmark that runs end to end. None of these is a default step: add one only when the user picks it in a review, or when a result shows it's needed. They close the gaps `benchmark-review` most often finds:

- **Cases that look like real use.** Inputs from files or a fixed, logged seed, never literals in the timed code. Sizes span the user's range plus one larger, one small and one off-shape case; regimes the user judges apart are separate metrics.
- **Long enough samples, warm-up outside.** Each timed sample takes about a second or more, or loops internally; warm-up iterations run before the timer, as many as the original's per-iteration times show are needed.
- **Fail fast.** Check correctness on small inputs before the full timed run, so a broken version fails in seconds.
- **Consume the output.** Time until the result exists and is used (checksummed, compared or written), so a compiler or a lazy result can't drop the work.
- **Gate every output of every run** against the original implementation, under the equivalence rule agreed with the user, including generated and edge inputs that aren't scored. Run the reference in a separate process or on fresh buffers.
- **Check every class** of output, including rare classes however few samples they have, and a margin above any quality floor.
- **Fresh state each repetition.** No cache, file or process survives from one repetition to the next; with files or data that can be cached, use fresh paths or fresh copies of the same inputs each repetition.
- **Same limits for everyone.** Pin threads, cores and memory in the benchmark command, the same for the original and every version.
- **Keep the scorer out of reach.** Harness, gate, data and expected outputs live outside the target files and are protected by a check on their contents, since target files don't stop edits. A holdout of real data stays outside the repository.

## Long benchmarks: small, medium and full tiers

Prepare tiers once the user has chosen [Fast-track Discovery](../discovery-start/FAST_TRACK.md). Reuse existing workload-selection options where possible; a custom harness could accept `--tier small`, `--tier medium` and `--tier full`. These are harness options, not Artemis CLI flags.

- Use deterministic, representative inputs from the same files or fixed seed, nested small ⊆ medium ⊆ full. Preserve the behavior being optimized; fewer tasks or samples must still exercise the target path.
- Keep metric names, units, definitions and directions identical across tiers. Keep the correctness gate at every tier with the same acceptance criteria; reducing benchmark coverage must not disable tests or relax quality tolerances.
- Save one Script per tier with its workload fixed in the benchmark command and the build/test gate included. Record each Script ID, workload and measured duration, and verify each through [SKILL.md](SKILL.md). Keep harness, workload selection and gates outside the Discovery agent's edit scope.

A smaller tier only screens versions: nested inputs do not guarantee the same ranking. Promotion and the final comparison are in [Fast-track Discovery](../discovery-start/FAST_TRACK.md).

## Minimal JSON example

```json
{"simulation_fps": 23.6}
```

Do not put strings, booleans, nested objects, or identifiers in the results file.

## Out of scope here

Language-specific framework tutorials, statistical methodology beyond a stable ranking metric, and Discovery task/budget design belong in product docs or a worked example—not in the wiring skill.
