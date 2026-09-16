# TurinTech AI Skills

A Claude Code plugin marketplace by [TurinTech AI](https://www.turintech.ai).

## Plugins

- **artemis** — Code optimization, analysis, and validation at scale powered by [Artemis](https://www.turintech.ai).

### Maintain

The `maintain` skill runs Artemis Maintain end to end: rules → scan → triage → fix → branch/PR → sync. It covers:

- Rules from the default catalogue, from a markdown file, or written by the maintain agent (`artemis maintain chat`).
- Coding fixes with `artemis maintain issues fix`, retries and comparisons with `issues fix-runs`, and board lanes with `issues transition`.
- Fixes by experiment with `artemis maintain issues fix --discovery --project <p>`. This goes through the maintain agent, like the UI does, so the issues move lanes. Don't use `discovery create` for this.
- Fixes made in your own checkout, uploaded with `artemis maintain issues submit-local-fix`.

## Installation

Add the marketplace:

```
/plugin marketplace add turintech/skills
```

Install a plugin:

```
/plugin install artemis@skills
```

## Updating

```
/plugin marketplace update skills
```
