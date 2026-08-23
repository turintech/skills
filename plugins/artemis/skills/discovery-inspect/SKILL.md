---
name: discovery-inspect
description: Inspect and interpret the results of an Artemis discovery run — is it done, did versions actually pass, what are the real numbers, and what code changed. Use when the user wants to check on a discovery run, read its results, see which versions won, or understand why a run produced nothing.
---

# Inspect a discovery run

## At a glance

- **Problem:** Interprets discovery status, experiments, versions, metrics, agent narration, and runner evidence without mistaking completion for success.
- **Must be available:** An authenticated CLI for the run's Artemis deployment and the discovery run ID.
- **Use / don't use:** Use to monitor, understand, or diagnose an existing discovery run; use `discovery-start` and the setup skills to create a run or resolve prerequisites.
- **Next skill:** For more versions with a new focus, use `discovery-steer`: expand the budget first, then send guidance.

The central rule is **completed does not mean passed**. Terminal status means the work ran, not that it produced a valid version. A run can complete with zero versions, and a completed version can fail its test. Trust recorded metrics and runner evidence rather than the status alone.

## Requirements

- CLI authenticated (`artemis status`) on the run's deployment.
- The `run_id` (from `discovery create`'s output, or `artemis discovery list --project <uuid>`).
- If the run or version ID is unknown, ask for its Web UI URL and extract the project, discovery, and optional version UUIDs using `artemis` §2.
- For a runner-executed failure, the version's `processId` or `executionLogId`; use `execution-log-inspect`.
- Optionally `jq`. Snippets below use it to filter `--output-format json`, but it is just one option — any JSON filter works (e.g. `python3 -c`).

## The inspection commands

All accept `--output-format json` for scripting.

```bash
artemis discovery list --project <uuid>        # all runs for a project
artemis discovery get <run-id>                 # the run record
artemis discovery experiments list <run-id>    # hypotheses + verdicts
artemis discovery experiments get <experiment-id> # one hypothesis + conclusion
artemis discovery versions list <run-id>       # candidates + lifecycle/fitness
artemis discovery versions get <version-id>    # one version (rationale, status)
artemis discovery metrics <run-id> [--all]     # measured numbers per version
```

### The agent's own narration

The reasoning the Web UI shows as a chat is reachable from the CLI, but not under `discovery` — it lives under `artemis chat`, and the chat's ID is the **`agentRunId` on the run record**:

```bash
run=$(artemis --output-format json discovery get <run-id>)
artemis chat messages "$(echo "$run" | jq -r .agentRunId)"   # narration + tool calls
artemis chat list --project <project-uuid>                   # if you lost the id
```

Use chat to see current activity and experiment records for complete hypotheses, conclusions, confidence, and reviewer notes. `chat messages` is a summary: assistant deltas may be truncated and tool events may omit inputs and outputs.

### Timestamps

Each event includes a `timestamp`. Text output prefixes events with wall-clock time, and JSON output exposes the field directly.

### Is it stuck, or just thinking?

Segment tool calls by `complete_version` (the call that closes a version) and compare each planning stretch with the run's earlier progress. A long interval alone does not prove a stall:

```bash
artemis --output-format json chat messages <agent-run-id> \
  | jq -r '.[] | select(.type=="tool.start")
           | "\(.timestamp) \(.payload.internalToolName)"'
```

Repeated status text or repeated `propose`/`conclude` calls can be normal while the agent drafts and revises experiments. Evidence of a stall is stronger when the run record stops updating, a version remains pending, narration emits no new calls, and the runner is idle. Check `discovery versions get <version-id>`, chat events, and runner activity together before concluding that work has stopped.

`discovery versions get` returns `changesetId`, `versionSha`, `llmRationale`, `processId`, `executionLogId`, and `observationId`. Read the actual discovery changeset with `artemis changeset diff <changeset-id> --project <project-uuid>`, or in the Web UI; `versionSha` belongs to the project's platform mirror, not the local clone.

When reporting a run or candidate, include clickable Web UI links:

```text
[Open Discovery](<base-url>/projects/<project-id>/discovery/<run-id>)
[Open version](<base-url>/projects/<project-id>/discovery/<run-id>/versions/<version-id>)
[Open changeset](<base-url>/projects/<project-id>/changesets/<changeset-id>)
```

## Inspect runner output

Use `execution-log-inspect` with the version's `processId` or `executionLogId` to diagnose compile, test, benchmark, and result-ingestion failures. A `generation_failed` version was never dispatched and has no runner task log; inspect its agent narration instead.

Host-local runner daemon output is separate evidence for connection, polling, dispatch, and process-lifecycle problems. When shell access exists, its location depends on how the runner was started:

- Wrapped in `nohup ./artemis-runner start … > runner.log 2>&1 &` (the convention for an automated runner) — the file is where you redirected it, typically `~/runner/runner.log`.
- Under a systemd unit — `journalctl -u artemis-runner --follow`.
- Foreground in a terminal — it's already in view.

### Baseline and evaluation delays

After the benchmark exits, the runner uploads its task log before baseline finalization or version ingestion can complete. Large logs can make this gap last several minutes. Compare task-log timestamps with the run record before treating silence as a stall; see [advanced log control](../repo-command-setup/ADVANCED.md#control-log-volume).

The next gap — evaluation finished to the next version being dispatched — is agent-side. Use timestamps in the narration and run record to distinguish continued planning from inactivity.

## Reading a run, in order

### 1. Is the baseline finalized? (did the run really start)

```bash
artemis --output-format json discovery get <run-id>
```

Look at `status`, `versionCount`, `experimentCount`, `baselineObservationId`, `baselineVersionSha`, `metricsSchema`. A healthy run has a non-null `baselineObservationId` + `metricsSchema`. **`baselineVersionSha` must match the commit you intended to run** — this is how you confirm the run is on the right code (a project pins `gitHash` at import, so a stale project runs old code).

### 2. What did the agent try? (experiments)

```bash
artemis discovery experiments list <run-id>
```

Each experiment is a hypothesis with `status` = `validated` / `refuted` / `inconclusive` and a `confidence`. This is the agent's *reasoning* — a validated experiment does not guarantee a fast version; cross-check the numbers.

### 3. Which candidates ran, and did they pass? (versions)

```bash
artemis discovery versions list <run-id>
```

Per version: `lifecycle` (`completed` / `generation_failed` / `scoring_failed`), `execution` (`success` / `failed`), and `fitness`. A `✓` with `execution=success` means it compiled, passed the test, and benchmarked. Failure modes seen in practice: `generation_failed` (agent produced nothing runnable), `execution=failed` (compile or test failed — e.g. a `NameError` from an undefined capability probe), `scoring_failed`. **`generation_failed` versions never reach the runner**, so they leave no trace in its log — this list is the only authoritative source for per-version outcome.

### 4. What are the real numbers? (metrics — the source of truth)

```bash
artemis discovery metrics <run-id> --all
```

Grouped by version, metric IDs resolved to names. Compare each version's custom metric (e.g. `decode_b8_ms`) against the `baseline:` row. **This is what you trust**, not fitness (see traps).

That grouping applies to the text output. `--output-format json` returns a flat `docs[]` keyed by `observationId` with no version number — to rank by version, join it against `discovery versions list` (`observationId` → `versionNumber`), and read `baselineObservationId` off the run record for the baseline row.

To see the winning change, read its `llmRationale` (`discovery versions get <version-id>`) and then read the diff itself — confirm it actually does what you asked (e.g. registers/calls the C++ op) rather than a shortcut that happens to score well. A rationale describing an optimisation is not evidence the diff implements one.

```bash
artemis changeset diff <changeset-id> --project <project-uuid>          # full diff
artemis changeset diff <changeset-id> --project <project-uuid> --stat   # file summary
```

`changesetId` comes from `discovery versions get`; `--project` is required. The Web UI shows the same changeset. (`artemis target diff` won't work here — it is for `target generate` versions, not discovery versions.)

## Common misreads

- **`versionCount: 0` is not conclusive by itself.** If the run is active, inspect `discovery versions list`, agent narration, and available execution logs; exploration may not have started. If it becomes terminal, the runner is idle, and no version exists, the run failed to explore; relaunch it through `discovery-start`.
- **Fitness is often not meaningful.** Agent-derived metric schemas may weight every metric equally (~0.02) and bundle compile-time/memory in, so `fitness` can be near-zero or **negative** for a version that improved your target metric. Rank by the **raw metric value**, not fitness.
- **Task logs cover only versions that reached a runner.** Use `execution-log-inspect` for compile, test, benchmark, and ingestion evidence. Cross-check `discovery versions list` because `generation_failed` versions were never dispatched.
- **`discovery metrics` prints logger noise to stdout.** vLLM/other imports emit WARNING/INFO to stdout, so piping the text output into a JSON parser fails. Use `--output-format json`, or read the printed table directly.
- **Names drift.** A project's platform-side name can diverge from whatever you called it at import time; always reference the **project UUID**.

## Checklist

- [ ] `discovery get`: baseline finalized (`baselineObservationId` + `metricsSchema` non-null) and `baselineVersionSha` == the intended commit.
- [ ] `discovery metrics --all`: each version's target metric compared to `baseline:` — the numbers, not `fitness`, decide the winner.
- [ ] `versions list`: winners are `execution=success`; every failure accounted for, including `generation_failed` ones execution logs cannot show.
- [ ] Winner's `llmRationale` + the actual diff (`changeset diff`, or the Web UI): the change genuinely does what was asked (not a scoring shortcut).
- [ ] Clickable Discovery, winning version, and changeset links returned to the user.
