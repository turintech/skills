---
name: cli-setup
description: Install, update, and authenticate the Artemis CLI by direct download from the Artemis file server, then log in with an API key the user creates. Use when the CLI is missing, older than the skills' minimum, or not signed in to the target deployment.
compatibility: Requires Artemis CLI 1.1.8+ and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.8"
  artemis-platform-min: "3.1.0"
---

# Set up the artemis CLI

## At a glance

- **Problem:** Installs, updates, and authenticates the Artemis CLI from the public file server, with no GitHub or source access needed.
- **Must be available:** Network access to the file server and Artemis deployment, plus an API key created in the Web UI and entered by the user in their own terminal.
- **Use / don't use:** Use when the CLI is missing, outdated, or unauthenticated; skip it when a working authenticated CLI is already available.
- **Next skill:** Return to the calling skill, or to `artemis` routing when invoked directly.

Use the supported distribution. This path requires no GitHub account and does not assume access to the CLI source repository.

## Requirements

- Network access to `files.artemis.turintech.ai` and the deployment's base URL.
- An API key for the target deployment, created by the user in the Web UI (`<deployment-base-url>/settings/api-keys`). The agent cannot create one, and it must be entered by the user in their own terminal, never in chat.

## Check what is already there

Before installing anything, look at the CLI that is already on this machine:

```bash
artemis --version
artemis status
```

If the version meets the skills' minimum (see *Verify*) and `status` is authenticated to the target deployment, there is nothing to do here. If it is installed but older, this is an update, not a fresh install. If it is authenticated to a different deployment, say which one and ask before logging it in elsewhere: the user may still be using that login.

## Install the CLI

Start here when there is no CLI, or it needs replacing. The deployment's own page at `<deployment-base-url>/settings/cli` is the source of truth for credentials and flags, and if anything below differs from it, follow the page.

Install by direct download. The installer script and the `latest/` directory can serve a build older than the skills' minimum, so always read `artemis --version` after downloading, and fall back to the newest versioned release when it is too old. The installer is described in [references/installer.md](references/installer.md) for when a deployment's page asks for it.

### Where to download from

**If the setup prompt or the user gave a CLI download directory, start there.** It is the deployment's own choice of build, and it holds the binaries directly under the names below. Check what it serves before keeping it: download, run `--version`, and compare with the minimum. When the directory's build is older than the minimum, use the newest release from the public listing instead, and say in one line which directory was out of date.

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

If the directory has no file for this machine, never install a different architecture's build in its place: it either fails to start or runs under emulation and misbehaves later. Try the newest versioned release, which carries all six, and if that has none either, tell the user no build exists for this machine and stop. Channels can differ in which builds they carry, so read the listing rather than assuming.

Without a directory from the prompt, install from the public path, which carries current releases. Check the listing first and take the newest, rather than trusting a version named here:

```bash
curl -s --anyauth -u "Artemis_User:Artemis_Custom_Runner_2025" \
  "https://files.artemis.turintech.ai/public/artemis-cli/" \
  | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | sort -uV | tail -5
```

Then fetch that version for the platform, verify it, and put it on `PATH`:

```bash
VER=<the newest version in the listing above>
PLATFORM="linux-amd64"   # from the table above
curl -fL --anyauth -u "Artemis_User:Artemis_Custom_Runner_2025" \
  "https://files.artemis.turintech.ai/public/artemis-cli/$VER/artemis-cli-$PLATFORM" \
  -o ~/.local/bin/artemis && chmod +x ~/.local/bin/artemis
artemis --version
```

A direct download configures no endpoints, so follow it with `artemis login --url <deployment-base-url>`.

The download credentials above are the published shared ones from the Web UI and the docs, not per-user secrets, so they can be used directly. Any *API key* is still a secret and must never enter the conversation.

## Authenticate

A direct download configures nothing, so the CLI needs a login with the API key described in Requirements.

One invariant decides the order here: **the key is the last thing the user copies.** Anything they have to copy after it overwrites it on the clipboard.

1. **In the browser route, open the API keys page first**, with `cli-follow-along`, pointer on the control that creates a key. Navigating costs the user nothing and touches no clipboard. Being shown where to go is most of the value of that route, so do not settle for printing a link until you have checked properly: on hosts where the browser tools are deferred they must be loaded before they can be seen at all, so a missing tool is not the same as a missing browser (`cli-follow-along` section 1).
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
- Ask any follow-up question in a separate message afterwards, never stacked under the command.

Keep the surrounding chatter short. At this step the user needs the command, where to click, and nothing else: status reports, version notes and next-step previews all belong before or after, never wrapped around the one thing they must act on.

`login` also accepts the shorthand names `dev`, `stg` and `prod`, but prefer the full URL so the deployment is unambiguous in the transcript.

For on-prem, use the base URL accepted by `artemis login --help`. Do not set individual service URLs unless the current CLI explicitly requires it; the base URL normally derives them.

Config precedence is `./.env` before `~/.config/artemis/.env`. Keep keys in the home config: a project-local `.env` is easy to leak and shadows the home config.

**This is the usual cause of a CLI that was working a minute ago.** When `artemis status` reports `USER_MGMT_URL: required but not set` and friends, look for a `.env` in the current directory before concluding the user is logged out: many repositories ship one for their own app, and working inside such a repository silently replaces the CLI's config. The fix is to run from elsewhere or pass `--config`, not to log in again.

### Deployments with a self-signed certificate

Only when TLS has actually failed: `artemis login` or `artemis status` reports `x509` or "unknown authority". Ask the user where the deployment's CA bundle is. Never fetch a bundle they did not name, and never turn certificate verification off.

On CLI 1.1.9 and newer, add the bundle for the CLI only:

```bash
export ARTEMIS_SSL_CERT_FILE=/absolute/path/to/ca-bundle.pem
```

It is trusted in addition to the system roots, so other deployments keep working, and it affects nothing but the CLI. `--ssl-cert-file <path>` does the same for a single command. CLI 1.1.8 has neither; update it rather than set `SSL_CERT_FILE`, which changes certificate trust for every program in that shell.

- **The path is the user's, and absolute.** Never `~` or `$HOME` in a command they paste, because your `HOME` and their shell's need not match.
- **It only lasts for that shell.** Making it permanent means editing their shell startup file, so say which file and why, and ask before writing to it. A login shell reads `~/.bash_profile` or `~/.profile` and ignores `~/.bashrc` unless one sources the other.
- **The runner has its own setting**, `--ssl-verify <path>`. See `runner-setup`.

Verify in a fresh login shell rather than the one where you just exported it:

```bash
bash -lc 'artemis status'
```

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

`discovery create` must accept `--script` and `--llm-metrics`. If either flag is missing, update the CLI by direct download (*Where to download from*).

Report the installed version, base URL, and authenticated user. Do not report success if `status` shows missing endpoints or an unauthenticated session.

## Update

Record the current version, download the newer build the same way as a fresh install (*Where to download from*), and repeat status verification. An update replaces the binary only, so the existing login normally survives; log in again only if `status` says so. Report the version before and after. Do not change deployment while performing an update.
