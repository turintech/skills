---
name: cli-setup
description: Install, update, and authenticate the Artemis CLI by direct download from the Artemis file server, then log in with an API key the user creates. Use when the CLI is missing, older than the skills' minimum, or not signed in to the target deployment, and once per session to check that the Artemis skills and CLI are current.
compatibility: Requires Artemis CLI 1.1.8+ and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.8"
  artemis-platform-min: "3.1.0"
---

# Set up the artemis CLI

## At a glance

- **Problem:** Installs, updates, and authenticates the Artemis CLI from the public file server, with no GitHub or source access needed.
- **Must be available:** Network access to the file server and Artemis deployment, plus an API key created in the Web UI and entered by the user in their own terminal.
- **Use / don't use:** Use when the CLI is missing, outdated, or unauthenticated, and once per session for *Check versions*; when a working authenticated CLI is already available, run *Check versions* and skip the rest.
- **Next skill:** Return to the calling skill, or to `artemis` routing when invoked directly.

Use the supported distribution. This path requires no GitHub account and does not assume access to the CLI source repository.

## Requirements

- Network access to `files.artemis.turintech.ai` and the deployment's base URL.
- An API key for the target deployment, created by the user in the Web UI (`<deployment-base-url>/settings/api-keys`). The agent cannot create one, and it must be entered by the user in their own terminal, never in chat.

## Check versions

The skills, the CLI and the platform are released separately, so a returning user can have any mix of them. Check once per session, before the first task, even when the CLI already works.

**1. The skills.** If the skills were installed earlier in this session, skip the update and do only *Asking for a reload*'s install check, below. Skip this step entirely if this session has already run an Artemis command that changes something (import, branch, validation, Discovery), or if the setup prompt says to use the installed skills as they are. Otherwise tell the user in one line ("Checking for Artemis skills updates.") and update only the Artemis skills:

- **Claude Code:** run `claude plugin marketplace update skills`, then `claude plugin update artemis@skills --json`. An `outcome` of `up_to_date` means current and `updated` means the skills changed; any other outcome means the check could not run (below).
- **Cursor, Codex, GitHub Copilot:** run `npx skills list -g`. If it lists the Artemis skills (the setup prompt installs them with `npx skills add --global`), run `npx skills update -g -y <names>`, naming only those, because with no names it updates every skill on the machine. "All global skills are up to date" means current; "Updated N skill(s)" means they changed. If it does not list them, they came from the host's own installer (`agent plugin marketplace add`, `codex plugin marketplace add` or `gh skill install`, usually pinned to a release) or were copied into the host's skills directory: run nothing, and tell the user in one line to update them the way they installed them.

Then:

- **Nothing changed:** say nothing more and carry on.
- **Something changed:** the copy already read is the old one, so ask the user once to reload (*Asking for a reload*, below), wait, then invoke the skill you were following again. Other hosts: usually a new chat, where they paste their request again. Do not repeat this step in the same chat; in a new chat it reports current.
- **The check could not run:** if a command fails, Claude Code finds no Artemis plugin, or this skill was not loaded from the installed plugin (in Claude Code its base directory is not under the plugins directory, `~/.claude/plugins/` by default, as with `--plugin-dir`), install nothing, say in one line that the skills could not be checked, and continue.

**Asking for a reload.** After an install, first check whether the Artemis skills are already usable in this session: if `artemis:quickstart` is among your available skills, or the Skill tool loads it, carry on without asking. After an update, or when they are not usable, send the request as its own message, two numbered boxes and nothing else (Claude Code shown):

````text
```
┌──────────────────────────────────────────────────────────┐
│  1  TYPE THIS HERE IN THIS CHAT                          │
└──────────────────────────────────────────────────────────┘
```

```
/reload-plugins
```

```
┌──────────────────────────────────────────────────────────┐
│  2  THEN SAY "DONE"                                      │
└──────────────────────────────────────────────────────────┘
```
````

If it warns about the cache, `/reload-plugins --force`, or restart Claude Code. If the user pastes a shell command or other text meant for step 1 instead, answer in one line that points back to step 1 and wait; don't explain the reload again.

**2. The CLI.** It must meet the skills' minimum: see *Verify*, and *Update* if it is older.

