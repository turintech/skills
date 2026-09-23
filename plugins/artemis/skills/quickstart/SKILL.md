---
name: quickstart
description: Take a user to a first measured Artemis result from wherever they are starting, whether a machine with nothing installed, a repository that is not yet a project, or an existing project URL or id. Offers to show each step in their browser or work in the terminal, and recommends the Particle Life example to anyone who has not run Artemis before. Use when the user pasted either Artemis Quickstart prompt, asks to get started with or try Artemis, gives a project URL or id, or asks for a project to be set up and measured.
compatibility: Requires Artemis CLI 1.1.8+ and Artemis Platform 3.1.0+. The browser route needs a browser-control tool such as Claude in Chrome.
metadata:
  artemis-cli-min: "1.1.8"
  artemis-platform-min: "3.1.0"
---

# Quickstart

## At a glance

- **Problem:** One skill for the whole first mile: from a pasted prompt to a setup the user has watched, a measured baseline, and a first Discovery run, resuming at whichever step is missing.
- **Must be available:** A coding assistant with the Artemis skills installed, network access, and a user who can create an API key in the Artemis Web UI. A repository or project by the time repository setup begins.
- **Use / don't use:** Use for both copyable prompts, for "get started" and "try Artemis", and for any request carrying a project URL or id. Don't use it when the user names a specific lower-level task and its inputs; the `artemis` router sends those to the owning skill.
- **Next skill:** This skill runs almost nothing itself. It hands each step to `cli-setup`, `project-import`, `runner-setup`, `repo-command-setup`, `discovery-start` and `discovery-inspect`, and in the browser route to `ui-walkthrough`. The two commands it owns are `changeset create` and `changeset validate`.

## Requirements

- The deployment base URL, from the prompt, a project URL, or the user.
- One of: nothing yet, a repository URL and branch, or a project URL or id.
- The user present at each human-only step (section 9).

## Operating rule: inspect, resume, delegate

Never redo a step that is done. Check the state first (section 0), start at the first thing missing, and hand each step to the skill that owns it. Do not re-import a project that exists, start a second runner on a machine that has one, replace commands that already produce a number, or start another Discovery when one is queued or running.

Carry these between skills, so nothing is asked twice: the deployment and whether the CLI is authenticated to it; the repository URL and branch; the project id; the changeset id and the commit it holds; the script id; the runner name and what its machine has installed; the validation id; the run id.

## 0. Look before asking

Check silently, and skip later steps that are already done.

| Check | How |
|---|---|
| Assistant host | Claude Code, Cursor, Codex, or GitHub Copilot |
| Browser control | Load the browser tools first, then check. On hosts where they are deferred they exist only as names until loaded, so a plain look reports none even when a browser is connected. In Claude Code, one `ToolSearch` for `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_create_mcp`. Only an empty result means no browser. See `ui-walkthrough` section 1 |
| Operating system | `uname -s`. `Darwin` means no runner on this machine (section 10) |
| CLI | `artemis --version` is 1.1.8 or newer, and `artemis status` is authenticated to the deployment in hand |
| Runner | `artemis runner list` shows one online |
| The project, when one was given | `artemis --output-format json project list --all`, matching the id. Keep its `gitUrl`, `gitBranch` and `gitHash`. **`--all` matters**: the default is one page of 20, and a busy deployment has hundreds, so without it a real project reads as missing |
| Commands already stored | `artemis project scripts list --project <id>` |
| The code, locally | `git -C . remote get-url origin` against the project's `gitUrl` |

## 1. Where the user is starting from

Three starting points, one flow. Work out which from what arrived, not by asking.

**A project URL or id.** This is the prompt behind **Set up with local agent** on a project's overview page. `https://<deployment>/projects/<project-id>/overview` carries both facts you need: the id from the path, the deployment from the origin. Confirm the CLI is authenticated to that same deployment: a CLI logged in elsewhere reports the project as missing, which reads like a broken link rather than the wrong login, and any branch you create lands on the wrong deployment. Name the deployment the CLI is on and settle it before creating anything. Skip the welcome, ask how they want to follow along (section 3) in one line, do whatever section 5 finds missing, and go to section 7b.

**A repository but no project.** Inspect the checkout or offer to clone it, import it with `project-import`, then continue exactly as above.

