---
name: getting-started
description: Welcome a new Artemis user and take them to a first measured result, offering to show each step in their browser or work in the terminal, and to run the Particle Life example or their own project. Use when the user pasted the Artemis Quickstart prompt, asks to get started with or try Artemis, or has no authenticated CLI and no concrete task yet.
compatibility: Requires Artemis CLI 1.1.8+ and Artemis Platform 3.1.0+. The browser route needs a browser-control tool such as Claude in Chrome.
metadata:
  artemis-cli-min: "1.1.8"
  artemis-platform-min: "3.1.0"
---

# Get started with Artemis

## At a glance

- **Problem:** Takes a brand-new user from a pasted prompt to a working setup and a first optimisation they have watched and understood.
- **Must be available:** A coding assistant with the Artemis skills installed, network access, and a user who can create an API key in the Artemis Web UI.
- **Use / don't use:** Use for new users and open-ended "get started" requests. Don't use it when the user already names a task and its inputs; the `artemis` router handles those. When the project already exists in Artemis and the user has its id, use `quickstart` instead.
- **Next skill:** This skill runs no commands itself. It hands each step to `cli-setup`, `runner-setup`, `project-import`, `repo-command-setup`, `discovery-start`, and `discovery-inspect`, and in the browser route to `ui-walkthrough`.

## Requirements

- The deployment base URL, from the Quickstart prompt or the user.
- The user present at each human-only step (section 6).

## 0. Look before asking

Check silently, and skip later steps that are already done.

| Check | How |
|---|---|
| Assistant host | Claude Code, Cursor, Codex, or GitHub Copilot |
| Browser control | Load the browser tools first, then check. On hosts where they are deferred they exist only as names until loaded, so a plain look reports none even when a browser is connected. In Claude Code, one `ToolSearch` for `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_create_mcp`. Only an empty result means no browser. See `ui-walkthrough` section 1 |
| Operating system | `uname -s` |
| CLI | `artemis --version` is 1.1.8 or newer, and `artemis status` is authenticated |
| Runner | `artemis runner list` shows one online |

## 1. Welcome

Say four short lines:

1. Artemis uses AI to try improvements to real code and measures every attempt.
2. The measuring happens on the user's own machine, through a small program called a runner.
3. Next comes a quick setup, then either a demo or their own project.
4. Setup takes a few minutes. The Particle Life example then runs 5 versions, about 15 minutes, most of it watching results arrive.

Say once, before starting the example, that the run uses account credits and the balance is in the Web UI header. Nothing more: no estimate framed as a comparison, no analogy, no joke about the price. Do not turn it into a question, and do not repeat it later.

## 2. How to follow along

Ask this **before** asking what they want to do. Seeing the platform is most of what makes the first session make sense, and a user who picks the browser route should see the setup steps too, not just the run.

- If browser control is available, ask: "I can show you each step in your browser as I go (recommended), or keep everything in this terminal. Which would you like?"
- If not, do not write the browser off yet. `ui-walkthrough` section 1 covers loading the tools, probing for a live browser, and the three things that actually stop one connecting: no visible window, an extension paired before the session existed, and a resumed session that lost its browser flag. Offer those, wait, and probe again. Say "we'll use the terminal" only once that has failed, and say which check failed so the user knows what to fix.

Remember the choice for the session. In the browser route, use `ui-walkthrough` to show the page named at each step below, and tell it this is a **first-run demo** so it uses its watchable pacing. That pacing is for this first tour only; a user who comes back does not need it.

## 3. Example or own project

Mark the recommended choice as **recommended** on the option itself, not only in the surrounding prose. A first-time user scanning two options should be able to see which one we advise without reading a paragraph. The same applies to the browser choice in section 2.

Recommend the example plainly, and say why:

"I'd suggest starting with our demo project, Particle Life (recommended). It is a small C++ simulation that is deliberately slow, so you can watch a real optimisation from start to finish in about 15 minutes and see what Artemis actually produces before pointing it at your own code. Would you like to do that, or go straight to your own project?"

- Example: section 4, then section 5a.
- Their own project: ask "What would you like to optimise?", then section 4, then section 5b.

If they are undecided, recommend the example again once and move on. Someone who has never seen a discovery run has no way to judge the settings their own project would need.

## 4. Setup

Hand each missing item to its skill. Say plainly when a step is the user's, and wait.

| Item | Skill | Human part | Page |
|---|---|---|---|
| CLI installed and authenticated | `cli-setup` | Creates an API key and enters it in their own terminal | API keys |
| Git access | `project-import` | Connects a Git provider if the account has none | Git |
| Runner on this machine | `runner-setup` | Agrees to start a long-lived process | Runners, once online |

Whichever runner this step starts or finds online is the one the demo uses. Pass it to `discovery-start` rather than asking the user to choose.

## 5a. The Particle Life example

| Stage | Skill | Page | Explain |
|---|---|---|---|
| Import `https://github.com/turintech/particle-life`, branch `main` | `project-import` | Project | A project is a repository pinned at a commit |
| Validation script from the commands below | `repo-command-setup` | Project | Build, test and benchmark are stored once and reused |
| Start: 5 versions, model `gpt-5.6-sol`, three measurements per version | `discovery-start` | Discover, then the run | The original code is measured first, and each version is measured three times so the charts show a range instead of a single point |
| Watch | `discovery-inspect` | Project overview, then the run, then its Experiments tab | Experiments are ideas; versions are attempts |
| Result | `discovery-inspect` | Metrics, then the winning version, then its code change | Read the chart to find the winner, then look at the code that produced it |

