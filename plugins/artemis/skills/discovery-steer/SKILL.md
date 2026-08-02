---
name: discovery-steer
description: Continue, expand, or redirect an Artemis discovery run, verify its child agent run was attached, and check whether later experiments follow new guidance. Use when the user wants to add budget, steer, redirect, or change the focus of an existing discovery run.
---

# Steer a discovery run

## At a glance

- **Problem:** Adds budget or changes an existing discovery agent's direction without creating a new run.
- **Must be available:** An authenticated CLI and the discovery run ID.
- **Use / don't use:** Use to add budget or give new guidance to an existing run; use `discovery-start` for a new run.
- **Next skill:** Use `discovery-inspect` to evaluate the resulting experiments, versions, metrics, and diffs.

Successful delivery is not proof of compliance. Verify both the agent-run handoff and the work produced afterward.

## 1. Inspect before steering

```bash
artemis --output-format json discovery get "<run-id>"
```

Confirm `status`, `taskDescription`, `targetFiles`, `versionCount`, `numVersions`, and `agentRunId`. Surface conflicts between the requested direction and the original task or targets; target files are guidance, not a guaranteed write boundary.

### Budget gate

- Active with budget remaining: steer directly.
- Terminal: add versions first. If an active run has exhausted its budget, wait for terminal status before continuing:

```bash
artemis discovery continue "<run-id>" --versions <n>
```

Refetch until the run is active with an `agentRunId`, then steer. `continue` expands and restarts the run but cannot carry new guidance; do not reverse this order when both are needed.

## 2. Send the instruction

```bash
artemis --output-format json discovery steer "<run-id>" \
  --message "<new direction>"
```

Add `--model <catalogue-uuid-or-model-type>` only when the user chose a model. Add `--skip-interaction` only when the user wants autonomous continuation.

`discovery steer` responds to the current agent run, follows any child run returned by the platform, repoints the discovery, and verifies the new `agentRunId`. Do not substitute generic `artemis chat send`; it does not perform discovery-specific repointing.

## 3. Verify delivery

Require `verified: true` in JSON output. Then confirm the discovery points at the resulting agent run:

```bash
artemis --output-format json discovery get "<run-id>"
artemis chat messages "<resulting-agent-run-id>"
```

The steering instruction should appear as the child run's user message. If response succeeded but repointing failed, report the parent, child, and discovery IDs from the error; do not send the instruction again blindly.

## 4. Verify behavioral uptake

After the agent has had time to propose or complete another experiment:

```bash
artemis discovery experiments list "<run-id>"
artemis discovery versions list "<run-id>"
```

Read relevant version rationales and diffs with `discovery-inspect`. In-flight work from before the steer may finish; judge uptake from subsequent experiments and code changes. If the agent repeatedly follows the old direction, report that as non-compliance rather than claiming the steer failed to deliver.

## Checklist

- [ ] Original task, targets, status, and current agent run inspected
- [ ] Budget remains, or it was expanded before steering
- [ ] Conflict with the requested direction surfaced
- [ ] `discovery steer` returned a resulting agent ID with `verified: true`
- [ ] Discovery `agentRunId` matches that result
- [ ] Child chat contains the instruction
- [ ] Later experiments and diffs were checked for behavioral uptake
