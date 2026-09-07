---
name: runner-setup
description: Register, start, update, and verify a supported Artemis runner — the artemis CLI running as a runner on the user's own hardware. Use when an end user needs to set up or manage a runner.
---

# Set up an Artemis runner

## At a glance

- **Problem:** Registers, starts, updates, and verifies an Artemis runner on the user's machine, following the Add a runner page in the Web UI.
- **Must be available:** A safe machine with the repository's toolchains and adequate resources, a unique runner name, and the `artemis` CLI installed and logged in to the deployment (`cli-setup`).
- **Use / don't use:** Use when a runner is missing, offline, outdated, or unverified; skip it when a suitable runner is already online and confirmed to be polling.
- **Next skill:** Return to `artemis` routing, usually toward `repo-command-setup`, `project-import`, or `discovery-start`.

A runner executes project-supplied compile, test, and benchmark commands on the user's machine. Treat it as a machine-level service, not a project dependency.

## Requirements

- A machine where running code from the connected repositories is safe.
- The toolchains required by the projects assigned to this runner installed on that machine — Artemis runs their commands as-is from the repository root, in the shell the runner is started from.
- Enough disk, memory, and network access for builds.
- A meaningful, unique runner name that identifies its owner or host. The default is the machine's hostname.
- The `artemis` CLI, logged in to the deployment. There is no separate runner binary: `artemis runner` is a command group of the same binary the installer places, and it reads the credential `artemis login` stored. Run `cli-setup` first if `artemis status` does not report the intended deployment and an authenticated user.

## Get the runner

`<deployment>/settings/runners/new` (**Settings → Runners → Add a runner**) is the source of truth. It generates, for the chosen operating system, the installer command, an `artemis login <deployment> --token …` line carrying a fresh registration token, then `artemis runner configure` and `artemis runner start`. Use it when a human is driving, when the commands below fail, or to mint a token for a machine that is not logged in yet. The token expires in an hour and is exchanged by the CLI for the machine's own API key; the user enters it in their own terminal, never in chat.

A machine that is already logged in needs nothing from that page: `artemis runner start` registers it on the first start.

## Start the runner

Before starting anything:

1. Check `artemis runner list` and local processes so an existing runner is not duplicated.
2. Explain that the runner is a long-lived process that executes connected repository code.
3. Offer to start it and obtain the user's explicit permission.

After permission, from a shell that has the project's build tools on `PATH` (activated virtualenv, `JAVA_HOME`, and so on — tools only outside that shell will not be found):

```bash
artemis runner configure --name <unique-name>   # registers; optional, start does it too
artemis runner start
```

`configure` stores the name and registers the machine; `start` reconnects as the same runner on every later run and never asks for a credential — a missing one errors naming `artemis login`. Options, each also an environment variable or a `runner.*` key in `settings.yaml`:

- `--name` (`ARTEMIS_RUNNER_NAME`): the name shown in the fleet. Defaults to the last registered name, then the hostname.
- `--instance` (`ARTEMIS_RUNNER_INSTANCE`): a second runner on the same machine, for a shell with its own build environment. Two instances are two runners with their own caches and build slots.
- `--shell` (`ARTEMIS_SHELL`, `runner.shell`): the shell session commands run in. Defaults to the shell you started from.
- `--keep-workspaces` (`ARTEMIS_KEEP_WORKSPACES`, `runner.keep_workspaces`): keep each session's workspace on disk when it ends, for host-local diagnosis. The default deletes them.
- `--non-interactive`: never prompt; a missing value is an error instead. Use it from scripts.

The name appears in the fleet as soon as the runner connects.

Keep the runner in a visible terminal for initial verification. If it needs to outlive that terminal, prefer a named `tmux` session when available, check that the session name is unused, and tell the user how to attach, detach, and stop it. If only a background process is possible, report its PID, output location, and exact stop command.

Ask separately before creating an operating-system service, even if the user already approved starting a process.

## Verify

The platform is authoritative; a running local process alone is not proof.

```bash
artemis runner list
artemis --output-format json runner list
```

Confirm the intended runner appears with an online count. If the command fails or omits the runner, check its terminal output and **Settings → Runners** in the Web UI.

For end-to-end verification, use `repo-command-setup` §5b to validate the project's original code and confirm its commands execute on the intended runner.

Report the runner name, host, and verification result. Do not claim success from a quiet process or log alone.

## Update or restart

Updating the runner is updating the CLI: rerun the installer (`cli-setup` → Update). Stop the running `artemis runner start` cleanly first, compare `artemis version` before and after, start it again from the same shell, then repeat verification. The registration and credential are kept in `environments.yaml`, so the runner reconnects under the same identity.
