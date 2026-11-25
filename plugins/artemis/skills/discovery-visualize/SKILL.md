---
name: discovery-visualize
description: Collect a normalized Artemis discovery snapshot and render it as a host-native chart or report. Use when the user wants to graph, chart, plot, compare, visualize, or build a discovery report, interactive chart studio, canvas, or artifact from a discovery run.
compatibility: Requires Artemis CLI 1.1.16+ (below 1.2.0) and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.16"
  artemis-cli-max: "1.2.0"
  artemis-platform-min: "3.1.0"
---

# Visualize a discovery run

## At a glance

- **Problem:** Turns a Discovery run into a report someone can take a conclusion away from: one normalized snapshot, then figures that each answer a question and state the answer, on the current agent host.
- **Must be available:** An authenticated CLI for the run's deployment and the discovery run ID.
- **Use / don't use:** Use for graphs, charts, canvases, artifacts, or visual discovery reports, for one run or for comparing every run in a project. Use `maintain` to chart a project's Maintain issues. Use `discovery-inspect` to diagnose a run, read diffs, or decide what the numbers mean before drawing them.
- **Next skill:** None required. Return to `discovery-inspect` for rationale/diff review, or `discovery-steer` for more versions.

## Requirements

- `artemis status` succeeds on the run's deployment.
- `artemis --version` is at least `artemis-cli-min` (1.1.16; from 1.1.20 `discovery compare` names falcon's best version, and from 1.1.25 it carries falcon's quartiles, so older CLIs draw no Best and no boxes, and the page says to update); if it is older, load the skill and follow `cli-setup` first.
- A `run_id`, or a project id to compare its runs. If unknown, ask for the Web UI URL and extract IDs using the router: load the skill and follow `artemis` §2.
- Python 3, stdlib only, to run [scripts/collect_discovery.py](scripts/collect_discovery.py).

## Workflow

1. Confirm authentication and the run ID.
2. **Settle the story.** The user's prompt takes precedence: a chart, chart type, colours, versions or layout they ask for is drawn exactly as asked. One chart asked for by name ("only the forest plot") is that one studio card, `build_studio.py --only`; a full report or "the most important charts" is the chart studio (both in *Interactive studio*). When the prompt only says compare, show, chart or visualise the run, build the default static report, **best vs baseline**, without asking. Other stories (how the search went, what worked) come from the table under *Settle the story first* in [references/report-design.md](references/report-design.md).
3. Collect the snapshot (do not hand-join CLI JSON):

```bash
python3 "<skill-dir>/scripts/collect_discovery.py" \
  --run-id "<run-id>" \
  --output /tmp/discovery-snapshot.json
```

Add `--pareto <metric-a>,<metric-b>` only when the user asked for a Pareto / trade-off view and named the axes, or when one target metric and one quality metric are the obvious pair and you label it as analysis.

