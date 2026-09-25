# Cursor adapter

Read the Cursor canvas skill if it is available, then write **one** `.canvas.tsx` beside the chat.

## Location

Write directly to the workspace canvas directory:

`/Users/<user>/.cursor/projects/<workspace>/canvases/<name>.canvas.tsx`

On Linux the home prefix is `/home/<user>`. Do not `mkdir` that directory. Use a kebab-case name such as `<project>-<run-short>-discovery.canvas.tsx`.

## Rules

- Default-export one component.
- Import **only** from `cursor/canvas`.
- Inline the snapshot (or the fields you plot). No `fetch()`, no CLI, no relative imports.
- Omit empty sections. Never invent placeholder series.
- Link the canvas with a markdown path when you mention it.
- Use [component-catalog.md](component-catalog.md) to select question-led recipes.
  Copy the needed implementations into the single canvas file; never import
  from `examples/`.

## Page

Follow the anatomy in [report-design.md](report-design.md) unless the user asked for another design:

1. An H1 that states the main finding, true of the raw measurements on the canvas.
2. Run status, baseline SHA, collection time, and a visible Artemis Discovery link directly below it; `UsageBar` for `versionCount` / `numVersions`.
3. The headline comparison: baseline mean, the change (`timesBetter` or `pctBetter`), the best version's mean, with a small theme-aware SVG arrow, units and counts.
4. Figures in the order the story needs, each with a question as its heading, the chart, and a `Callout` holding the finding.

Do not add execution-success or experiment-status count tiles. When the raw winner is ineligible, keep it in the primary comparison, add a concise warning naming the failed gate, and show the eligible alternative secondarily.

When there is no measured version, show only provenance, progress, and the baseline; omit the arrow and empty charts.

## Mapping

| Snapshot | Canvas primitive |
|---|---|
| Provenance / raw winner | `Stat`, `Callout`, `Text`, `Link`, small theme-aware SVG arrow |
| Finding under a figure | `Callout` |
| Target trajectory | custom SVG: generation-order means, baseline reference, raw-winner point |
| Every run against the baseline band | custom SVG strip plot |
| Ranked % vs baseline | `BarChart` `horizontal` |
| Experiment mix when requested | Secondary `Stat` or `PieChart` of validated/refuted/inconclusive |
| Audit / focused version | `Table` |
| Rank-by / focus | `Select` + `useCanvasState` |
| Version budget | `UsageBar` (`versionCount` / `numVersions`) |
| Winner diff (only if you also fetched it) | `DiffView` / `DiffStats` |
| Pareto | custom SVG: canvas has no scatter-with-labels primitive |

Do not colour bars by statistical verdict. Use fitness only when the user asked to rank by AI score.

The mapping above is a default, not a fixed dashboard. For focused questions,
prefer the matching component or composition recipe and omit unrelated panels.

## Custom SVG

Allowed for Pareto or a raw-winner point mark the line chart cannot express. Keep it flat: host theme tokens via `useHostTheme()` if exported; no gradients, emojis, or box shadows.

## Fallback

If a canvas cannot be written (no canvases directory, or the environment is not Cursor), write the fallback HTML from [report-design.md](report-design.md) and give the file path.