**3. The platform.** Skills declare `metadata.artemis-platform-min`, but the CLI cannot report the platform's version, so do not guess it. If a command that `--help` lists fails with an unknown route, or with a 404 for an id you have just seen in a list on this deployment, say the deployment may be older than these skills need or the id may not be visible to this login, rather than retrying.

## Check what is already there

Before installing anything, look at the CLI that is already on this machine:

```bash
artemis --version
artemis status
artemis runner list
```

`status` can report authentication as ok with a revoked key, so the key is only proven when `runner list` succeeds; a `401` there means log in again. If the version meets the skills' minimum (see *Verify*), `status` names the target deployment and `runner list` succeeds, there is nothing to install or log in. If it is installed but older, this is an update, not a fresh install. If it is authenticated to a different deployment, say which one and ask before logging it in elsewhere: the user may still be using that login.

## Install the CLI

Start here when there is no CLI, or it needs replacing. The deployment's **Connect Your Agent** page at `<deployment-base-url>/settings/connect-agent` is the source of truth for credentials and flags, and if anything below differs from it, follow the page.

Install by direct download. The installer script and the `latest/` directory can serve a build older than the skills' minimum, so always check a downloaded build's version before it replaces anything, and fall back to the newest versioned release when it is too old. The installer is described in [references/installer.md](references/installer.md) for when a deployment's page asks for it.

### Where to download from

**If the setup prompt or the user gave a CLI download directory, start there.** It is the deployment's own choice of build, and it holds the binaries directly under the names below, with a `checksums.txt`. Check what it serves before it replaces anything: this downloads into a temporary directory, checks the checksum and the version there, and installs only a build that passes both:

```bash
DIR="<the CLI download directory from the prompt>"
PLATFORM="linux-amd64"   # see the table below
MIN="1.1.15"             # the highest artemis-cli-min of the skills in use
TMP="$(mktemp -d)"; F="$TMP/artemis-cli-$PLATFORM"
if ! curl -fsSL "$DIR/artemis-cli-$PLATFORM" -o "$F"; then
  echo "NO BUILD: $DIR has no artemis-cli-$PLATFORM"
elif ! ( cd "$TMP" && curl -fsSLO "$DIR/checksums.txt" \
     && grep " artemis-cli-$PLATFORM\$" checksums.txt > sum.txt && [ -s sum.txt ] \
     && { sha256sum -c sum.txt 2>/dev/null || shasum -a 256 -c sum.txt; } ); then
  echo "INSTALL FAILED: checksum"
elif ! V="$(chmod +x "$F" && "$F" --version)"; then
  echo "WON'T RUN: the downloaded build did not start"
elif VN="$(echo "$V" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"; [ -z "$VN" ] || [ -z "$MIN" ] \
     || [ "$(printf '%s\n' "$MIN" "$VN" | sort -V | head -1)" != "$MIN" ]; then
  echo "TOO OLD: the directory's build reports \"$V\", below $MIN"
else
  { mkdir -p ~/.local/bin && install -m 755 "$F" ~/.local/bin/artemis && ~/.local/bin/artemis --version; } \
    || echo "INSTALL FAILED: could not write ~/.local/bin/artemis"
fi
rm -rf "$TMP"
```

Nothing is replaced unless the last branch runs. On `TOO OLD` or `NO BUILD`, install the newest release from the public listing below instead, and say in one line which directory was out of date or missing this machine's build. On `INSTALL FAILED` or `WON'T RUN`, stop as below.

The public download paths need no login, so send no credentials.

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
curl -s "https://files.artemis.turintech.ai/public/artemis-cli/" \
  | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | sort -uV | tail -5
```

Then fetch that version for the platform, check it against the release's `checksums.txt`, and only then put it on `PATH`:

