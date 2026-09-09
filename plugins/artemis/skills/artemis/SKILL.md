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

Artemis evaluates repository code on a user-supplied runner using scripts with ordered `setup`, `benchmark`, and `teardown` commands. Setup normally builds and checks correctness once; benchmark commands measure and may repeat. `repo-command-setup` owns that execution and numeric-results contract. When a clean rebuild is prohibitively expensive, `workspace-setup` owns the persistent cache those commands use.

An **Artemis Branch** (called a `changeset` by the API and CLI) is the preparation workspace: its versioned repository edits, scripts used for validation, runner selection and measurements stay connected. Script templates remain shared at project level; preparing a changeset must not silently overwrite unrelated templates. A **project** imports a repository branch at a specific commit; a **version** is the baseline or an AI-generated candidate; a **discovery run** generates and evaluates versions against a metric.

Use the supplied UI origin for browser links and the API deployment for CLI requests. They may differ on localhost. User-facing machine setup is **Settings → Machines → Connect your machine**; keep `runner` in actual commands and API names.

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
| Benchmark preparation | Build a correctness-gated harness and record a baseline before optimisation | Changeset or local Git branch; runner for final verification |
| Discovery | Generate and assess alternatives using code-based scoring and optional execution measurements | Model and version budget; machine and commands when executing code |
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
- `/projects/<project-id>/branches/<changeset-id>/...`

Extract all available IDs from that URL; do not ask for each separately. Use the deployment base URL shown by the user.

### Return Web UI links

After creating, importing, or reporting a user-visible resource, give the user a clickable Web UI link immediately. Build it from the authenticated deployment base URL and the captured UUIDs:

- project: `<base-url>/projects/<project-id>`
- discovery: `<base-url>/projects/<project-id>/discovery/<discovery-id>`
- discovery version: `<base-url>/projects/<project-id>/discovery/<discovery-id>/versions/<version-id>`
- changeset: `<base-url>/projects/<project-id>/branches/<changeset-id>`

Use Markdown links with a short label such as `Open project` or `Open Discovery`. Keep using UUIDs for CLI commands; a link is a user handoff, not a substitute for verified identifiers.

### Benchmark preparation paths

When an Overview or Prepare Benchmark handoff supplies a changeset ID, keep working in that exact changeset. Repository preparation is not a reason to create another project or changeset.

- **Local agent with Artemis CLI:** use `benchmark-prepare-changeset` to download, edit, save and validate that changeset. With no supplied changeset, inspect existing work and create one only when needed. Check installed CLI capabilities first.
- **Local agent with Git:** use `benchmark-prepare-git` to prepare and test a branch, commit/push within the user's authorisation, then hand back the branch and SHA for selection in Artemis. This path does not mutate an existing Artemis changeset.
- **Artemis agent:** hand off to the Branch’s Metrics → Set up metrics page. The UI's agent action starts a changeset coder; do not start another agent or launch discovery merely to prepare the benchmark.

The payoff is a trustworthy feedback loop for optimisation. A checklist, script definition, local JSON file or saved version is not a validated baseline: distinguish those from successful runner execution and observed metrics.

## 3. Resolve blocking decisions

Raise only rows required by the selected workflow:

| What | Resolve before proceeding | Skill |
|---|---|---|
| CLI | Target deployment and authenticated `artemis status` | `cli-setup` |
| Runner | Approved machine, required toolchain and resources, and availability | `runner-setup` |
| Repository | Importable user-controlled remote, or permission to create a fork or mirror | `repo-prepare-fork` |
| Project | Fresh project for new work, or explicit reuse of the same prior work | `project-import` |
| Commands | Exact verified commands and a suitable correctness-gated benchmark; use `workspace-setup` first when those commands need a persistent cache | `repo-command-setup` |

Maintain needs no runner or benchmark. Discovery can also assess code without running it: use the supported no-execution mode when the user chooses it. A machine is required for script execution, and recorded measurements are required for numerical performance comparisons. Successful logs are execution evidence, not automatically imported metrics. Inspection normally needs only the authenticated CLI and identifiers.

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

For discovery or validation with execution, settle the commands, machine, stopping boundary and any requested metrics and directions; for discovery also settle the task, optional model, and version budget. For Maintain, settle scan/fix scope, model when overriding the default, and whether fixes stop at changesets, branches, or pull requests.

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
- Benchmark preparation in a supplied Artemis changeset: `benchmark-prepare-changeset`
- Benchmark preparation through a local Git branch: `benchmark-prepare-git`
- Repository command derivation, correctness-gated harness authoring, and execution troubleshooting: `repo-command-setup`
- Persistent incremental builds: `workspace-setup`
- Project registration: `project-import`
- Discovery launch: `discovery-start`
- Discovery continuation, budget expansion, steering, or redirection: `discovery-steer`
- Discovery interpretation: `discovery-inspect`
- Runner task diagnostics without host access: `execution-log-inspect`
- Maintain: use the `maintain` skill when present; otherwise inspect `artemis maintain --help` before any mutation

Proceed when every required fact is verified or explicitly chosen. Ask for unresolved choices together and do not re-ask facts the user supplied.
