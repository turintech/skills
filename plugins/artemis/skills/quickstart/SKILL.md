---
name: quickstart
description: Take a user to a first measured Artemis result from wherever they are starting, whether a machine with nothing installed, a returning user with a new project, a repository that is not yet a project, or an existing project URL or id. Works in the terminal by default, offers to show each step in the browser instead, and recommends the Particle Life example to anyone who has not run Artemis before. Use when the user pasted either Artemis Quickstart prompt, asks to get started with or try Artemis, gives a project URL or id, or asks for a project to be set up and measured.
compatibility: Requires Artemis CLI 1.1.8+ and Artemis Platform 3.1.0+. The browser route needs a browser-control tool such as Claude in Chrome.
metadata:
  artemis-cli-min: "1.1.8"
  artemis-platform-min: "3.1.0"
---

# Quickstart

## At a glance

- **Problem:** One skill for the whole first mile: from a pasted prompt to a setup the user has watched, a measured baseline, and a first Discovery run, resuming at whichever step is missing.
- **Must be available:** A coding assistant with the Artemis skills installed, network access, and a user who can create an API key in the Artemis Web UI. A repository or project by the time repository setup begins.
- **Use / don't use:** Use for both copyable prompts, for "get started" and "try Artemis", for a returning user setting up a new project, and for any request carrying a project URL or id. Don't use it when the user names a specific lower-level task and its inputs; the `artemis` router sends those to the owning skill.
- **Next skill:** This skill runs almost nothing itself. It hands each step to `cli-setup`, `project-import`, `runner-setup`, `repo-command-setup`, `discovery-start` and `discovery-inspect`, and in the browser route to `cli-follow-along`. The two commands it owns are `changeset create` and `changeset validate`.

## Requirements

- The deployment base URL, from the prompt, a project URL, or the user.
- One of: nothing yet, a repository URL and branch, or a project URL or id.
- The user present at each human-only step (section 9).

## Operating rule: inspect, resume, delegate

Never redo a step that is done. Check the state first, start at the first thing missing, and hand each step to the skill that owns it. Do not re-import a project that exists, start a second runner on a machine that has one, replace commands that already produce a number, create a second `artemis/measure` branch, or start another Discovery when one is queued, running, or has already completed for the same request. The one exception is the demo, when the user chooses a fresh start (section 4).

Carry these between skills so nothing is asked twice: deployment and whether the CLI is authenticated to it; the CLI download directory, when the prompt gave one, for `cli-setup`; repository URL and branch; project id; changeset id and the commit it holds; script id; runner name and what its machine has installed; validation id; run id.

## 0. Look before asking

Check silently, and skip later steps that are already done.

| Check | How |
|---|---|
| Assistant host | Claude Code, Cursor, Codex, or GitHub Copilot |
| Browser control | Load the browser tools before looking; deferred tools report none until loaded. `cli-follow-along` section 1 has the exact call |
| Operating system | `uname -s`, for `runner-setup`'s platform check |
| CLI | `artemis --version` meets the skills' minimum (`metadata.artemis-cli-min`), and `artemis status` is authenticated to the deployment in hand |
| Runner | `artemis runner list` shows one online |
| Projects | `artemis --output-format json project list --all`. **`--all` matters**: the default is one page of 20. Match a given project id here and keep its `gitUrl`, `gitBranch` and `gitHash` |
| Commands already stored | `artemis project scripts list --project <id>` |
| The code, locally | `git -C . remote get-url origin` against the project's `gitUrl` |

## 1. Where the user is starting from

Four starting points, one flow. Work out which from what arrived and what section 0 found, not by asking.

**A project URL or id.** The prompt behind **Setup with a local agent** on a project's overview page. The URL carries the project id and the deployment. Confirm the CLI is signed in to that deployment before creating anything: signed in elsewhere, the project reads as missing and any branch lands on the wrong deployment. Ask the follow-along question in one line, then section 4.

**An Artemis user with a new project.** The CLI is signed in, a runner is online, and the account already has projects. They know Artemis: skip the welcome, the demo and the follow-along question (stay in the terminal unless they ask). Ask only where the code lives, unless the current directory is it, then section 4.

**A repository but no project.** Treat it like the case above when the CLI is already set up; otherwise like "nothing yet", with their repository in place of the demo.

