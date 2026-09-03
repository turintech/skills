# Discovery visualization component catalog

Choose recipes by the user's question. Read only the matching files, copy the
component into the host artifact, and adapt its props to the normalized
snapshot. These files are examples, not an importable runtime package.

## Selection guide

| User question | Primary recipe | Required snapshot fields |
|---|---|---|
| Where did the metric start, and what is the best measured result? | [Baseline comparison](../examples/components/baseline-comparison.tsx) | `baseline.metrics`, `perMetricWinners`, metric metadata |
| Which versions improved or regressed most? | [Version ranking](../examples/components/version-ranking.tsx) | `rankings[metric]`, version URLs |
| How did the metric evolve through the run? | [Metric trajectory](../examples/components/metric-trajectory.tsx) | `runningBest[metric]`, baseline metric, `perMetricWinners[metric].raw` |
| What was each version trying to do? | [Version cards](../examples/components/version-cards.tsx) | `versions`, experiment titles or rationales, version URLs |
| Which ideas or versions build on earlier work? | [Experiment lineage](../examples/components/experiment-lineage.tsx) | `experiments`, parent IDs, linked versions |
| Did failures or eligibility gates affect the result? | [Failure summary](../examples/components/failure-summary.tsx) | `executionSummary`, raw and eligible winners |
| What are the trade-offs between two metrics? | [Pareto scatter](../examples/components/pareto-scatter.tsx) | opt-in `pareto` snapshot field |

## Composition guide

- [Discovery overview](../examples/compositions/discovery-overview.canvas.tsx):
  provenance, version budget, baseline comparison, trajectory, and conditional
  failure accounting. Use for a general “visualize this discovery” request.
- [Version investigation](../examples/compositions/version-investigation.canvas.tsx):
  ranked performance plus expandable intent and platform links. Use when the
  user asks what versions attempted or whether they worked.
- [Experiment story](../examples/compositions/experiment-story.canvas.tsx):
  experiment/version lineage plus focused detail. Use when the user asks how
  ideas accumulated or branched.

Compositions are complete single-file canvases. They intentionally duplicate
small component implementations because generated canvases cannot import local
skill files.

## Adaptation contract

Each component recipe states:

- the question it answers;
- the snapshot fields it expects;
- safe visual customization points;
- semantic constraints that must survive customization.

Keep those constraints when combining recipes:

- Raw per-metric winners remain primary measurements.
- Eligibility is a warning/filter, not a performance verdict.
- Missing observations remain gaps.
- `pctBetter` comes from the collector and stays oriented so positive is better.
- Quality, harness, worker, and experiment-status signals remain distinct.
- Every chart retains metric name, units, source, baseline, and accessible text.

## Do not

- Import recipes from a generated `.canvas.tsx`.
- Build a component merely because data exists; it must answer the request.
- Recompute winners or percentages inside a visual component.
- Include all recipes by default.
