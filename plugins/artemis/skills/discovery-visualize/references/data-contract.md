# Discovery snapshot contract

`schemaVersion` is `2`. The collector is the only writer, and it computes no statistics: changes, intervals and verdicts are falcon's, from `artemis discovery compare` (CLI 1.1.14 or newer). Renderers must not recompute winners, percentages, statistics, or fitness ranks.

## Top-level fields

| Field | Meaning |
|---|---|
| `collectedAt` | UTC timestamp of the collect |
| `provenance.commands` | CLI commands used |
| `run` | Status, task, counts, baseline SHA/observation, `projectName` (from `project get`, or `project list` on CLIs before 1.1.16; `null` if unavailable), `runner` (the runner's name, else its id), `projectUrl` (stable), `webUrl` (the run on newer deployments; if it 404s, link the project and name the Discover page) |
| `metrics[]` | `key`, `source`, `unit` (from the platform, else from the name, e.g. `fps`), `role: "reference"` on a control metric and `reference` on the target it controls, `higherIsBetter` (from the platform; `null` when it stores no direction, and then the metric gets no ranking or winner), `kind` (`target` / `quality` / `harness`) |
| `baseline.metrics` | Per-metric `{mean,min,max,count}` (plus `std`/`ste` when the CLI sent them, `runs`: each individual measurement in order, `q1`/`median`/`q3` from those runs for box plots, and `vsReference`) |
| `baseline.readings` | Readings per metric that falcon compared against |
| `versions[]` | Lifecycle, execution, fitness, experiment fields (title, status, conclusion), `overallVerdict` (falcon's, across the version's metrics), per-metric stats + `runs` (only when the collector had each reading, as for the baseline), `pctBetter`, `timesBetter`, `vsBaseline`, `eligible` |
| `experiments[]` | Title, status, confidence, parents, linked version |
| `rankings[metric]` | Best-first rows with `eligible` and experiment status, ordered by falcon's `pctBetter` (computed from the metric's own aggregator, as the Web UI does). Versions falcon has no change for are left out |
| `runningBest[metric]` | Generation order, by `mean` (a plot of means); `mean` is `null` on gaps; `bestVersion`/`bestMean` carry forward |
| `perMetricWinners[metric]` | `{raw, eligible, unranked}`, the first rows of `rankings`, plus the labels left unranked because falcon has no change for them; `raw` and `eligible` may be `null`. When `raw` is `null` (no stored direction, or no change from falcon yet), `reason` says why |
| `executionSummary` | Completed / generation_failed / scoring_failed / execution_* / `missingTargetMetrics` |
| `experimentSummary` | validated / refuted / inconclusive counts |
| `pareto` | `null` unless `--pareto` was passed |
| `references` | Target and reference metric pairs, such as a Triton kernel and cuBLAS measured in the same benchmark |

`pctBetter` is falcon's `improvementPct`, oriented so positive means better whichever way the metric points. `null` when falcon has no comparison for that version and metric.

`vsReference.ratio` compares a target with its reference in the same measurement group, oriented like `timesBetter`: above 1 means better than the reference. Because both come from the same benchmark process, it cancels machine drift between runs.

With `--project`, the output is `{kind: "project", projectId, runs: [snapshot, ...], skipped: [...]}`, one snapshot per run in creation order.

## Verdicts

Each version's metric carries `vsBaseline`, falcon's comparison against the run's baseline as `discovery compare` returns it:

| Field | Meaning |
|---|---|
| `source` | `"falcon"` |
| `verdict` | `better`, `worse`, `noise` (the interval crosses 0) or `pending` (too few runs to tell) |
| `improvementPct` | Same as `pctBetter` |
| `ciLowPct`, `ciHighPct` | falcon's 95% interval, oriented like `pctBetter`; `null` when there are too few runs |
| `readings` | Readings on this version |
| `recommendedReadings`, `recommendedReadingsReason` | Total readings per side that would settle the verdict, or why there is no count (`settled`, `too_small`, `no_effect`, `no_data`) |
| `spreadPct` | falcon's spread of the readings; `null` with readings on both sides means the readings were identical |

`vsBaseline` is `null` when falcon has no comparison for that metric. Say "within the noise" for `noise`, never "worse".

`timesBetter` is `pctBetter` as a ratio, so `2.0` reads as "2x faster" either way. `null` when there is no `pctBetter` or no direction.

`eligible` is `lifecycle=completed` and `executionStatus=success` and `experimentStatus != refuted`.

`eligible` is renderer safety metadata, not a measurement, validation result, or required headline. The recommended default leads with the raw per-metric winner and uses eligibility only to warn and provide a secondary alternative when the raw winner fails the gate.

## Kinds

- **target** — worker metrics that are not compile/test/benchmark harness timings. These are the default plots.
- **quality**: AI Metrics (`source=agent`): the Orchestrator model scores them from the code. A judgement, not a measurement; never given a verdict in a report.
- **harness** — `compile_*`, `unit_test_*`, `benchmark_*`. Show on request or in the audit table, not as headline KPIs.

## Do not add

- A single `winner` / `bestVersion` for the whole run
- UI verdict colours
- Interpolated zeros for missing versions
- Live fetches from the rendered artifact
