---
name: discovery-start
description: Start an Artemis discovery run: create a validation script, pass it to discovery create, wait for the baseline to finalize, and verify it actually explored. Use when the user wants to start discovery, launch a discovery run, or create a discovery experiment.
compatibility: Requires Artemis CLI 1.1.14+ and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.14"
  artemis-platform-min: "3.1.0"
---

# Start a discovery run

## At a glance

- **Problem:** Creates a discovery run from a project validation script, waits for baseline finalization, and confirms that the run actually explored versions.
- **Must be available:** An authenticated CLI, an online runner (confirmed by the user or supplied by the calling skill), an imported project UUID, a validation script built from verified commands, and the required benchmark metrics.
- **Use / don't use:** Use only after runner, project, command, and metric readiness are resolved; use `discovery-inspect` rather than this skill for post-launch interpretation. When the user only asked how to start a run, explain the steps and end with one line saying you can also show them in their browser (it needs the Claude browser extension).
- **Next skill:** Use `discovery-inspect` after baseline finalization and the exploration sanity check, or return to `project-import` if a baseline failure leaves the project unusable.

## Requirements

- `artemis status` succeeds on the target deployment.
- An imported project UUID from `project-import`.
- Verified, self-contained root-level commands from `repo-command-setup`, stored as a project validation script.
- A benchmark that writes numeric `artemis_results.json` or `.csv` as defined in `repo-command-setup` §4, unless qualitative-only optimization is deliberate.
- An online runner compatible with those commands, confirmed by the user or supplied by the calling skill.
- Optionally `jq`. Snippets below use it to filter `--output-format json`, but it is just one option; any JSON filter works (e.g. `python3 -c`).

## Model selection

Direct creation requires `--model`. It accepts either a model catalogue UUID or a model-type code. Guided `--setup` may defer the choice, but a model must be set before setup completes.

```bash
artemis model list --help
artemis model list
```

Only listed models can be used by agents. When the user has not named one, recommend the high-effort preset, `artemis --output-format json model list | python3 -c 'import json,sys; print(next((m["modelId"] for m in json.load(sys.stdin) if "high" in (m.get("effort") or "").split(", ")), ""))'` (if that prints nothing, the model in the **High Effort** group of `artemis model groups`), rather than offering a list; record the chosen UUID or model-type code.

**When a calling skill supplies the model, version budget or measurement count, use them and do not re-ask.** `quickstart` fixes all of these for its demo so a first-time user is never asked to choose between things they have not seen yet. When the user is driving the run themselves and has not said what they want, recommend the high-effort model and 5 versions instead of asking, and let them change either in their reply to the go-ahead below.

## 1. Create the run

**When a calling skill has already chosen the runner, use it and do not re-ask**, the same as the model and budget above. `quickstart` picks one for its demo so a first-time user is never asked to choose between machines they have not heard of.

Otherwise confirm which runner to use before `discovery create`; do not select one merely because it is online. If the project has a default (`artemis project runner get --project "<project-uuid>"`), confirm it remains appropriate. If no runner was named and several are online, list them and ask.

Check whether the project already has a queued or running discovery:

