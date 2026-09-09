---
name: cli-setup
description: Install, update, and authenticate Artemis CLI on macOS, Linux, or Windows using the official distribution. Use when a task needs CLI capabilities or authentication that are not already available.
---

# Set up Artemis CLI

Reuse a working installation and login. Connecting a machine alone does not require this skill: `runner-setup` installs the separate machine software. Return to the user's original task once CLI setup is verified.

## Check the environment and task

Detect the operating system, architecture and shell. Check `command -v artemis` on macOS/Linux or `Get-Command artemis -ErrorAction SilentlyContinue` in PowerShell, then `artemis version`. Keep the CLI in the same environment as the coding agent; WSL and native Windows installations are separate.

Use the supplied API deployment for requests and the supplied UI origin for browser links. A localhost UI may use a remote API. Do not replace the user's deployment with production. The UI setup page is `{ui-origin}/settings/connect-agent`, titled **Use Artemis with your agent**.

When supported, run `artemis --output-format json capabilities` once. A valid report has `version` and `commands` entries with exact `command` paths and `flags`. Check the commands and flags needed for the user's task. If the command is absent or returns help instead of that report, fall back to command-specific `--help`; a zero exit code or parent help does not prove support. The report describes the installed CLI, not server compatibility or authentication.

If missing, ask the user to install the CLI and offer to do it. If installed, compare official release information and required capabilities before updating; do not downgrade a newer build. Ask before installation or an update unless already authorised. If the installed binary already matches stable but lacks required commands, report the release requirement and offer the matching UI journey. Reinstalling the same release will not add commands. Do not silently select nightly/dev or substitute a different code workflow.

## Install or update

No GitHub account or source checkout is required. Use the public distribution at `https://files.artemis.turintech.ai/public/artemis-cli/latest/`.

### macOS and Linux

Download the installer into a temporary directory, inspect it, then run it with the requested API deployment:

```bash
curl -fL "https://files.artemis.turintech.ai/public/artemis-cli/latest/artemis-cli-installer.sh" \
  -o installer.sh
chmod +x installer.sh
./installer.sh --base-url "<deployment>"
```

The installer detects the platform, defaults to the latest stable release and `~/.local/bin`, and configures endpoints. Its current options include `--install-dir`, `--version`, `--nightly` and `--dev`; confirm live installer help before using options. Keep the same deployment during updates. Installation does not create an API key or authenticate the CLI. If configuration fails, inspect the installed binary and login help before reinstalling.

### Native Windows PowerShell

Use the Windows x64 binary `artemis-cli-windows-amd64.exe` and `checksums.txt` from the same public distribution directory. Download both into a temporary directory. Require exactly one checksum entry for that filename and compare it with `Get-FileHash -Algorithm SHA256` before installing. Stop on a missing, ambiguous or mismatched checksum.

Install as `artemis.exe` in a user-owned directory such as `$env:LOCALAPPDATA\Artemis\bin`, add that directory once to the user's PATH and the current shell PATH, and verify `artemis version`. This does not require administrator access or an execution-policy change. Do not run Bash commands in PowerShell. On Windows ARM64, confirm x64 emulation before using this build; do not invent an ARM64 artifact. The UI's manual setup tab provides a copyable PowerShell script for these steps.

Open a new terminal if another agent session needs the updated PATH. Recheck the installed version and task capabilities after an update.

## Authenticate and verify

Inspect `artemis status` without printing secrets. Reuse an authenticated login for the requested deployment. When login is needed, show the supplied `apiKeysUrl`, or `{ui-origin}/settings/api-keys`, and tell the user to generate a key there if they do not already have one. Keys belong to one deployment. Never ask for a key in chat or place it in repository files or command arguments.

Have the user run the following in their own terminal so the CLI prompts privately:

```bash
artemis login --url "<deployment>"
```

Wait for login to finish, then check `artemis status` and one read-only request for the supplied project (or another resource relevant to the task). Do not claim success from local configuration or a capability report alone. A request failure does not imply the project must be imported again.

Report the installed version, deployment, and verification outcome without credentials. Continue the original task automatically when its requirements are met; otherwise identify the specific missing capability or authentication step.
