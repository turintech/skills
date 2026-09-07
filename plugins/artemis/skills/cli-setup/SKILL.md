---
name: cli-setup
description: Install, update, and connect the supported artemis CLI through the official installer. Use when an end user needs to set up or update the artemis CLI.
---

# Set up the artemis CLI

## At a glance

- **Problem:** Installs, updates, and connects the Artemis CLI to a deployment through the supported installer without requiring GitHub or source access.
- **Must be available:** Network access to the file server and the Artemis deployment, plus a credential the user enters in their own terminal — a registration token from the deployment's Connect Your Agent page, or an API key created in the Web UI.
- **Use / don't use:** Use when the CLI is missing, outdated, or not connected; skip it when `artemis status` already reports the intended deployment and an authenticated user.
- **Next skill:** Return to `artemis` routing, usually toward `runner-setup`, `project-import`, or `repo-command-setup`.

Use the supported distribution. This path requires no GitHub account and does not assume access to the CLI source repository.

## Requirements

- Network access to `files.artemis.turintech.ai` and the deployment's URL.
- The deployment URL. The setup prompt pasted from the Web UI names it as `Artemis deployment: <url>`; otherwise ask. Hosted Artemis is `https://artemis.turintech.ai`; an on-prem deployment is wherever its Web UI is served from.
- A credential for that deployment, entered by the user in their own terminal, never in chat. Either works and both store the same kind of key:
  - A **registration token** from `<deployment>/settings/connect-agent` (also `<deployment>/settings/runners/new`). It is minted per visit, expires in an hour, and the CLI exchanges it for this machine's own API key.
  - An **API key** created by the user under `<deployment>/settings/api-keys`.

## Install with the official installer

1. Open `<deployment>/settings/connect-agent`. The Web UI is the source of truth; if the download, credentials, flags, or artifact below differ or fail, use the command currently published there.
2. Inspect what is already installed: `artemis version` printing a version means the installer can be skipped.

The installer detects the platform, downloads the binary, verifies its checksum and puts it on `PATH`. It does not know which deployment you use — connecting is the binary's job, in the next section — so the same command serves hosted and on-prem alike.

Linux, macOS and WSL:

```bash
(
  set -e
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  curl -fL --digest -u "Artemis_User:Artemis_Custom_Runner_2025" \
    "https://files.artemis.turintech.ai/public/artemis-cli/latest/artemis-cli-installer.sh" \
    -o "$TMP/installer.sh"
  chmod +x "$TMP/installer.sh"
  "$TMP/installer.sh"
)
```

Windows, from PowerShell:

```powershell
curl.exe -L --digest -u "Artemis_User:Artemis_Custom_Runner_2025" `
  "https://files.artemis.turintech.ai/public/artemis-cli/latest/artemis-cli-installer.ps1" `
  -o installer.ps1
powershell -ExecutionPolicy Bypass -File .\installer.ps1
```

Windows, from Command Prompt: the same download with `artemis-cli-installer.cmd`, then `installer.cmd`.

The `latest/` path always serves the current installer. It selects only **which build**: the newest stable release by default, `--version X.Y.Z` to pin one, `--nightly` to include prereleases, `--dev` for the rolling development build (`-Version`, `-Nightly`, `-Dev` in PowerShell). `--install-dir` (or `ARTEMIS_INSTALL_DIR`) moves the binary from the default `~/.local/bin` (`%LOCALAPPDATA%\Programs\artemis` on Windows). There is no deployment flag any more; an older `--env` or `--base-url` is rejected.

The download credentials above are the published shared ones from the Web UI and the docs, not per-user secrets, so they can be used directly. A registration token or API key is still a secret and must never enter the conversation.

Do not guess installer flags: the live installer may have changed.

## Connect

`artemis login` is the only command that acquires a credential. It verifies the deployment is reachable, validates the credential against it, and stores both in `environments.yaml` under the config directory (`~/.config/artemis` on Linux, `~/Library/Application Support/artemis` on macOS, `%AppData%\artemis` on Windows; `ARTEMIS_CONFIG_DIR` overrides). The CLI and the runner read that one record, so logging in once serves both.

Have the user run it themselves, in their own terminal:

```bash
artemis login <deployment-url> --token <registration token>   # from Connect Your Agent
artemis login <deployment-url>                                  # prompts for an API key, masked
```

The prompt is only offered in a terminal; with `--output-format json` the command errors instead. `--api-key <key>` exists for scripts but puts the key in shell history and `ps`, so do not suggest it to a person. Do not set individual service URLs unless the current CLI explicitly requires it; the deployment URL derives them.

A machine can hold several deployments. `artemis env list` shows them, `artemis env current` the active one, `artemis env use <alias-or-url>` switches; a second `login` against another URL adds a record without touching the first. `ARTEMIS_URL` and `ARTEMIS_API_KEY` in the environment override the record for one command. The older `.env` files are gone; an install that still has one is migrated on the first run and says so.

Non-credential settings live in `settings.yaml` beside it, read with `artemis config show` and written with `artemis config set <section.key> <value>` — for example `network.ca_cert` for a deployment behind a private CA, or `cli.timeout`.

## Verify

```bash
artemis version
artemis status
```

Confirm the build carries the command groups the task needs — for example `artemis discovery --help`.

Report the installed version, deployment URL, and authenticated user. Do not report success if `status` shows missing endpoints or an unauthenticated session.

## Update

Record the current version, rerun the installer, and repeat `artemis status`. The stored record survives a reinstall, so no new login is needed. Report the version before and after. Do not change deployment while performing an update.
