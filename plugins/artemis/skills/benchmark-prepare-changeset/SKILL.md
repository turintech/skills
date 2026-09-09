---
name: benchmark-prepare-changeset
description: Prepare a correctness-gated Artemis benchmark with a local agent, saving repository edits into a specified Artemis changeset through the CLI. Use for the local-agent changeset workflow, not the commit-and-push Git workflow.
---

# Report metrics from an Artemis Branch

The UI calls this workspace an **Artemis Branch**. The API and CLI still use `changeset`; retain those command names and use the same workspace ID in `/branches/{id}` UI links.

Use the deployment, project ID, changeset ID, branch and objective supplied with the request. A changeset is the workspace for repository edits and validation; project scripts are shared templates. Preserve the supplied changeset instead of creating another. `sourceSha`, when supplied, records the source when the prompt was copied. Verify the downloaded code matches that source before editing. If the branch has advanced, explain the difference and confirm the intended starting version rather than silently preparing different code.

## Install or update the CLI and sign in first

Complete this setup before downloading, editing or validating the benchmark.

1. Detect the operating system, architecture and shell. Check `command -v artemis` on macOS/Linux or `Get-Command artemis -ErrorAction SilentlyContinue` in native Windows PowerShell, `artemis version`, and `artemis --help`. If missing, ask the user to install Artemis CLI, offering to do the installation for them. If present, check the official release information and required command help to decide whether an update is needed. Do not invent an `artemis update` command, downgrade a newer installation, or claim it is current when release information is unavailable. Ask before installing an update unless already authorised.
2. Use the official installer below for installation or an approved update on macOS/Linux (or a supported Bash environment). Download into a temporary directory, inspect it, then execute it with the requested deployment substituted for `<deployment>`:

   ```bash
   curl -fL "https://files.artemis.turintech.ai/public/artemis-cli/latest/artemis-cli-installer.sh" -o installer.sh
   chmod +x installer.sh
   ./installer.sh --base-url "<deployment>"
   ```

   The installer defaults to the newest stable release and `~/.local/bin`; it also supports `--install-dir`, `--version`, `--nightly` and `--dev`. Use stable by default; ask before switching release channels. Check PATH and re-run `artemis version` after installation. An installer configuration error does not necessarily mean the binary was not installed: inspect the result and `artemis login --help` before retrying. CLI documentation: https://docs.artemis.turintech.ai/features/artemis-cli.

   For native Windows PowerShell, download https://files.artemis.turintech.ai/public/artemis-cli/latest/artemis-cli-windows-amd64.exe into a temporary directory with `Invoke-WebRequest`. Verify its SHA256 using `Get-FileHash` against the matching filename in https://files.artemis.turintech.ai/public/artemis-cli/latest/checksums.txt; stop on a missing or mismatched checksum. Install as `artemis.exe` in a user-owned directory such as `%LOCALAPPDATA%\Artemis\bin`, add that directory to the user and current-session PATH without replacing existing entries, and verify `artemis version`. Do not require administrator rights, change execution policy, or run Bash syntax in PowerShell. The published Windows binary is x64; confirm x64 emulation before using it on ARM64. WSL uses the Linux installer and has a separate installation and configuration. Keep the CLI in the environment where the agent runs.

3. Confirm that command-specific help exposes `changeset download`, `changeset save`, `changeset validate`, and `project scripts`, including the flags needed below. Check `changeset create` only when a new changeset is needed. A zero exit code is insufficient: older CLIs can print parent help for an unsupported subcommand. Parent usage such as `artemis changeset [command]` does not establish support for `changeset save`. If the installed CLI matches the official stable release but lacks a required command, stop and report a CLI release requirement; repeatedly reinstalling the same release will not help. Do not switch to a development channel or the Git workflow without the user choosing it.
4. Inspect `artemis status` without exposing credentials. Reuse an authenticated login for the requested deployment. Only when login is needed, explicitly show the clickable `apiKeysUrl` supplied with this request, or `{deployment}/settings/api-keys`, and say: “Open API Keys in Artemis and create a key for this deployment if you do not already have one. Keep it out of this chat; enter it in your own terminal when Artemis asks.” API-key help: https://docs.artemis.turintech.ai/settings/user-settings#api-keys. Installation does not create or configure an API key. Keys belong to a particular deployment; do not silently use production for a development project. If the supplied localhost URL serves only the UI, confirm the actual Artemis API deployment before configuring the CLI.
5. When login is needed, have the user run `artemis login --url "<deployment>"` in their own terminal, with no `--api-key` argument, so the CLI prompts privately. Wait for the user to finish, then verify `artemis status`. For both reused and new logins, verify a read-only request for the supplied project. Never request a key in chat, print configuration secrets, or put a key in a command, file in the repository, or copied prompt. If login or the required commands are still unavailable after an approved update, explain the blocker and stop before benchmark work.
6. Once installation and authentication are verified, continue with the supplied benchmark objective and the same changeset automatically.

