---
name: cli-setup
description: Install, update, and authenticate the supported artemis CLI through the official installer. Use when an end user needs to set up or update the artemis CLI.
compatibility: Requires Artemis CLI 1.1.8+ and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.8"
  artemis-platform-min: "3.1.0"
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
- An API key for the target deployment, created by the user in the Web UI (`<deployment-base-url>/settings/api-keys`, for example `https://artemis.turintech.ai/settings/api-keys`). The agent cannot create one, and it must be entered by the user in their own terminal, never in chat.

## Check what is already there

Before installing anything, look at the CLI that is already on this machine:

```bash
artemis --version
artemis status
```

If the version meets the skills' minimum (see *Verify*) and `status` is authenticated to the target deployment, there is nothing to do here. If it is installed but older, this is an update, not a fresh install. If it is authenticated to a different deployment, say which one and ask before logging it in elsewhere: the user may still be using that login.

## Install the CLI

Start here when there is no CLI, or it needs replacing. The deployment's own page at `<deployment-base-url>/settings/cli` is the source of truth for credentials and flags, and if anything below differs from it, follow the page.

**Do not reach for the official installer script first.** It has `https://files.artemis.turintech.ai/artemis-cli` built in, and that path carries no release above **1.0.11**:

| What you ask for | What you get |
|---|---|
| default, or `--nightly` | 1.0.11 |
| `--dev` | a rolling build from 30 July |
| `--version 1.1.8` | fails, no such directory on that path |

None of those have `--script`, `--eval-runs`, `--source-changeset` or `project scripts`, so a CLI installed that way cannot start a discovery run at all. The installer is still the documented route and will be right again once its source is fixed, so it is kept at the end of this skill; until then it is a footnote, not the path.

### Where to download from

**If the setup prompt or the user gave a CLI download directory, start there.** It is the deployment's own choice of build, and it holds the binaries directly under the names below. Check what it serves before keeping it: download, run `--version`, and compare with the minimum. The default directory, `https://files.artemis.turintech.ai/public/artemis-cli/latest/`, still serves **1.0.11**, which cannot start a discovery run. When the directory's build is older than the minimum, use the newest release from the public listing instead, and say in one line which directory was out of date.

```bash
DIR="<the CLI download directory from the prompt>"
PLATFORM="linux-amd64"   # see the table below
curl -fL "$DIR/artemis-cli-$PLATFORM" -o ~/.local/bin/artemis && chmod +x ~/.local/bin/artemis
artemis --version
```

Only send the shared download credentials to `files.artemis.turintech.ai`. A directory on any other host gets a plain request.

**Match the build to this machine.** Read `uname -s` and `uname -m` (on Windows, the processor architecture), and pick the file:

| Machine | File |
|---|---|
| Linux, `x86_64` | `artemis-cli-linux-amd64` |
| Linux, `aarch64` or `arm64` | `artemis-cli-linux-arm64` |
| macOS, Apple silicon (`arm64`) | `artemis-cli-darwin-arm64` |
| macOS, Intel (`x86_64`) | `artemis-cli-darwin-amd64` |
| Windows, x64 | `artemis-cli-windows-amd64.exe` |
| Windows, ARM64 | `artemis-cli-windows-arm64.exe` |

If the directory has no file for this machine, never install a different architecture's build in its place: it either fails to start or runs under emulation and misbehaves later. Try the newest versioned release, which carries all six, and if that has none either, tell the user no build exists for this machine and stop. Channels differ: `latest/` has no Windows ARM64 build today, while the versioned releases do.

Without a directory from the prompt, install from the public path, which carries current releases. Check the listing first and take the newest, rather than trusting a version named here:

```bash
curl -s --anyauth -u "Artemis_User:Artemis_Custom_Runner_2025" \
  "https://files.artemis.turintech.ai/public/artemis-cli/" \
  | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | sort -uV | tail -5
```

Then fetch that version for the platform, verify it, and put it on `PATH`:

