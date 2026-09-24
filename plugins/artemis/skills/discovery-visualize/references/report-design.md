# Shared discovery report design

Render the snapshot. Do not re-join CLI JSON. Headings state evidence, not slogans.

## Recommended default

Users may request any presentation. Without further direction, optimize the opening for one left-to-right question: where did the metric start, where is the best measured version, and how large is the change?

For each target metric:

1. **Neutral title** — `<metric>: baseline vs best measured version`. Keep values out of the title; the comparison below owns them.
2. **Compact provenance** — project/run identity, status, baseline SHA, `collectedAt`, and a prominent Web UI link.
3. **Version-budget progress** — `versionCount` / `numVersions` when the host has a compact progress primitive.
4. **Baseline-to-best comparison** — baseline mean → directional arrow with `pctBetter` above it → raw per-metric winner mean and version label. Include units and observation counts.
5. **One trajectory per target metric** — generation-order means with a baseline reference and a mark on the raw per-metric winner (`perMetricWinners[metric].raw`). Gaps stay empty. Do not plot a running-best overlay unless the user is evaluating search speed.
6. **Focused candidate** — the raw winner's experiment title/status, quality metrics when present, and one-line rationale.
7. **Failure accounting** — show a concise warning only when versions failed, target metrics are missing, or the raw winner is ineligible.
8. **Audit table** — every version: lifecycle, execution, fitness, target means, % vs baseline, experiment status. Collapse it if the host allows progressive disclosure.

Use `perMetricWinners[metric].raw` for the default comparison. Do not introduce “eligible” in the title or primary comparison. If raw and eligible differ, retain the raw result as the measured headline, add a warning that names the failed gate, and show the eligible alternative as secondary context. Eligibility is a report-safety filter, not a measurement or statistical conclusion.

Do not show execution-success or experiment-status counts as headline tiles by default. They add little when healthy. Keep experiment details in a secondary or collapsible section; surface counts only when the user asks or when a failure pattern is itself the finding.

### Sparse and multi-metric states

- With a baseline but no measured version, show provenance, progress, and the baseline only. Omit the arrow, uplift, winner, trajectory, and empty tables.
- With measured versions but no eligible winner, still show the raw winner and explain the gate failure.
- With multiple target metrics, render one baseline-to-best comparison and trajectory per metric. Never create an aggregate winner unless the user supplies the aggregation rule.

Optional, only when the snapshot includes them or the user asked:

- Pareto scatter of two named axes. Caption: analytical view, not a verdict. Label only non-dominated points.
- Grouped bars when the same metric family has shape/batch keys (for example `m=1` / `m=8` / `m=32`).
- Experiment counts as compact secondary stats, not a fake donut of “success”.

## Captions

Every plot names:

- the metric key and units
- that values are **means** (and `n` / min / max when `count != 1`)
- the baseline SHA
- the source: `artemis discovery metrics --all --stats`

State that % is mean vs baseline, not an Artemis statistical verdict.

## Interaction

Keep it small: hover tooltips, a rank-by or focus control, and collapsible tables. No live polling. Refresh = re-run the collector and rewrite the artifact.

## Accessibility and tone

- Charts need a title, axis labels with units, and an accessible name.
- Support light and dark if the host has a theme hook; otherwise follow `prefers-color-scheme`.
- Separate factual summary from editorial analysis. If you write an interpretive heading (“the search converges late”), the figure body must show the generation-order mean series and the raw-winner mark that justify it.
- Do not colour bars as better/worse/noise.

## Fallback HTML

If the native host surface is missing, write one self-contained `.html` file (inline CSS/JS, no npm). Prefer semantic HTML + SVG. Put it outside the repository unless the user asks to keep it. Include the same sections as the minimum report.
