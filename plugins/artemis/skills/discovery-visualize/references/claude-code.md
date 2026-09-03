# Claude Code adapter

Publish a **self-contained HTML** discovery report as a Claude Code Artifact.

## Build

1. Write one `.html` file in a temporary directory outside the project unless the user asked to keep it.
2. Inline CSS and JavaScript. Zero npm. No backend.
3. Prefer semantic HTML (`header`, `section`, `figure`, `table`, `details`) and hand-built SVG, as in a typical Claude Artifact dashboard.
4. Allowed extra libraries, if needed, come only from Artifact CDN hosts (`cdnjs.cloudflare.com`, `cdn.jsdelivr.net`, `cdn.tailwindcss.com`, `code.jquery.com`). Default to no CDN.
5. Follow [report-design.md](report-design.md): compact provenance and Artemis link, version-budget progress, baseline → percentage change → raw winner, generation-order figures, optional Pareto, and collapsible audit tables.

## Recommended opening

Use a neutral metric title without values. Follow it with compact provenance and a progress element, then render baseline mean on the left and the raw per-metric winner on the right with a directional SVG arrow; place the snapshot's `pctBetter` above the arrow. Do not repeat the three values in the title.

Do not show execution-success or experiment-status count tiles by default. If the raw winner is ineligible, keep the measured result primary, add a warning naming the failed gate, and show the eligible alternative as secondary context. With no measured version, omit the arrow and show only provenance, progress, and baseline.

## Artifact constraints

- One page, no routes, no form storage.
- Do not `fetch` Artemis from the published page. Embed the snapshot.
- Images as data URIs only. Keep the page well under the Artifact size limit.
- Honor `prefers-color-scheme` / `data-theme`.
- Give each SVG a `role="img"` and an `aria-label` that names the metric and baseline.
- Hover tooltips are enough. Do not add zoom/brush unless asked.

## Publish

Ask before the first publish. Tell the user the page is uploaded to claude.ai and contains the snapshot (run IDs, metrics, experiment titles).

After approval, publish or update the Artifact and return its URL plus the Discovery Web UI link. Later edits republish the same artifact when the user gives that URL.

If Artifacts are disabled, leave the local HTML in place and give the file path.

## Patterns to keep

- Compact provenance and Artemis link before any chart
- Version-budget progress, then baseline → percentage change → raw winner
- Generation-order means with a mark on the raw winner, not a running-best overlay
- `<details>` tables under each figure
- Explicit notes for `n=1`, LLM quality scores, and ineligible raw winners without making eligibility the headline
