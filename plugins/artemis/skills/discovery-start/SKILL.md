---
name: discovery-start
description: Start an Artemis discovery from the intended project or saved Branch, using the installed CLI's supported execution mode, then verify exploration. Use when the user asks to launch a discovery or optimisation experiment; use discovery-inspect for existing results.
---

# Start a Discovery

Preserve the selected repository, source Branch and saved SHA. Starting a Discovery is separate from preparing commands or validating a benchmark; do not launch a search merely because preparation finished.

## Check the installed interface

Use the supplied API deployment for CLI requests and UI origin for browser links. Reuse matching authentication and task choices.

```bash
artemis status
artemis discovery create --help
artemis discovery get --help
artemis model list --help
```

Inspect actual subcommand usage and flags, not just the exit code. Older CLIs may print parent help for an unsupported command. Do not silently change the user's source or execution mode to fit an older CLI. Explain the missing capability and offer the corresponding UI journey when needed; do not reinstall an identical release repeatedly.

The stable CLI 1.0.11 reviewed for this flow uses inline command flags and `--skip-execution`. The newer reviewed source interface uses `--script`, `--execution-mode`, `--source-changeset`, `--source-sha` and optional parked `--setup`. These are different interfaces; use only flags exposed by the installed CLI. A source build is not proof of stable release availability.

## Preserve source and choose execution

- **Saved Artemis Branch:** pass its ID and exact saved SHA through supported `--source-changeset` and `--source-sha`. Confirm both fields in the created run. If unavailable, return the user to that Branch's Metrics or Discoveries page to start from it. Do not publish to Git, switch the project branch, or substitute the project base.
- **Project source:** confirm the intended project branch and commit before launch. Do not assume a previously selected Branch is the project base.
- **No machine or commands:** when the user chooses code-based assessment, use `--execution-mode skip`, or `--skip-execution` on the older interface. No machine or script is needed. Explain that no tests or performance measurements will run.
- **Existing commands or logs only:** where supported, use `--execution-mode test` and code-based scoring (`--llm-metrics` on the newer interface). Successful command exits/logs remain execution evidence. Arbitrary numbers in stdout are not imported as performance metrics. If the installed interface cannot express this mode, offer the UI flow rather than silently switching to benchmark or skipping execution.
- **Measured performance:** use benchmark execution with the verified script and intended machine. Measurements can come from configured built-in options or structured custom results. Review correctness, units and metric directions; a valid local JSON file alone is not a recorded baseline.

For execution, reuse the machine already selected for this task when it remains suitable. If missing, unavailable or ambiguous, ask which machine to use; never pick a teammate's machine merely because it is online. Use `runner-setup` only when connection is needed and `repo-command-setup` when commands need work. Do not require a new harness for a user who only wants to run existing commands.

Check existing runs before creating work, preserve known run IDs when retrying, and respect the authorised version/time budget. A lost create response needs reconciliation before retry; creating another run blindly can duplicate work. Do not cancel unrelated jobs to make room.

## Model and launch

Inspect `artemis model list` and select an available model consistent with the user's preference. The reviewed CLI requires `--model` for immediate launch; do not assume a server default. The newer parked `--setup` flow makes it optional until setup is completed. Accepted UUIDs or model codes depend on installed help.

For the newer interface, an execution example is:

```bash
artemis --output-format json discovery create \
  --project "<project-id>" \
  --source-changeset "<branch-id>" --source-sha "<saved-sha>" \
  --task "<optimisation objective>" --model "<available-model>" \
  --script "<verified-script-id>" --runner "<selected-machine>" \
  --execution-mode benchmark --versions <budget>
```

Use `test` for the logs-only path. For `skip`, omit script and machine. Omit source flags only for an explicitly chosen project-base path. Replace placeholders with observed identifiers and do not use this example unless the installed CLI exposes its flags. The older execution interface takes `--compile-cmd`, `--test-cmd` and `--benchmark-cmd`; inspect the resulting run-level commands instead of assuming project defaults are current.

If the user wants to review setup first and `--setup` is supported, create a parked run. Inspect help for `discovery update` and `discovery setup complete`; no execution starts merely because a setup record exists. Return the setup URL and identify the remaining choices rather than claiming Discovery has started.

## Verify and hand back

Capture the returned run ID immediately. Use the UI origin for the link:

- Running Discovery: `<ui-origin>/projects/<project-id>/discover/<run-id>`
- Parked setup: `<ui-origin>/projects/<project-id>/discover/setup/<run-id>`

Inspect `discovery get` for the intended source, script, machine, execution mode and model. Report any mismatch before further work. For execution, follow baseline status and actual command outcomes; a no-execution run does not need a machine observation or a custom results file. Never fabricate metric UUIDs or overwrite a metrics schema to make a failed run appear ready.

A finalized baseline is not proof of exploration. Poll status and versions using supported commands until at least one candidate appears, a terminal outcome is observed, or the agreed monitoring boundary is reached. State which of those happened. A still-running job at the boundary is not complete.

On failure, preserve the project and run IDs and use `discovery-inspect` to inspect the source, agent state, commands and logs. Do not re-import the repository as a default recovery action; that loses context and creates duplicate projects. Return the existing run link, observed failure and next required action.
