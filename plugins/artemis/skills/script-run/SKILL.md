---
name: script-run
description: Run a project's Script once on one version of an Artemis branch on a runner, wait for it, and report pass or fail and the metric values it recorded. Use when the user wants to run their Script on a runner, validate or measure the code already in the project, get a baseline number, or re-run after fixing the Script or the code, and when another skill needs one measured run. Not for writing or fixing commands or making a repo Discovery-ready (repo-command-setup), or for checking whether an uncommitted local change is faster (change-validate).
compatibility: Requires Artemis CLI 1.1.14+ (below 1.2.0) and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.14"
  artemis-cli-max: "1.2.0"
  artemis-platform-min: "3.1.0"
---

# Run a Script on a branch

## At a glance

- **Problem:** One measured run of a project Script on a runner (a Validation, listed under **Script runs**), the same primitive Discovery uses for the baseline and every version, reported as pass or fail with its numbers.
- **Must be available:** An authenticated CLI, an imported project with a Script, and an online runner.
- **Use / don't use:** Use for a single run, or a series another skill drives one run at a time. To write or fix the Script's commands, use `repo-command-setup`. To decide whether a change is really faster, use `change-validate`, which calls this skill for each run.
- **Next skill:** Return to the calling skill. A failed command goes to `repo-command-setup`; a run that never finishes goes to `execution-log-inspect`.

## Requirements

- `artemis --version` is at least `artemis-cli-min`; otherwise load `cli-setup`.
- The project id the caller passed, else ask the user.
- The Script id the caller passed, else the project's default from `artemis project scripts list --project <project-id>`; with no default, ask which Script to run.
- An online runner's name from `artemis runner list`; with more than one online, ask which. Otherwise `runner-setup`.

## 1. Pick the branch and version

Use the branch the caller passed. With none, put a branch over the project's current code:

```bash
artemis --output-format json changeset create --project "<project-id>" --name "<name>"
```

Keep the response's `id` as `<changeset-id>`, and name the branch after the run, for example `baseline <date>`. Its one version is the starting commit. `<version>` decides which code runs: `original` is the starting commit, `latest` the branch's last commit (an agent's fix or a saved change), or a SHA from `artemis changeset versions <changeset-id> --project <project-id>`. After a `project pull`, create a new branch: an older branch's `original` stays on the old commit.

## 2. Start it

Start it without `--wait`, and keep the id it prints. Run this block and §3's loop as written, filling in only the `<...>` values; never retype them or rebuild them by filtering this file:

```bash
out=$(artemis --output-format json changeset validate "<changeset-id>" --project "<project-id>" \
  --version "<version>" --script "<script-id>" --runner "<runner-name>") \
  && printf '%s' "$out" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'
```

If it exits non-zero, show the CLI's error and stop; do not retry on another runner or Script unasked.

To repeat the benchmark inside one run (CLI 1.1.17+), add `--eval-runs <n>` (1 to 500), or `--max-runs <n>` to repeat until the results settle, at most n times (it implies `--eval-mode until_stable`). Without them the server's defaults apply. If `changeset validate --help` does not list them, update the CLI with `cli-setup`.

Then post the start block and say what Artemis is doing, as [waiting.md](../artemis/references/waiting.md) says: a Validation block, then what the Script does on that runner (by default building, testing and benchmarking), followed on the branch's Scripts tab. In a series a caller drives (pairs, turns), the caller posts one block at its start; skip it here. While the run is `created`, the runner has not picked it up yet; say so.

## 3. Wait

The loop follows [Bounded waits](../artemis/references/waiting.md#bounded-waits):

```bash
for i in $(seq 16); do
  out=$(artemis --output-format json changeset validation get "<validation-id>" \
        --project "<project-id>") || { echo "validation get failed"; break; }
  s=$(printf '%s' "$out" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status") or "")')
  case "$s" in success|failed|cancelled) break ;; esac
  sleep 30
done; echo "$s"
```

A validation ends `success`, `failed` or `cancelled`. `completed` is a Discovery run's word, so a loop that waits for it polls the full 8 minutes after a pass.

`validation get failed` means the CLI call failed, not the run: it may still be going. If the loop ends that way, or still `created` or `running`, post the waiting line and run it once more. If it is unfinished after the second loop, stop and check it with `execution-log-inspect`. A validation behind an offline runner stays `created`, and so can one whose commands ran but recorded nothing, so check `artemis process status "<processId>"`, with `processId` from `validation get`: if the process has finished, read the result as in §4; if it never started, the runner is the cause.

## 4. Read the result

```bash
artemis --output-format json changeset validation get "<validation-id>" --project "<project-id>"
artemis changeset validation logs "<validation-id>" --project "<project-id>"
```

- **Pass:** `status` is `success` and every entry in `commands` has `exitCode` 0, on the intended runner (`customWorkerName`). Report a `cancelled` run as cancelled, not failed.
- **Values:** on CLI 1.1.18+, `measurements` lists each metric's `name`, `mean`, `std`, `count` and `unit`, from the platform. If it passed and `measurements` is still empty, read it once more 30 seconds later; if it is still empty, read the values in the logs as below. On older CLIs, `validation get` has no values: read them in the logs, after `artemis_results.json content:`. Either way, the logs' `Wrote N metric values to observation` line confirms they were saved; a Script with a benchmark that passes without it measured nothing.
- Read command output in the logs, or with `execution-log-inspect` and the `processId`, not a per-command `logId`. Both read through the platform; no access to the runner host is needed.

## 5. Report

Say passed, failed or cancelled; which command failed and its exit code; each metric's value in the repository's own units (with the count when the benchmark repeated); how long it took, from the start block to the end status; and the Scripts tab link, `<deployment-base-url>/projects/<project-id>/branches/<changeset-id>/validations`, with the base URL `artemis status` reports. Give the caller the validation id. Never call it measured when no metric values were written.

When a command fails, say whether the command string is wrong (fix the Script with `repo-command-setup` and run again on the same branch) or the repository's code is (fix it in Git, then `project pull` and a new branch).

## Checklist

- [ ] The version passed explicitly; started without `--wait`, id kept, start block posted (or the caller's series block)
- [ ] Waited with the loop as written, at most two loops, then `execution-log-inspect`
- [ ] Status and every command's exit code checked, and the runner it ran on
- [ ] Metric values read from `measurements` or the logs, never assumed from a pass
- [ ] Scripts tab link and validation id given
