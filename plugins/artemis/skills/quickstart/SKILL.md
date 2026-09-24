---
name: quickstart
description: Take a user to a first measured Artemis result from wherever they are starting, whether a machine with nothing installed, a repository that is not yet a project, or an existing project URL or id. Works in the terminal by default, offers to show each step in the browser instead, and recommends the Particle Life example to anyone who has not run Artemis before. Use when the user pasted either Artemis Quickstart prompt, asks to get started with or try Artemis, gives a project URL or id, or asks for a project to be set up and measured.
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

Never redo a step that is done. Check the state first, start at the first thing missing, and hand each step to the skill that owns it. Do not re-import a project that exists, start a second runner on a machine that has one, replace commands that already produce a number, or start another Discovery when one is queued or running.

Carry these between skills so nothing is asked twice: deployment and whether the CLI is authenticated to it; the CLI download directory, when the prompt gave one, for `cli-setup`; repository URL and branch; project id; changeset id and the commit it holds; script id; runner name and what its machine has installed; validation id; run id.

## 0. Look before asking

Check silently, and skip later steps that are already done.

| Check | How |
|---|---|
| Assistant host | Claude Code, Cursor, Codex, or GitHub Copilot |
| Browser control | Load the browser tools before looking; deferred tools report none until loaded. `ui-walkthrough` section 1 has the exact call |
| Operating system | `uname -s`, for `runner-setup`'s platform check |
| CLI | `artemis --version` meets the skills' minimum (`metadata.artemis-cli-min`), and `artemis status` is authenticated to the deployment in hand |
| Runner | `artemis runner list` shows one online |
| The project, when one was given | `artemis --output-format json project list --all`, matching the id. Keep its `gitUrl`, `gitBranch` and `gitHash`. **`--all` matters**: the default is one page of 20, so on a busy deployment a real project reads as missing without it |
| Commands already stored | `artemis project scripts list --project <id>` |
| The code, locally | `git -C . remote get-url origin` against the project's `gitUrl` |

## 1. Where the user is starting from

Three starting points, one flow. Work out which from what arrived, not by asking.

**A project URL or id.** This is the prompt behind **Set up with local agent** on a project's overview page. `https://<deployment>/projects/<project-id>/overview` carries the id in the path and the deployment in the origin. Confirm the CLI is authenticated to that deployment: a CLI logged in elsewhere reports the project as missing, which reads like a broken link, and any branch you create lands on the wrong deployment. Skip the welcome, ask how they want to follow along (section 3) in one line, do whatever section 5 finds missing, then 7b and section 7.

**A repository but no project.** Inspect the checkout or offer to clone it, import it with `project-import`, then continue as above.

**Nothing yet.** This is the prompt on the Connect your agent page, or "get started". Sections 2, 3 and 4 in order, then 5, then section 7.

Having a project does not mean the user has run anything. The first time you use a word the platform owns, say what it means in one short clause: a branch is Artemis's own copy of the code; a Discovery run is the agent trying versions and measuring each one.

## 2. Welcome

For a user with nothing yet. Say four short lines:

1. Artemis uses AI to try improvements to real code and measures every attempt.
2. The measuring happens on the user's own machine, through a small program called a runner.
3. Next comes a quick setup, then either a demo or their own project.
4. Setup takes a few minutes. The Particle Life example then runs 5 versions, about 15 minutes, most of it watching results arrive.

Say once, before the first run, that runs use account credits and the balance is in the Web UI header. Nothing more: no comparison, no analogy, no question, and do not repeat it.

## 3. Two questions, asked together

Ask both in one short message, straight after the welcome. Ask them even when the prompt says not to ask the user to choose settings: they are choices about the session, not run settings, and they are the only questions before the run.

1. **What to start with.** "I'd suggest our demo project, Particle Life (recommended): a small C++ simulation that is deliberately slow, so you can watch a real optimisation end to end in about 15 minutes before pointing Artemis at your own code. Or we can go straight to your own project." Mark the demo **recommended** on the option itself.
2. **How to follow along.** Offer two options with exactly these labels: **Terminal, with links (recommended)**, where you work in the terminal and give a link to each Artemis page as something appears on it; and **Terminal with computer use in your browser**, where you also drive Chrome so the user watches each page change, which needs the Claude browser extension connected to this session. The terminal alone is the default; recommend it even when a browser is already connected.

For a project URL, skip the first question and ask the second in one line.

If they choose the browser, hand the connection step to `ui-walkthrough` section 1 and tell it the browser is **optional**, so it makes one request and no more. If that does not connect, say so in one line and carry on in the terminal; they can switch later. In the browser route, `ui-walkthrough` shows the page named at each step; tell it this is a **first-run demo** so it uses its watchable pacing.