## Establish the workspace

1. When no changeset was supplied, list the project's changesets and reuse one only when its branch and code match the requested work. Otherwise create one with `artemis changeset create --project <project-id> --name "Prepare benchmark"`. Check the returned branch and base SHA before editing. The CLI create command may use the project base; if another branch is required, use the UI branch-aware changeset creation flow and resume with its ID.
2. Download the target's latest version into a dedicated empty workspace:

   ```bash
   artemis changeset download <changeset-id> --project <project-id> --out <workspace>
   ```

   Retain `.artemis/changeset.json`, which records the project, changeset, source SHA and file hashes. Do not overwrite an active checkout or use files from a different branch. Record the starting SHA.

## Report metrics from existing code

Start with the code and commands the user already runs. Ask which metrics matter when that is unclear. Reuse existing output or add instrumentation to those commands; a separate benchmark harness is optional and should be proposed only when the current commands cannot produce useful measurements. Preserve correctness checks and keep setup, downloads, compilation and warmup outside timed regions.

Use repository-owned, non-interactive commands from the root. A script has ordered `setup`, `benchmark` and `teardown` phases: setup builds and checks correctness once, benchmark measures the workload and may repeat, teardown cleans up. Preserve non-zero failures. Do not weaken tests or substitute fabricated measurements.

Use built-in Runtime, CPU and Memory command measurements when they cover the requested metrics. For custom metrics, write fresh `artemis_results.json` or `artemis_results.csv` in the invocation directory (the project root). JSON accepts one object or an array of objects; CSV needs a header and numeric rows. Values must be finite numbers, with stable metric names and units. No strings, booleans, null or nested values. JSON takes precedence if both files exist. Remove stale output before measuring and write the new output atomically where practical. If the workload runs elsewhere, copy its fresh output back and propagate failures.

Run the exact setup and benchmark commands locally when the environment supports them. Verify correctness and fresh numeric output. Report local limitations without calling them runner verification.

If the existing script runs successfully but structured metrics cannot yet be produced, preserve the working commands and logs. Report execution success and missing measurements separately, explain what is needed to add metrics, and return the saved workspace for review. Do not fabricate numbers, call successful execution a failed benchmark, or claim log output establishes measured performance. The user can choose Discovery with Artemis Score while keeping measured metrics optional.

## Save and validate the same changeset

Review the diff and check the remote changeset head still matches the downloaded version before saving. If another agent changed it, reconcile in a fresh workspace; do not overwrite its edits. Save only the intended source, harness and configuration paths, with explicit `--delete` entries for intended removals:

```bash
artemis changeset save <changeset-id> --project <project-id> --root <workspace> \
  -m "Prepare correctness-gated benchmark" <changed-path> <new-harness-path>
```

Do not use a blanket save after a build: it can upload generated output, dependencies or results. Do not publish, open a PR, or push to the external Git provider as part of this workflow.

Inspect existing scripts with `artemis project scripts list --project <project-id>`. Reuse a matching template or create a separately named script for this preparation. Avoid overwriting another workflow's shared script or changing the project default incidentally. `artemis project scripts create --help` documents `--setup-cmd`, `--benchmark-cmd`, `--teardown-cmd` and the JSON command-list `--file` option.

Use the supplied `machineName` when it identifies one accessible machine suitable for these commands. If no machine is connected, show `connectMachineUrl` and help the user connect it; do not choose an arbitrary runner or describe local execution as an Artemis validation.

Validate the **saved version SHA**, not `original`, with the selected runner and explicit script:

```bash
artemis changeset validate <changeset-id> --project <project-id> \
  --version <saved-version-sha> --script <script-id> --runner <runner-name> --wait
```

Bound the validation to a baseline check; do not launch an optimisation search unless requested. Inspect validation status, command exits, logs and recorded metrics using the installed CLI's help. A successful save or locally valid JSON alone does not prove Artemis readiness.

Return the changeset URL, saved SHA, script ID, runner, literal commands, metric names/units/directions, validation ID and observed results. Distinguish completed checks from anything still unverified. Keep subsequent fixes in this changeset.

Finish with a clickable **Review benchmark in Artemis** link to the saved version, not an unpinned overview. Use `measuredVersionUrlTemplate` when supplied; otherwise construct `{deployment}/projects/{project-id}/branches/{changeset-id}/benchmarks?head={saved-version-sha}&metricScript={script-id}`. Replace every placeholder with observed IDs, URL-encode path and query values, and preserve the requested deployment. Include a URL-encoded `machine` query parameter for the machine actually selected for validation; replace any machine already in the template if the user chose a different one. Omit this parameter if no machine was selected. This opens the saved code and script even if the changeset advances later, and preserves the machine for subsequent runs. If no script was configured, omit `metricScript`; if saving has not succeeded, do not invent a saved SHA or claim the link is a verified baseline. The generic `returnUrl` is only a fallback for locating the workspace. Do not create another changeset when the user follows up from this link.
