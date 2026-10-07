---
name: discovery-visualize
description: Collect a normalized Artemis discovery snapshot and render it as a host-native chart or report. Use when the user wants to graph, chart, plot, compare, visualize, or build a discovery report, canvas, or artifact from a discovery run, or chart a project's Maintain issues by severity and triage.
compatibility: Requires Artemis CLI 1.1.14+ and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.14"
  artemis-platform-min: "3.1.0"
---

# Visualize a discovery run

## At a glance

- **Problem:** Turns a Discovery run into a report someone can take a conclusion away from: one normalized snapshot, then figures that each answer a question and state the answer, on the current agent host.
- **Must be available:** An authenticated CLI for the run's deployment and the discovery run ID.
- **Use / don't use:** Use for graphs, charts, canvases, artifacts, or visual discovery reports, for one run or for comparing every run in a project, and for charting a project's Maintain issues ([references/maintain-report.md](references/maintain-report.md)). Use `discovery-inspect` to diagnose a run, read diffs, or decide what the numbers mean before drawing them.
- **Next skill:** None required. Return to `discovery-inspect` for rationale/diff review, or `discovery-steer` for more versions.

## Requirements

- `artemis status` succeeds on the run's deployment.
- `artemis --version` is at least `artemis-cli-min` (1.1.14, which has `discovery compare`); if it is older, load the skill and follow `cli-setup` first.
- A `run_id`, or a project id to compare its runs. If unknown, ask for the Web UI URL and extract IDs using the router: load the skill and follow `artemis` §2.
- Python 3, stdlib only, to run [scripts/collect_discovery.py](scripts/collect_discovery.py).

## Workflow

1. Confirm authentication and the run ID.
2. **Settle the story.** The user's prompt takes precedence: a chart, chart type, colours, versions or layout they ask for is drawn exactly as asked. When the prompt only says compare, show, chart or visualise the run, build the default, **best vs baseline**, without asking. Other stories (how the search went, what worked) come from the table under *Settle the story first* in [references/report-design.md](references/report-design.md).
3. Collect the snapshot (do not hand-join CLI JSON):

```bash
python3 "<skill-dir>/scripts/collect_discovery.py" \
  --run-id "<run-id>" \
  --output /tmp/discovery-snapshot.json
```

Add `--pareto <metric-a>,<metric-b>` only when the user asked for a Pareto / trade-off view and named the axes, or when one target metric and one quality metric are the obvious pair and you label it as analysis.

