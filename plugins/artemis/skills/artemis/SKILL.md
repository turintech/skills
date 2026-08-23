---
name: artemis
description: Classify an Artemis request, check workflow readiness, surface consequential choices before long-running work begins, and route to the appropriate task-specific skills. Use whenever a user wants to set up, run, resume, inspect, validate, optimize, or maintain code with Artemis.
---

# Start an Artemis workflow

## At a glance

- **Problem:** Classifies the user's goal, identifies blocking decisions before long-running work, and routes to the appropriate task-specific skill.
- **Must be available:** Enough context to determine the intended workflow and inspect any relevant repository, deployment, project, runner, commands, or existing run.
- **Use / don't use:** Use for any new Artemis setup, discovery, validation, maintain, resume, or inspection request; skip it when the requested downstream step is already explicit.
- **Next skill:** There is no fixed next skill; route to the setup, repository-preparation, import, discovery, inspection, or maintain skill selected by the workflow.

## Requirements

- Enough context to identify the user's intended outcome or ask one focused classification question.
- Read access to any relevant repository and available Artemis state needed to distinguish known facts from unresolved choices.

Inspect before asking. Present only facts that remain unresolved and decisions that materially affect cost, runtime, shared infrastructure, repository writes, or result quality.

When the user names a downstream task and supplies its inputs, route directly to that skill after surfacing any unresolved choice required before external writes or long-running work.

## Operating context

Artemis evaluates repository code on a user-supplied runner with root-level `compile`, `test`, and `benchmark` commands. `repo-command-setup` owns that execution and numeric-results contract.

A **project** imports a repository branch at a specific commit; a **version** is the baseline or an AI-generated candidate; a **discovery run** generates and evaluates versions against a metric.

### Official docs

The public product docs live at `https://docs.artemis.turintech.ai`. Recommend the matching page when the user wants to follow along or when answering a conceptual question. Do not treat docs as a substitute for executing the owning skill.

Give a clickable Markdown link with a short label:

- Skills: [Artemis Skills](https://docs.artemis.turintech.ai/features/artemis-agent-skills)
- CLI: [Artemis CLI](https://docs.artemis.turintech.ai/features/artemis-cli)
- API keys: [API Keys](https://docs.artemis.turintech.ai/settings/user-settings#api-keys)
- Runner: [Artemis runner](https://docs.artemis.turintech.ai/features/artemis-runner)
- Project import: [Import a codebase](https://docs.artemis.turintech.ai/project-setup/import-codebase)
- Git credentials: [Git keys](https://docs.artemis.turintech.ai/project-setup/git-keys)
- Commands and metrics: [Custom metrics](https://docs.artemis.turintech.ai/features/custom-metrics)
- Discovery: [Discovery](https://docs.artemis.turintech.ai/optimization/discover)
- Guided demo: [Particle Life tutorial](https://docs.artemis.turintech.ai/optimization/discover/tutorials/particle-life-example)
- Maintain: [Scan](https://docs.artemis.turintech.ai/scan/overview)

## 1. Classify the workflow

| Workflow | Intended outcome | Required infrastructure |
|---|---|---|
| Discovery | Generate and benchmark alternatives to improve a metric | Runner, repository commands, model, version budget |
| Validation | Build, test, and benchmark known code without searching | Runner and repository commands |
| Maintain | Scan, triage, fix, or publish code-health issues | Rules, scope, and push access when publishing |
| Setup | Install or repair a CLI, runner, repository, credential, or harness | Depends on the component |
| Inspection | Resume, monitor, diagnose, or summarize existing work | Existing project or run identifiers |

If the intent is ambiguous, explain the smallest relevant distinction and ask one focused question.

## 2. Inspect current state

Use available local and Artemis state to inspect the repository and its documentation, remote, branch, seed SHA, ownership, working tree, deployment, authentication, imported projects, runners, commands, metrics, and existing run IDs. Do not make external changes during readiness inspection.

### Recover IDs from the Web UI

When resuming existing work, ask the user to paste the URL of the most specific entity they are viewing. Artemis URLs expose the required UUIDs:

- `/projects/<project-id>/...`
- `/projects/<project-id>/discovery/<discovery-id>`
- `/projects/<project-id>/discovery/<discovery-id>/versions/<version-id>`
- `/projects/<project-id>/changesets/<changeset-id>/...`

Extract all available IDs from that URL; do not ask for each separately. Use the deployment base URL shown by the user.

### Return Web UI links

After creating, importing, or reporting a user-visible resource, give the user a clickable Web UI link immediately. Build it from the authenticated deployment base URL and the captured UUIDs:

- project: `<base-url>/projects/<project-id>`
- discovery: `<base-url>/projects/<project-id>/discovery/<discovery-id>`
- discovery version: `<base-url>/projects/<project-id>/discovery/<discovery-id>/versions/<version-id>`
- changeset: `<base-url>/projects/<project-id>/changesets/<changeset-id>`

Use Markdown links with a short label such as `Open project` or `Open Discovery`. Keep using UUIDs for CLI commands; a link is a user handoff, not a substitute for verified identifiers.

## 3. Resolve blocking decisions

Raise only rows required by the selected workflow:

| What | Resolve before proceeding | Skill |
|---|---|---|
| CLI | Target deployment and authenticated `artemis status` | `cli-setup` |
| Runner | Approved machine, required toolchain and resources, and availability | `runner-setup` |
| Repository | Importable user-controlled remote, or permission to create a fork or mirror | `repo-prepare-fork` |
| Project | Fresh project for new work, or explicit reuse of the same prior work | `project-import` |
| Commands | Exact verified commands and a suitable correctness-gated benchmark | `repo-command-setup` |

Maintain needs no runner or benchmark. Inspection normally needs only the authenticated CLI and identifiers.

## 4. Present the readiness brief

Before setup that changes external state or any long-running operation, give the user one concise brief:

```text
Workflow:
Target deployment:
Repository / branch / seed:
Goal and success metric:
Ready:
Missing prerequisites:
Decisions needed:
Expected runtime and persistence:
External changes requiring approval:
```

Omit fields that do not apply. A missing prerequisite is not a user choice. The **seed** is the exact imported commit later checked against a discovery's `baselineVersionSha`.

For discovery or validation, settle the correctness gate, metric and direction, runner, and stopping boundary; for discovery also settle the task, optional model, and version budget. For Maintain, settle scan/fix scope, model when overriding the default, and whether fixes stop at changesets, branches, or pull requests.

## 5. Make long-running work deliberate

Before launching discovery, validation, or Maintain:

1. Estimate runtime from command timings and scope, and confirm the runner or service can remain available.
2. Check queued or running work that could conflict with or delay the operation.
3. Agree on the stopping boundary.
4. Capture project, run, scan, chat, and agent IDs as they are created.
5. Explain what continues platform-side after the interactive session ends and what still requires monitoring.

## 6. Route to the owning skill

- CLI: `cli-setup`
- Runner: `runner-setup`
- Repository ownership: `repo-prepare-fork`
- Repository commands, Discovery-ready harness authoring, and validation: `repo-command-setup`
- Project registration: `project-import`
- Discovery launch: `discovery-start`
- Discovery continuation, budget expansion, steering, or redirection: `discovery-steer`
- Discovery interpretation: `discovery-inspect`
- Runner task diagnostics without host access: `execution-log-inspect`
- Maintain: use the `maintain` skill when present; otherwise inspect `artemis maintain --help` before any mutation

Proceed when every required fact is verified or explicitly chosen. Ask for unresolved choices together and do not re-ask facts the user supplied.
