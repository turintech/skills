---
name: quickstart
description: Take an existing Artemis project to a first measured result, covering a changeset of the current code, compile/test/benchmark commands that produce a number, a runner, a measured validation, and a Discovery run. Use when the user gives a project URL or id, or asks to set up or measure a project that is already imported.
compatibility: Requires Artemis CLI 1.0.7+ and Artemis Platform 3.0.3+.
metadata:
  artemis-cli-min: "1.0.7"
  artemis-platform-min: "3.0.3"
---

# Quickstart an existing project

## At a glance

- **Problem:** Turns an imported project into a measured baseline and a running Discovery, using the production compile, test, and benchmark commands.
- **Must be available:** A project that already exists in Artemis, its URL or id, and a user who can create an API key if the CLI is not yet authenticated.
- **Use / don't use:** Use when the project exists. Use `getting-started` when the user has no project or wants the Particle Life demo.
- **Next skill:** Hands each step to `cli-setup`, `repo-command-setup`, `runner-setup`, `discovery-start`, and `discovery-inspect`.

## Requirements

- The project, as a Web UI URL or a bare UUID.

Nothing else is required from the user. Everything below is checked rather than asked for.

If `artemis discovery create --help` offers `--script` and not `--compile-cmd`, stop. That CLI targets a newer platform than this skill. Do not pass `--script`, `--source-changeset`, `--eval-mode`, `--eval-runs`, `--llm-metrics`, or `--setup-cmd`.

## 0. Read the project URL

`https://<deployment>/projects/<project-id>` carries both facts this skill needs: the project id from the path, the deployment from the origin. Take them from there rather than asking.

Then confirm the CLI is authenticated to that same deployment. A CLI logged in elsewhere reports the project as missing. Name the deployment `artemis status` is on, and fix that before creating anything.

## 1. Look before asking

Check silently, and skip what is already done.

| Check | How |
|---|---|
| CLI and authentication | `artemis --version`, `artemis status` |
| The project is real and reachable | `artemis --output-format json project list`, matching the id. Keep its `gitUrl`, `gitBranch`, and `gitHash` |
| Commands already stored | `artemis project commands get --project <id>` when that command exists; otherwise `artemis project get` |
| A runner online | `artemis runner list` |
| The code, locally | `git -C . remote get-url origin` against the project's `gitUrl` |

The prompt arrives in whatever directory the user's agent happens to be running in, which is not always the project's repository. If the origin remote does not match the project's `gitUrl`, say so and ask which checkout to work in. If there is no checkout, the flow still works, because every command runs on the runner, but say that writing a benchmark without the code in front of you is slower and offer to clone it first.

A new changeset is created from the project's current imported commit. Read that commit with `artemis project compare <project-id>` and tell the user that one, rather than assuming their local checkout matches.

## 2. The rules for this flow

- **Never ask the user to choose run settings.** Not the model or the version budget. Fix them here and state what you are using.
- **Announce, do not ask,** for anything long-lived or external: starting a runner, creating a changeset, starting a run. Say what you are about to do, then do it.
- **The user's credentials are theirs.** Give the login command first, take them to the key page second, and never read, type, or handle a key. Never ask them to paste a key, token, or password into the chat.
- **Assume nothing about what they know.** The first time you use a word the platform owns, say what it means in one short clause: a changeset is Artemis's copy of the code at the imported commit, a Discovery run is the agent trying versions and measuring each one.
- **Stop cleanly rather than inventing.** If there is nothing measurable, say so. Do not fabricate a metric to satisfy the last step.

## 3. What "better" means here

Particle Life ships a benchmark. A real repository usually does not, and Discovery cannot optimise what nobody measures.

1. **Read the repository first:** build files, CI config, test layout, existing scripts, README. Most projects answer this themselves.
2. **Then ask, once,** only what the code cannot tell you: what "better" means for them, which command represents it, and roughly how long it takes.
3. If the honest answer is that nothing worth measuring exists yet, say so and stop.

Hand the three commands to `repo-command-setup`. That skill owns the compile, test, and benchmark contract, including a numeric `artemis_results.json` or `artemis_results.csv`.

## 4. The seven steps

Each step has an owning skill. Use it rather than improvising.

| Step | Skill | Command |
|---|---|---|
| 1. CLI installed and authenticated | `cli-setup` | `artemis status`, then return here |
| 2. A changeset over the current code | this skill | `artemis changeset create --project <id> --name baseline` |
| 3. A runner that can build this project | `runner-setup` | Reuse one that is online and on this machine. Install one only if there is none |
| 4. Commands that produce a number | `repo-command-setup` | compile, test, and benchmark |
| 5. Run them on the changeset | this skill | `artemis changeset validate` with three `--command` flags |
| 6. Confirm metrics exist | `execution-log-inspect` | The validate process id, then the results file in the log |
| 7. Discovery from those commands | `discovery-start` | `artemis discovery create` with the same commands inline |

### Step 2, the changeset

```bash
artemis --output-format json changeset create --project "<project-id>" --name "baseline"
```

A new changeset holds exactly one version: the project's code as imported. Capture its id. Steps 5 and the explanation of "code out" both need it.

### Before step 4, ask the runner what it has

An online runner is not the same as a runner that can build this project. Its environment is whatever shell started it. Find out before writing commands that assume a toolchain:

```bash
artemis --output-format json changeset validate "<changeset-id>" --project "<project-id>" \
  --version original \
  --command "python3 --version; cmake --version; c++ --version" \
  --runner "<runner-name>" --wait
```

Name the tools this repository actually needs. A probe costs seconds and saves authoring a benchmark that cannot run. If the runner is missing what the project needs, say exactly which tool is missing on which machine, and let the user choose between installing it there and using a different machine. Do not quietly rewrite the project's commands to avoid the missing tool.

### Step 5, the measured run

After `repo-command-setup` has the three commands:

```bash
artemis --output-format json changeset validate "<changeset-id>" --project "<project-id>" \
  --version original \
  --command "<compile>" \
  --command "<test>" \
  --command "<benchmark>" \
  --runner "<runner-name>" --wait
```

`--project` and `--runner` are required. `--version original` is the code as it stands. `--wait` gives up after 20 minutes and exits 6, so pass `--timeout` when the benchmark is slower than that, and say how long you expect it to take before starting.

This is the same primitive Discovery uses to evaluate every version, so a pass here means Discovery can run, and the user has a real number before anything is spent on a run. The Discovery baseline measures the same code again inside the run. Expect the two numbers to agree. If they do not, say so: that is evidence the benchmark is noisy.

Run it through the platform, on the runner, not locally. A local run proves nothing about the machine Discovery will use.

Store the same commands on the project so the Web UI settings match:

```bash
artemis project commands set --project "<project-id>" \
  --compile "<compile>" \
  --test "<test>" \
  --benchmark "<benchmark>"
```

Discovery does not consume those stored defaults. Pass the same strings inline in step 7.

### Step 6, the numbers

`changeset validation get` answers one question: did every command pass. It reports `exitCode`, `runtime`, `cpu`, and `memory` per command and nothing about the benchmark's own metrics.

The task log is where the proof is. `execution-log-inspect` fetches it from `status.id` on the validate response. Do not use a per-command `logId`. Look for `artemis_results.json` or `artemis_results.csv` and the metric values. If the benchmark passed but wrote no metrics, fix the commands with `repo-command-setup` and run step 5 again. A run with no measurement wastes the user's credits.

Report the measured value in the repository's own units, never the runtime of the benchmark command.

### Step 7, the run

Settings for this flow, so the user is never asked:

- `--versions 5`
- `--model` set to `gpt-5.6-sol` when `artemis model list` offers it, otherwise another preset from that list, named in one line

`--model` is required. The API has no default, so a run without it is refused. Pass the catalogue UUID or the model-type code from `artemis model list`.

```bash
artemis --output-format json discovery create --project "<project-id>" \
  --runner "<runner-name>" \
  --model "<model>" \
  --task "<the user's goal, in their words>" \
  --compile-cmd "<compile>" \
  --test-cmd "<test>" \
  --benchmark-cmd "<benchmark>" \
  --versions 5
```

Add `--target-files <path>` (repeatable) when the repository made it obvious which files carry the work. Leave it off rather than guessing.

There is no `--source-changeset` on this platform. The run measures the project's imported code. The changeset from step 2 is how you proved those commands, and how you show the diff of later candidates. It is not a source argument to `discovery create`.

Give the link immediately:

```text
[Open Discovery](<base-url>/projects/<project-id>/discovery/<run-id>)
```

### Code in, run, code out

Say this once, in three lines:

1. **Code in.** The project is pinned at the commit `project compare` reported. The runner checks out that commit.
2. **Run.** Compile, test, and benchmark run on the runner, in that order. The benchmark writes the metric file.
3. **Code out.** `discovery-inspect` reads a candidate with `artemis changeset diff <changeset-id> --project <project-id>`. Edits pushed to the Git remote come back with `artemis project compare` and `artemis project pull`.

## 5. Showing it

Give a link to the project, then to the Discovery run. Name the page to open. Do not depend on a browser-control skill.

## 6. When it cannot continue

| Situation | Do |
|---|---|
| CLI missing, unauthenticated, or without `--compile-cmd` | `cli-setup`, then return to step 2. Stay on the compile/test/benchmark command surface |
| No runner, and the user does not want one | Say plainly that nothing can be measured without a machine, and stop |
| The runner is online but lacks the toolchain | Name the missing tool and the machine |
| The benchmark produces no numbers | Fix the commands and re-run step 5. Never start Discovery on an unmeasured project |
| Nothing worth measuring in this project | Say so and stop |
| The run fails in seconds with no baseline | `discovery-inspect`, checking the project's Git access first |
| The project URL's deployment is not the one the CLI is logged into | Say both, and settle it before creating anything |

## 7. Close

Report what now exists: the changeset, the commands, the runner, the measured value, and the Discovery run with a link. Say what it is optimising and roughly how long it will take. Then hand over to `discovery-inspect` for reading the result.

Say that the run continues on the platform if the terminal is closed, and give the runner stop command.

## Checklist

- [ ] Project id confirmed against a real project on the authenticated deployment
- [ ] The user was asked about their goal only where the repository could not answer
- [ ] Changeset created and its id captured
- [ ] Commands verified on the runner with `changeset validate --command`, not assumed
- [ ] Metric values seen in the task log, not assumed from a passing benchmark
- [ ] The same commands stored with `project commands set` and passed inline to `discovery create`
- [ ] Discovery started with `--versions 5` and a `--model` from `artemis model list`
- [ ] User told what was measured, what is running, and where to watch it