4. Read the snapshot. Trust `webUiBest`, `perMetricWinners`, `rankings`, raw `metrics` means, `runs`, `timesBetter`, `vsBaseline` (falcon's verdict and interval) and `steering` (each steer, from the run's chat). Lead with `webUiBest`. `bestLines.lede` and `bestLines.notes` are the sentences that say so, name each measured metric whose own best differs, and flag a stored direction worth checking (`directionChecks` holds those warnings on their own; carry each word for word too, in the chat reply when there is no Best page): put them on the page word for word, whatever page you write (`check_report.py` fails without them; the studio says it in one line); if a raw winner differs from the eligible winner, explain the failed gate and show the eligible alternative as secondary context. Do not invent any other overall winner. If `perMetricWinners[metric].raw` is `null`, say its `reason` (no stored direction, or no change from Artemis yet) and draw no winner for it. Collect with `--from-dir` only from a folder that holds `comparison.json` from `discovery compare`.
5. Read [references/report-design.md](references/report-design.md) in full: page anatomy, the figure for each story, how to write findings, and the visual standard. The figures are kit functions ([references/report-kit.md](references/report-kit.md)); [references/component-catalog.md](references/component-catalog.md) is only for a Cursor canvas.
6. Build the page with the kit in [references/report-kit.md](references/report-kit.md), on every host: write a short page script and run `build_report.py`. Give the user the built page's path in one line at once, and open it where the host can, so they have it whatever happens next. Then run `check_report.py` and fix everything it reports. A studio or `--only` page is checked with `check_report.py --studio` instead (see *Interactive studio*). **The check never stops the flow:** if it can't run (no Chrome, NOT RENDERED) or needs the user's go first, say so in one line, open the page and look at it yourself, and carry on to publish and hand over. The result is one HTML file that looks the same whichever agent built it. Then read the adapter for how to hand it over:
   - Claude Code: [references/claude-code.md](references/claude-code.md) (publish as an Artifact)
   - GitHub Copilot / VS Code: [references/copilot.md](references/copilot.md) (open in the editor's browser)
   - Cursor: [references/cursor.md](references/cursor.md) (open in the browser; a canvas only when the user wants the chart in the chat)
   - Codex or any other agent: return the file path, and open it in a browser when the host can.
7. Check every number in a title or finding against the snapshot, then look at the rendered page once for collisions and clipping.
8. Hand it over as in *Hand it over* below: a summary of at most four lines, then the link in a box.

The data contract is in [references/data-contract.md](references/data-contract.md).

## Hand it over

Keep the message short: the report says the rest. In this order, and nothing after the box:

1. **At most four lines of summary:** open with the first sentence of `bestLines.lede` and its "Best on a single metric instead" sentence when there is one, then the main finding with a number. To point the user at a version other than the Web UI's Best, say it differs from the Web UI's Best and why: which metric, in the direction the project stores. No nested bullets, no restating every figure.
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

## Interactive studio

The static report (steps 5 and 6) is the default when the user only says compare, show, chart or visualise. Build the chart studio for a full report or the most important charts (step 2), and when the user wants to explore the run themselves: switch metrics and views, hide versions, and download any chart as PNG, SVG or CSV. Use it as well to set several Discovery runs of one project side by side as sessions. What each card draws is in [references/studio.md](references/studio.md).

```bash
python3 "<skill-dir>/scripts/build_studio.py" --snapshot /tmp/discovery-snapshot.json --output /tmp/discovery-studio.html
python3 "<skill-dir>/scripts/check_report.py" --studio /tmp/discovery-studio.html
```

- **Simple first, then more detail.** Chart 1 is a plain bar of falcon's Best (`webUiBest`) against the original: the Best's bar always Artemis purple (`--accent`), labelled with one plain phrase from falcon's `improvementPct`, "40.5% better than the original (lower is better)", and nothing else; every Conclusion states a change the same way. No interval, verdict, significance, run count or rerun wording on it, its tooltips or the hero above it. Chart 2 is every version's change as bars in falcon's verdict colours (green improved, amber no significant difference, red regressed). The cards after it add detail. Names are shown in full (models, files, versions), wrapped rather than cut. `tests/test_studio_cards.py` `SimpleFirstTests` holds the page to this.
- `--snapshot` is a run snapshot, or a `--project` snapshot whose runs become sessions, oldest first (a run with no measured version is left out and named). Repeat it to put several in one picker, each with a short `--label` in the same order.
- `--only best|ranked|forest|time|box|table|tradeoff|pareto|ai|sessions` draws that one card on a page of its own. Use it whenever the user names one chart. It exits 2 without writing a page when the data has no such chart; say why and offer the nearest one.
- `--tradeoff X,Y` sets the two metrics the trade-off card opens on, from the collector's `tradeoffMetrics`. Use it when the lead metric is a composite or penalised objective that would squash an axis. `tradeoff` is the main card, opening on both metrics' own values (Within the cap and Artemis's % change one click away); `pareto` (the Trade-off rail item, where the trade-off card can't be drawn) plots raw means on the collector's `--pareto` axes, only when the run has no trade-off card: a page shows one or the other, never both.
- `--failed N:SESSION:VERSIONS` marks versions that failed a check of the user's own, outside the snapshot (N is the `--snapshot`'s position, from 1). Use it only when the user names them. `--title` sets the browser tab's title.
- Run-specific facts come from the collector, never from the page: `--gate-metric` for the run's own gate, a size cap stated in the brief, and `--reference` for models scored outside Discovery (see *Collector flags*).
- The page says how Best was chosen in one line and names each metric whose own best is another version, in place of `bestLines` word for word; `check_report.py --studio` checks those.
- Give the user the built page's path in one line as soon as `build_studio.py` writes it, and open it where the host can. Then check it.
- `check_report.py --studio` needs Chrome or Chromium; without one it fails with NOT RENDERED. Fix everything it reports. If it can't run, or needs the user's go first, say so in one line and carry on: never stop before the page is published and handed over. It also fails a "Better on both" corner or an axis title that disagrees with `metrics[].higherIsBetter`, and an empty Conclusion bullet.
- **Look at it before you publish.** Add `--shots /tmp/studio-shots` to the check, open both pictures (desktop and phone width), and check:
  1. each axis's better direction matches `metrics[].higherIsBetter`;
  2. no empty bullets;
  3. no overlapping or clipped labels;
  4. the headline matches `webUiBest`;
  5. every number in a title is in the snapshot.

  Fix, rebuild and check again, then hand the page over as in step 8. When the check didn't run, hand it over anyway with the one-line note. On Claude Code, publish it with `capabilities: {downloads: true}` so the Download buttons save files.

## Recipe rules (Cursor canvas only)

- Select components by the question they answer, not by chart type.
- Copy recipes into the generated artifact; do not import files from this skill.
- Keep snapshot-derived values as props or inline data. Never fetch from a rendered artifact.
- Prefer the smallest composition that answers the question. Do not assemble every example into a dashboard by default.
- Preserve recipe accessibility and truth-rule annotations when adapting its visual design.

## Truth rules

These override any host chart default:

- The headline version is the Web UI's Best (`webUiBest`, falcon's pick by the highest Composite score), and the page says that is how it was chosen. When a measured metric's own best version differs, say so up front. Without a Web UI Best, lead with the raw winner on the target metric and say why.
- Rank versions within a metric by Artemis's change against the baseline from `discovery compare` (the collector's `rankings`). The Composite score (`fitnessScore`) is a roll-up of the metrics by importance tier: it picks the headline version, never a per-metric rank or a verdict.
- Use the **raw** per-metric winner for each metric's own best. A per-metric **eligible** winner requires `lifecycle=completed`, `executionStatus=success`, and `experimentStatus != refuted`; when the raw winner fails that gate, warn clearly and show the eligible alternative secondarily.
- Never claim one overall winner for multiple objectives unless the user supplied the aggregation rule. The Web UI's Best is the platform's own rule (the Composite score): name it as that, not as the best on every metric.
- The collector reads each metric's direction from the platform only. When `higherIsBetter` is `null`, the metric has no ranking or winner: ask the user which way is better before naming one.
- Missing observations are gaps, not zeroes. `generation_failed` versions never reached the runner.
- Plot `mean` / `min` / `max` / `count`, and individual `runs` when present.
- Verdicts and intervals are falcon's, in `vsBaseline` (`better`, `worse`, `noise`, `pending`), the same ones the Web UI shows; never compute statistics in the page or the conversation. Show the runs beside any verdict. Say "within the noise", not "worse", for `noise`, and "too few runs to tell" for `pending`.
- On a page you write, colour by better and worse only when the user asks for it; the studio's colours are falcon's verdicts and stay as built.
- Keep measured metrics, AI Metrics (`kind: quality`) and Experiment conclusions visually distinct: AI Metrics get their own figure, never the headline, the forest or a verdict.
- Versions are numbered in the order they were made, so version order is generation order. The version chart shows search progress: the leader so far and each new leader, read from the collector's `runningBest`, with no claim that one leader is clear of another.
- A Pareto front is an analytical view over named axes, not an Artemis verdict: the collector stores every one (`fronts`, a plain dominance rule on falcon's means) and no page works one out. Anything the studio works out itself, rather than reads from Artemis, is said in its card's ⓘ as "worked out on this page from Artemis's numbers" (`here()` in `assets/studio-core.js`); the static report kit keeps its own label.

## Collector flags

```text
--run-id UUID          live CLI collect
--from-dir DIR         fixture/replay collect (run.json, versions.json, metrics.json|stats.json, experiments.json)
--project UUID         every Discovery run in a project, one snapshot each
--output PATH          write JSON; default stdout
--base-url URL         https Web UI origin the page links to, if status cannot infer it
--pareto a,b           optional axes; repeatable
--cli PATH             path to the CLI binary; default `artemis` on PATH
--config PATH          passed to every CLI call as `--config`, e.g. a runner env file
--ssl-cert-file PATH   passed to every CLI call, for a deployment whose TLS uses its own CA
--keep-raw-text        keep runner names, hosts and absolute paths in the text (replaced by default: pages get published)
--gate-metric KEY      the run's own 0/1 gate metric (1 = passed): a version below 1 is never ranked, a winner or on a front.
                       Default: the run's one metric named as a gate (eligible, gate, gate_ok, ...); `none` turns it off
--size-cap SIZE        the run's size cap, e.g. "1.3 GB", used instead of reading one from the brief
--budget-metric KEY    the byte-unit metric a size cap applies to; needed when the run has more than one
--reference SPEC       label=NAME,file=PATH[,note=PATH][,failures=PATH]: a model the run's referee scored outside
                       Discovery, as a JSON object of readings on this run's metric keys; repeatable
```

A size cap the brief states ("at most N bytes", "under 1.3 GB", "Size cap: 1.3 GB", "max 1.3 GB", "fit in 1.3 GB", "<= 500 MiB") is read without a flag (`--size-cap` overrides it), and applies to the run's one byte-unit metric; with several, to the one `--budget-metric` names, or else to the only one written in the cap's own unit (`model_bytes` for a cap in bytes beside `model_size_mb`). Otherwise none, and the collector does not guess. Fields and file formats: [references/data-contract.md](references/data-contract.md).

The collector already strips logger noise before JSON and joins `observationGroupId` / `experimentId`.

## Checklist

- [ ] Snapshot written; `schemaVersion` is 2.
- [ ] The user's own chart, colours and versions were drawn exactly as asked; otherwise the default, best vs baseline.
- [ ] The title states the main finding and falcon's verdict for it, and every figure has a question heading and bullet findings, with numbers from the snapshot.
- [ ] Each target metric has a baseline, change and raw winner view; any raw/eligible difference is explained without making eligibility the headline.
- [ ] Failed and missing versions are accounted for.
- [ ] The method note or a caption says the verdicts are Artemis's own (`discovery compare`) and gives the runs per side.
- [ ] The built page's path was given as soon as it was written; the page was handed over even if the render check couldn't run (said in one line).
- [ ] Studio only: `check_report.py --studio --shots` passes, and both pictures were checked against the five points under *Interactive studio*, or a one-line note says why the check didn't run.
- [ ] Handed over with at most four lines of summary and the report link in the box, then the Discovery Web UI link.