**Nothing yet.** The prompt on the Connect your agent page, or "get started". Sections 2, 3 and 4.

The first time you use a word the platform owns, say what it means in one short clause: a branch is Artemis's own copy of the code; a Discovery run is the agent trying versions and measuring each one.

## 2. Welcome

For a user with nothing yet, as the first part of section 3. Four short lines:

1. Artemis uses AI to try improvements to real code and measures every attempt.
2. The measuring happens on the user's own machine, through a small program called a runner.
3. Next comes a quick setup, then either a demo or their own project.
4. Setup takes a few minutes. The Particle Life demo then runs 5 versions, about 15 minutes, most of it watching results arrive.

Say once, before the first run, that runs use account credits and the balance is in the Web UI header. Nothing more, and do not repeat it.

## 3. Two questions, asked together

First write the section 2 welcome as reply text: the question box shows no text of its own, and narration in your reasoning is not seen. Then ask both questions in one question box, in the same turn. Ask them even when the prompt says not to ask about settings: they are about the session, not the run, and they are the only questions before it, apart from the fresh-or-continue question in section 4.

1. **Start with:** **Particle Life demo (recommended)**, a deliberately slow C++ simulation that shows a real optimisation end to end in about 15 minutes, or **your own project**.
2. **Follow along in:** **Terminal, with links (recommended)**, or **Terminal with computer use in your browser**, which also drives Chrome so they watch each page change and needs the Claude browser extension. Recommend the terminal even when a browser is connected.

If they choose the browser, hand the connection to `cli-follow-along` section 1 and tell it the browser is **optional** and this is a **first-run demo**. If it does not connect after its one request, say so in one line and carry on in the terminal.

If they are undecided about the demo, recommend it again once and move on.

## 4. Show the plan

Your first action after the two answers is the plan, before any other tool call. Returning users get it once their starting point is clear.

Put it in the host's task list (Claude Code's task list, Cursor's todos, Codex's plan tool): one item per step, the finished ones already done. It stays on screen and ticks as the session goes. When a step finishes, mark it done and add its link from the "Tell them" columns to the item. Only when the host has no task list, send it as a numbered message instead, and again after setup and after the measurement.

Only the steps this user needs; say which are theirs and roughly how long the long ones take. At the close (section 11), send it as a numbered message, one step per line, each ticked line with its link. For a brand-new user choosing the demo:

```text
Here's the plan:
1. ✓ Artemis skills, already installed
2. ○ Install the Artemis CLI
3. ○ Sign in: you'll create an API key
4. ○ Start a runner on this machine
5. ○ Import Particle Life
6. ○ Measure it on a branch, about a minute
7. ○ Start a Discovery run, about 15 minutes
```

At the close each ticked line ends with its link, for example `5. ✓ Particle Life imported: <project link>`.

Then the starting point decides what comes before section 7:

- **The demo:** `project-import` imports `https://github.com/turintech/particle-life`, branch `main`, named `Particle Life`, then section 7 with 7a's inputs. Before importing, check for an existing project with that `gitUrl`. If there is one, ask one question, naming the newest such project, when it was created, and how many there are:
  - **Start fresh (recommended):** `project-import` imports a new project, and a new Discovery run starts in step 7, about 15 minutes, using credits.
  - **Continue with it:** pass its id to `project-import`. If it has a completed run, show that result with the date it ran, then offer to steer it (`discovery-steer`) or start a fresh run from its branch.
- **Their own code:** where it lives (repository URL and branch, and can Artemis reach it), `project-import` if it is not a project yet, then 7b and section 7.
- **A project URL:** 7b, then section 7.

## 5. Setup

Hand each missing item to its skill. Say plainly when a step is the user's, and wait.

| Item | Skill | Human part | Tell them (section 8) |
|---|---|---|---|
| CLI installed and signed in | `cli-setup` | Creates an API key and enters it in their own terminal | |
| Git access | `project-import` | Connects a Git provider if the account has none | |
| Runner on this machine | `runner-setup` | Nothing: announce it, start it, give the stop command | Settings, then **Runners**: their machine, online |
| Project imported or reused | `project-import` | Nothing | `<deployment-base-url>/projects/<project-id>`: the project's overview page |

