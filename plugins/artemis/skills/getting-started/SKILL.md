---
name: getting-started
description: Welcome a new Artemis user and take them to a first measured result, either the Particle Life example or their own project. Use when the user pasted a get-started prompt, asks to get started with or try Artemis, or has no authenticated CLI and no concrete task yet.
compatibility: Requires Artemis CLI 1.0.7+ and Artemis Platform 3.0.3+.
metadata:
  artemis-cli-min: "1.0.7"
  artemis-platform-min: "3.0.3"
---

# Get started with Artemis

## At a glance

- **Problem:** Takes a new user from a pasted prompt to a working setup and a first optimisation they have watched and understood.
- **Must be available:** A coding assistant with the Artemis skills installed, network access, and a user who can create an API key in the Artemis Web UI.
- **Use / don't use:** Use for new users and open-ended "get started" requests. When the project already exists in Artemis and the user has its URL or id, use `quickstart` instead. When the user already names a concrete task and its inputs, the `artemis` router handles that.
- **Next skill:** This skill runs no commands itself. It hands each step to `cli-setup`, `runner-setup`, `project-import`, `repo-command-setup`, `discovery-start`, and `discovery-inspect`.

## Requirements

- The deployment base URL, from the prompt or the user.
- The user present at each human-only step.

Follow along in the terminal and with links. Give a clickable project or Discovery link at each handoff. Do not look for a browser-control skill.

## 0. Look before asking

Check silently, and skip later steps that are already done.

| Check | How |
|---|---|
| CLI | `artemis --version` is 1.0.7 or newer, and `artemis status` is authenticated against the deployment in the prompt |
| Command surface | `artemis discovery create --help` offers `--compile-cmd`, `--test-cmd`, and `--benchmark-cmd`. `artemis changeset validate --help` offers repeatable `--command` |
| Git access | `artemis key list` returns at least one key id |
| Runner | `artemis runner list` shows one online whose `PATH` has `cmake`, a C++17 compiler, and `python3` |

If `discovery create --help` offers `--script` and not `--compile-cmd`, stop. That CLI targets a newer platform than these skills. Do not pass `--script`, `--source-changeset`, `--eval-mode`, `--eval-runs`, `--llm-metrics`, or `--setup-cmd`.

## 1. Welcome

Say four short lines:

1. Artemis uses AI to try improvements to real code and measures every attempt.
2. The measuring happens on the user's own machine, through a small program called a runner.
3. Next comes a short setup, then either a demo or their own project.
4. Setup takes a few minutes. The Particle Life example then runs 5 versions. Most of that time is waiting for results.

Say once, before starting the example, that the run uses account credits and the balance is in the Web UI header. Do not turn that into a question, and do not repeat it later.

## 2. How to follow along

Links are the way to watch. After each create or import, give the Web UI link and name the page to open. The run continues on the platform if the terminal is closed.

## 3. Example or own project

Recommend the example, and say why:

"I'd suggest starting with our demo project, Particle Life (recommended). It is a small C++ simulation that is deliberately slow, so you can watch a real optimisation from start to finish and see what Artemis produces before pointing it at your own code. Would you like to do that, or go straight to your own project?"

- Example: section 4, then section 5a.
- Their own project: ask "What would you like to optimise?", then section 4, then section 5b.

If they are undecided, recommend the example again once and move on.

## 4. Setup

Hand each missing item to its skill. Say plainly when a step is the user's, and wait.

| Item | Skill | Human part |
|---|---|---|
| CLI installed and authenticated to this deployment | `cli-setup` | Creates an API key and enters it in their own terminal |
| Git access | `project-import` | Connects a Git provider if the account has none |
| Runner on this machine | `runner-setup` | Agrees to start a long-lived process |

The runner this step starts or finds online is the one the demo uses. Pass it to `discovery-start`. Do not ask the user to pick among online runners when one suitable runner is already up.

Confirm `cmake`, `ctest`, a C++17 compiler, and `python3` are on that runner's `PATH` before importing. A missing tool fails the benchmark in a way that looks like a platform fault.

## 5a. The Particle Life example

| Stage | Skill | Explain |
|---|---|---|
| Import `https://github.com/turintech/particle-life`, branch `main`, named `Particle Life` | `project-import` | A project is a repository pinned at a commit. Record the `gitHash` from `artemis project compare` |
| Store and verify the commands below | `repo-command-setup` | Build, test, and benchmark are checked on the runner before Discovery spends a version budget |
| Start: 5 versions, model from section 5a | `discovery-start` | The original code is measured first. That measurement is the baseline |
| Watch and report | `discovery-inspect` | Versions are attempts. The diff is the code that produced the winning measurement |

