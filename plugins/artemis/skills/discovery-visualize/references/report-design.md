# Shared discovery report design

Render the snapshot. Do not re-join CLI JSON. Headings state evidence, not slogans.

## Minimum report

1. **Provenance** — project/run IDs, status, `versionCount` / `numVersions`, baseline SHA, `collectedAt`, Web UI link.
2. **Execution outcomes** — completed, generation_failed, execution failed, experiment mix.
3. **One baseline-relative view per target metric** — generation-order trajectory with a baseline reference and a running-best overlay. Gaps stay empty.
4. **Headline tiles** — one tile per target metric: raw-best value, % vs baseline, version label, and whether that version is eligible. If raw and eligible differ, show both or footnote the ineligible raw best.
5. **Focused candidates** — raw and eligible winners: experiment title/status, quality metrics, one-line rationale.
6. **Missing / failure accounting** — list `generation_failed` and `missingTargetMetrics`.
7. **Audit table** — every version: lifecycle, execution, fitness, target means, % vs baseline, experiment status. Collapse it if the host allows progressive disclosure.

Optional, only when the snapshot includes them or the user asked:

- Pareto scatter of two named axes. Caption: analytical view, not a verdict. Label only non-dominated points.
- Grouped bars when the same metric family has shape/batch keys (for example `m=1` / `m=8` / `m=32`).
- Experiment counts as compact stats, not a fake donut of “success”.

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
- Separate factual summary from editorial analysis. If you write an interpretive heading (“the search converges late”), the figure body must show the running-best series that justifies it.
- Do not colour bars as better/worse/noise.

## Fallback HTML

If the native host surface is missing, write one self-contained `.html` file (inline CSS/JS, no npm). Prefer semantic HTML + SVG. Put it outside the repository unless the user asks to keep it. Include the same sections as the minimum report.