Whichever runner `runner-setup` reuses or starts is the one every later step uses; pass it on rather than asking.

## 6. Rules for this flow

- **Never ask the user to choose run settings.** Not the model, the version budget, the number of measurements, the target files, or the task wording. They are fixed in step 7 and 7a; pass them to the owning skills.
- **Announce, do not ask,** for anything long-lived or external: starting a runner, creating a project or branch, starting a run.
- **The user's credentials are theirs.** `cli-setup` owns the login message. Never read, type or handle a key, never ask for one in chat, and never put one on a command line.
- **Stop cleanly rather than inventing.** If nothing is measurable, say so; never fabricate a metric.

## 7. The seven steps

What the Web UI's setup flow does by hand: an Artemis branch, commands that produce a number, a machine, a measured run, and a Discovery started from that branch. The demo and a user's own project both follow it. Each owning skill has the commands; this section says what to pass it.

| Step | Owner | What happens | For the demo | Tell them (section 8) |
|---|---|---|---|---|
| 1. CLI signed in | `cli-setup` | Already done in section 5 | Same | |
| 2. A branch over the current code | this skill | `changeset create`, below | Same | The project, then **Branches**: a branch named `artemis/measure` |
| 3. A runner that can build it | `runner-setup` | Reuse or start one; for an own project, its toolchain probe | No probe | |
| 4. Commands that produce a number | `repo-command-setup` | Pass it the changeset and runner from steps 2 and 3, so it validates on them instead of making its own | Commands fixed in 7a; tell it to skip its own verification | |
| 5. A measured run on the branch | this skill | `changeset validate --wait` on the runner (`repo-command-setup` §5b) | About a minute | The branch's **Script runs**: one run, passed |
| 6. Metrics confirmed | this skill | Read the values from `changeset validation logs`, not `validation get` | `simulation_fps` near 32 | The same run, with its number |
| 7. Discovery from that branch | `discovery-start` | Pass the changeset, script, runner, task and the settings below | Settings and target files from 7a | The project, then **Discover**, then the run: experiments filling in; later its **Metrics** tab and the winning version |

A step is not finished until its "Tell them" line has been said.

**Step 2.** Reuse the newest changeset named `artemis/measure` (`changeset list --project <id>`) unless the project's code has moved on since (its `baseVersionSha` differs from the project's `gitHash`). Otherwise:

```bash
artemis --output-format json changeset create --project "<project-id>" --name "artemis/measure"
```

Capture its id. Read the commit it holds with `artemis changeset versions <changeset-id> --project <id>` and report that one, not the project's `gitHash`.

**Step 5.** Run it on the runner, never locally. When resuming, run it again: the CLI cannot list a changeset's validations, so an earlier measurement cannot be found, and it costs runner time, not credits. Say how long you expect it to take.

**Step 6.** If the benchmark passed but wrote no metrics, fix the script with `repo-command-setup` and run step 5 again before going near Discovery. Report the value in the repository's own units. If compile took more than about 5 minutes on the runner, every version pays it again: set up a build cache with `workspace-setup`, measure again, then go to step 7.

**Step 7.** If a run is queued or running, give its link and hand over to `discovery-inspect`. If one has completed and the user asked for a first run, that request is met: give its result with the link and the date it ran, never as this session's result, and offer to steer it (`discovery-steer`), start a fresh run, or set up their own project. Otherwise hand these to `discovery-start`:

- `--source-changeset` from step 2, so the run starts from the code and numbers the user just saw
- 5 versions, `--eval-mode fixed --eval-runs 3`, `--llm-metrics=false`
- model `gpt-5.6-terra`. This is the one place the model is named; change it here. If the catalogue lacks it, use the catalogue default and say so in one line
- `--target-files` only when the repository made them obvious

Then follow the run with `discovery-inspect`.

## 7a. The demo's fixed inputs

The user chose the demo; that was the decision. Go through section 7 in one pass with:

