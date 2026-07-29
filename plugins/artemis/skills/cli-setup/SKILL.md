---
name: cli-setup
description: Install, update, and authenticate the supported artemis CLI through the official installer. Use when an end user needs to set up or update the artemis CLI.
---

# Set up the artemis CLI

## At a glance

- **Problem:** Installs, updates, and authenticates the Artemis CLI through the supported installer without requiring GitHub or source access.
- **Must be available:** Network access to the file server and Artemis deployment, plus an API key created in the Web UI and entered by the user in their own terminal.
- **Use / don't use:** Use when the CLI is missing, outdated, or unauthenticated; skip it when a working authenticated CLI is already available.
- **Next skill:** Return to `artemis` routing, usually toward `runner-setup`, `project-import`, or `repo-command-setup`.

Use the supported distribution. This path requires no GitHub account and does not assume access to the CLI source repository.

## Requirements

- Network access to `files.artemis.turintech.ai` and the deployment's base URL.
- An API key for the target deployment — created by the user in the Web UI (`https://artemis.turintech.ai/settings/api-keys` for hosted, the same path on an on-prem deployment's base URL). The agent cannot create one, and it must be entered by the user in their own terminal, never in chat.

## Install with the official installer

1. Open https://artemis.turintech.ai/settings/cli. The Web UI is the source of truth; if the download, credentials, flags, or artifact below differ or fail, use the command currently published there.
2. Confirm whether this is hosted Artemis or an on-prem deployment with a custom base URL — it selects which invocation below to use.

The installer detects the platform, installs the CLI, and configures service endpoints. The commands below are the direct supported route and avoid unnecessary navigation when they still match the published setup flow.

For hosted (SaaS) Artemis:

```bash
(
  set -e
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  curl -fL --anyauth -u "Artemis_User:Artemis_Custom_Runner_2025" \
    "https://files.artemis.turintech.ai/artemis-cli/prod/artemis-cli-installer.sh" \
    -o "$TMP/installer.sh"
  chmod +x "$TMP/installer.sh"
  "$TMP/installer.sh" --env prod
)
```

For on-prem Artemis, keep `--env prod` and add the deployment's base URL:

```bash
(
  set -e
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  curl -fL --anyauth -u "Artemis_User:Artemis_Custom_Runner_2025" \
    "https://files.artemis.turintech.ai/artemis-cli/prod/artemis-cli-installer.sh" \
    -o "$TMP/installer.sh"
  chmod +x "$TMP/installer.sh"
  "$TMP/installer.sh" --env prod \
    --base-url https://your-custom.artemis.turintech.ai
)
```

The two flags control different things: `--env` selects the download directory on the file server, `--base-url` sets the service endpoints written to the config. Keep `--env prod` in the on-prem form — the installer defaults `ENV` to `stg` when `--env` is absent, so dropping it silently installs a staging binary.

The download credentials above are the published shared ones from the Web UI and the docs, not per-user secrets, so they can be used directly. Any *API key* is still a secret and must never enter the conversation.

Do not guess installer flags: the live installer may have changed.

## Authenticate

The installer configures endpoints but the CLI still needs the API key described in Requirements. Have the user run the interactive login themselves:

```bash
artemis login --url prod
```

For on-prem, use the base URL accepted by `artemis login --help`. Do not set individual service URLs unless the current CLI explicitly requires it; the base URL normally derives them.

Config precedence is `./.env` before `~/.config/artemis/.env`. Keep keys in the home config: a project-local `.env` is easy to leak and shadows the home config.

## Verify

```bash
artemis --version || artemis version
artemis status
```

Report the installed version, base URL, and authenticated user. Do not report success if `status` shows missing endpoints or an unauthenticated session.

## Update

Record the current version, rerun the installer for the same deployment, and repeat authentication and status verification. Report the version before and after. Do not change deployment while performing an update.
