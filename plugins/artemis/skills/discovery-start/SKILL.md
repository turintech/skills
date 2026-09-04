---
name: discovery-start
description: Start an Artemis discovery run — create a validation script, pass it to discovery create, wait for the baseline to finalize, and verify it actually explored. Use when the user wants to start discovery, launch a discovery run, or create a discovery experiment.
---

# Start a discovery run

## At a glance

- **Problem:** Creates a discovery run from a project validation script, waits for baseline finalization, and confirms that the run actually explored versions.
- **Must be available:** An authenticated CLI, a user-confirmed online runner, an imported project UUID, a validation script built from verified commands, and the required benchmark metrics.
- **Use / don't use:** Use only after runner, project, command, and metric readiness are resolved; use `discovery-inspect` rather than this skill for post-launch interpretation.
- **Next skill:** Use `discovery-inspect` after baseline finalization and the exploration sanity check, or return to `project-import` if a baseline failure leaves the project unusable.

## Requirements

- `artemis status` succeeds on the target deployment.
- An imported project UUID from `project-import`.
- Verified, self-contained root-level commands from `repo-command-setup`, stored as a project validation script.
- A benchmark that writes numeric `artemis_results.json` or `.csv` as defined in `repo-command-setup` §4, unless qualitative-only optimization is deliberate.
- A user-confirmed runner that is online and compatible with those commands.
- Optionally `jq`. Snippets below use it to filter `--output-format json`, but it is just one option — any JSON filter works (e.g. `python3 -c`).

## Model selection

Direct creation requires `--model`. It accepts either a model catalogue UUID or a model-type code. Guided `--setup` may defer the choice, but a model must be set before setup completes.

```bash
artemis model list --help
artemis model list
```

Inspect the current model list, present meaningful choices when the user has not selected one, and record the chosen UUID or model-type code. Only listed models can be used by agents.

## 1. Create the run

Confirm which runner to use before `discovery create`; do not select one merely because it is online. If the project has a default (`artemis project runner get --project "<project-uuid>"`), confirm it remains appropriate. If no runner was named and several are online, list them and ask.

Check whether the project already has a queued or running discovery:

- Queuing is **per runner**: runs on one runner serialize; runs on different runners can execute concurrently.
- An offline runner blocks its queue indefinitely, including later work assigned to it.

```bash
artemis --output-format json discovery list --project "<project-uuid>" \
  | jq -r '.docs[]?
      | select(.status=="created" or .status=="running" or .status=="awaiting_approval")
      | "\(.id) \(.status) vc=\(.versionCount)"'
```

Choose whether to accept serialization, use another runner, or provision one. Never cancel queued or running work without user confirmation; cancellation retains its versions, experiments, and logs for inspection.

Execution runs require a validation script. `--compile-cmd`, `--test-cmd`, and `--benchmark-cmd` are legacy run-level fields and do **not** satisfy that requirement. Creating without `--script` or a project default fails with `NoDefaultValidationScriptError`.

List existing scripts, or create one from the verified commands:

```bash
artemis --output-format json project scripts list --project "<project-uuid>"

artemis --output-format json project scripts create \
  --project "<project-uuid>" \
  --name "<script-name>" \
  --setup-cmd "<compile>" \
  --setup-cmd "<test>" \
  --benchmark-cmd "<benchmark>" \
  --measure none
```

Compile and test are unmeasured setup commands. Use `--measure none` when the benchmark publishes custom `artemis_results` metrics and command runtime must not become an extra worker metric. Use `--measure runtime` (or `cpu`/`memory`) only when those measurements are part of the optimization target. Pass `--default` only when this script should become the project default.

Capture `script_id` from the create or list response. Prefer passing `--script` explicitly even when a default exists.

```bash
artemis --output-format json discovery create \
  --project "<project-uuid>" \
  --runner "<runner-name>" \
  --script "<script-id>" \
  --task "<what you want optimised, in plain language>" \
  --model "<catalogue-uuid-or-model-type>" \
  --versions <n> \
  --llm-metrics=false
```

`--llm-metrics` defaults to `true` on create. Pass `--llm-metrics=false` unless the user asked for LLM-judged metrics. Confirm the response has `scriptId` set and `useLlmMetrics` matching that choice before walking away.

Capture `run_id` from the JSON — every later command needs it.

Immediately give the user a clickable link:

```text
[Open Discovery](<base-url>/projects/<project-uuid>/discovery/<run_id>)
```

Use the authenticated deployment base URL and repeat the link in later progress or failure reports.

### Guided setup

Use `--setup` when the user wants to trial-run the script or shape the metrics schema before the agent is dispatched. Setup steps, in order, are `goal`, `preferences`, `runner`, `script`, `objective`, and `confirm`. A setup run is not dispatched until `discovery setup complete`.

```bash
artemis --output-format json discovery create \
  --project "<project-uuid>" --setup --task "<goal>"
artemis discovery update "<run-id>" \
  --model "<catalogue-uuid-or-model-type>" --versions <n> \
  --runner "<runner-name>" --script "<script-id>" \
  --llm-metrics=false --setup-step script
artemis discovery setup trial-run "<run-id>" --wait
artemis discovery metrics-schema regenerate "<run-id>"
artemis discovery setup complete "<run-id>"
```

`--setup` does not copy project command defaults. Script selection is `--script` plus, optionally, `setup trial-run --script`. Use `metrics-schema propose`, `regenerate`, or `set` on the objective step.

## 2. Baseline / metrics schema

During baseline finalization, Artemis derives and stores `metricsSchema` using the selected model. Poll:

```bash
artemis --output-format json discovery get "<run_id>"
# Wait until baselineGroupId / baselineVersionSha / metricsSchema are
# non-null and status is running (or failed).
```

If baseline finalization is delayed, use `discovery-inspect` to compare the run record with runner activity. Large task logs can delay ingestion; see [advanced log control](../repo-command-setup/ADVANCED.md#control-log-volume).

Use **`discovery baseline set`** only with a hand-authored schema whose `metricId` values are real project metric UUIDs, never placeholders:

```bash
artemis discovery baseline set "<run_id>" --metrics-schema "<path-to-schema.json>"
```

## 3. Verify exploration started

A finalized baseline does not prove that the run explored a version. Poll until at least one version appears or the run becomes terminal:

```bash
artemis --output-format json discovery get "<run_id>" \
  | jq '{status, versionCount, experimentCount, agentRunId}'
```

A running run with zero versions may not have started exploration yet. If it becomes terminal without a version, hand off to `discovery-inspect` to confirm the runner is idle and diagnose the failure.

## 4. If the project looks corrupt after a failed baseline

Occasionally a failed baseline leaves the project in a bad state on the Web UI. Correcting the runner or launch inputs and re-importing (`project-import`) is usually faster than trying to recover the same project.

## Checklist

- [ ] Project UUID confirmed; runner choice confirmed **with the user**, not just picked because it showed online/available
- [ ] Benchmark writes `artemis_results.json`/`.csv` (or qualitative-only is a deliberate choice)
- [ ] Explicit model choice recorded as a catalogue UUID or model-type code
- [ ] Validation script created or reused; `--script` passed (or a project default confirmed)
- [ ] `--llm-metrics=false` unless LLM-judged metrics were requested; create response checked for `scriptId` and `useLlmMetrics`
- [ ] Clickable Discovery link returned to the user
- [ ] Baseline finalized (`baselineGroupId` + schema non-null) before walking away
- [ ] At least one version appeared, or a zero-version terminal run was confirmed through `discovery-inspect`
