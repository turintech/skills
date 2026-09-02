# TurinTech AI Skills

A portable [Agent Skills](https://agentskills.io) marketplace by [TurinTech AI](https://www.turintech.ai).

The canonical source is this repository. One skill directory is the source of truth; do not fork copies per agent.

## Plugins

- **artemis** — Code optimization, analysis, and validation at scale powered by [Artemis](https://www.turintech.ai).

## Installation

The skill format is shared. How you install it depends on the agent.

### Claude Code

Add the marketplace, then install the plugin:

```
/plugin marketplace add turintech/skills
/plugin install artemis@skills
```

Update with `/plugin marketplace update skills`.

### Cursor

Cursor loads project skills from `.agents/skills/` or `.cursor/skills/`, and also discovers `.claude/skills/`. Copy or submodule the skill folders you need:

```text
plugins/artemis/skills/<skill-name>/
```

into one of those directories (the folder name must match the skill `name`). Personal installs can go in `~/.cursor/skills/` or `~/.agents/skills/` on the machine where the agent runs. Cloud Agents only see project skills in the repo.

### GitHub Copilot / VS Code

Copy the same skill folders into `.github/skills/`, `.agents/skills/`, or `.claude/skills/` in the workspace, or into `~/.copilot/skills/` / `~/.agents/skills/` for a personal install. Skills appear as slash commands and can also load from description.

## Artemis skills

| Skill | Use when |
|---|---|
| `artemis` | Classify a request and route to the right skill |
| `cli-setup` | Install or authenticate the CLI |
| `runner-setup` | Install, register, or start a runner |
| `repo-prepare-fork` | Fork or mirror a repository you do not control |
| `repo-command-setup` | Derive and verify compile/test/benchmark commands |
| `workspace-setup` | Persistent incremental build cache |
| `project-import` | Import a branch as an Artemis project |
| `discovery-start` | Create a discovery run |
| `discovery-inspect` | Interpret status, versions, metrics, and diffs |
| `discovery-visualize` | Chart or report a discovery run on Cursor, Claude Code, or Copilot |
| `discovery-steer` | Continue, expand, or redirect a live run |
| `execution-log-inspect` | Read runner task logs |
| `maintain` | Scan, triage, fix, and ship code-health issues |