If they are undecided about the demo, recommend it again once and move on.

## 4. Demo or own project

Both go through the same seven steps (section 7). Only the starting point differs:

- **The demo:** `project-import` imports `https://github.com/turintech/particle-life`, branch `main`, named `Particle Life`, then section 7 with the inputs fixed in 7a.
- **Their own project:** ask one question, because it decides everything after it: where does the code live, repository URL and branch, and can Artemis reach it? Then `project-import`, then 7b, then section 7.

## 5. Setup

Hand each missing item to its skill. Say plainly when a step is the user's, and wait.

| Item | Skill | Human part | Page |
|---|---|---|---|
| CLI installed and authenticated | `cli-setup` | Creates an API key and enters it in their own terminal | API keys |
| Git access | `project-import` | Connects a Git provider if the account has none | Git |
| Runner on this machine | `runner-setup` | Agrees to start a long-lived process | Runners, once online |

`runner-setup` decides whether a runner online can be reused (only one on this machine). Whichever runner this step starts or finds is the one every later step uses; pass it on rather than asking the user to choose.

## 6. Rules for this flow

- **Never ask the user to choose run settings.** Not the model, the version budget, the number of measurements, the target files, or the task wording. Fix them here and state what you are using. Downstream skills may require these values; supply them from this file.
- **Announce, do not ask,** for anything long-lived or external: starting a runner, creating a project or branch, starting a run. Say what you are about to do, do it, and keep going. A readiness report is said on the way past, not waited behind.
- **The user's credentials are theirs.** `cli-setup` owns the login order and the exact message. Never read, type, or handle a key, never ask for one in chat, and never put one on a command line.
- **Stop cleanly rather than inventing.** If there is nothing measurable, say so; do not fabricate a metric to satisfy the last step.

## 7. The seven steps

This mirrors what the Web UI's setup flow does by hand: an Artemis branch, commands that produce a number, a machine, a measured run, and a Discovery started from that branch. The demo and a user's own project both follow it.

| Step | Skill | Command | For the demo |
|---|---|---|---|
| 1. CLI installed and authenticated | `cli-setup` | `artemis status`, then return here | Same |
| 2. An Artemis branch over the current code | this skill | `artemis changeset create --project <id> --name <name>` | Same |
| 3. A runner that can build this project | `runner-setup` | Reuse or start one, per `runner-setup` | Same |
| 4. Commands that produce a number | `repo-command-setup` | `artemis project scripts create ...`; pass it the changeset and runner from steps 2 and 3 so it validates on them instead of creating its own | Commands fixed in 7a. No toolchain probe or authoring, and tell `repo-command-setup` to skip its own verification: step 5 is the verification |
| 5. Run them on the branch | this skill | `artemis changeset validate <changeset-id> --project <id> --version original --runner <name> --wait` | Same, about a minute |
| 6. Confirm metrics exist | this skill | `artemis changeset validation get`, then `changeset validation logs` for the values | Same: `simulation_fps` near 32 |
| 7. Discovery from that branch | `discovery-start` | `artemis discovery create --source-changeset <changeset-id> ...` | Settings and target files from 7a |

### Step 2, the branch

```bash
artemis --output-format json changeset create --project "<project-id>" --name "artemis/measure"
```

A new changeset holds one version: the project's code as it is now. Capture its id; steps 5 and 7 need it. The Web UI calls this a branch and names it `artemis/measure`; keep that name unless asked otherwise.

The project record carries a `gitHash`, but a new changeset is created from the **current head of the tracked branch**, which is often newer. Read the commit that went in with `artemis changeset versions <changeset-id> --project <id>` and report that one.


### Before step 4, ask the runner what it has

Own projects only. An online runner is not a runner that can build this project. Its environment is whatever shell started it. Probe before writing commands that assume a toolchain:

```bash
artemis project scripts create --project "<project-id>" --name "toolchain-probe" \
  --setup-cmd "python3 --version; node --version; cargo --version; which uv poetry cmake" --measure none
artemis changeset validate "<changeset-id>" --project "<project-id>" --version original \
  --script "<probe-script-id>" --runner "<runner-name>" --wait
artemis changeset validation logs "<validation-id>" --project "<project-id>"
```

Name the tools this repository actually needs. If one is missing, say which tool on which machine, and let the user choose between installing it there and using another machine. Do not rewrite the project's commands to dodge it.

### Step 5, the measured run

