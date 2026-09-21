---
name: quickstart
description: Take an existing Artemis project to a first measured result, covering the Artemis branch, commands that produce a number, a runner, a measured run, and a Discovery run started from that branch. Use when the user gives a project URL or id, or asks to set up or measure a project that is already imported, including from the Set up with local agent button on a project's overview page.
compatibility: Requires Artemis CLI 1.1.8+ and Artemis Platform 3.1.0+. The browser walkthrough needs a browser-control tool such as Claude in Chrome.
metadata:
  artemis-cli-min: "1.1.8"
  artemis-platform-min: "3.1.0"
---

# Quickstart an existing project

## At a glance

- **Problem:** Turns an imported project into a measured baseline and a running Discovery, doing in the terminal what the Web UI's setup flow does by hand.
- **Must be available:** A project that already exists in Artemis, its URL or id, and a user who can create an API key if the CLI is not yet authenticated.
- **Use / don't use:** Use when the project exists, whether or not the user has done this before. Use `getting-started` instead when the user has no project or wants the Particle Life demo.
- **Next skill:** Hands each step to `cli-setup`, `repo-command-setup`, `runner-setup`, `discovery-start`, and `discovery-inspect`; `ui-walkthrough` shows the pages in the browser route.

## Requirements

- The project, as a Web UI URL or a bare UUID. A URL is the usual case: the prompt behind a project's **Set up with local agent** button carries one.

Nothing else is required from the user. Everything below is checked rather than asked for.

## 0. Read the project URL

`https://<deployment>/projects/<project-id>/overview` carries both facts this skill needs: the project id from the path, the deployment from the origin. Take them from there rather than asking.

Then confirm the CLI is authenticated to that same deployment. A CLI logged in elsewhere reports the project as missing, which reads like a broken link rather than the wrong login, and any branch you create lands on the wrong deployment. Name the deployment the CLI is on, and fix that before creating anything.

## 1. Look before asking

Check silently, and skip what is already done. A project that has been set up before may need only the last step.

| Check | How |
|---|---|
| CLI and authentication | `artemis --version`, `artemis status` |
| The project is real and reachable | `artemis --output-format json project list --all`, matching the id. Keep its `gitUrl`, `gitBranch` and `gitHash`. **`--all` matters**: the default is one page of 20, and a busy deployment has hundreds, so without it a real project reads as missing |
| Commands already stored | `artemis project scripts list --project <id>` |
| A runner online | `artemis runner list` |
| The code, locally | `git -C . remote get-url origin` against the project's `gitUrl` |
| Browser control | Load the tools first, then check. See `ui-walkthrough` section 1 |

The prompt arrives in whatever directory the user's agent happens to be running in, which is not always the project's repository. Settle that before reading any code: if the origin remote does not match the project's `gitUrl`, say so and ask which checkout to work in rather than quietly describing an unrelated repo. If there is no checkout at all, the flow still works, because every command runs on the runner, but say that writing a benchmark without the code in front of you is slower and offer to clone it first.

The project is pinned at `gitHash`. If the user's checkout has moved on, the run measures the pinned commit, not what they are looking at; say which commit is being measured.

## 2. The rules for this flow

- **Never ask the user to choose run settings.** Not the model, the version budget, or the number of measurements. Fix them here and state what you are using.
- **Announce, do not ask,** for anything long-lived or external: starting a runner, creating a branch, starting a run. Say what you are about to do, then do it.
- **The user's credentials are theirs.** Give the login command first, take them to the key page second, and never read, type, or handle a key. Never ask them to paste a key, token or password into the chat, and never put one on a command line.
- **Assume nothing about what they know.** Having a project does not mean they have run anything. The first time you use a word the platform owns, say what it means in one short clause: a branch is Artemis's own copy of the code, a Discovery run is the agent trying versions and measuring each one.
- **Stop cleanly rather than inventing.** If there is nothing measurable, say so; do not fabricate a metric to satisfy the last step.

## 3. What "better" means here

Particle Life ships a benchmark. A real repository usually does not, and Discovery cannot optimise what nobody measures.

1. **Read the repository first:** build files, CI config, test layout, existing scripts, README. Most projects answer this themselves.
2. **Then ask, once,** only what the code cannot tell you: what "better" means for them, which command represents it, and roughly how long it takes. One round, not an interview.
3. If the honest answer is that nothing worth measuring exists yet, say so and stop. That is a useful result.

## 4. The seven steps

Mirror the manual flow. Each step has an owning skill; use it rather than improvising.

| Step | Skill | Command |
|---|---|---|
| 1. CLI installed and authenticated | `cli-setup` | `artemis status`, then return here |
| 2. An Artemis branch over the current code | this skill | `artemis changeset create --project <id> --name <name>` |
| 3. A runner that can build this project | `runner-setup` | Reuse one that is online; install one only if there is none |
| 4. Commands that produce a number | `repo-command-setup` | `artemis project scripts create ...`, build and test as `--setup-cmd`, the measured one as `--benchmark-cmd` |
| 5. Run them on the branch | this skill | `artemis changeset validate <changeset-id> --project <id> --version original --runner <name> --wait` |
| 6. Confirm metrics exist | this skill | `artemis changeset validation get`, then `changeset validation logs` for the values |
| 7. Discovery from that branch | `discovery-start` | `artemis discovery create --source-changeset <changeset-id> ...` |