4. Read the snapshot. Trust `perMetricWinners`, `rankings`, raw `metrics` means, `runs`, `timesBetter` and `vsBaseline` (falcon's verdict and interval). Default to the raw per-metric winner; if it differs from the eligible winner, explain the failed gate and show the eligible alternative as secondary context. Do not invent a single overall winner. If `perMetricWinners[metric].raw` is `null`, say its `reason` (no stored direction, or no change from Artemis yet) and draw no winner for it. Collect with `--from-dir` only from a folder that holds `comparison.json` from `discovery compare`.
5. Read [references/report-design.md](references/report-design.md) in full: page anatomy, the figure for each story, how to write findings, and the visual standard. The figures are kit functions ([references/report-kit.md](references/report-kit.md)); [references/component-catalog.md](references/component-catalog.md) is only for a Cursor canvas.
6. Build the page with the kit in [references/report-kit.md](references/report-kit.md), on every host: write a short page script, run `build_report.py`, then `check_report.py`, and fix everything it reports. The result is one HTML file that looks the same whichever agent built it. Then read the adapter for how to hand it over:
   - Claude Code: [references/claude-code.md](references/claude-code.md) (publish as an Artifact)
   - GitHub Copilot / VS Code: [references/copilot.md](references/copilot.md) (open in the editor's browser)
   - Cursor: [references/cursor.md](references/cursor.md) (open in the browser; a canvas only when the user wants the chart in the chat)
   - Codex or any other agent: return the file path, and open it in a browser when the host can.
7. Check every number in a title or finding against the snapshot, then look at the rendered page once for collisions and clipping.
8. Hand it over as in *Hand it over* below: a summary of at most four lines, then the link in a box.

The data contract is in [references/data-contract.md](references/data-contract.md).

## 8. Hand it over

Keep the message short: the report says the rest. In this order, and nothing after the box:

1. **At most four lines of summary:** the main finding in one sentence, then up to two supporting facts or one caveat, each with a number. No nested bullets, no restating every figure.
2. **The link in a box, as its own block,** so it cannot be missed:

````text
```
┌──────────────────────────────────────────────────────────┐
│  OPEN YOUR REPORT                                        │
└──────────────────────────────────────────────────────────┘
```

<report link, or the file path on hosts without Artifacts>

Private until you share it from the page's Share menu. The run in Artemis: <Discovery Web UI link>
````

On a host without Artifacts the box says **OPEN YOUR REPORT** and the line under it is the file path, opened in the browser where the host can. Drop the "Private until…" sentence there; keep the Discovery link.

## Recipe rules (Cursor canvas only)

- Select components by the question they answer, not by chart type.
- Copy recipes into the generated artifact; do not import files from this skill.
- Keep snapshot-derived values as props or inline data. Never fetch from a rendered artifact.
- Prefer the smallest composition that answers the question. Do not assemble every example into a dashboard by default.
- Preserve recipe accessibility and truth-rule annotations when adapting its visual design.

## Truth rules

These override any host chart default:

- Rank by Artemis's change against the baseline from `discovery compare` (the collector's `rankings`), not the Composite score (`fitnessScore`), which is a roll-up of the metrics by importance tier. Show the Composite score only as a separate platform score.
- Use the **raw** per-metric winner in the default headline comparison. A per-metric **eligible** winner requires `lifecycle=completed`, `executionStatus=success`, and `experimentStatus != refuted`; when the raw winner fails that gate, warn clearly and show the eligible alternative secondarily.
- Never claim one overall winner for multiple objectives unless the user supplied the aggregation rule.
- The collector reads each metric's direction from the platform only. When `higherIsBetter` is `null`, the metric has no ranking or winner: ask the user which way is better before naming one.
- Missing observations are gaps, not zeroes. `generation_failed` versions never reached the runner.
- Plot `mean` / `min` / `max` / `count`, and individual `runs` when present.
- Verdicts and intervals are falcon's, in `vsBaseline` (`better`, `worse`, `noise`, `pending`), the same ones the Web UI shows; never compute statistics in the page or the conversation. Show the runs beside any verdict. Say "within the noise", not "worse", for `noise`, and "too few runs to tell" for `pending`.
- Colour by better and worse only when the user asks for it.
- Keep measured metrics, AI Metrics (`kind: quality`) and Experiment conclusions visually distinct: AI Metrics get their own figure, never the headline, the forest or a verdict.
- Versions are numbered in the order they were made, so version order is generation order. The trajectory marks the raw winner only; plot running-best only when the user is judging search speed.
- A Pareto front is an analytical view over named axes, not an Artemis verdict.

## Collector flags

```text
--run-id UUID          live CLI collect
--from-dir DIR         fixture/replay collect (run.json, versions.json, metrics.json|stats.json, experiments.json)
--project UUID         every Discovery run in a project, one snapshot each
--output PATH          write JSON; default stdout
--base-url URL         Web UI origin if status cannot infer it
--pareto a,b           optional axes; repeatable
--cli PATH             path to the CLI binary; default `artemis` on PATH
--config PATH          passed to every CLI call as `--config`, e.g. a runner env file
```

The collector already strips logger noise before JSON and joins `observationGroupId` / `experimentId`.

## Checklist

- [ ] Snapshot written; `schemaVersion` is 2.
- [ ] The user's own chart, colours and versions were drawn exactly as asked; otherwise the default, best vs baseline.
- [ ] The title states the main finding and falcon's verdict for it, and every figure has a question heading and bullet findings, with numbers from the snapshot.
- [ ] Each target metric has a baseline, change and raw winner view; any raw/eligible difference is explained without making eligibility the headline.
- [ ] Failed and missing versions are accounted for.
- [ ] The method note or a caption says the verdicts are Artemis's own (`discovery compare`) and gives the runs per side.
- [ ] Handed over with at most four lines of summary and the report link in the box, then the Discovery Web UI link.