**Nothing yet.** This is the prompt on the Connect your agent page, or "get started". Sections 2, 3 and 4 in order, then 5, then 7a or 7b.

Having a project does not mean the user has run anything. Assume nothing about what they know: the first time you use a word the platform owns, say what it means in one short clause. A branch is Artemis's own copy of the code; a Discovery run is the agent trying versions and measuring each one.

## 2. Welcome

For a user with nothing yet. Say four short lines:

1. Artemis uses AI to try improvements to real code and measures every attempt.
2. The measuring happens on the user's own machine, through a small program called a runner.
3. Next comes a quick setup, then either a demo or their own project.
4. Setup takes a few minutes. The Particle Life example then runs 5 versions, about 15 minutes, most of it watching results arrive.

Say once, before the first run, that runs use account credits and the balance is in the Web UI header. Nothing more: no estimate framed as a comparison, no analogy, no joke about the price. Do not turn it into a question, and do not repeat it later.

## 3. How to follow along

Ask this **before** asking what they want to do. Seeing the platform is most of what makes a first session make sense, and a user who picks the browser route should see the setup steps too, not just the run.

- Name the two routes for what they are: **computer use in the browser**, where the agent drives Chrome and the user watches each Artemis page, or **terminal only**, with links. Recommend the first, and mark it **recommended** on the option itself, not only in the surrounding prose.
- If nothing is connected, that is the normal state, not a dead end. Offer computer use anyway, and once they choose it, hand the connection step to `ui-walkthrough` section 1, which owns the wording and decides when to give up. Say "we'll use the terminal" only after that, and say what failed.

Remember the choice for the session. In the browser route, use `ui-walkthrough` to show the page named at each step below, and tell it this is a **first-run demo** so it uses its watchable pacing. That pacing is for the first tour only; a user who comes back does not need it.

## 4. Example or own project

For a user with nothing yet. Mark the recommended choice as **recommended** on the option itself. A first-time user scanning two options should see which one we advise without reading a paragraph.

Recommend the example plainly, and say why:

"I'd suggest starting with our demo project, Particle Life (recommended). It is a small C++ simulation that is deliberately slow, so you can watch a real optimisation from start to finish in about 15 minutes and see what Artemis actually produces before pointing it at your own code. Would you like to do that, or go straight to your own project?"

- Example: section 5, then section 7a.
- Their own project: ask one question, because it decides everything after it: where does the code live, repository URL and branch, and can Artemis reach it? Then section 5, `project-import`, and section 7b. Do not ask the questions 7b is about to ask.

If they are undecided, recommend the example again once and move on. Someone who has never seen a Discovery run has no way to judge the settings their own project would need.

## 5. Setup

Hand each missing item to its skill. Say plainly when a step is the user's, and wait.

| Item | Skill | Human part | Page |
|---|---|---|---|
| CLI installed and authenticated | `cli-setup` | Creates an API key and enters it in their own terminal | API keys |
| Git access | `project-import` | Connects a Git provider if the account has none | Git |
| Runner on this machine | `runner-setup` | Agrees to start a long-lived process | Runners, once online |

Reuse a runner that is online **and on this machine**; install one only if there is none. Whichever runner this step starts or finds is the one every later step uses. Pass it to `discovery-start` rather than asking the user to choose.

## 6. Rules for this flow

- **Never ask the user to choose run settings.** Not the model, the version budget, the number of measurements, the target files, or the task wording. Fix them here and state what you are using. Downstream skills may require these values; supply them from this file rather than passing the question on.
- **Announce, do not ask,** for anything long-lived or external: starting a runner, creating a project, creating a branch, starting a run. Say what you are about to do, then do it, and keep going. A readiness report is something you say on the way past, not a gate you wait behind.
- **The user's credentials are theirs.** `cli-setup` owns the login order and the exact message. Never read, type, or handle a key. Never ask them to paste a key, token or password into the chat, and never put one on a command line.
- **Stop cleanly rather than inventing.** If there is nothing measurable, say so; do not fabricate a metric to satisfy the last step.

## 7a. The Particle Life example

