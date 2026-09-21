# TurinTech AI Skills

A portable [Agent Skills](https://agentskills.io) marketplace by [TurinTech AI](https://www.turintech.ai).

The canonical source is this repository. One skill directory is the source of truth; do not fork copies per agent.

## Plugins

- **artemis** — Code optimization, analysis, and validation at scale powered by [Artemis](https://www.turintech.ai).

## Installation

The skill format is shared. How you install it depends on the agent. Pin a released tag such as [v1.0.1](https://github.com/turintech/skills/releases/tag/v1.0.1) when you need production-compatible skills. `develop` is the next CLI and platform release and is not a pin.

### Claude Code

```bash
/plugin marketplace add turintech/skills
/plugin install artemis@skills
```

Update with `/plugin marketplace update skills`.

### Cursor

```bash
agent plugin marketplace add https://github.com/turintech/skills.git \
  --git-ref v1.0.1
```

Then install `artemis` from the marketplace. Copying `plugins/artemis/skills/<skill-name>/` into `.agents/skills/`, `.cursor/skills/`, or `.claude/skills/` still works when you need a project-local checkout.

### Codex

```bash
codex plugin marketplace add turintech/skills --ref v1.0.1
```

### GitHub Copilot / VS Code

```bash
gh skill install turintech/skills --all --pin v1.0.1
```

Or copy the same skill folders into `.github/skills/`, `.agents/skills/`, or `.claude/skills/` in the workspace.

## Releasing

Skills are versioned independently of the Artemis CLI and platform. Commits use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). See [RELEASING.md](RELEASING.md).

## Artemis skills

| Skill | Use when |
|---|---|
| `getting-started` | Onboard a new user to a first measured result, in the browser or the terminal |
| `quickstart` | Take a project that already exists in Artemis to its first measured result |
| `ui-walkthrough` | Show the matching Artemis Web UI page while work happens |
| `artemis` | Classify a request and route to the right skill |
| `cli-setup` | Install or authenticate the CLI |
| `runner-setup` | Install, register, or start a runner |
| `repo-command-setup` | Derive, verify, and store compile/test/benchmark commands as a validation script |
| `workspace-setup` | Persistent incremental build cache |
| `project-import` | Import a branch as an Artemis project |
| `discovery-start` | Create a discovery run |
| `discovery-inspect` | Interpret status, versions, metrics, and diffs |
| `discovery-visualize` | Chart or report a discovery run on Cursor, Claude Code, or Copilot |
| `discovery-steer` | Continue, expand, or redirect a live run |
| `execution-log-inspect` | Read runner task logs |
| `maintain` | Scan, triage, fix, and ship code-health issues |

## Versioning

Each skill declares the oldest Artemis CLI it works with, using the Agent Skills spec's fields:

    compatibility: Requires Artemis CLI 1.1.8+ and Artemis Platform 3.1.0+.
    metadata:
      artemis-cli-min: "1.1.8"
      artemis-platform-min: "3.1.0"

Raise `artemis-cli-min` or `artemis-platform-min` in the same commit that makes a skill depend on a newer CLI or platform feature. Run `scripts/check-skills.sh` before pushing; it validates every skill with `skills-ref` (set `SKILLS_REF` to its path) and requires both tags.
