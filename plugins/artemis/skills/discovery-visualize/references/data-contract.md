# Discovery snapshot contract

`schemaVersion` is `1`. The collector is the only writer. Renderers must not recompute winners, percentages, or fitness ranks.

## Top-level fields

| Field | Meaning |
|---|---|
| `collectedAt` | UTC timestamp of the collect |
| `provenance.commands` | CLI commands used |
| `run` | Status, task, counts, baseline SHA/observation, `webUrl` |
| `metrics[]` | `key`, `source`, `higherIsBetter`, `kind` (`target` / `quality` / `harness`) |
| `baseline.metrics` | Per-metric `{mean,min,max,count}` (plus `std`/`ste` when the CLI sent them) |
| `versions[]` | Lifecycle, execution, fitness, experiment fields, per-metric stats + `pctBetter`, `eligible` |
| `experiments[]` | Title, status, confidence, parents, linked version |
| `rankings[metric]` | Best-first rows with `eligible` and experiment status |
| `runningBest[metric]` | Generation order; `mean` is `null` on gaps; `bestVersion`/`bestMean` carry forward |
| `perMetricWinners[metric]` | `{raw, eligible}` — each may be `null` |
| `executionSummary` | Completed / generation_failed / scoring_failed / execution_* / `missingTargetMetrics` |
| `experimentSummary` | validated / refuted / inconclusive counts |
| `pareto` | `null` unless `--pareto` was passed |

`pctBetter` is oriented so positive means better given `higherIsBetter`:

- minimize: `(baseline - value) / |baseline| * 100`
- maximize: `(value - baseline) / |baseline| * 100`

`eligible` is `lifecycle=completed` and `executionStatus=success` and `experimentStatus != refuted`.

`eligible` is renderer safety metadata, not a measurement, validation result, or required headline. The recommended default leads with the raw per-metric winner and uses eligibility only to warn and provide a secondary alternative when the raw winner fails the gate.

## Kinds

- **target** — worker metrics that are not compile/test/benchmark harness timings. These are the default plots.
- **quality** — `source=agent`. Triage signal, not a measured error bound unless the description says otherwise.
- **harness** — `compile_*`, `unit_test_*`, `benchmark_*`. Show on request or in the audit table, not as headline KPIs.

## Do not add

- A single `winner` / `bestVersion` for the whole run
- Confidence intervals or UI verdict colours
- Interpolated zeros for missing versions
- Live fetches from the rendered artifact