| Stage | Skill | Page | Explain |
|---|---|---|---|
| Import `https://github.com/turintech/particle-life`, branch `main`, named `Particle Life` | `project-import` | Project | A project is a repository pinned at a commit |
| Validation script from the inputs below | `repo-command-setup` | Project | Build, test and benchmark are stored once and reused. **Skip its verification pass for the demo**: these commands are known good, and the run measures them anyway. Do not ask the user whether to verify, either way |
| Start: 5 versions, model `gpt-5.6-sol`, three measurements per version | `discovery-start` | Discover, then the run | The original code is measured first, and each version is measured three times so the charts show a range instead of a single point |
| Watch | `discovery-inspect` | Project overview, then the run, then its Experiments tab | Experiments are ideas; versions are attempts |
| Result | `discovery-inspect` | Metrics, then the winning version, then its code change | Read the chart to find the winner, then look at the code that produced it |

The user already chose the demo, and that was the decision. Import, script, run, watch, result, in one continuous pass.

Check the account has credits before starting the run. There is no CLI command for the balance: in the browser route read the Web UI header, which is already open, and in the terminal route ask the user to glance at it once. An account with no credits fails the run in a way that looks like a platform fault, which is a poor first impression and easy to prevent.

Particle Life inputs:

- compile: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel`
- test: `ctest --test-dir build --output-on-failure`
- benchmark: `python3 tools/benchmark.py --no-visualize`
- target files: `--target-files src/simulation.cpp --target-files src/simulation.hpp`
- task: `Maximize simulation_fps without changing simulation behavior or weakening the correctness tests.`
- measurement: `--eval-mode fixed --eval-runs 3`
- scoring: `--llm-metrics=false`
- model: `gpt-5.6-sol`
- runner: the one section 5 started or found

The model is pinned on purpose. The win this demo exists to show is a spatial grid replacing the all-pairs loop, and finding it is model-dependent. Do not substitute the catalogue default by choice: that turns the demo into a coin flip and leaves a first-time user looking at a "Best" badge on a fraction of a percent. **Catalogues differ between deployments, so check first.** If `artemis model list` does not offer `gpt-5.6-sol` here, fall back to the catalogue default, say in one line that you have done so, and continue. Never fail the demo over a missing model.

LLM-judged metrics are off on purpose. The point of a first run is the measured number, `simulation_fps`, and a judged score sitting beside it invites the reader to treat an opinion as a measurement.

Three measurements per version is deliberate here. One measurement gives a single number with no sense of how much it wobbles; three give the range the charts are built on. Particle Life measures in about three seconds, so this adds roughly two minutes to the demo. It is not a default to copy onto a slow benchmark without doing that arithmetic first.

### Watching the run in the browser

The run is the part worth seeing, so follow it on screen rather than reporting it from the terminal. Stand on the page before each command runs, so the platform changes in front of the user: Projects before `project import`, the project overview before `discovery create`. `ui-walkthrough`'s *Arrive before the change, never after* owns the rule.

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

## 7b. A project of their own

This mirrors what the Web UI's setup flow does by hand: an Artemis branch, commands that produce a number, a machine, a measured run, and a Discovery started from that branch.

### Settle which code you are looking at

The prompt arrives in whatever directory the user's agent happens to be running in, which is not always the project's repository. If the origin remote does not match the project's `gitUrl`, say so and ask which checkout to work in rather than quietly describing an unrelated repo. If there is no checkout at all, the flow still works, because every command runs on the runner, but say that writing a benchmark without the code in front of you is slower and offer to clone it first.

The project record carries a `gitHash`, but a new changeset is created from the **current head of the tracked branch**, which is often newer. Read the commit that actually went in with `artemis changeset versions <changeset-id> --project <id>` and tell the user that one, rather than repeating the project's `gitHash` or assuming their local checkout matches.

### What "better" means here

Particle Life ships a benchmark. A real repository usually does not, and Discovery cannot optimise what nobody measures.

1. **Read the repository first:** build files, CI config, test layout, existing scripts, README. Most projects answer this themselves.
2. **Then ask, once,** only what the code cannot tell you: what "better" means for them, which command represents it, and roughly how long it takes. One round, not an interview.
3. If the honest answer is that nothing worth measuring exists yet, say so and stop. That is a useful result.

### The seven steps

Each step has an owning skill; use it rather than improvising.

| Step | Skill | Command |
|---|---|---|
| 1. CLI installed and authenticated | `cli-setup` | `artemis status`, then return here |
| 2. An Artemis branch over the current code | this skill | `artemis changeset create --project <id> --name <name>` |
| 3. A runner that can build this project | `runner-setup` | Reuse one that is online **and on this machine**; install one only if there is none |
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

### Before step 4, ask the runner what it has

An online runner is not the same as a runner that can build this project. Its environment is whatever shell started it, which is rarely the user's. Find out before writing commands that assume a toolchain:

```bash
artemis project scripts create --project "<project-id>" --name "toolchain-probe" \
  --setup-cmd "python3 --version; node --version; cargo --version; which uv poetry cmake" --measure none