### Step 2, the branch

```bash
artemis --output-format json changeset create --project "<project-id>" --name "artemis/measure"
```

A new changeset holds exactly one version: the project's code as it is now. Capture its id; steps 5 and 7 both need it. The Web UI calls this a branch and names it `artemis/measure` by default; keep that name unless the user asks otherwise.

Two things about the script are easy to get wrong. There is no `--compile-cmd` or `--test-cmd`: building and testing are `--setup-cmd`, which runs once and is not measured, and only `--benchmark-cmd` is repeated and measured. And `--measure` defaults to `runtime`, which adds a command-runtime metric beside the repository's own, so the user sees two numbers and has to work out which one the run is chasing. Pass `--measure none` unless command runtime is genuinely the target.

### Step 5, the measured run

```bash
artemis changeset validate "<changeset-id>" --project "<project-id>" --version original \
  --script "<script-id>" --runner "<runner-name>" --wait
```

`--project` and `--runner` are required. Drop `--script` to use the project's configured commands. `--wait` gives up after 20 minutes and exits 6, so pass `--timeout` when the benchmark is slower than that, and say how long you expect it to take before starting. `--version original` is the code as it stands.

This is the same primitive Discovery uses to evaluate every version, so a pass here means Discovery can run, and the user has a real number before anything is spent on a run. It is not literally the run's baseline: `discovery create --source-changeset` copies the branch into a baseline changeset of its own and measures that, so the same code is measured again inside the run. Expect the two numbers to agree. If they do not, say so, because that is evidence the benchmark is noisy rather than evidence of an improvement.

Run it through the platform, on the runner, not locally. A local run proves nothing about the machine Discovery will use, and `--wait` is what turns it into evidence.

### Step 6, the numbers

```bash
artemis --output-format json changeset validation get "<validation-id>" --project "<project-id>"
artemis changeset validation logs "<validation-id>" --project "<project-id>"
```

`validation get` answers one question: did every command pass. It reports `exitCode`, `runtime`, `cpu` and `memory` per command and **nothing about the benchmark's own metrics**, so on its own it cannot tell you anything was measured.

The logs command is where the proof is, and it comes through the platform rather than off the runner's disk, so it needs no access to that machine. Look for `artemis_results.json content:` and `Wrote N metric values to observation`. If the benchmark passed but wrote no metrics, fix the script with `repo-command-setup` and run it again before going near Discovery: a run with no measurement wastes the user's credits and teaches them nothing.

Report the measured value in the repository's own units, never the runtime of the benchmark command, which is a different number that happens to sit nearby.

### Step 7, the run

Settings for this flow, so the user is never asked:

- 5 versions
- `--eval-mode fixed --eval-runs 3`, so each version is measured three times and the charts show a range
- `--llm-metrics=false`, because the point of a first run is the measured number
- model `gpt-5.6-sol`

**`--model` is required.** The API has no default, so a run without it is refused. Catalogues differ between deployments: if `artemis model list` does not offer `gpt-5.6-sol` here, pick another model from that list, say in one line which one and why, and continue.

Start from the branch, not the project base:

```bash
artemis discovery create --project "<project-id>" --source-changeset "<changeset-id>" \
  --runner "<runner-name>" --script "<script-id>" --model gpt-5.6-sol \
  --task "<the user's goal, in their words>" \
  --versions 5 --eval-mode fixed --eval-runs 3 --llm-metrics=false
```

Add `--target-files <path>` (repeatable) when the repository made it obvious which files carry the work. Leave it off rather than guessing: a wrong guess hides the code that matters.

`--source-changeset` copies the branch you just measured into the run's baseline, so Discovery starts from the same code and the same numbers the user just watched.

## 5. Showing it

In the browser route, hand each step to `ui-walkthrough` and be on the page **before** the command runs, so the user watches the platform change rather than being shown the result: the project page before the branch appears, the branch before the run, the run's Experiments tab while versions are generated.

In the terminal route, give a link to the project and name the page to open.

## 6. When it cannot continue

| Situation | Do |
|---|---|
| CLI missing or unauthenticated | `cli-setup`, then return to step 2 |
| No runner, and the user does not want one | Say plainly that nothing can be measured without a machine, and stop. Do not start a run |
| The benchmark produces no numbers | Fix the script and re-run. Never start Discovery on an unmeasured branch |
| Nothing worth measuring in this project | Say so and stop |
| The run fails in seconds with no baseline | `discovery-inspect`, checking the project's Git access first |
| A skill named here is not installed | Say which one is missing, then do that step with the commands in this file. Do not invent a different route |
| The project URL's deployment is not the one the CLI is logged into | Say both, and settle it before creating anything. Work created on the wrong deployment is invisible to the user |

## 7. Close

Report what now exists: the branch, the commands, the runner, the measured baseline with its numbers, and the Discovery run with a link. Say what it is optimising and roughly how long it will take. Then hand over to `discovery-inspect` for reading the result.

## Checklist

- [ ] Project id confirmed against a real project on the authenticated deployment
- [ ] The user was asked about their goal only where the repository could not answer
- [ ] Branch created, and its changeset id captured for the run
- [ ] Commands verified by running them, not assumed
- [ ] Metric values seen in the validation logs, not assumed from a passing benchmark
- [ ] Discovery started from the branch, with settings fixed rather than asked
- [ ] User told what was measured, what is running, and where to watch it
