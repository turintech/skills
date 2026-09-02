# GitHub Copilot / VS Code adapter

Write the same self-contained HTML report as Claude Code, then preview it locally. Copilot has no Artifact/Canvas host.

## Build

- One `.html` file with inline CSS/JS, semantic markup, and SVG charts.
- Follow [report-design.md](report-design.md).
- Default output: a temp path or an untracked file the user can open. Do **not** commit it unless asked.
- Cloud agents cannot assume a local browser; they should still write the file and return its path.

## Preview

In VS Code / Copilot agent mode, open the file in the integrated browser when browser tools are available (`workbench.browser.enableChatTools`, `#browser`). Check that tiles, one target chart, and the audit table render.

If the browser tools are off, return a clickable file path and tell the user to open it.

Do not call `xdg-open` / `open` on a cloud worker.

## Constraints

- No live Artemis calls from the page.
- No Vercel/public deploy unless the user asks.
- Same truth rules as `SKILL.md`: raw vs eligible winners, gaps, no invented CIs.

## Fallback

The HTML **is** the fallback. If even that cannot be written, print the provenance strip and per-metric winner table in chat and say the visual host was unavailable.
