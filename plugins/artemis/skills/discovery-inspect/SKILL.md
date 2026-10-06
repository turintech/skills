---
name: discovery-inspect
description: Inspect and interpret the results of an Artemis discovery run — is it done, did versions actually pass, what are the real numbers, and what code changed. Use when the user wants to check on a discovery run, read its results, see which versions won, or understand why a run produced nothing.
compatibility: Requires Artemis CLI 1.1.14+ and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.14"
  artemis-platform-min: "3.1.0"
---

# Inspect a discovery run

## At a glance

- **Problem:** Interprets discovery status, experiments, versions, metrics, agent narration, and runner evidence without mistaking completion for success.
- **Must be available:** An authenticated CLI for the run's Artemis deployment and the discovery run ID.
- **Use / don't use:** Use to monitor, understand, or diagnose an existing discovery run; use `discovery-visualize` when the user wants charts or a visual report; use `discovery-start` and the setup skills to create a run or resolve prerequisites.
- **Next skill:** For graphs, canvases, or a visual report, use `discovery-visualize`. For more versions with a new focus, use `discovery-steer`: expand the budget first, then send guidance.

The central rule is **completed does not mean passed**. Terminal status means the work ran, not that it produced a valid version. A run can complete with zero versions, and a completed version can fail its test. Trust recorded metrics and runner evidence rather than the status alone.

## Requirements