- Queuing is **per runner**: work on one runner process serializes; different runners execute concurrently. Several machines can share one runner name; see [parallel runners](FAST_TRACK.md#parallel-runners).
- An offline runner blocks its queue indefinitely, including later work assigned to it.

```bash
artemis --output-format json discovery list --project "<project-uuid>" --all \
  | jq -r '.docs[]?
      | select(.status=="created" or .status=="running" or .status=="awaiting_approval")
      | "\(.id) \(.status) vc=\(.versionCount)"'
```

Choose whether to accept serialization, use another runner, or provision one. Before starting or reusing another runner, ask the user and name the machines: it runs their code on their hardware. Never cancel queued or running work without user confirmation; cancellation retains its versions, experiments, and logs for inspection.

Execution runs require a validation script. Creating without `--script` or a project default fails with `NoDefaultValidationScriptError`.

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

Capture the script's `id` from the create or list response. Prefer passing `--script` explicitly even when a default exists.

Before the command that dispatches the agent, tell the user the model, the number of versions, and that each version is agent work that spends credits, and go ahead only on their yes; this one question also carries the recommended defaults. For a direct run that command is `discovery create`; for a `--setup` run it is `discovery setup complete` (and a later `discovery update --versions` changes the count, so confirm again). Skip asking when a calling skill passes the user's go-ahead, as `quickstart` does for its demo after naming the credits in its welcome or in its one-line question before the run.

A calling skill's go-ahead counts only if the user was told, earlier in this session, that the run uses account credits. If you cannot see that they were, ask in one line before dispatching: "This uses account credits; go ahead?", and wait for a yes.

```bash
artemis --output-format json discovery create \
  --project "<project-uuid>" \
  --runner "<runner-name>" \
  --script "<script-id>" \
  --task "<what you want optimised, in plain language>" \
  --model "<catalogue-uuid-or-model-type>" \
  --versions <n> \
  --llm-metrics=false \
  [--source-changeset "<changeset-id>"] \
  [--target-files <path> --target-files <path>]
```

Pass `--source-changeset` when starting from an existing branch, including a version from an earlier Discovery run. It copies that branch's head into the new run, which measures it again as its baseline; no readings carry over. Confirm the head is the intended version before creating the run. Without it the run starts from the project's imported code.

`--target-files` is repeatable and optional. It points the agent at the files worth changing; without it the whole repository is in scope. A calling skill that knows the files, such as the demo in `quickstart`, passes them here.

`--execution-mode` defaults to `benchmark`, which runs and measures every version. `test` runs the commands only as a pass or fail gate, so measurements do not count, and `skip` turns Benchmark Metrics off: nothing runs and only AI Metrics score versions. Keep the default for a measured run.

`--llm-metrics` defaults to `true` on create. Pass `--llm-metrics=false` unless the user asked for AI Metrics. Confirm the response has `scriptId` set and `useLlmMetrics` matching that choice before walking away.

### How many times each version is measured

The server default is one measurement per version, recorded on the run as `evaluationMode` and `evaluationRepetitions`. One measurement yields a point estimate and no interval, so a difference between two versions cannot be separated from ordinary noise.

```bash
--eval-mode fixed --eval-runs 3        # measure every version three times
--eval-mode until_stable --max-runs 20 # repeat until results settle, capped
```

Repetitions multiply **runner** time, not agent time: a 10-version run at three repeats performs 33 measurements instead of 11. On a benchmark measured in seconds that is a couple of extra minutes and well worth it. On one measured in tens of minutes it dominates the run.

Unless a calling skill supplied the measurement count, decide with the user against their benchmark's duration rather than copying a number. Use verified timings when available; otherwise ask. Estimate benchmark time as duration × (versions + one baseline) × repetitions; use the cap for `until_stable`. Add build/test time per version and queue delays separately, and give the estimate before creating the run.

### Long benchmarks

When the estimate above is longer than the user wants to wait, offer [Fast-track Discovery](FAST_TRACK.md) before creating the run: search on a smaller benchmark first, and run independent searches on separate runners.

Capture the run's `id` from the JSON (there is no `run_id` key); every later command needs it.

Immediately give the user a clickable link:

```text
[Open run](<deployment-base-url>/projects/<project-uuid>/discover/<run-id>)
```

A `--setup` run lives at `<deployment-base-url>/projects/<project-uuid>/discover/setup/<run-id>` until `setup complete`, then at the link above. If that link returns not found, give the project link, `<deployment-base-url>/projects/<project-uuid>`, where Discover lists the run.

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
artemis --output-format json discovery setup trial-run "<run-id>"   # returns at once; the check's id is .validation.id
artemis discovery metrics-schema regenerate "<run-id>"
artemis discovery setup complete "<run-id>"
```

Run `trial-run` without `--wait`: it returns the check's validation id at once (`.validation.id`, also recorded on the run as `baselineValidationId`). Wait for it with the loop in `repo-command-setup` §5b: one shell call, 30 seconds between checks, at most 8 minutes. Give that shell call a 10-minute timeout, or run it in the background. If it is still `created` or `running` after a second loop, stop and report it with `execution-log-inspect` (a trial run behind an offline runner stays `created`); never start another trial run. Ask the user before `setup complete`, as above.

`--setup` does not copy project command defaults. Script selection is `--script` plus, optionally, `setup trial-run --script`. Use `metrics-schema propose`, `regenerate`, or `set` on the objective step.

## 2. Baseline / metrics schema

During baseline finalization, Artemis derives and stores `metricsSchema` using the selected model. Wait in one shell call: 30 seconds between checks, at most 8 minutes. Give that shell call a 10-minute timeout, or run it in the background. Never a foreground `sleep` between tool calls. Run the loop again once if the baseline is still pending:

```bash
for i in $(seq 16); do
  out=$(artemis --output-format json discovery get "<run_id>") || { echo "discovery get failed"; break; }
  printf '%s' "$out" | python3 -c 'import json,sys; r=json.load(sys.stdin); sys.exit(0 if (r.get("baselineVersionSha") is not None and r.get("metricsSchema") is not None) or r.get("status") == "failed" else 1)' && break
  sleep 30
done; printf '%s' "$out" | python3 -c 'import json,sys; r=json.load(sys.stdin); print(json.dumps({"status": r.get("status"), "baselineVersionSha": r.get("baselineVersionSha"), "hasSchema": r.get("metricsSchema") is not None}))'
```

If baseline finalization is delayed, use `discovery-inspect` to compare the run record with runner activity. Large task logs can delay ingestion; see [advanced log control](../repo-command-setup/ADVANCED.md#control-log-volume).

Use **`discovery baseline set`** only with a hand-authored schema whose `metricId` values are real project metric UUIDs, never placeholders:

```bash
artemis discovery baseline set "<run_id>" --metrics-schema "<path-to-schema.json>"
```

## 3. Verify exploration started

A finalized baseline does not prove that the run explored a version. Check the same way, one shell call of at most 8 minutes with a 10-minute shell timeout, until at least one version appears or the run becomes terminal:

```bash
for i in $(seq 16); do
  out=$(artemis --output-format json discovery get "<run_id>") || { echo "discovery get failed"; break; }
  printf '%s' "$out" | python3 -c 'import json,sys; r=json.load(sys.stdin); sys.exit(0 if (r.get("versionCount") or 0) > 0 or r.get("status") in ("completed", "failed", "cancelled") else 1)' && break
  sleep 30
done; printf '%s' "$out" | python3 -c 'import json,sys; r=json.load(sys.stdin); print(json.dumps({k: r.get(k) for k in ("status", "versionCount", "experimentCount", "agentRunId")}))'
```

A running run with zero versions may not have started exploration yet. If it becomes terminal without a version, or still has none after two loops (16 minutes), stop checking and hand off to `discovery-inspect`. When the user's benchmark is long (a version takes more than about 5 minutes with its repetitions), say so and allow one more loop before handing off.

## 4. If the project looks corrupt after a failed baseline

Occasionally a failed baseline leaves the project in a bad state on the Web UI. Only after `discovery-inspect` has ruled out an agent-side stop: correcting the runner or launch inputs and re-importing (`project-import`) is usually faster than trying to recover the same project.

## Checklist

- [ ] Project UUID confirmed; runner either supplied by the calling skill, or confirmed **with the user** rather than picked because it showed online
- [ ] Benchmark writes `artemis_results.json`/`.csv` (or qualitative-only is a deliberate choice)
- [ ] Explicit model choice recorded as a catalogue UUID or model-type code
- [ ] User said yes to the model, version count and credit spend before the run was dispatched (`discovery create`, or `setup complete` for a setup run), unless a calling skill passed their go-ahead and the user was told earlier this session that the run uses account credits
- [ ] Validation script created or reused; `--script` passed (or a project default confirmed)
- [ ] `--llm-metrics=false` unless AI Metrics were requested; create response checked for `scriptId` and `useLlmMetrics`
- [ ] Measurements per version chosen deliberately against the benchmark's duration, and `evaluationRepetitions` on the create response matches it
- [ ] Fast-track offered when the estimate was longer than the user wanted to wait; if used, its [checklist](FAST_TRACK.md#checklist) completed
- [ ] Clickable Discovery link returned to the user
- [ ] Baseline finalized (`baselineVersionSha` + schema non-null) before walking away
- [ ] At least one version appeared, or a zero-version terminal run was confirmed through `discovery-inspect`
