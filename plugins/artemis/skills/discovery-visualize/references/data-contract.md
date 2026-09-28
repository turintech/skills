# Discovery snapshot contract

`schemaVersion` is `1`. The collector is the only writer. Renderers must not recompute winners, percentages, statistics, or fitness ranks.

## Top-level fields

| Field | Meaning |
|---|---|
| `collectedAt` | UTC timestamp of the collect |
| `provenance.commands` | CLI commands used |
| `run` | Status, task, counts, baseline SHA/observation, `projectName` (from `project list`; `null` if unavailable), `runner` (the runner's name, else its id), `projectUrl` (stable), `webUrl` (the run on newer deployments; if it 404s, link the project and name the Discover page) |
| `metrics[]` | `key`, `source`, `unit` (from the platform, else from the name, e.g. `fps`), `role: "reference"` on a control metric and `reference` on the target it controls, `higherIsBetter`, `higherIsBetterInferred` (`true` only when neither the run's schema nor the platform's measurements gave a direction, so it was guessed from the name), `kind` (`target` / `quality` / `harness`) |
| `baseline.metrics` | Per-metric `{mean,min,max,count}` (plus `std`/`ste` when the CLI sent them, `runs`: each individual measurement in order, `q1`/`median`/`q3` from those runs, and `vsReference`) |
| `versions[]` | Lifecycle, execution, fitness, experiment fields (title, status, conclusion), per-metric stats + `runs`, `pctBetter`, `timesBetter`, `vsBaseline` (target metrics), `eligible` |
| `experiments[]` | Title, status, confidence, parents, linked version |
| `rankings[metric]` | Best-first rows with `eligible` and experiment status |
| `runningBest[metric]` | Generation order; `mean` is `null` on gaps; `bestVersion`/`bestMean` carry forward |
| `perMetricWinners[metric]` | `{raw, eligible}` — each may be `null` |
| `executionSummary` | Completed / generation_failed / scoring_failed / execution_* / `missingTargetMetrics` |
| `experimentSummary` | validated / refuted / inconclusive counts |
| `pareto` | `null` unless `--pareto` was passed |
| `references` | Target and reference metric pairs, such as a Triton kernel and cuBLAS measured in the same benchmark |

`pctBetter` is oriented so positive means better given `higherIsBetter`:

- minimize: `(baseline - value) / |baseline| * 100`
- maximize: `(value - baseline) / |baseline| * 100`

`vsReference.ratio` compares a target with its reference in the same measurement group, oriented like `timesBetter`: above 1 means better than the reference. Because both come from the same benchmark process, it cancels machine drift between runs.

With `--project`, the output is `{kind: "project", projectId, runs: [snapshot, ...], skipped: [...]}`, one snapshot per run in creation order.

## Stats

Each version's target metric carries `vsBaseline`, Welch's two-sided t-test of its `runs` against the baseline's `runs`:

| Field | Meaning |
|---|---|
| `test` | `"welch"` |
| `n`, `nBaseline` | Runs on each side |
| `t` | Oriented like `pctBetter`: positive means better |
| `df` | Welch-Satterthwaite degrees of freedom, fractional, never rounded |
| `p` | Two-sided p-value |
| `ciLowPct`, `ciHighPct` | 95% interval of the difference in means as % of the baseline mean, oriented like `pctBetter` |
| `significant` | `ciLowPct > 0`: the interval excludes 0 on the better side |

`vsBaseline` is `null` when either side has fewer than 2 runs, or when neither side varies. An interval wholly below 0 is a real loss; one that crosses 0 is "not significant". The Student-t distribution is computed with the stdlib (regularized incomplete beta), so the collector still needs no packages. Adding it kept `schemaVersion` at 1: the field is additive.

`timesBetter` is the same comparison as a ratio, so `2.0` reads as "2x faster" either way: `value / baseline` when maximizing, `baseline / value` when minimizing. `null` when either is zero or negative.

`eligible` is `lifecycle=completed` and `executionStatus=success` and `experimentStatus != refuted`.

`eligible` is renderer safety metadata, not a measurement, validation result, or required headline. The recommended default leads with the raw per-metric winner and uses eligibility only to warn and provide a secondary alternative when the raw winner fails the gate.

## Kinds

- **target** — worker metrics that are not compile/test/benchmark harness timings. These are the default plots.
- **quality** — `source=agent`. Triage signal, not a measured error bound unless the description says otherwise.
- **harness** — `compile_*`, `unit_test_*`, `benchmark_*`. Show on request or in the audit table, not as headline KPIs.

## Do not add

- A single `winner` / `bestVersion` for the whole run
- UI verdict colours
- Interpolated zeros for missing versions
- Live fetches from the rendered artifact