artemis changeset validate "<changeset-id>" --project "<project-id>" --version original \
  --script "<probe-script-id>" --runner "<runner-name>" --wait
artemis changeset validation logs "<validation-id>" --project "<project-id>"
```

Name the tools this repository actually needs. A probe costs seconds and saves authoring a benchmark that cannot run. If the runner is missing what the project needs, say exactly which tool is missing on which machine, and let the user choose between installing it there and using a different machine. Do not quietly rewrite the project's commands to avoid the missing tool.

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

First check `artemis discovery list --project <id> --all`. If a run is queued, running, or awaiting approval, give its link and hand over to `discovery-inspect`; do not create another.

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

## 8. Showing it

In the browser route, hand each step to `ui-walkthrough` and follow its *Arrive before the change, never after*: the Projects list before an import, the project page before the branch appears, the branch before the run, the run's Experiments tab while versions are generated. The demo's own choreography is in section 7a.

In the terminal route, give a link to the project and name the page to open.

## 9. Human-only steps

| Step | Agent's job |
|---|---|
| Log in and create an API key | `cli-setup` owns the order and the exact message. The invariant: the key is the last thing the user copies, so nothing overwrites it on their clipboard. Say plainly that this step is theirs, and wait |
| Connect a Git provider | Take them to the page |
| Start the runner | Say what you are starting, start it in the background, and give the stop command |

## 10. When it cannot continue

| Situation | Do |
|---|---|
| The browser route fails | Continue in the terminal with links |
| The CLI is missing, unauthenticated, or older than 1.1.8 | `cli-setup`, then return to where you were |
| The project URL's deployment is not the one the CLI is logged into | Say both, and settle it before creating anything. Work created on the wrong deployment is invisible to the user |
| `uname -s` reports `Darwin` | There is no macOS runner build, so this Mac cannot host one. Say so before recommending anything, and use a runner on another machine |
| No runner, and the user does not want one | Say plainly that nothing can be measured without a machine, and stop. Do not start a run |
| The runner is online but lacks the toolchain | Name the missing tool and the machine. Installing it is the user's call, not a reason to change what the project measures |
| The benchmark produces no numbers | Fix the script and re-run. Never start Discovery on an unmeasured branch |
| Nothing worth measuring in this project | Say so and stop |
| A run fails within seconds with no baseline | `discovery-inspect`, checking the project's Git access first |
| A skill named here is not installed | Say which one is missing, then do that step with the commands in this file. Do not invent a different route |
| The user wants to stop | Summarise what exists, with ids, so this skill can resume from the first missing step |

## 11. Close

Report what now exists: the project, the branch, the commands, the runner, the measured baseline with its numbers, and the Discovery run with a link. For the demo, report the original and best measured values. Then suggest three next steps: steer the run (`discovery-steer`), chart the results (`discovery-visualize`), or try their own project.

Two things a first-time user does not know, and should hear once:

- **The run does not depend on this session.** It continues on the platform if the terminal is closed, and the Web UI shows it either way. Say this while the run is going, not at the end, so nobody sits guarding a terminal they are afraid to close.
- **The runner is still running.** Give the stop command again at the end, and say it can stay up for the next run.

## Checklist

- [ ] State checked before asking anything, and the starting point taken from what arrived
- [ ] Browser route offered first, and only when possible
- [ ] Example recommended to anyone with nothing yet
- [ ] Every human-only step named as the user's
- [ ] Each step handed to its owning skill
- [ ] For a project: branch created and its changeset id captured, commands verified by running them, metric values seen in the validation logs
- [ ] Discovery started from the branch, with settings fixed rather than asked
- [ ] Result reported with measured numbers and links, and the runner's stop command given
