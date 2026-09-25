# Claude Code adapter

Publish a **self-contained HTML** discovery report as a Claude Code Artifact.

## Build

1. Write one `.html` file in a temporary directory outside the project unless the user asked to keep it.
2. Inline CSS and JavaScript. Zero npm. No backend.
3. Prefer semantic HTML (`header`, `section`, `figure`, `table`, `details`) and hand-built SVG, as in a typical Claude Artifact dashboard.
4. Allowed extra libraries, if needed, come only from Artifact CDN hosts (`cdnjs.cloudflare.com`, `cdn.jsdelivr.net`, `cdn.tailwindcss.com`, `code.jquery.com`). Default to no CDN.
5. Follow [report-design.md](report-design.md): the story, the page anatomy, the figures, and the visual standard.

## Page

Follow the anatomy in [report-design.md](report-design.md): the main finding as the title, a lede, provenance with the Artemis link, the headline comparison, then numbered figures that each carry a question heading and a finding. Do not show execution-success or experiment-status count tiles. With no measured version, show only provenance, progress, and the baseline.

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

- The finding in the title, and a finding under every figure
- Provenance and the Artemis link before any chart
- Individual runs against the baseline band when there are several per version
- `<details>` for the full version table
- Explicit notes for `n=1`, LLM quality scores, and ineligible raw winners without making eligibility the headline
