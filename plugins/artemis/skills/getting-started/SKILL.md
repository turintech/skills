---
name: getting-started
description: Welcome a new Artemis user and take them to a first measured result, offering to show each step in their browser or work in the terminal, and to run the Particle Life example or their own project. Use when the user pasted the Artemis Quickstart prompt, asks to get started with or try Artemis, or has no authenticated CLI and no concrete task yet.
compatibility: Requires Artemis CLI 1.1.5 or newer. The browser route needs a browser-control tool such as Claude in Chrome.
metadata:
  artemis-cli-min: "1.1.5"
---

# Get started with Artemis

## At a glance

- **Problem:** Takes a brand-new user from a pasted prompt to a working setup and a first optimisation they have watched and understood.
- **Must be available:** A coding assistant with the Artemis skills installed, network access, and a user who can create an API key in the Artemis Web UI.
- **Use / don't use:** Use for new users and open-ended "get started" requests. Don't use it when the user already names a task and its inputs; the `artemis` router handles those.
- **Next skill:** This skill runs no commands itself. It hands each step to `cli-setup`, `runner-setup`, `project-import`, `repo-command-setup`, `discovery-start`, and `discovery-inspect`, and in the browser route to `ui-walkthrough`.

## Requirements

- The deployment base URL, from the Quickstart prompt or the user.
- The user present at each human-only step (section 6).

## 0. Look before asking

Check silently, and skip later steps that are already done.

| Check | How |
|---|---|
| Assistant host | Claude Code, Cursor, Codex, or GitHub Copilot |
| Browser control | A browser-control tool is available and a browser is connected |
| Operating system | `uname -s` |
| CLI | `artemis --version` is 1.1.5 or newer, and `artemis status` is authenticated |
| Runner | `artemis runner list` shows one online |

## 1. Welcome

Say four short lines:

1. Artemis uses AI to try improvements to real code and measures every attempt.
2. The measuring happens on the user's own machine, through a small program called a runner.
3. Next comes a quick setup, then either a demo or their own project.
4. Setup takes a few minutes. The Particle Life example then runs 10 versions, roughly 15 to 20 minutes, most of it watching results arrive.

## 2. How to follow along

- If browser control is available, ask: "I can show you each step in your browser as I go (recommended), or keep everything in this terminal. Which would you like?"
- If not, say: "Seeing the platform in your browser needs Claude Code with Claude in Chrome, so we'll use the terminal." Then continue.

Remember the choice for the session. In the browser route, use `ui-walkthrough` to show the page named at each step below.

## 3. Example or own project

Ask: "Would you like to see an example first? (recommended) I'll run our demo project, Particle Life, so you can watch a real optimisation from start to finish."

- Yes: section 4, then section 5a.
- No: ask "What would you like to optimise?", then section 4, then section 5b.

## 4. Setup

Hand each missing item to its skill. Say plainly when a step is the user's, and wait.

| Item | Skill | Human part | Page |
|---|---|---|---|
| CLI installed and authenticated | `cli-setup` | Creates an API key and enters it in their own terminal | API keys |
| Git access | `project-import` | Connects a Git provider if the account has none | Git |
| Runner on this machine | `runner-setup` | Agrees to start a long-lived process | Runners, once online |

## 5a. The Particle Life example

| Stage | Skill | Page | Explain |
|---|---|---|---|
| Import `https://github.com/turintech/particle-life`, branch `main` | `project-import` | Project | A project is a repository pinned at a commit |
| Validation script from the commands below | `repo-command-setup` | Project | Build, test and benchmark are stored once and reused |
| Start: 10 versions, the catalogue's default preset model | `discovery-start` | Discover, then the run | The original code is measured first |
| Watch | `discovery-inspect` | Discovery run | Experiments are ideas; versions are attempts |
| Result | `discovery-inspect` | Discovery version (the fastest) | Which numbers are measured and which are AI-judged; "BEST" is a blended score, not always the fastest |

Particle Life inputs:

- compile: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel`
- test: `ctest --test-dir build --output-on-failure`
- benchmark: `python3 tools/benchmark.py --no-visualize`
- target files: `src/simulation.cpp` and `src/simulation.hpp`
- task: `Maximize simulation_fps without changing simulation behavior or weakening the correctness tests.`

## 5b. Their own project

Assume nothing is known. Ask one question at a time:

1. Where does the code live (repository URL and branch), and can Artemis reach it?
2. What does "better" mean: which metric, and is higher or lower better?
3. How is it built and tested today?
4. Which machine should run it? The default is this one.

Then hand over to the `artemis` router's readiness brief. `repo-command-setup` prepares the benchmark and validation script on an Artemis changeset, and `discovery-start` starts from that changeset with `--source-changeset`.

## 6. Human-only steps

| Step | Agent's job |
|---|---|
| Create an API key | Take them to the page, say it is their step, wait |
| Enter the key | Give the exact terminal command; never ask for the key in chat |
| Connect a Git provider | Take them to the page |
| Start the runner | Ask permission, prefer a named tmux session, and explain how to stop it |

## 7. When things go wrong

| Situation | Do |
|---|---|
| The browser route fails | Continue in the terminal with links |
| The CLI is older than 1.1.5 | `cli-setup` updates it |
| The runner is offline before starting | `runner-setup`, then retry |
| A run fails within seconds with no baseline | `discovery-inspect`, checking the project's Git access first |
| The user wants to stop | Summarise what exists and how to resume |

## 8. Close

Report what is set up, what ran, and the result: the original and best measured values, with links. Then suggest three next steps: steer a run (`discovery-steer`), chart the results (`discovery-visualize`), or try their own project.

## Checklist

- [ ] State checked before asking anything
- [ ] Browser route offered only when possible
- [ ] Example recommended
- [ ] Every human-only step named as the user's
- [ ] Each step handed to its owning skill
- [ ] Result reported with measured numbers and links