- CLI authenticated (`artemis status`) on the run's deployment.
- `artemis --version` is at least `artemis-cli-min` (1.1.14, which has `discovery compare`); if it is older, load the skill and follow `cli-setup` first.
- The `run_id` (from `discovery create`'s output, or `artemis discovery list --project <uuid>`).
- If the run or version ID is unknown, ask for its Web UI URL and extract the project, discovery, and optional version UUIDs using the router: load the skill and follow `artemis` §2.
- For a runner-executed failure, use the version's `processId` with `execution-log-inspect`, or use `artemis discovery versions logs <version-id>`.
- Optionally `jq`. Snippets below use it to filter `--output-format json`, but it is just one option — any JSON filter works (e.g. `python3 -c`).

## The inspection commands

All accept `--output-format json` for scripting.

```bash
artemis discovery list --project <uuid> --all  # all runs for a project
artemis discovery get <run-id>                 # the run record
artemis discovery experiments list <run-id> --all  # hypotheses + verdicts
artemis discovery experiments get <experiment-id> # one hypothesis + conclusion
artemis discovery versions list <run-id> --all     # candidates + lifecycle/Composite score
artemis discovery versions get <version-id>    # one version (rationale, status)
artemis discovery versions logs <version-id>   # runner output for one version
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

`discovery versions get` returns `changesetId`, `versionSha`, `llmRationale`, `processId`, and `observationGroupId`. Read the actual discovery changeset with `artemis changeset diff <changeset-id> --project <project-uuid>`, or in the Web UI; `versionSha` belongs to the project's platform mirror, not the local clone.

When reporting a run or candidate, include clickable Web UI links:

```text
[Open project](<deployment-base-url>/projects/<project-id>)
```

Link the project, then name the page to open, such as Discover, the run, or its Versions tab. Run and version paths differ between deployments, so do not build them from memory.

## Inspect runner output

Use `artemis discovery versions logs <version-id>` or `execution-log-inspect` with the version's `processId` to diagnose compile, test, benchmark, and result-ingestion failures. A `generation_failed` version was never dispatched and has no runner task log; inspect its agent narration instead.

Host-local runner daemon output is separate evidence for connection, polling, dispatch, and process-lifecycle problems. When shell access exists, its location depends on how the runner was started:

- Started in the background with its output redirected: the file is wherever that redirect pointed, which `runner-setup` reports as the log path when it starts one.
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

Look at `status`, `versionCount`, `experimentCount`, `baselineVersionSha`, `metricsSchema`. A run past its baseline has a non-null `baselineVersionSha` + `metricsSchema` (a run still in `setup` can too, before any version); `baselineGroupId` is set as soon as a baseline is dispatched or adopted, before it finishes, so it proves nothing. **`baselineVersionSha` must match the commit you intended to run** — this is how you confirm the run is on the right code (a project pins `gitHash` at import, so a stale project runs old code).

### 2. What did the agent try? (experiments)

```bash
artemis discovery experiments list <run-id> --all
```

Each experiment is a hypothesis with `status` = `validated` / `refuted` / `inconclusive` and a `confidence`. This is the agent's *reasoning* — a validated experiment does not guarantee a fast version; cross-check the numbers.

### 3. Which candidates ran, and did they pass? (versions)

```bash
artemis discovery versions list <run-id> --all
```

Per version: `lifecycle` (`completed` / `generation_failed` / `scoring_failed`), `executionStatus` (`success` / `failed`), and `fitnessScore` (the Composite score). A `✓` with `executionStatus=success` means it compiled, passed the test, and benchmarked. Failure modes seen in practice: `generation_failed` (agent produced nothing runnable), `executionStatus=failed` (compile or test failed, e.g. a `NameError` from an undefined capability probe), `scoring_failed`. **`generation_failed` versions never reach the runner**, so they leave no trace in its log; this list is the only authoritative source for per-version outcome.

### 4. What are the real numbers? (metrics — the source of truth)

```bash
artemis --output-format json discovery compare <run-id>
```

This is Artemis's own verdict, the one the Web UI shows: per version and metric, the % change against the baseline, its 95% interval and a verdict (`better`, `worse`, `noise`, or `pending` when there are too few runs), plus an overall verdict per version and the runs that would settle a `pending` one. **This is what you trust**, not the Composite score (see *Common misreads*). Report the verdicts as given; never judge noise from the spread yourself.

`artemis discovery metrics <run-id> --all --stats` adds the mean, spread and sample count per version and baseline as context, and without `--stats` one row per repetition.

To see the winning change, read its `llmRationale` (`discovery versions get <version-id>`) and then read the diff itself — confirm it actually does what you asked (e.g. registers/calls the C++ op) rather than a shortcut that happens to score well. A rationale describing an optimisation is not evidence the diff implements one.

```bash
artemis changeset diff <changeset-id> --project <project-uuid>          # full diff
artemis changeset diff <changeset-id> --project <project-uuid> --stat   # file summary
```

`changesetId` comes from `discovery versions get`; `--project` is required. The Web UI shows the same changeset.

## When the agent stops, not the runner

A run can fail while the machine, the runner, and the project are all healthy. The agent driving the run talks to a model provider through the platform, and that conversation can end on its own.

Symptoms, together: the run goes terminal with far fewer versions than its budget, the last version completed normally seconds earlier, the runner is still online with a live process, and the platform may return intermittent `502`s while you read the run.

It can also happen **before the baseline exists**, a minute into a new run: `versionCount` and `experimentCount` both zero, `baselineVersionSha` and `metricsSchema` null, and the narration ending mid-analysis. That looks like a broken setup and is not one. The giveaway is that the narration shows the agent reading the repository successfully and reasoning about it right up to the last message, and that the Web UI may still show the run spinning after the record says `failed`.

```bash
run=$(artemis --output-format json discovery get <run-id>)
echo "$run" | jq '{status, versionCount, numVersions, experimentCount, agentRunId}'
artemis chat messages "$(echo "$run" | jq -r .agentRunId)" | tail -20
```

The narration's final messages carry the reason, such as `ERR_LLM_CONNECTION` with `Connection error.`, or a bare `session.end  Internal error` immediately after a normal assistant turn. The CLI's run record doesn't include the run's own reason; read it in the run's chat. A version's `failureReason` (`discovery versions list` or `versions get`) is set when the agent set the version aside, its edits never landed, or the run stopped under it. It is empty when the version's commands failed (`executionStatus` `failed`) or the user cancelled it; read `versions logs` for those. Read it before blaming the project:

- Versions already recorded are real. Their measurements happened on the runner and stand on their own.
- Do not re-run setup, reinstall the runner, or re-import the project. None of them caused it.
- `experimentCount` above `versionCount` means planned experiments never became versions, which is the expected shape here rather than a second fault.
- Report it as a platform-side failure and name the remaining budget. If a calling skill has a retry rule, follow it. Otherwise follow `discovery-steer`: a failed run is retried through its agent (`discovery steer` with "Please retry the last action that failed."), and a cancelled run gets `discovery continue <run-id> --versions <n>` with the unused budget offered as `n`; both only with the user's yes, since they spend credits.

## Common misreads

- **`versionCount: 0` is not conclusive by itself.** If the run is active, inspect `discovery versions list`, agent narration, and available execution logs; exploration may not have started. If it becomes terminal, the runner is idle, and no version exists, the run failed to explore; relaunch it through `discovery-start`.
- **The Composite score (`fitnessScore`) is a roll-up of the metrics by importance tier against the baseline, not a verdict.** It can be near zero or negative for a version that improved your target, so decide with `discovery compare`'s verdicts. A score shown as PENDING means a metric has no interval (one measurement per version); it does not mean work is still running. AI Metrics are scored 1-5 and stored as 0-1, so 0.8 means 4/5, not 80%.
- **Task logs cover only versions that reached a runner.** Use `execution-log-inspect` for compile, test, benchmark, and ingestion evidence. Cross-check `discovery versions list` because `generation_failed` versions were never dispatched.
- **Names drift.** A project's platform-side name can diverge from whatever you called it at import time; always reference the **project UUID**.

## Checklist

- [ ] `discovery get`: baseline finalized (`baselineVersionSha` + `metricsSchema` non-null) and `baselineVersionSha` == the intended commit.
- [ ] `discovery compare`: each version's verdict on the target metric, as Artemis gives it; the verdicts, not the Composite score, decide the winner.
- [ ] `versions list`: winners are `executionStatus=success`; every failure accounted for, including `generation_failed` ones execution logs cannot show.
- [ ] Winner's `llmRationale` + the actual diff (`changeset diff`, or the Web UI): the change genuinely does what was asked (not a scoring shortcut).
- [ ] Project link returned, naming the page to open (Discover, the run, its Versions tab, the winning version).
- [ ] A run that ended short of its budget checked against the agent narration first, so a platform-side stop is reported as such and not as a project, runner, or setup fault.
