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

## Mapping

| Snapshot | Canvas primitive |
|---|---|
| Provenance / winners | `Stat`, `Callout`, `Text`, `Link` |
| Target trajectory | `LineChart` with a baseline `referenceLines` entry; categories are `vN` |
| Ranked % vs baseline | `BarChart` `horizontal` |
| Experiment mix | `Stat` or `PieChart` of validated/refuted/inconclusive |
| Audit / focused version | `Table` |
| Rank-by / focus | `Select` + `useCanvasState` |
| Version budget | `UsageBar` (`versionCount` / `numVersions`) |
| Winner diff (only if you also fetched it) | `DiffView` / `DiffStats` |
| Pareto or CI whiskers | custom SVG — canvas has no forest/error-bar primitive |

Do not colour bars by statistical verdict. Use fitness only when the user asked to rank by AI score.

## Custom SVG

Allowed for Pareto or running-best overlays the line chart cannot express. Keep it flat: host theme tokens via `useHostTheme()` if exported; no gradients, emojis, or box shadows.

## Fallback

If a canvas cannot be written (no canvases directory, or the environment is not Cursor), write the fallback HTML from [report-design.md](report-design.md) and give the file path.
