---
description: Install and configure the Artemis runner on a machine
---

## What is Artemis

Artemis is TurinTech AI's code optimization and analysis platform. It analyzes, optimizes, and validates codebases at scale — improving performance, efficiency, and reducing costs. The platform uses **runners** (agents installed on user machines) to execute build, test, and benchmark commands against code. Users configure their project on the Artemis web UI, and the runner executes commands in a temporary copy of the repo.

---

You are guiding the user through installing and configuring the Artemis runner on their machine. Be patient and step-by-step.

## Pacing

- **Ask only ONE question per message.**
- **Verify every step.** After each instruction, ask "did that work?" or "what output did you see?" before moving on.
- **Do not dump all steps at once.** Walk through the setup one step at a time.

---

## 1. Prerequisites

Before installing, confirm the user has:
- A machine with the project's build toolchain (e.g. `cmake`, `g++`, `ctest` for C++) — the runner runs the project's own build/test/benchmark commands, headless.
- 1GB+ free disk space and internet access.
- Bash (macOS/Linux) or PowerShell 5.0+ (Windows).
- Their deployment URL (e.g. `https://staging.artemis.turintech.ai`).

The standalone binary needs **no Python and no download credentials**. (Python 3.11 is only needed for the legacy pip path in the Troubleshooting section.)

## 2. Download the runner (standalone binary)

The runner is a single self-contained binary on a public download path — no login needed.

### macOS / Linux

```bash
mkdir artemis-runner && cd artemis-runner
curl -L "https://files.artemis.turintech.ai/public/artemis-runner/artemis-runner-latest-linux" \
  -o artemis-runner && chmod +x artemis-runner
./artemis-runner --version
```

### Windows PowerShell

```powershell
mkdir artemis-runner; cd artemis-runner
iwr -Uri "https://files.artemis.turintech.ai/public/artemis-runner/artemis-runner-latest-windows.exe" -OutFile "artemis-runner.exe"
.\artemis-runner.exe --version
```

`-latest` on this public path always resolves to the newest release. To pin a specific version, replace `latest` with a version name shown in the directory listing (e.g. `artemis-runner-5.2.0-linux`).

Ask the user what `--version` printed before continuing.

## 3. Configure (register the runner)

In the Artemis web UI, go to **Runners → Add new Artemis runner**. It shows a **single-use registration token** (`turin_reg_…`, valid ~60 minutes) and the deployment URL. Ask the user to copy the token, then:

```bash
./artemis-runner configure --url <deployment-url> --token <turin_reg_...> --runner-name <name>
```

- `<deployment-url>`: e.g. `https://staging.artemis.turintech.ai`.
- `<name>`: a memorable identifier for this machine (e.g. `alice-laptop`). If you omit `--runner-name`, the wizard prompts for it.
- If the token has expired, ask the user to click **Regenerate** in the UI.

This writes a saved configuration; you don't need to re-enter the token to start again.

> Alternative (CI/scripts): instead of a registration token you can authenticate with an **API key** and skip `configure` — `./artemis-runner start --url <deployment-url> --api-key <key> --runner-name <name>` (or set `ARTEMIS_API_KEY`).

## 4. Start

```bash
./artemis-runner start
```

`start` runs from the saved configuration. Priority is CLI flags > environment variables > saved settings > defaults, so you can override any value on the command line.

To keep it running in the background (macOS/Linux):

```bash
nohup ./artemis-runner start > runner.log 2>&1 &
```

## 5. Verify

The runner name should appear in the Artemis web UI under **Active Runners**, and the runner's own output/log should show it polling for tasks. Ask the user to confirm the runner shows up in the UI.

## 6. Keeping the runner up to date

The runner can upgrade itself:

```bash
./artemis-runner upgrade          # install the latest permitted release
./artemis-runner upgrade --list   # list installable versions and choose one
```

Which pre-releases are allowed depends on the deployment (dev: alpha/beta/rc, staging: rc only, prod: finals only).

## 7. Advanced options

Set these as flags on `start` (or via `configure`):
- `--no-delete-task-output` — keep each task's build artefacts for inspection (they are deleted by default).
- `--worker-output-dir <path>` — where candidate versions are cloned and outputs saved (defaults to the system cache directory).
- `--ram-limit-mb <n>` — cap runner memory.

## 8. Troubleshooting

- **Runner not appearing in UI:** check the process is running, has internet access, and that the registration token hadn't expired (regenerate and re-`configure` if so).
- **Token expired:** tokens are single-use and time-limited — click **Regenerate** in the UI.
- **Permission denied:** on macOS/Linux ensure the binary is executable (`chmod +x artemis-runner`).
- **`glibc`/library errors on a minimal container:** the standalone binary is dynamically linked; use a standard base image, or fall back to the legacy pip path below.
- **Firewall/proxy issues:** the runner needs to reach `files.artemis.turintech.ai` and the Artemis platform API.

**Legacy pip path (only if the binary won't run):** requires Python 3.11. Download `artemis-tools-latest.tar.gz` from the `tools-bundle/` path (with the UI-provided download credentials), extract, `python3.11 -m venv .venv && source .venv/bin/activate && pip install --find-links wheels/ artemis-runner`, then use the same `configure`/`start` commands.

## 9. Checklist

Before finishing, verify:

- [ ] Runner binary downloaded and `--version` works
- [ ] Runner configured with the registration token (or API key)
- [ ] Runner process is running
- [ ] Runner name appears in the Artemis web UI (Active Runners)
- [ ] User knows how to start/stop and `upgrade` the runner