```bash
artemis changeset validate "<changeset-id>" --project "<project-id>" --version original \
  --script "<script-id>" --runner "<runner-name>" --wait
```

`--project` and `--runner` are required. `--wait` gives up after 20 minutes and exits 6, so pass `--timeout` for a slower benchmark, and say how long you expect it to take. Run it on the runner, through the platform, never locally: a local run proves nothing about the machine Discovery will use.

This is the same primitive Discovery uses for every version, so a pass here means Discovery can run, and the user has a real number before credits are spent. The run measures the same code again as its own baseline; expect the two numbers to agree, and say so if they do not, because that is evidence of a noisy benchmark.

### Step 6, the numbers

```bash
artemis --output-format json changeset validation get "<validation-id>" --project "<project-id>"
artemis changeset validation logs "<validation-id>" --project "<project-id>"
```

`validation get` does not show the benchmark's metrics; the values are in `validation logs` (`repo-command-setup` §5b says what to look for). If the benchmark passed but wrote no metrics, fix the script with `repo-command-setup` and run it again before going near Discovery.

Report the measured value in the repository's own units, never the runtime of the benchmark command.

### Step 7, the run

First check `artemis discovery list --project <id> --all`. If a run is queued, running, or awaiting approval, give its link and hand over to `discovery-inspect`; do not create another.

Settings, so the user is never asked: 5 versions, `--eval-mode fixed --eval-runs 3`, `--llm-metrics=false`, and the model `gpt-5.6-terra`. This is the one place the model is named; change it here. **`--model` is required**; the API has no default. If the catalogue lacks this model, use the catalogue default, say which in one line, and continue.

```bash
artemis discovery create --project "<project-id>" --source-changeset "<changeset-id>" \
  --runner "<runner-name>" --script "<script-id>" --model "<the model above>" \
  --task "<the user's goal, in their words>" \
  --versions 5 --eval-mode fixed --eval-runs 3 --llm-metrics=false
```

Add `--target-files <path>` (repeatable) only when the repository made it obvious which files carry the work; a wrong guess hides the code that matters. `--source-changeset` copies the measured branch into the run's baseline, so Discovery starts from the code and numbers the user just watched.

Then follow the run with `discovery-inspect`: experiments as they arrive, then the result.

## 7a. The demo's fixed inputs

The user already chose the demo; that was the decision. Go through section 7 in one pass with these inputs:

- compile: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel`
- test: `ctest --test-dir build --output-on-failure`
- benchmark: `python3 tools/benchmark.py --no-visualize`
- target files: `--target-files src/simulation.cpp --target-files src/simulation.hpp`
- task: `Maximize simulation_fps without changing simulation behavior or weakening the correctness tests.`
- measurement: `--eval-mode fixed --eval-runs 3`
- scoring: `--llm-metrics=false`
- model: the one named in step 7
- runner: the one section 5 started or found

Why these are fixed. The model is pinned because the win this demo exists to show, a spatial grid replacing the all-pairs loop, is model-dependent; the catalogue default turns it into a coin flip. LLM-judged metrics are off because a judged score beside the measured `simulation_fps` invites the reader to treat an opinion as a measurement. Three measurements give the range the charts are built on; Particle Life measures in about three seconds, so this costs two minutes here and is not a default to copy onto a slow benchmark.

Do not check or ask about credits before the run: new accounts have them. If the run fails with a 402 or `INSUFFICIENT_BALANCE`, that is the account's credit, not a platform fault; say so and point to the balance in the Web UI header.

### Showing the result

End on the code, not on a number:

1. The run's **Metrics** tab: which version won and by how much.
2. That version's **code change**: the actual diff Artemis wrote, and the thing worth retelling afterwards.

Say which numbers are measured and which are AI-judged, and that "BEST" is a blended score rather than always the fastest.

## 7b. Before section 7 on their own code

### Settle which code you are looking at

The prompt arrives in whatever directory the agent happens to be running in. If the origin remote does not match the project's `gitUrl`, say so and ask which checkout to work in rather than describing an unrelated repo. With no checkout at all the flow still works, because every command runs on the runner, but say that writing a benchmark without the code in front of you is slower and offer to clone it first.

### What "better" means here

Particle Life ships a benchmark. A real repository usually does not, and Discovery cannot optimise what nobody measures.

1. **Read the repository first:** build files, CI config, test layout, existing scripts, README. Most projects answer this themselves.
2. **Then ask, once,** only what the code cannot tell you: what "better" means, which command represents it, and roughly how long it takes.
3. If nothing worth measuring exists yet, say so and stop. That is a useful result.

## 8. Where to look

The user should always know where the thing that just happened is. Each time something appears in Artemis, say it in one or two plain sentences: what happened, the link, and what they will see there. Do this in both routes; in the browser route the page is already open, so say what to look at on it.

| Moment | Link | What they will see |
|---|---|---|
| Runner online | Settings, then **Runners** | Their machine listed as online |
| Project imported | `<deployment-base-url>/projects/<project-id>` | The project's overview page, under the name you gave it |
| Branch created | The project, then **Branches** | A branch named `artemis/measure` |
| Measured run finished | The branch's **Script runs** | One run, passed, with the measured number (for the demo, `simulation_fps` near 32) |
| Discovery started | The project, then **Discover**, then the run | The run, with experiments filling in as the agent plans them |
| Result | The run's **Metrics** tab, then the winning version | Which version won, and its code change |

For example: "Your project is in Artemis: [Open project](<link>). You'll see the Particle Life overview; nothing has run yet." Link the project and name the page for anything deeper, because run and branch paths differ between deployments. Keep it to what is on screen; the user does not need the command behind it.

In the browser route, hand each step to `ui-walkthrough` and follow its *Arrive before the change, never after* table, then end on the Metrics tab and the winning version's code change.

## 9. Human-only steps

| Step | Agent's job |
|---|---|
| Log in and create an API key | `cli-setup` owns the order and the message. The key is the last thing the user copies, so nothing overwrites it on their clipboard. Say the step is theirs, and wait |
| Connect a Git provider | Take them to the page |
| Start the runner | Say what you are starting, start it in the background, and give the stop command |

## 10. When it cannot continue

| Situation | Do |
|---|---|
| The browser route fails | Continue in the terminal with links |
| The run fails before any version exists, and its narration shows a model error (`Invalid request`, `ERR_LLM_GATEWAY`, `UnsupportedParamsError`, `tool_choice`) | Start one fresh run from the same branch with the catalogue default, or with the step 7 model if a different one had been used. Say in one line which model failed and which you are using. Once only, and never for a build, test or benchmark failure: those are the code's, and a new model will not fix them |
| The CLI is missing, unauthenticated, or older than the skills' minimum | `cli-setup`, then return to where you were |
| The project URL's deployment is not the one the CLI is logged into | Say both, and settle it before creating anything |
| `runner-setup` finds no runner build for this platform | Say so before recommending anything, and use a runner on another machine |
| No runner, and the user does not want one | Say that nothing can be measured without a machine, and stop. Do not start a run |
| The runner is online but lacks the toolchain | Name the missing tool and the machine. Installing it is the user's call |
| The benchmark produces no numbers | Fix the script and re-run. Never start Discovery on an unmeasured branch |
| Nothing worth measuring in this project | Say so and stop |
| A run fails within seconds with no baseline | `discovery-inspect`, checking the project's Git access first |
| A skill named here is not installed | Say which, then do that step with the commands in this file |
| The user wants to stop | Give the section 11 report, with ids, so this skill can resume from the first missing step |

## 11. Close

End with a short readiness report, whether the session finished or stopped early. Every line comes from a check you ran, not from memory:

- **Agent and skills:** the host, and that the Artemis skills are installed.
- **CLI:** version, deployment, the account `artemis status` reports, and whether it was already there, updated or newly installed.
- **Runner:** its name and machine, and whether it was reused, newly started, or skipped and why.
- **Work:** the project, the branch, the commands, the measured baseline with its numbers, and the Discovery run with a link. For the demo, the original and best measured values.
- **Still yours to do:** anything left for the user, such as creating a key or connecting Git, or "nothing".

Then suggest three next steps: steer the run (`discovery-steer`), chart the results (`discovery-visualize`), or try their own project.

Say two things once: the run does not depend on this session and continues on the platform if the terminal is closed (say this while the run is going, so nobody guards a terminal they are afraid to close); and the runner is still running, with its stop command, and can stay up for the next run.

## Checklist

- [ ] State checked before asking anything, and the starting point taken from what arrived
- [ ] Both opening questions asked together: demo (recommended) or own project, and terminal (recommended) or browser
- [ ] Example recommended to anyone with nothing yet
- [ ] Every human-only step named as the user's
- [ ] Each step handed to its owning skill
- [ ] Changeset id captured, commands run on the branch, metric values seen in the validation logs, for the demo as well as a project
- [ ] A link and what they will see given each time something appeared in Artemis (section 8)
- [ ] Discovery started from the branch, with settings fixed rather than asked
- [ ] Readiness report given (section 11): CLI, runner, work, and what is still the user's, each from a check that ran
- [ ] Result reported with measured numbers and links, and the runner's stop command given
