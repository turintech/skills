---
name: discovery-steer
description: Redirect an active Artemis discovery agent, verify its child agent run was attached, and check whether subsequent experiments follow the new instruction. Use when the user wants to steer, redirect, or change the focus of an existing discovery run.
---

# Steer a discovery run

## At a glance

- **Problem:** Changes an active discovery agent's direction without starting a new discovery.
- **Must be available:** An authenticated CLI and the discovery run ID.
- **Use / don't use:** Use for a new instruction within the existing version budget; use `discovery continue` to add versions to a finished run.
- **Next skill:** Use `discovery-inspect` to evaluate the resulting experiments, versions, metrics, and diffs.

Successful delivery is not proof of compliance. Verify both the agent-run handoff and the work produced afterward.

## 1. Inspect before steering

```bash
artemis --output-format json discovery get "<run-id>"
```

Confirm the current `status`, `taskDescription`, `targetFiles`, `versionCount`, and `agentRunId`. Surface conflicts between the requested direction and the original task or targets; target files are guidance, not a guaranteed write boundary.

Do not steer merely to add budget. For a completed run that needs more versions:

```bash
artemis discovery continue "<run-id>" --versions <n>
```

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
- [ ] Conflict with the requested direction surfaced
- [ ] `discovery steer` returned a resulting agent ID with `verified: true`
- [ ] Discovery `agentRunId` matches that result
- [ ] Child chat contains the instruction
- [ ] Later experiments and diffs were checked for behavioral uptake