**Do not ask the user to choose the demo settings.** Never ask a new user for the version budget, the model, the target files, or the task wording. State what you are running and start it. Downstream skills may require these values; supply them from this section.

**Show the benchmark setup. Do not skip verification.** The commands are known, so do not ask the user to author a harness, and do not ask whether to verify. Run the verification and say what it proved: compile, test, and a fresh numeric `artemis_results` file on the runner.

**Do not stop for approval between the steps.** The user already chose the demo. Say what you are about to do, do it, and keep going: import, verify, run, watch, result.

### Commands

Hand these to `repo-command-setup` unchanged:

- compile: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel`
- test: `ctest --test-dir build --output-on-failure`
- benchmark: `python3 tools/benchmark.py --no-visualize`
- target files: `src/simulation.cpp` and `src/simulation.hpp`
- task: `Maximize simulation_fps without changing simulation behavior or weakening the correctness tests.`
- versions: `5`
- metric: `simulation_fps`, higher is better

`repo-command-setup` verifies them with `changeset validate` and repeatable `--command` flags, in compile, test, benchmark order, on `--version original`. Then `execution-log-inspect` reads the task log for a fresh `artemis_results.json` or `artemis_results.csv`. `changeset validation get` reports exit codes only. Do not start Discovery until that file is in the log.

Also store the same three commands with `artemis project commands set` so the project settings match what Discovery will run. Discovery does not read those defaults. Pass the same commands inline to `discovery create`.

### Code in, run, code out

Say this once while the demo is running, in three lines:

1. **Code in.** Import pins the repository at the commit `project compare` reported. The runner checks out that commit. It does not use the user's working tree.
2. **Run.** The platform sends compile, then test, then benchmark to the runner. The benchmark writes `simulation_fps`.
3. **Code out.** Each candidate is a changeset. `discovery-inspect` reads the winning diff with `artemis changeset diff`. A later edit to the Git remote comes back with `artemis project compare` and `artemis project pull`.

### Model

`--model` is required. `artemis discovery create --help` marks it required, and the API does not default it.

Prefer `gpt-5.6-sol`. Resolve it with `artemis model list` and pass the catalogue UUID or the model-type code that list shows. If this deployment does not offer `gpt-5.6-sol`, pick another preset from that list, say in one line which one, and continue. Never fail the demo over a missing model, and never omit `--model`.

### Links

- project: `<base-url>/projects/<project-id>`
- discovery: `<base-url>/projects/<project-id>/discovery/<run-id>`

## 5b. Their own project

Ask one question first: where does the code live (repository URL and branch), and can Artemis reach it?

Import it with `project-import`, then hand the project to `quickstart`. `quickstart` owns the branch, the commands, the runner check, the measured run, and the first Discovery. Do not ask the questions it is about to ask.

Come back here only to close the session (section 8).

## 6. Human-only steps

| Step | Agent's job |
|---|---|
| Log in and create an API key | `cli-setup` owns the order. The key is the last thing the user copies. Say plainly that this step is theirs, and wait |
| Connect a Git provider | Take them to the Git page and give the link |
| Start the runner | Say what you are starting, start it in the background, and give the stop command |

## 7. When things go wrong

| Situation | Do |
|---|---|
| The CLI is older than 1.0.7, or its help has no `--compile-cmd` | `cli-setup` installs a CLI in the 1.0.7–1.0.8 range that still has `--compile-cmd` and `changeset validate --command`. Do not switch this flow onto validation scripts |
| The runner is offline | `runner-setup`, then retry |
| The runner lacks cmake, a C++ compiler, or python3 | Name the missing tool and the machine. Do not rewrite the Particle Life commands to avoid it |
| Verify fails | `execution-log-inspect` on the validate process id. Fix the command or the runner, then validate again. Do not start Discovery |
| A run fails within seconds with no baseline | `discovery-inspect`, checking the project's Git access first |
| The user wants to stop | Summarise what exists, give the links, and say how to resume with `discovery-inspect` |

## 8. Close

Report what is set up, what ran, and the result: the original and best measured `simulation_fps`, with links. Then suggest two next steps: steer the run (`discovery-steer`), or try their own project through `quickstart`.

Say two things once:

- **The run does not depend on this session.** It continues on the platform if the terminal is closed. Say this while the run is going.
- **The runner is still running.** Give the stop command again at the end, and say it can stay up for the next run.

## Checklist

- [ ] State checked before asking anything
- [ ] CLI help shows `--compile-cmd` and `changeset validate --command`
- [ ] Example recommended
- [ ] Every human-only step named as the user's
- [ ] Particle Life commands verified on the runner, and `artemis_results` seen in the task log
- [ ] Discovery started with those same commands inline, `--versions 5`, and a `--model` from `artemis model list`
- [ ] Result reported with measured numbers, the winning diff, and links
