---
name: cli-setup
description: Install, update, and authenticate the supported artemis CLI through the official installer. Use when an end user needs to set up or update the artemis CLI.
compatibility: Requires Artemis CLI 1.1.5 or newer.
metadata:
  artemis-cli-min: "1.1.5"
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
- An API key for the target deployment, created by the user in the Web UI (`<deployment-base-url>/settings/api-keys`, for example `https://dev.artemis.turintech.ai/settings/api-keys`). The agent cannot create one, and it must be entered by the user in their own terminal, never in chat.

## Install with the official installer

1. Open `<deployment-base-url>/settings/cli` for the deployment you are setting up. The Web UI is the source of truth; if the download, credentials, flags, or artifact below differ or fail, use the command currently published there.
2. Confirm whether this is hosted Artemis or an on-prem deployment with a custom base URL — it selects which invocation below to use.

The installer detects the platform, installs the CLI, and configures service endpoints.

**Check which version it produces before relying on it.** Its built-in download source currently carries nothing above 1.0.11, which cannot run a discovery run on a current deployment. On dev, testing, or any deployment needing 1.1.5 or newer, use the direct download in *The installer's own download source is stale* below, then `artemis login`. Use the installer when 1.0.11 is genuinely enough, or once the file server is fixed.

For hosted (SaaS) Artemis:

```bash
(
  set -e
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  curl -fL --anyauth -u "Artemis_User:Artemis_Custom_Runner_2025" \
    "https://files.artemis.turintech.ai/public/artemis-cli/latest/artemis-cli-installer.sh" \
    -o "$TMP/installer.sh"
  chmod +x "$TMP/installer.sh"
  "$TMP/installer.sh"
)
```

For on-prem Artemis, add the deployment's base URL:

```bash
(
  set -e
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  curl -fL --anyauth -u "Artemis_User:Artemis_Custom_Runner_2025" \
    "https://files.artemis.turintech.ai/public/artemis-cli/latest/artemis-cli-installer.sh" \
    -o "$TMP/installer.sh"
  chmod +x "$TMP/installer.sh"
  "$TMP/installer.sh" --base-url https://your-custom.artemis.turintech.ai
)
```

The installer selects two independent things. **Which build:** the newest stable release by default, or `--version X.Y.Z` to pin one, `--nightly` to include prereleases, `--dev` for the rolling development build. **Which deployment the CLI points at:** `--base-url` with a full URL, which writes the endpoint config and does not change where the binary is downloaded from.

### The installer's own download source is stale (verified 16 September 2026)

The installer has `https://files.artemis.turintech.ai/artemis-cli` built in, and that path carries no release above **1.0.11**. Everything it can reach from there is too old for current deployments:

| What you ask for | What you get |
|---|---|
| default, or `--nightly` | 1.0.11 |
| `--dev` | a rolling build from 30 July |
| `--version 1.1.5` or `1.1.7` | fails, no such directory on that path |

None of those have `--script`, `--eval-runs`, `--source-changeset` or `project scripts`, so a CLI installed that way cannot start a discovery run on a current deployment.

**Install the binary directly from the public path instead**, which does carry current releases. Check the directory first and take the newest, rather than trusting a version named here:

```bash
curl -s --anyauth -u "Artemis_User:Artemis_Custom_Runner_2025" \
  "https://files.artemis.turintech.ai/public/artemis-cli/" \
  | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | sort -uV | tail -5
```

Then fetch that version for the platform, verify it, and put it on `PATH`:

```bash
VER=1.1.7   # replace with the newest from the listing above
PLATFORM="linux-amd64"   # or darwin-arm64, darwin-amd64, linux-arm64, windows-amd64.exe
curl -fL --anyauth -u "Artemis_User:Artemis_Custom_Runner_2025" \
  "https://files.artemis.turintech.ai/public/artemis-cli/$VER/artemis-cli-$PLATFORM" \
  -o ~/.local/bin/artemis && chmod +x ~/.local/bin/artemis
artemis --version
```

A direct download configures no endpoints, so follow it with `artemis login --url <deployment-base-url>`.

Report the stale installer source rather than working around it silently: it affects every new user who follows the published instructions.

The download credentials above are the published shared ones from the Web UI and the docs, not per-user secrets, so they can be used directly. Any *API key* is still a secret and must never enter the conversation.

Do not guess installer flags: the live installer may have changed.

## Authenticate

The installer configures endpoints but the CLI still needs the API key described in Requirements.

**In the browser route, take the user to the page rather than printing a link.** Being shown where to go is most of the value of the browser walkthrough, so hand off to `ui-walkthrough`: open the API keys page on their deployment, put the pointer on the control that creates a key, say plainly that this step is theirs, and wait there. Never read, type, or copy the key, and never ask for it in chat. Print the link only when there is no browser control, and check that properly first: on hosts where the browser tools are deferred they must be loaded before they can be seen at all, so a missing tool is not the same as a missing browser. See `ui-walkthrough` section 1.

Then have the user run the interactive login themselves:

```bash
artemis login --url <deployment-base-url>
```

`login` also accepts the shorthand names `dev`, `stg` and `prod`, but prefer the full URL so the deployment is unambiguous in the transcript.

For on-prem, use the base URL accepted by `artemis login --help`. Do not set individual service URLs unless the current CLI explicitly requires it; the base URL normally derives them.

Config precedence is `./.env` before `~/.config/artemis/.env`. Keep keys in the home config: a project-local `.env` is easy to leak and shadows the home config.

### Deployments with a self-signed certificate

Some deployments, including `dev`, present a certificate the system trust store does not know. `artemis login` and `artemis status` then fail with an `x509` or "unknown authority" error. Point the CLI at the deployment's CA bundle:

```bash
export SSL_CERT_FILE="$HOME/.config/artemis/ca-bundle.pem"
```

Two things make this fail quietly, so handle both:

- **Put it where every shell reads it, not only `~/.bashrc`.** A login shell reads `~/.bash_profile` or `~/.profile` and ignores `~/.bashrc` unless one of those sources it. If neither file exists, create `~/.profile` with the export as well, or the variable is missing from exactly the sessions the user opens next.
- **Long-lived processes do not inherit it later.** The runner keeps whatever environment it was started with, so the variable belongs in its start command too. See `runner-setup`.

Verify in a shell that did not set it interactively, rather than in the one where you just exported it:

```bash
bash -lc 'artemis status'
```

Ask the user where the bundle came from before trusting it. Never fetch a CA bundle from a source the user did not name, and never disable certificate verification to work around this.

## Verify

Compare the installed CLI with the skills you are about to use. Each skill declares its minimum in its frontmatter as `metadata.artemis-cli-min`. Read `artemis --version`: a release reports a version such as `1.1.5`; a development build reports `dev-<timestamp>-<sha>` and counts as newer than every release. If the installed release is lower than the highest minimum required, update the CLI before continuing.

```bash
artemis --version || artemis version
artemis status
```

Confirm the build carries the command groups the task needs. For Discovery on current deployments, the CLI must expose:

```bash
artemis project scripts --help
artemis discovery create --help
```

`discovery create` must accept `--script` and `--llm-metrics`. Update the CLI if either flag is missing, using the direct download above rather than `--dev`: the installer's `dev` channel is months behind and has neither flag.

Report the installed version, base URL, and authenticated user. Do not report success if `status` shows missing endpoints or an unauthenticated session.

## Update

Record the current version, rerun the installer for the same deployment, and repeat authentication and status verification. Report the version before and after. Do not change deployment while performing an update.
