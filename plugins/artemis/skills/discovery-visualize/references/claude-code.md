# Claude Code adapter

Publish a **self-contained HTML** discovery report as a Claude Code Artifact.

## Build

1. Build with the kit ([report-kit.md](report-kit.md)): a page script, `build_report.py`, then `check_report.py`. Write files in a temporary directory outside the project unless the user asked to keep them.
2. The built page is one self-contained file: kit, styles and snapshot inlined, no npm, no backend, no CDN.
3. Follow [report-design.md](report-design.md): the story, the page anatomy, the figures, and the visual standard. For a chart the kit does not have, draw SVG with `ArtemisReport.s` in the same style.

## Page

Follow the anatomy in [report-design.md](report-design.md): the main finding as the title, a lede, provenance with the Artemis link, the headline comparison, then numbered figures that each carry a question heading and a finding. Do not show execution-success or experiment-status count tiles. With no measured version, show only provenance, progress, and the baseline.

## Artifact constraints

- One page, no routes, no form storage.
- Do not `fetch` Artemis from the published page. Embed the snapshot.
- Images as data URIs only. Keep the page well under the Artifact size limit.
- Honor `prefers-color-scheme` / `data-theme`.
- Give each SVG a `role="img"` and an `aria-label` that names the metric and baseline.
- Hover tooltips are enough. Do not add zoom/brush unless asked.
- Never name a top-level script variable `top`, `name`, `parent`, `status`, `length` or `origin`: they are browser globals, and a `const top` stops the whole script with nothing on the page to show why.

## Publish

Publish without asking: an Artifact starts private to the user. Hand it over as in SKILL.md *Hand it over*: a summary of at most four lines, then the Artifact link in the **OPEN YOUR REPORT** box, the privacy line and the Discovery Web UI link. Later edits republish the same artifact.

If Artifacts are disabled, leave the local HTML in place and give the file path.

## Patterns to keep

- The finding in the title, and a finding under every figure
- Provenance and the Artemis link before any chart
- Individual runs against the baseline band when there are several per version
- `<details>` for the full version table
- Explicit notes for `n=1`, LLM quality scores, and ineligible raw winners without making eligibility the headline
