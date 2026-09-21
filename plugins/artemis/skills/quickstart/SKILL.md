---
name: quickstart
description: Take an existing Artemis project to a first measured result, covering the Artemis branch, commands that produce a number, a runner, a measured run, and a Discovery run started from that branch. Use when the user gives a project id or asks to get started on a project that is already imported, including from the Quickstart button on a project's overview page.
compatibility: Requires Artemis CLI 1.1.5 or newer. The browser walkthrough needs a browser-control tool such as Claude in Chrome.
metadata:
  artemis-cli-min: "1.1.5"
---

# Quickstart an existing project

## At a glance

- **Problem:** Turns an imported project into a measured baseline and a running Discovery, doing in the terminal what the Web UI's setup flow does by hand.
- **Must be available:** A project that already exists in Artemis, its id, and a user who can create an API key if the CLI is not yet authenticated.
- **Use / don't use:** Use when the project exists. Use `getting-started` instead when the user has no project, no CLI, or wants the Particle Life demo.
- **Next skill:** Hands each step to `cli-setup`, `repo-command-setup`, `runner-setup`, `discovery-start`, and `discovery-inspect`; `ui-walkthrough` shows the pages in the browser route.

## Requirements

- The project id, from the user or the prompt that launched this skill.
- The deployment base URL the project lives on.

## 0. Look before asking

Check silently, and skip what is already done. A project that has been set up before may need only the last step.

| Check | How |
|---|---|
| CLI and authentication | `artemis --version`, `artemis status` |
| The project is real and reachable | `artemis --output-format json project list`, matching the id |
| Commands already stored | `artemis project scripts list --project <id>` |
| A runner online | `artemis runner list` |
| Browser control | Load the tools first, then check. See `ui-walkthrough` section 1 |

## 1. The rules for this flow

- **Never ask the user to choose run settings.** Not the model, the version budget, or the number of measurements. Fix them here and state what you are using.
- **Announce, do not ask,** for anything long-lived or external: starting a runner, creating a branch, starting a run. Say what you are about to do, then do it.
- **The user's credentials are theirs.** Give the login command first, take them to the key page second, and never read, type, or handle a key.
- **Stop cleanly rather than inventing.** If there is nothing measurable, say so; do not fabricate a metric to satisfy the last step.

## 2. What "better" means here

Particle Life ships a benchmark. A real repository usually does not, and Discovery cannot optimise what nobody measures.

1. **Read the repository first:** build files, CI config, test layout, existing scripts, README. Most projects answer this themselves.
2. **Then ask, once,** only what the code cannot tell you: what "better" means for them, which command represents it, and roughly how long it takes. One round, not an interview.
3. If the honest answer is that nothing worth measuring exists yet, say so and stop. That is a useful result.

## 3. The seven steps

Mirror the manual flow. Each step has an owning skill; use it rather than improvising.

| Step | Skill | Command |
|---|---|---|
| 1. CLI installed and authenticated | `cli-setup` | `artemis status`, then return here |
| 2. An Artemis branch over the current code | this skill | `artemis changeset create --project <id> --name <name>` |
| 3. A runner that can build this project | `runner-setup` | Reuse one that is online; install one only if there is none |
| 4. Commands that produce a number | `repo-command-setup` | `artemis project scripts create ...` |
| 5. Run them on the branch | this skill | `artemis changeset validate <changeset-id> --project <id> --version original --runner <name> --wait` |
| 6. Confirm metrics exist | this skill | `artemis changeset validation get <validation-id> --project <id>` |
| 7. Discovery from that branch | `discovery-start` | `artemis discovery create --source-changeset <changeset-id> ...` |

### Step 2, the branch

```bash
artemis --output-format json changeset create --project "<project-id>" --name "artemis/measure"
```

A new changeset holds exactly one version: the project's code as it is now. Capture its id; steps 5 and 7 both need it. The Web UI calls this a branch and names it `artemis/measure` by default; keep that name unless the user asks otherwise.

### Step 5, the measured run

```bash
artemis changeset validate "<changeset-id>" --project "<project-id>" --version original \
  --script "<script-id>" --runner "<runner-name>" --wait
```

`--project` and `--runner` are required. Drop `--script` to use the project's configured commands. `--version original` is the code as it stands, which is the baseline Discovery will measure against; this is the same primitive Discovery uses for every version, so a pass here means Discovery can run.

Run it through the platform, on the runner, not locally. A local run proves nothing about the machine Discovery will use, and `--wait` is what turns it into evidence.

### Step 6, the numbers

```bash
artemis --output-format json changeset validation get "<validation-id>" --project "<project-id>"
```

Read the values back from the validation. Do not grep the runner log. If the benchmark produced no metrics, fix the script with `repo-command-setup` and run it again before going near Discovery: a run with no measurement wastes the user's credits and teaches them nothing.

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

`--source-changeset` copies the branch you just measured into the run's baseline, so Discovery starts from the same code and the same numbers the user just watched.

## 4. Showing it

In the browser route, hand each step to `ui-walkthrough` and be on the page **before** the command runs, so the user watches the platform change rather than being shown the result: the project page before the branch appears, the branch before the run, the run's Experiments tab while versions are generated.

In the terminal route, give a link to the project and name the page to open.

## 5. When it cannot continue

| Situation | Do |
|---|---|
| CLI missing or unauthenticated | `cli-setup`, then return to step 2 |
| No runner, and the user does not want one | Say plainly that nothing can be measured without a machine, and stop. Do not start a run |
| The benchmark produces no numbers | Fix the script and re-run. Never start Discovery on an unmeasured branch |
| Nothing worth measuring in this project | Say so and stop |
| The run fails in seconds with no baseline | `discovery-inspect`, checking the project's Git access first |

## 6. Close

Report what now exists: the branch, the commands, the runner, the measured baseline with its numbers, and the Discovery run with a link. Say what it is optimising and roughly how long it will take. Then hand over to `discovery-inspect` for reading the result.

## Checklist

- [ ] Project id confirmed against a real project on the authenticated deployment
- [ ] The user was asked about their goal only where the repository could not answer
- [ ] Branch created, and its changeset id captured for the run
- [ ] Commands verified by running them, not assumed
- [ ] Metrics read back from the validation, not from a log
- [ ] Discovery started from the branch, with settings fixed rather than asked
- [ ] User told what was measured, what is running, and where to watch it