```bash
VER=<the newest version in the listing above>
PLATFORM="linux-amd64"   # from the table above
BASE="https://files.artemis.turintech.ai/public/artemis-cli/$VER"
TMP="$(mktemp -d)"
( cd "$TMP" \
  && curl -fLO "$BASE/artemis-cli-$PLATFORM" && curl -fLO "$BASE/checksums.txt" \
  && grep " artemis-cli-$PLATFORM\$" checksums.txt > sum.txt && [ -s sum.txt ] \
  && { sha256sum -c sum.txt 2>/dev/null || shasum -a 256 -c sum.txt; } \
  && mkdir -p ~/.local/bin && install -m 755 "artemis-cli-$PLATFORM" ~/.local/bin/artemis \
  && ~/.local/bin/artemis --version ) || echo "INSTALL FAILED: checksum or download"
rm -rf "$TMP"
```

The same lines work on Linux (`sha256sum`) and macOS (`shasum`). On `INSTALL FAILED`, stop and tell the user: never run a binary that doesn't match its checksum, and don't trust an older `artemis` already on `PATH`.

A direct download configures no endpoints, so follow it with `artemis login --url <deployment-base-url>`. Check that the user's own shell finds it with `bash -lc 'command -v artemis'`; if not, use the absolute path in the login box and offer, asking first, to add `~/.local/bin` to PATH in their shell startup file. On Windows, download the `.exe` and ask the user where to put it on PATH.

An *API key* is a secret and must never enter the conversation.

## Authenticate

A direct download configures nothing, so the CLI needs a login with the API key described in Requirements.

One invariant decides the order here: **the key is the last thing the user copies.** Anything they have to copy after it overwrites it on the clipboard.

1. **In the browser route, open the API keys page first**, with `cli-follow-along`, pointer on the control that creates a key. Navigating costs the user nothing and touches no clipboard. Being shown where to go is most of the value of that route, so do not settle for printing a link until you have checked properly: on hosts where the browser tools are deferred they must be loaded before they can be seen at all, so a missing tool is not the same as a missing browser (load the skill and follow `cli-follow-along` section 1).
2. **Then send the step as its own message**, three numbered boxes and nothing else.
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

```
┌──────────────────────────────────────────────────────────┐
│  3  PASTE THE KEY INTO THAT TERMINAL                     │
└──────────────────────────────────────────────────────────┘
```

At the waiting `API key:` prompt, not here in the chat.
````

Rules for that message:

- **Nothing else in it.** No docs links, no status lines, no version notes, no "and next I will". Those belong in the message before or after. The user is about to act, and every extra sentence is something to read past.
- **One command, one line.** If an environment variable is genuinely needed for an already-open terminal, put it on the same line so it is a single copy.
- **Absolute paths only. Never `~` or `$HOME` in a command the user pastes.** Your `HOME` and the user's shell `HOME` can differ, and the same string then points at two different files. The failure looks like a certificate or credential problem, not a path problem, so it costs a full cycle to find. Expand every path yourself before showing it, and verify the file exists at the expanded path first.
- **Three boxes, one per user action:** run the command, create the key, paste the key. The line under box 3 says where it goes: the waiting prompt, not the chat.
- Ask any follow-up question in a separate message afterwards, never stacked under the command.

Keep the surrounding chatter short. At this step the user needs the command, where to click, and nothing else: status reports, version notes and next-step previews all belong before or after, never wrapped around the one thing they must act on.

For on-prem, use the base URL accepted by `artemis login --help`. Do not set individual service URLs unless the current CLI explicitly requires it; the base URL normally derives them.

Config precedence is `./.env` before `~/.config/artemis/.env`. Keep keys in the home config: a project-local `.env` is easy to leak and shadows the home config.

**This is the usual cause of a CLI that was working a minute ago.** When `artemis status` reports `USER_MGMT_URL: required but not set` and friends, look for a `.env` in the current directory before concluding the user is logged out: many repositories ship one for their own app, and working inside such a repository silently replaces the CLI's config. The fix is to run from elsewhere or pass `--config`, not to log in again.

**A deployment URL in the environment needs its own key.** From CLI 1.1.15, if `ARTEMIS_BASE_URL` (or a service URL) is set in the shell to a different deployment from the one the config file's key belongs to, commands that reach the deployment are refused: "the stored key would be sent to a deployment it was not issued for". The user is not logged out. Unset the variable, set `ARTEMIS_API_KEY` beside it, or log in to that deployment with `artemis login` (a named `artemis env` keeps both).

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
artemis runner list   # proves the key; status alone can pass with a revoked one
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