- compile: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel`
- test: `ctest --test-dir build --output-on-failure`
- benchmark: `python3 tools/benchmark.py --no-visualize`
- target files: `src/simulation.cpp`, `src/simulation.hpp`
- task: `Maximize simulation_fps without changing simulation behavior or weakening the correctness tests. The tests compare floating-point results exactly, so keep the order in which forces are added.`

The model is pinned because the win this demo shows, a spatial grid replacing the all-pairs loop, depends on it. LLM-judged metrics are off so only the measured `simulation_fps` is on show.

Do not check or ask about credits first: new accounts have them. A 402 or `INSUFFICIENT_BALANCE` is the account's credit, not a platform fault; say so and point to the balance in the Web UI header.

End on the code, not a number: the run's **Metrics** tab to show which version won and by how much, then that version's **code change**. Say which numbers are measured and which are AI-judged.

## 7b. Before section 7 on their own code

**Which code.** Skip this when the project already has a script whose measured run produces metrics. Otherwise, if the current directory's origin does not match the project's `gitUrl`, say so and ask which checkout to use, or offer to clone it: writing a benchmark without the code is slower.

**What "better" means.** Read the repository first (build files, CI, tests, scripts, README), then ask once only what the code cannot tell you: what "better" means, which command shows it, and roughly how long it takes. If nothing worth measuring exists, say so and stop; that is a useful result.

## 8. Where to look

The user should always know where the thing that just happened is. The "Tell them" columns in sections 5 and 7 say when and where; say it in one or two plain sentences: what happened, the link, and what they will see there.

For example: "Your project is in Artemis: [Open project](<link>). You'll see the Particle Life overview; nothing has run yet." Link the project and name the page for anything deeper, because paths differ between deployments. In the browser route the page is already open: say what to look at, and follow `cli-follow-along`'s *Arrive before the change* table.

## 9. Human-only steps

| Step | Agent's job |
|---|---|
| Sign in and create an API key | `cli-setup` owns the order and the message. Say the step is theirs, and wait |
| Connect a Git provider | Take them to the page |

## 10. When it cannot continue

| Situation | Do |
|---|---|
| The run fails before any version exists, with a model error in its narration (`Invalid request`, `ERR_LLM_GATEWAY`, `UnsupportedParamsError`, `tool_choice`) | Start one fresh run from the same branch with the catalogue default, or the step 7 model if another was used, and say which model failed. Once only, and never for a build, test or benchmark failure |
| The project URL's deployment is not the one the CLI is signed in to | Say both, and settle it before creating anything |
| No runner can run here, or the user does not want one | Say that nothing can be measured without a machine, and stop |
| The runner lacks the toolchain | Name the tool and the machine; installing it is the user's call |
| Nothing worth measuring | Say so and stop |
| A run fails within seconds with no baseline | `discovery-inspect` |
| A skill named here is not installed | Say which, then do that step with the commands in this file |
| The user wants to stop | Give the section 11 report, with ids, so this skill can resume |

Anything else goes to the owning skill: `cli-setup`, `runner-setup`, `repo-command-setup`, `discovery-start` or `discovery-inspect`.

## 11. Close

Show the plan again with everything ticked, then a short readiness report, whether the session finished or stopped early. Every line comes from a check you ran:

- **Agent and skills:** the host, and that the Artemis skills are installed.
- **CLI:** version, deployment, the account when the CLI shows it, and whether it was already there, updated or new.
- **Runner:** name and machine, and whether it was reused, started, or skipped and why.
- **Work:** the project, the branch, the baseline with its numbers, and the Discovery run with a link. For the demo, the original and best measured values.
- **Still yours to do:** anything left for the user, or "nothing".

Suggest three next steps: steer the run (`discovery-steer`), chart the results (`discovery-visualize`), or try their own project.

Say once, while the run is going, that it continues on the platform if the terminal is closed; and at the end, that the runner is still running, with its stop command.

## Checklist

- [ ] State checked first, and the starting point taken from what arrived
- [ ] New users: both opening questions asked together; returning users: only where the code lives
- [ ] Welcome written as text before the question box
- [ ] The plan in the host's task list before any other tool call, each item ticked with its link, and a numbered list at the close
- [ ] Demo: an existing Particle Life project found before importing, and the user asked fresh or continue
- [ ] Each step handed to its owning skill, with the ids and settings it needs
- [ ] Changeset id captured, commands run on the branch, metric values seen in the logs
- [ ] A link and what they will see each time something appeared in Artemis
- [ ] Discovery started from the branch, with settings fixed rather than asked
- [ ] Readiness report given, each line from a check that ran
