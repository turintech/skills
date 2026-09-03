---
name: discovery-visualize
description: Collect a normalized Artemis discovery snapshot and render it as a host-native chart or report. Use when the user wants to graph, chart, plot, compare, visualize, or build a discovery report, canvas, or artifact from a discovery run.
---

# Visualize a discovery run

## At a glance

- **Problem:** Turns CLI discovery records into one normalized snapshot, then renders that snapshot on the current agent host without changing metric semantics.
- **Must be available:** An authenticated CLI for the run's deployment and the discovery run ID.
- **Use / don't use:** Use for graphs, charts, canvases, artifacts, or visual discovery reports. Use `discovery-inspect` to diagnose a run, read diffs, or decide what the numbers mean before drawing them.
- **Next skill:** None required. Return to `discovery-inspect` for rationale/diff review, or `discovery-steer` for more versions.

## Requirements

- `artemis status` succeeds on the run's deployment.
- A `run_id`. If unknown, ask for the Web UI URL and extract IDs using `artemis` §2.
- Python 3, stdlib only, to run [scripts/collect_discovery.py](scripts/collect_discovery.py).

## Workflow

1. Confirm authentication and the run ID.
2. Collect the snapshot (do not hand-join CLI JSON):

```bash
python3 "<skill-dir>/scripts/collect_discovery.py" \
  --run-id "<run-id>" \
  --output /tmp/discovery-snapshot.json
```

Add `--pareto <metric-a>,<metric-b>` only when the user asked for a Pareto / trade-off view and named the axes, or when one target metric and one quality metric are the obvious pair and you label it as analysis.

3. Read the snapshot. Trust `perMetricWinners`, `rankings`, and raw `metrics` means. Default to the raw per-metric winner; if it differs from the eligible winner, explain the failed gate and show the eligible alternative as secondary context. Do not invent a single overall winner.
4. Identify the user's primary question and read the matching recipes in [references/component-catalog.md](references/component-catalog.md). Copy and adapt only the components needed to answer it; examples are recipes, not runtime imports.
5. Read [references/report-design.md](references/report-design.md), then the matching adapter:
   - Cursor: [references/cursor.md](references/cursor.md)
   - Claude Code: [references/claude-code.md](references/claude-code.md)
   - GitHub Copilot / VS Code: [references/copilot.md](references/copilot.md)
   - Unknown host: write the fallback HTML report from `report-design.md`.
6. Verify labels, units, baseline deltas, gaps, and captions against the snapshot. Return the artifact link plus the Discovery Web UI link.

The data contract is in [references/data-contract.md](references/data-contract.md).

## Recipe rules

- Select components by the question they answer, not by chart type.
- Copy recipes into the generated artifact; do not import files from this skill.
- Keep snapshot-derived values as props or inline data. Never fetch from a rendered artifact.
- Prefer the smallest composition that answers the question. Do not assemble every example into a dashboard by default.
- Preserve recipe accessibility and truth-rule annotations when adapting its visual design.

## Truth rules

These override any host chart default:

- Rank by the raw target metric, not `fitness`. Show fitness only as a separate platform score.
- Use the **raw** per-metric winner in the default headline comparison. A per-metric **eligible** winner requires `lifecycle=completed`, `executionStatus=success`, and `experimentStatus != refuted`; when the raw winner fails that gate, warn clearly and show the eligible alternative secondarily.
- Never claim one overall winner for multiple objectives unless the user supplied the aggregation rule.
- Missing observations are gaps, not zeroes. `generation_failed` versions never reached the runner.
- Plot and caption `mean` / `min` / `max` / `count`. Do not invent confidence intervals or UI `better` / `worse` / `noise` verdicts.
- Keep worker measurements, agent-scored quality metrics, and experiment verdicts visually distinct.
- Default trajectory plots generation-order means and marks the raw winner only. Do not plot running-best unless the user is evaluating search dynamics.
- A Pareto front is an analytical view over named axes, not an Artemis verdict.

## Collector flags

```text
--run-id UUID          live CLI collect
--from-dir DIR         fixture/replay collect (run.json, versions.json, metrics.json|stats.json, experiments.json)
--output PATH          write JSON; default stdout
--base-url URL         Web UI origin if status cannot infer it
--pareto a,b           optional axes; repeatable
```

The collector already strips logger noise before JSON and joins `observationGroupId` / `experimentId`.

## Checklist

- [ ] Snapshot written; `schemaVersion` is 1.
- [ ] Each target metric has a baseline → % change → raw winner view; any raw/eligible difference is explained without making eligibility the headline.
- [ ] Failed and missing versions are accounted for.
- [ ] Caption names the CLI source and that % is mean vs baseline.
- [ ] Host artifact or fallback HTML opened/linked.
- [ ] Discovery Web UI link returned.