**Do not ask the user to choose any of this.** The demo's settings are fixed here precisely so a first-time user is never asked a question they have no basis to answer. Never ask a new user for the version budget, the model, the number of measurements, the target files, or the task wording. State what you are running and start it. Downstream skills may require these values; supply them from this section rather than passing the question on.

**Do not stop for approval between the steps either.** The user already chose the demo, and that was the decision. Say what you are about to do, do it, and keep going: import, script, run, watch, result, in one continuous pass. A readiness report is something you say on the way past, not a gate you wait behind. Starting the runner and creating the project are announced, not asked.

### Watching the run in the browser

The run is the part worth seeing, so follow it on screen rather than reporting it from the terminal:

Stand on the page **before** the thing happens, so the user sees the platform change rather than being shown the result afterwards. This applies to every creating step, not just the import: Projects before `project import`, the project overview before `discovery create`, the listing tab before anything that adds a version or branch. See `ui-walkthrough`, *Arrive before the change, never after*, which also says to click into the thing that just appeared rather than jumping to it.

1. Open the project. The overview lists the run that was just started.
2. Move the pointer to that run and click it, so the user sees where it came from rather than arriving on a page by magic.
3. Open the **Experiments** tab and **stay there**. Experiments appear as the agent thinks of them, so the page fills while the user watches. That is the moment the platform explains itself.
4. Leave the tab up while work continues. Do not flick between tabs to gather status; read what you need from the CLI instead, and keep the screen still.
5. Move to the versions and the result only once there is something measured to show.

### Showing the result

End on the code, not on a number. Keep it brief:

1. Open the run's **Metrics** tab and read the chart. The winner is visible there, so the user sees which version won and by how much rather than being told.
2. Click into that version.
3. Show its **code change**. This is the payoff: the actual diff Artemis wrote to make the code faster, and the thing worth retelling afterwards.
4. Then its details, if there is anything worth pointing out.

Say which numbers are measured and which are AI-judged, and that "BEST" is a blended score rather than always the fastest.

Check the account has credits before starting it. There is no CLI command for the balance: in the browser route read the Web UI header, which is already open, and in the terminal route ask the user to glance at it once. An account with no credits fails the run in a way that looks like a platform fault, which is a poor first impression and easy to prevent.

Particle Life inputs:

- compile: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel`
- test: `ctest --test-dir build --output-on-failure`
- benchmark: `python3 tools/benchmark.py --no-visualize`
- target files: `--target-files src/simulation.cpp --target-files src/simulation.hpp`
- task: `Maximize simulation_fps without changing simulation behavior or weakening the correctness tests.`
- measurement: `--eval-mode fixed --eval-runs 3`
- scoring: `--llm-metrics=false`
- model: `gpt-5.6-sol`

The model is pinned on purpose. The win this demo exists to show is a spatial grid replacing the all-pairs loop, and finding it is model-dependent. Do not substitute the catalogue default by choice: that turns the demo into a coin flip and leaves a first-time user looking at a "Best" badge on a fraction of a percent.

**Catalogues differ between deployments, so check before using it.** If `artemis model list` does not offer `gpt-5.6-sol` on this deployment, fall back to the catalogue default, say in one line that you have done so, and continue. Never fail the demo over a missing model.

LLM-judged metrics are off for the demo on purpose. The point of a first run is the measured number, `simulation_fps`, and a judged score sitting beside it invites the reader to treat an opinion as a measurement.

Three measurements per version is deliberate here. One measurement gives a single number with no sense of how much it wobbles, so the run can only report a point estimate; three give the range the charts are built on. Particle Life measures in about three seconds, so this adds roughly two minutes to the demo. It is not a default to copy onto a slow benchmark without doing that arithmetic first.

## 5b. Their own project

Ask one question first, because it decides everything after it: where does the code live, repository URL and branch, and can Artemis reach it?

Then import it with `project-import`, and hand the project to `quickstart`, which owns this path from here: reading the repository to work out what "better" means, storing commands that produce a number, reusing or installing a runner, measuring the original code, and starting Discovery from that branch. Do not ask the questions it is about to ask.

Come back here only to close the session (section 8).

## 6. Human-only steps

| Step | Agent's job |
|---|---|
| Log in and create an API key | `cli-setup` owns the order and the exact message. The invariant: the key is the last thing the user copies, so nothing overwrites it on their clipboard. Say plainly that this step is theirs, and wait |
| Connect a Git provider | Take them to the page |
| Start the runner | Say what you are starting, start it in the background, and give the stop command |

## 7. When things go wrong

| Situation | Do |
|---|---|
| The browser route fails | Continue in the terminal with links |
| The CLI is older than 1.1.8 | `cli-setup` updates it |
| The runner is offline before starting | `runner-setup`, then retry |
| A run fails within seconds with no baseline | `discovery-inspect`, checking the project's Git access first |
| The user wants to stop | Summarise what exists and how to resume |
| `uname -s` reports `Darwin` | There is no macOS runner build, so this Mac cannot host one. Say so in section 3, before recommending anything, and use a runner on another machine |

## 8. Close

Report what is set up, what ran, and the result: the original and best measured values, with links. Then suggest three next steps: steer a run (`discovery-steer`), chart the results (`discovery-visualize`), or try their own project.

Two things a first-time user does not know, and should hear once:

- **The run does not depend on this session.** It continues on the platform if the terminal is closed, and the Web UI shows it either way. Say this while the run is going, not at the end, so nobody sits guarding a terminal they are afraid to close.
- **The runner is still running.** Give the stop command again at the end, and say it can stay up for the next run.

## Checklist

- [ ] State checked before asking anything
- [ ] Browser route offered only when possible
- [ ] Example recommended
- [ ] Every human-only step named as the user's
- [ ] Each step handed to its owning skill
- [ ] Result reported with measured numbers and links
