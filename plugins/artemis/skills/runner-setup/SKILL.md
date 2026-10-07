---
name: runner-setup
description: Install, register, start, update, and verify a supported Artemis custom runner. Use when an end user needs to set up or manage a runner.
compatibility: Requires Artemis CLI 1.1.8+ and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.8"
  artemis-platform-min: "3.1.0"
---

# Set up an Artemis runner

## At a glance

- **Problem:** Downloads, registers, starts, updates and verifies an Artemis runner on this machine, and checks it has the toolchain a project needs.
- **Must be available:** A safe machine with the repository's toolchains and adequate resources, a unique runner-group name, and an authenticated CLI, whose API key registers the runner.
- **Use / don't use:** Use when a runner is missing, offline, outdated, or unverified; skip it when a suitable runner is already online and confirmed to be polling.
- **Next skill:** Return to the calling skill, or to `artemis` routing when invoked directly.

A runner executes project-supplied compile, test, and benchmark commands on the user's machine. Treat it as a machine-level service, not a project dependency.

## Requirements

- A machine where running code from the connected repositories is safe.
- The toolchains required by the projects assigned to this runner installed on that machine — Artemis runs their commands as-is from the repository root.
- Enough disk, memory, and network access for builds.
- A meaningful runner name that identifies its owner or host, unique unless the user is adding capacity to a group (see [Shared names add capacity](#shared-names-add-capacity)).
- An authenticated `artemis` CLI on the target deployment. The runner uses the same API key, read from the CLI's config file.

## Get the runner

Do this in its own directory, never the user's repository: the runner, its log and its PID file live there.

```bash
mkdir -p <absolute-home>/artemis-runner && cd <absolute-home>/artemis-runner
```

`<absolute-home>` is the expanded home path, such as `/home/alice`, never `~`.

Download it yourself from `https://files.artemis.turintech.ai/public/artemis-runner/`. Read that directory and take the newest version the deployment accepts, the same rule `artemis-runner upgrade` follows: on `dev.artemis.turintech.ai` any build, including alphas (`a`), betas (`b`) and release candidates (`rc`); on `staging.artemis.turintech.ai` finals and release candidates; everywhere else finals only (`X.Y.Z`). Never take the `latest-*` files, which can point at a release candidate. Don't reuse a version from memory, because the published set moves. Download with `curl -fL -o <file> <url>`, so an error page is never saved as the runner.

- **Linux or Windows on x64:** the standalone executable, `artemis-runner-<version>-linux` or `artemis-runner-<version>-windows.exe`. Save it as `artemis-runner` (Linux needs `chmod +x artemis-runner`).
- **macOS (Intel or Apple silicon) and Linux on ARM64:** the Python package, `artemis-runner-<version>-wheels.tar.gz`. It needs Python 3.11: `tar -xzf` it, `cd artemis-runner-*-wheels`, run `python3.11 -m venv .venv` and `.venv/bin/pip install --find-links wheels/ artemis-runner`. Then `cd <absolute-home>/artemis-runner` again, so `runner.log` and `runner.pid` stay in one place. Call the runner by its full path rather than activating the environment, so build commands don't inherit the environment's Python on `PATH`.
- **Windows on ARM64:** the `-wheels.zip`, installed as the deployment's **Add new Artemis runner** page shows.

Check the download before going on: `<absolute-home>/artemis-runner/artemis-runner --version` (for the Python package, `<absolute-home>/artemis-runner/artemis-runner-<version>-wheels/.venv/bin/artemis-runner --version`) must print a version.

Match the runner to the deployment. A build that is too old fails its sign-in or task calls with `404`s, which looks like a network or credential fault and is not one. If the download fails or the deployment needs another build, its **Add new Artemis runner** page (`<deployment-base-url>/settings/runners/new`) offers the one it expects.

For an on-prem deployment, use that deployment's page rather than inventing service URLs.

## Start the runner

Before starting anything, check `artemis runner list` and local processes so an existing runner is not duplicated.

Before starting or reusing additional runners, ask the user: name the machines, explain that their code will execute there and use their hardware, and wait for approval. The startup instructions below apply after that approval; ordinary single-runner setup is unchanged.

**Do not offer a menu of ways to start it.** Say in one line what you are about to do, start it as a background process, and report the result. A first-time user has no basis to choose between a background process, a visible terminal and a tmux session, and asking turns setup into an interview. Use `tmux` only when the user has already asked for it.

State before starting: the runner is a long-lived process that executes this repository's commands on this machine, and it keeps running until stopped. Start it, and only once the check below passes, report the name, the PID, the log path, and the exact stop command. If the user would rather it were not running, they can stop it with that command.

On every start the runner signs in with an API key and appears in the fleet under the name it is given. When adding approved capacity to an existing group, pass its exact name as `<unique-name>`. Use the CLI's key, so the agent needs nothing from the user. Export only `ARTEMIS_API_KEY`, read from the CLI's config file inside the shell: never print the file or the key, so it stays out of the conversation, the command line and `ps`. The config file is the one the CLI is using:

- a `.env` in the folder where the user's `artemis` commands run (usually the repository, not this runner folder), if there is one;
- otherwise, when `artemis env current` names an environment other than `default`, `envs/<name>.env` in the CLI's config folder;
- otherwise `.env` in that folder: `<absolute-home>/.config/artemis/` on Linux (`$XDG_CONFIG_HOME/artemis/` when that is set), `<absolute-home>/Library/Application Support/artemis/` on macOS, `%AppData%\artemis\` on Windows.

Pass the deployment that key belongs to as `<deployment-base-url>`. If the file has no key, the CLI was logged in some other way: ask the user where its key lives rather than searching for one. The snippet stops rather than start without a key, because `start` would then fall back to a `settings.env` left by an earlier `artemis-runner configure` and run on that old key. Other values in such a `settings.env` (CA bundle, output folder, memory limit) still apply, so if one exists, say so before starting.

```bash
cd <absolute-home>/artemis-runner
RUNNER=<absolute-home>/artemis-runner/artemis-runner   # Python package: <absolute-home>/artemis-runner/artemis-runner-<version>-wheels/.venv/bin/artemis-runner
CLI_ENV="<the CLI's config file, from the list above>"
(
  export ARTEMIS_API_KEY="$(sed -n 's/^\(export \)\{0,1\}ARTEMIS_API_KEY=//p' "$CLI_ENV" | tail -n 1 | tr -d "\r\"'" | sed 's/[[:space:]].*$//')"
  [ -n "$ARTEMIS_API_KEY" ] || { echo "No ARTEMIS_API_KEY in $CLI_ENV" >&2; exit 1; }
  nohup "$RUNNER" start --runner-name <unique-name> --url <deployment-base-url> > runner.log 2>&1 &
  echo $! > runner.pid   # stop: kill "$(cat runner.pid)"
) && {
  i=0
  while [ $i -lt 60 ] && kill -0 "$(cat runner.pid)" 2>/dev/null && ! grep -q "Connected to Artemis" runner.log; do sleep 1; i=$((i+1)); done
  if kill -0 "$(cat runner.pid)" 2>/dev/null && grep -q "Connected to Artemis" runner.log; then echo "runner connected"; else echo "runner did not start:"; tail -n 20 runner.log; fi
}
```

If it did not start, report the log lines rather than success: a rejected key, a wrong URL or a build that does not match the deployment all end here.

Build commands the runner starts can read this key (`THANOS_API_KEY`) and act as the user, as they could with any runner key. To cut a runner off remotely, revoke the key at `<deployment-base-url>/settings/api-keys`; that signs the CLI out too, so log in again with a new key.

On a deployment whose certificate this machine does not trust, and only when TLS actually fails, add `--ssl-verify /absolute/path/to/ca-bundle.pem` to the `start` line above.

`--ssl-verify` applies the bundle to the runner's own connection only. Do not use environment variables such as `REQUESTS_CA_BUNDLE` instead: they replace the trust store for the runner and every build it starts, and a runner restarted from another shell comes up without them. Use the absolute path the user gave you, never `~` or `$HOME`, because the runner's `HOME` need not be the one you are reading. See `cli-setup` for the CLI side.

The name appears in the fleet as soon as it connects. Add `--no-delete-task-output` to `start` to keep each task's working directory and log for host-local diagnosis; by default they are removed within seconds.

Use a visible terminal or a named `tmux` session only when the user asks for one; then check the session name is unused and say how to attach, detach and stop it.

Ask separately before creating an operating-system service, even if the user already approved starting a process.

### Shared names add capacity

Several runner processes on different machines can serve the same Discovery when registered with the same exact name. Public docs still say names must be unique; interpret this as **unique per runner group**, intentionally shared only to add capacity. Verify `artemis runner list` and the run's actual executions through `discovery-inspect` before relying on multiple instances; an online name alone does not prove they are taking work.

For speed or memory comparisons, share a name only across interchangeable machines (identical hardware, OS, toolchain and load): the pool assigns each task to any member. Give machines that differ their own names. Accuracy-only benchmarks can use any machine with the required environment. Follow [Fast-track Discovery](../discovery-start/SKILL.md#fast-track-discovery-time-to-trustworthy-results) for measurement checks.

## Whose runner is that?

`runner list` shows every runner on the deployment, including other people's. Reusing one means running this repository's commands on a colleague's machine, so default to reusing a runner you can show belongs to **this** machine: read the running process (`--runner-name` on the local `artemis-runner start` command) and match that name against the list. If nothing local matches, start one here rather than borrowing a name that happens to be online. For approved parallel capacity, verify the additional hosts and intended group with the user; a local process match does not establish ownership of every instance sharing its name.

`runner list --output-format json` carries a `userId` per runner, but `artemis status` does not report who you are and there is no identity command, so that field cannot be compared against the current user. Use the local-process check for a single local runner, and user-confirmed hosts for additional instances.

## Verify

The platform is authoritative; a running local process alone is not proof.

```bash
artemis runner list --help
artemis --output-format json runner list
```

Confirm the intended runner appears online. If the command fails or omits the runner, check `runner.log`. A project's runner is set on the project's **Runner and Scripts** settings page (`<deployment-base-url>/projects/<project-id>/settings/execution`).

For end-to-end verification, use `repo-command-setup` §5b to validate the project's original code and confirm its commands execute on the intended runner.

### The runner's environment is not the user's shell

A runner inherits the environment of whatever shell started it, and keeps it for its whole life. A runner inside a container sees only what is installed or mounted in that container, whatever the host has. Tools installed under a home directory, a version manager, or a virtual environment are routinely on the user's `PATH` and absent from the runner's, so "I can run this command" is not evidence the runner can. Check the toolchain as the runner sees it, and when a tool is only reachable by an absolute path, either start the runner from an environment that has it or make the project's commands name it explicitly.

Before a project's commands are written, probe what the runner actually has, through the platform, on a changeset of that project:

```bash
artemis project scripts create --project "<project-id>" --name "toolchain-probe" \
  --setup-cmd 'for t in python3 node cargo uv poetry cmake; do command -v "$t" >/dev/null && echo "$t: $("$t" --version 2>&1 | head -n1)" || echo "$t: MISSING"; done' --measure none
artemis changeset validate "<changeset-id>" --project "<project-id>" --version original \
  --script "<probe-script-id>" --runner "<runner-name>" --wait
artemis changeset validation logs "<validation-id>" --project "<project-id>"
```

Use the changeset the caller passed (quickstart's `artemis/measure`). Probe for the tools this repository needs. If one is missing, say which tool on which machine and let the user choose between installing it there and using another machine. Do not rewrite the project's commands to dodge it.

Report the runner name, host, and verification result. Do not claim success from a quiet process or log alone.

## Update or restart

Stop the running process cleanly, run `"$RUNNER" upgrade` (or download the newest build as in *Get the runner*). The standalone executable upgrades to the latest without a prompt. On the Python package, `upgrade` asks **Proceed?** and has no flag to skip it, so the user runs it themselves. Then start it again from the same directory with the same command, and repeat *Verify*. Report the version before and after. A human at a browser can use the Web UI's updater instead.
