---
name: cli-setup
description: Install, update, and authenticate the supported artemis CLI through the official installer. Use when an end user needs to set up or update the artemis CLI.
compatibility: Production Platform 3.0.3 onboarding requires the Artemis CLI 1.0.8 command surface; stable CLI 1.0.9 through 1.0.11 are not compatible.
metadata:
  artemis-cli-min: "1.0.8"
  artemis-cli-tested: "1.0.8"
  artemis-platform-min: "3.0.3"
---

# Set up the artemis CLI

## At a glance

- **Problem:** Installs, updates, and authenticates the Artemis CLI through the supported installer without requiring GitHub or source access.
- **Must be available:** Network access to the file server and Artemis deployment, plus an API key created in the Web UI and entered by the user in their own terminal.
- **Use / don't use:** Use when the CLI is missing, outdated, or unauthenticated; skip it when a working authenticated CLI is already available.
- **Next skill:** Return to `artemis` routing, usually toward `runner-setup`, `project-import`, or `repo-command-setup`.

Use the supported distribution. This path requires no GitHub account and does not assume access to the CLI source repository.

For production Platform 3.0.3, install CLI **1.0.8 exactly**. Do not infer compatibility from semver: the required `changeset create` and `changeset validate` surface exists in 1.0.8 but is absent from stable 1.0.9 through 1.0.11. Do not substitute `latest`, `--nightly`, or `--dev`.

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
    "https://files.artemis.turintech.ai/artemis-cli/latest/artemis-cli-installer.sh" \
    -o "$TMP/installer.sh"
  chmod +x "$TMP/installer.sh"
  if ! "$TMP/installer.sh" --version 1.0.8; then
    # Some installer revisions return non-zero after placing the binary but
    # before authentication has been configured. Verify the payload itself.
    export PATH="$HOME/.local/bin:$PATH"
    artemis --version 2>/dev/null | grep -q '1\.0\.8' || exit 1
  fi
)
```

For on-prem Artemis, add the deployment's base URL:

```bash
(
  set -e
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  curl -fL --anyauth -u "Artemis_User:Artemis_Custom_Runner_2025" \
    "https://files.artemis.turintech.ai/artemis-cli/latest/artemis-cli-installer.sh" \
    -o "$TMP/installer.sh"
  chmod +x "$TMP/installer.sh"
  if ! "$TMP/installer.sh" --version 1.0.8 \
      --base-url https://your-custom.artemis.turintech.ai; then
    export PATH="$HOME/.local/bin:$PATH"
    artemis --version 2>/dev/null | grep -q '1\.0\.8' || exit 1
  fi
)
```

The `latest/` path above fetches the current **installer script**, not the CLI payload. `--version 1.0.8` pins the payload. The deployment remains a separate choice: hosted production is the default, while on-prem uses `--base-url`.

The download credentials above are the published shared ones from the Web UI and the docs, not per-user secrets, so they can be used directly. Any *API key* is still a secret and must never enter the conversation.

Do not guess installer flags or switch channels. If the installer no longer accepts `--version 1.0.8`, stop and report that the production-compatible CLI cannot be installed through the published route.

## Authenticate

The installer configures endpoints but the CLI still needs the API key described in Requirements. Have the user run the interactive login themselves:

```bash
artemis login --url prod
```

For on-prem, use the base URL accepted by `artemis login --help`. Do not set individual service URLs unless the current CLI explicitly requires it; the base URL normally derives them.

Config precedence is `./.env` before `~/.config/artemis/.env`. Keep keys in the home config: a project-local `.env` is easy to leak and shadows the home config.

## Verify

```bash
export PATH="$HOME/.local/bin:$PATH"
artemis --version || artemis version
artemis status
artemis changeset create --help
artemis changeset validate --help
artemis discovery create --help
```

Confirm the version is 1.0.8 and the build carries:

- `changeset create`;
- `changeset validate` with repeatable `--command`, `--version`, `--runner`, and `--wait`;
- `discovery create` with `--compile-cmd`, `--test-cmd`, and `--benchmark-cmd`.

If any check is missing, stop. `validation run`, a dev build, and a newer stable CLI are not substitutes for this production flow.

Report the installed version, base URL, and authenticated user. Do not report success if `status` shows missing endpoints or an unauthenticated session.

## Update

Record the current version and command surface. For Platform 3.0.3, reinstall 1.0.8 exactly and repeat authentication and verification. Do not follow an upgrade prompt, switch to `latest`, or change deployment while repairing this production setup.