```bash
VER=1.1.8   # or the newest in the listing above, never older than the skills require
PLATFORM="linux-amd64"   # from the table above
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

One invariant decides the order here: **the key is the last thing the user copies.** Anything they have to copy after it overwrites it on the clipboard.

1. **In the browser route, open the API keys page first**, with `ui-walkthrough`, pointer on the control that creates a key. Navigating costs the user nothing and touches no clipboard. Being shown where to go is most of the value of that route, so do not settle for printing a link until you have checked properly: on hosts where the browser tools are deferred they must be loaded before they can be seen at all, so a missing tool is not the same as a missing browser (`ui-walkthrough` section 1).
2. **Then send the step as its own message**, two numbered boxes and nothing else.
3. **The user acts:** they paste the command, create the key on the page already in front of them, and paste it at the waiting `API key:` prompt.

Never read, type or copy a key, and never ask for one in the chat.

````text
```
┌──────────────────────────────────────────────────────────┐
│  1  PASTE THIS INTO YOUR OWN TERMINAL                    │
└──────────────────────────────────────────────────────────┘
```

```bash
artemis login --url <deployment-base-url>
```

```
┌──────────────────────────────────────────────────────────┐
│  2  OPEN THIS PAGE TO CREATE AN API KEY                  │
└──────────────────────────────────────────────────────────┘
```

<deployment-base-url>/settings/api-keys

Paste the key at the waiting `API key:` prompt, not here.
````

Rules for that message:

- **Nothing else in it.** No docs links, no status lines, no version notes, no "and next I will". Those belong in the message before or after. The user is about to act, and every extra sentence is something to read past.
- **One command, one line.** If an environment variable is genuinely needed for an already-open terminal, put it on the same line so it is a single copy.
- **Absolute paths only. Never `~` or `$HOME` in a command the user pastes.** Your `HOME` and the user's shell `HOME` can differ, and the same string then points at two different files. The failure looks like a certificate or credential problem, not a path problem, so it costs a full cycle to find. Expand every path yourself before showing it, and verify the file exists at the expanded path first.
- **Say what "done" looks like**, in one sentence: the prompt is waiting, the key goes there, not in the chat.
- Ask the follow-up question (demo or own project) in a **separate** message afterwards, never stacked under the command.

Keep the surrounding chatter short. At this step the user needs the command, where to click, and nothing else: status reports, version notes and next-step previews all belong before or after, never wrapped around the one thing they must act on.

`login` also accepts the shorthand names `dev`, `stg` and `prod`, but prefer the full URL so the deployment is unambiguous in the transcript.

For on-prem, use the base URL accepted by `artemis login --help`. Do not set individual service URLs unless the current CLI explicitly requires it; the base URL normally derives them.

Config precedence is `./.env` before `~/.config/artemis/.env`. Keep keys in the home config: a project-local `.env` is easy to leak and shadows the home config.

**This is the usual cause of a CLI that was working a minute ago.** When `artemis status` reports `USER_MGMT_URL: required but not set` and friends, look for a `.env` in the current directory before concluding the user is logged out: many repositories ship one for their own app, and working inside such a repository silently replaces the CLI's config. The fix is to run from elsewhere or pass `--config`, not to log in again.

### Deployments with a self-signed certificate

**Only do this when TLS has actually failed.** `SSL_CERT_FILE` replaces the system trust store rather than adding to it, so pointing it at one deployment's bundle breaks every deployment whose certificate is in the store already. Setting it "to be safe", or carrying it over from another deployment, is how a working CLI stops working.

Some deployments present a certificate the system trust store does not know, `dev` among them today. `artemis login` and `artemis status` then fail with an `x509` or "unknown authority" error. Only then, point the CLI at that deployment's CA bundle:

```bash
export SSL_CERT_FILE=/absolute/path/to/ca-bundle.pem
```

Four things to get right:

- **The path is the user's, and absolute.** Ask where the bundle came from; never `~` or `$HOME` in a command they paste, because your `HOME` and their shell's need not match.
- **This is the Go CLI's Linux behaviour.** On macOS and Windows the CLI uses the system trust store, so the variable does nothing there and the certificate has to be trusted by the operating system instead.
- **It only lasts for that shell.** Making it permanent means editing their shell startup file, so say which file and why, and ask before writing to it. A login shell reads `~/.bash_profile` or `~/.profile` and ignores `~/.bashrc` unless one sources the other, so the wrong file looks like the fix silently failing.
- **The runner does not need this variable.** It has `--ssl-verify <path>`, which scopes the bundle to its own connection. See `runner-setup`.

Verify in a shell that did not set it interactively, rather than in the one where you just exported it:

```bash
bash -lc 'artemis status'
```

Ask the user where the bundle came from before trusting it. Never fetch a CA bundle from a source the user did not name, and never disable certificate verification to work around this.

When the user later moves to a deployment with an ordinary certificate, the variable has to come back out of their shell files, or it follows them and breaks the new one.

## Verify

Compare the installed CLI with the skills you are about to use. Each skill declares its minimum in its frontmatter as `metadata.artemis-cli-min`. Read `artemis --version`: a release reports a version such as `1.1.8`; a development build reports `dev-<timestamp>-<sha>` and counts as newer than every release. If the installed release is lower than the highest minimum required, update the CLI before continuing.

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

Record the current version, download the newer build the same way as a fresh install (*Where to download from*), and repeat status verification. An update replaces the binary only, so the existing login normally survives; log in again only if `status` says so. Report the version before and after. Do not change deployment while performing an update.

## The official installer, once its source is fixed

1. Open `<deployment-base-url>/settings/cli` for the deployment you are setting up. The Web UI is the source of truth; if the download, credentials, flags, or artifact below differ or fail, use the command currently published there.
2. Confirm whether this is hosted Artemis or an on-prem deployment with a custom base URL — it selects which invocation below to use.

The installer detects the platform, installs the CLI, and configures service endpoints.

**Check which version it produces before relying on it.** Its built-in download source currently carries nothing above 1.0.11, which cannot run a discovery run on a current deployment. On any deployment needing 1.1.8 or newer, use the direct download in *The installer's own download source is stale* below, then `artemis login`. Use the installer when 1.0.11 is genuinely enough, or once the file server is fixed.

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
