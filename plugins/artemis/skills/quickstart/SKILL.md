---
name: quickstart
description: Take a user to a first measured Artemis result from wherever they are starting, whether a machine with nothing installed, a returning user with a new project, a repository that is not yet a project, or an existing project URL or id. Works in the terminal by default, offers to show each step in the browser instead, and starts the Particle Life example by default for anyone who has not run Artemis before, or stops once the CLI and a runner are ready when the user only wants setup. Use when the user pasted either Artemis Quickstart prompt, asks to get started with or try Artemis, gives a project URL or id to set up, or asks for a project to be set up and measured.
compatibility: Requires Artemis CLI 1.1.15+ and Artemis Platform 3.1.0+. The browser route needs a browser-control tool such as Claude in Chrome.
metadata:
  artemis-cli-min: "1.1.15"
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

Never redo a step that is done. Check the state first, start at the first thing missing, and hand each step to the skill that owns it. Do not start a second runner on a machine that has one, replace commands that already produce a number, create a second `artemis/measure` branch, or start another Discovery when one is queued, running, or has already completed for the same request. A project is the user's choice: reuse it when they are continuing that work, and import a fresh one when they want to start afresh (section 4).

Carry these between skills so nothing is asked twice: deployment and whether the CLI is authenticated to it; the CLI download directory, when the prompt gave one, for `cli-setup`; repository URL and branch; project id; changeset id and the commit it holds; script id; runner name and what its machine has installed; validation id; run id.

## 0. Look before asking

Check silently, and skip later steps that are already done. A missing CLI or a folder that is not a git repository is an answer, not a failure: end each check with `|| true` so the user's first sight of Artemis is not a red error.

| Check | How |
|---|---|
| Assistant host | Claude Code, Cursor, Codex, or GitHub Copilot |
| Skills up to date | Load `cli-setup` and run its *Check versions* step 1 once, after the host is known and before the other checks, even when the CLI already works, unless the setup prompt says to use the installed skills as they are. The one check that may speak: one line before it runs, and a reload request only if it updated something, or if they were installed this session and are not loaded yet |
| Browser control | Not checked here. Only when the user asks for the browser, section 3 hands over to `cli-follow-along` section 1 |
| Operating system | `uname -s`, for `runner-setup`'s platform check |
| Demo toolchain | Unless the user brought their own code, and when the runner will run on this machine: the check below. The demo builds with CMake 3.20 or newer (`ctest --test-dir`) and a C++ compiler and benchmarks with Python 3. A missing tool is the user's to install before the runner step: name it and the command, such as `brew install cmake` or `sudo apt install cmake g++ python3` |
| CLI | `artemis --version` is at least this skill's `artemis-cli-min` (1.1.15, the highest of the Artemis skills, so neither the later steps here nor a skill the user moves on to, such as `maintain`, stops for an update). If it is older, `cli-setup` updates it now, before the runner and project checks. Then `artemis status` names the deployment in hand, and `artemis runner list` succeeds (status alone can pass with a revoked key). If they fail with `x509` or "unknown authority", follow `cli-setup`'s *Deployments with a self-signed certificate*: `ARTEMIS_SSL_CERT_FILE`, never `SSL_CERT_FILE` |
| Runner | `artemis runner list` shows one online whose name matches a local `artemis-runner start` process (`runner-setup`, *Whose runner is that?*) |
| Projects | `artemis --output-format json project list --all`. **`--all` matters**: the default is one page of 20. Match a given project id here and keep its `gitUrl`, `gitBranch` and `gitHash` |
| Commands already stored | `artemis project scripts list --project <id>` |
| The code, locally | `git -C . remote get-url origin` against the project's `gitUrl` |

The demo toolchain check:

```bash
for t in cmake ctest c++ python3; do command -v "$t" >/dev/null || echo "missing: $t"; done
if command -v cmake >/dev/null; then
  set -- $(cmake --version); v=$3; major=${v%%.*}; minor=${v#*.}; minor=${minor%%.*}
  if [ "$major" -lt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -lt 20 ]; }; then echo "too old: cmake $v, the demo needs 3.20 or newer"; fi
fi
if [ "$(uname -s)" = Darwin ] && ! xcode-select -p >/dev/null 2>&1; then echo "missing: Xcode Command Line Tools (xcode-select --install)"; fi
```

## 1. Where the user is starting from

Four starting points, one flow. Work out which from what arrived and what section 0 found, not by asking.

**A project URL or id.** The prompt behind **Setup with a local agent** on a project's overview page. The URL carries the project id and the deployment. Confirm the CLI is signed in to that deployment before creating anything: signed in elsewhere, the project reads as missing and any branch lands on the wrong deployment. Stay in the terminal unless they ask for the browser, then section 4.

**An Artemis user with a new project.** The CLI is signed in, a runner is online, and the account already has projects. They know Artemis: skip the welcome and the demo, and stay in the terminal unless they ask. Ask only where the code lives, unless the current directory is it, then section 4.

**A repository but no project.** Treat it like the case above when the CLI is already set up; otherwise like "nothing yet", with their repository in place of the demo.

**Nothing yet.** The prompt on the Connect your agent page, or "get started". Sections 2, 3 and 4.

The first time you use a word the platform owns, say what it means in one short clause: a branch is Artemis's own copy of the code; a Discovery run is the agent trying versions and measuring each one.

## 2. Welcome

For a user with nothing yet, as the first part of section 3. Four short lines:

1. Artemis uses AI to try improvements to real code and measures every attempt.
2. The measuring happens on the user's own machine, through a small program called a runner.
3. Next comes a quick setup, then the Particle Life demo, run from this session with links to each page. Say "my own code", "just set me up" or "show me in the browser" at any time to change that.
4. Setup takes a few minutes. The demo then runs 5 versions, about 15 minutes, using account credits (the balance is at the bottom of the Web UI's left sidebar).

When the request already named their own code or asked for setup only, say that in place of the demo in line 3 ("then your repository, measured on a branch" or "then stop once the CLI and a runner are ready"), and line 4 becomes just "Setup takes a few minutes." For the demo, line 4 is the welcome's only mention of credits; the §6 one-line question, when it is needed, names them again.

## 3. Defaults, stated rather than asked

Write the section 2 welcome as reply text, all four lines, then go straight on to section 4 in the same turn. Never skip it for a new user: line 4 is where they learn the demo uses credits, and the demo run's go-ahead depends on it. Do not ask before starting: the defaults are the **Particle Life demo** and the **terminal, with links**. Switch whenever the user says so:

1. **Their own project:** the "A repository but no project" path in section 1.
2. **Just set me up:** the CLI, sign-in and a runner, then stop, with no project and no run.
3. **The browser:** computer use drives Chrome so they watch each page change, and it needs the Claude browser extension.

On a switch, rewrite the plan in the task list. A switch after the demo run has started does not stop it: say it carries on in the platform, then continue with the new choice.

If they ask for the browser, load the skill and follow `cli-follow-along` section 1 for the connection, and tell it the browser is **optional** and this is a **first-run demo**. If it does not connect after its one request, say so in one line and carry on in the terminal.

## 4. Show the plan

Your first action after the welcome is the plan, before any other tool call. Returning users get it once their starting point is clear.

Put it in the host's task list (Claude Code's task list, Cursor's todos, Codex's plan tool; load the task tools first if they are deferred, as with the browser tools): one item per step, the finished ones already done. It stays on screen and ticks as the session goes. When a step finishes, mark it done and add its link from the "Tell them" columns to the item. Only when the host has no task list, send it as a numbered message instead, and again after setup and after the measurement.

Only the steps this user needs; say which are theirs and roughly how long the long ones take. At the close (section 11), send it as a numbered message, one step per line, each ticked line with its link. For a brand-new user on the demo default:

```text
Here's the plan:
1. ✓ Artemis skills, already installed
2. ○ Install the Artemis CLI
3. ○ Sign in: you'll create an API key
4. ○ Connect to GitHub: one click on the Git page, about a minute
5. ○ Start a runner on this machine
6. ○ Import Particle Life
7. ○ Measure it on a branch, about a minute
8. ○ Start a Discovery run, about 15 minutes
```

At the close each ticked line ends with its link, for example `6. ✓ Particle Life imported: <project link>`. Leave out step 4 when `artemis --output-format json key list` already shows a key whose `provider` starts with `github_` (`github_oauth_token`, `github_app`, `github_pat`), or when the user continues an existing Particle Life project. Number the remaining steps in order.

Then the starting point decides what comes before section 7:

- **The demo:** `project-import` imports `https://github.com/turintech/particle-life`, branch `main`, named `Particle Life`, then section 7 with 7a's inputs. Before importing, check for an existing project with that `gitUrl`. If there is one, ask one question, naming the newest such project, when it was created, and how many there are:
  - **Start fresh (recommended):** `project-import` imports a new project, and a new Discovery run starts in section 7's step 7, about 15 minutes, using credits.
  - **Continue with it:** pass its id to `project-import`. If it has a completed run, show that result with the date it ran, then offer to steer it (`discovery-steer`) or start a fresh run from its branch (it uses account credits).
- **Their own code:** where it lives (repository URL and branch, and can Artemis reach it). `project-import` imports it as a new project, then 7b and section 7. If projects for it already exist and the user hasn't said to continue one, don't ask: import fresh and say in one line which one exists, for example "Importing a new project; `<name>` from `<date>` already exists, say 'continue' to use it instead." If they say so before section 7's step 2, switch to that project's id and tell them the new, still-empty project can be archived. A project this session created, or one named in a section 11 report being resumed, counts as continuing: use it without importing again.
- **A project URL:** 7b, then section 7.
- **Just set me up:** the plan is steps 1, 2, 3 and 5 only (skills, CLI, sign-in, runner). Do section 5's CLI and runner items, skip Git access and the project, then go straight to section 11.

## 5. Setup

Hand each missing item to its skill. Say plainly when a step is the user's, and wait.

| Item | Skill | Human part | Tell them (section 8) |
|---|---|---|---|
| CLI installed and signed in | `cli-setup` | Creates an API key and enters it in their own terminal | |
| Git access | `project-import`, its section 3 only: keep the key UUID; the import itself waits for the plan's Import step | For the demo: clicks **Connect to GitHub** on the Git page if there is no `github_*` key (the CLI needs one even for the public demo). Own code: connects a key for the repository's git service if none can read it | `<deployment-base-url>/settings/git`; they say "done" when the GitHub section shows **Connected**, or when the access key is saved if the page has no Connect button |
| Runner on this machine | `runner-setup` | Nothing: the agent downloads it and starts it with the CLI's API key | Its name, online. Once the project exists: `<deployment-base-url>/projects/<project-id>/settings/execution` (**Runner and Scripts**) |
| Project imported or reused | `project-import` | Nothing | `<deployment-base-url>/projects/<project-id>`: the project's overview page |

Whichever runner `runner-setup` reuses or starts is the one every later step uses; pass it on rather than asking.

## 6. Rules for this flow

- **Never ask the user to choose run settings.** Not the model, the version budget, the number of Benchmark runs, the target files, or the task wording. They are fixed in section 7's step 7 and 7a; pass them to the owning skills.
- **Announce, do not ask,** for anything long-lived or external: starting a runner, creating a project or branch.
- **The demo run** is announced, not asked, only when this session sent the §2 welcome with its credits line and the user has since replied in chat (a permission prompt is not a reply) or answered the §4 fresh-or-continue question, without switching away from the demo. Otherwise, at section 7's step 7 and before handing over to `discovery-start`, ask one line and wait for a yes: "Setup is done. Start the Particle Life run now? It uses account credits." A run on the user's own code goes through `discovery-start`, which asks first.
- **The user's credentials are theirs.** `cli-setup` owns the login message. Never read, type or handle a key, never ask for one in chat, and never put one on a command line.
- **Stop cleanly rather than inventing.** If nothing is measurable, say so; never fabricate a metric.

## 7. The seven steps

What the Web UI's setup flow does by hand: an Artemis branch, commands that produce a number, a machine, a measured run, and a Discovery started from that branch. The demo and a user's own project both follow it. Each owning skill has the commands; this section says what to pass it.

| Step | Owner | What happens | For the demo | Tell them (section 8) |
|---|---|---|---|---|
| 1. CLI signed in | `cli-setup` | Already done in section 5 | Same | |
| 2. A branch over the current code | this skill | `changeset create`, below | Same | The project, then **Branches**: a branch named `artemis/measure` |
| 3. A runner that can build it | `runner-setup` | Reuse or start one; for an own project, its toolchain probe | Section 0's demo toolchain check instead | |
| 4. Commands that produce a number | `repo-command-setup` | Pass it the changeset and runner from steps 2 and 3. Its `repo-command-setup` §5b run on them is step 5; do not run it again | Commands fixed in 7a; tell it to skip its own verification | |
| 5. A measured run on the branch | this skill | `changeset validate` on the runner, post the start block (`artemis`'s *Start block*: Validation started), then wait in one bounded loop (`repo-command-setup` §5b) | About a minute | The branch's **Scripts** tab, under **Script runs**: one run, passed |
| 6. Metrics confirmed | this skill | Read the values from `changeset validation logs`, not `validation get` | `simulation_fps` near 32 | The same run, with its number |
| 7. Discovery from that branch | `discovery-start` | Pass the changeset, script, runner, task and the settings below | Settings and target files from 7a | The project, then **Discover**, then the run: experiments filling in; later the run's **Metrics** and the winning version |

A step is not finished until its "Tell them" line has been said.

**Step 2.** Reuse the newest changeset named `artemis/measure` (`changeset list --project <id> --all`) unless the project's code has moved on since (its `baseVersionSha` differs from the project's `gitHash`). Otherwise:

```bash
artemis --output-format json changeset create --project "<project-id>" --name "artemis/measure"
```

Capture its id. Read the commit it holds with `artemis changeset versions <changeset-id> --project <id>` and report that one, not the project's `gitHash`.

**Step 5.** Run it on the runner, never locally. When resuming, run it again: the CLI cannot list a changeset's validations, so an earlier measurement cannot be found, and it costs runner time, not credits. Say how long you expect it to take. Start it without `--wait` so its id is printed at once, then wait with the loop in `repo-command-setup` §5b. Wait in one shell call: 30 seconds between checks, at most 8 minutes. Give that shell call a 10-minute timeout, or run it in the background. If it is still `created` or `running` after a second loop, stop and report it with `execution-log-inspect` (a validation behind an offline runner stays `created`); never start another validation.

**Step 6.** If the benchmark passed but wrote no metrics, fix the script with `repo-command-setup` and run step 5 again before going near Discovery. Report the value in the repository's own units. If compile took more than about 5 minutes on the runner, every version pays it again: set up a build cache with `workspace-setup`, measure again, then go to step 7.

**Step 7.** If a run is queued or running, give its link and hand over to `discovery-inspect`. If one has completed and the user asked for a first run, that request is met: give its result with the link and the date it ran, never as this session's result, and offer to steer it (`discovery-steer`), start a fresh run (it uses account credits), or set up their own project. Otherwise hand these to `discovery-start`:

- `--source-changeset` from step 2, so the run starts from the code and numbers the user just saw
- 5 versions, `--eval-mode fixed --eval-runs 3`, `--llm-metrics=false`
- model `gpt-6-sol`. This is the one place the model is named; change it here. If the catalogue lacks it, pick a model from the top tier in `artemis model groups` and name it in one line
- `--target-files` only when the repository made them obvious
- for the demo, the user's go-ahead under the §6 rule (the welcome with its credits line was sent and the user replied since without switching, or they said yes to its one-line question), so `discovery-start` does not ask again. On the user's own code, pass nothing here: `discovery-start` asks

Then follow the run with `discovery-inspect`.

## 7a. The demo's fixed inputs

The demo is the default the user kept; that was the decision. Go through section 7 in one pass with:

- compile: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel`
- test: `ctest --test-dir build --output-on-failure`
- benchmark: `python3 tools/benchmark.py --no-visualize`
- target files: `src/simulation.cpp`, `src/simulation.hpp`
- task: `Maximize simulation_fps without changing simulation behavior or weakening the correctness tests. The tests compare floating-point results exactly, so keep the order in which forces are added.`

`repo-command-setup` skips its own verification for the demo, so it does not create the script; create it here, after step 3 and before step 5, unless `project scripts list --project <project-id>` already has one with these commands (a resumed session):

```bash
artemis --output-format json project scripts create --project "<project-id>" --name "Particle Life benchmark" \
  --setup-cmd "cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel" \
  --setup-cmd "ctest --test-dir build --output-on-failure" \
  --benchmark-cmd "python3 tools/benchmark.py --no-visualize" --measure none
```

Capture the script's `id`: step 5 runs it with `--script` and step 7 passes it to `discovery-start`. `--measure none` because the benchmark writes `simulation_fps` itself.

The model is pinned because the win this demo shows, a spatial grid replacing the all-pairs loop, depends on it. AI Metrics are off (`--llm-metrics=false`) so only the measured `simulation_fps` is on show.

Do not check the credit balance or ask whether the account has credits: new accounts have them. A 402 or `INSUFFICIENT_BALANCE` is the account's credit, not a platform fault; say so and point to the balance at the bottom of the Web UI's left sidebar.

End on the code, not a number: the run's **Metrics** to show which version won and by how much, then that version's **code change**. Say that `simulation_fps` was measured on their runner, and that the Composite score beside it is a roll-up of the metrics by importance, not a measurement.

## 7b. Before section 7 on their own code

**Which code.** Skip this when the project already has a script whose measured run produces metrics. Otherwise, if the current directory's origin does not match the project's `gitUrl`, say so and ask which checkout to use, or offer to clone it: writing a benchmark without the code is slower.

**What "better" means.** Read the repository first (build files, CI, tests, scripts, README), then ask once only what the code cannot tell you: what "better" means, which command shows it, and roughly how long it takes. If nothing worth measuring exists, say so and stop; that is a useful result.

## 8. Where to look

The user should always know where the thing that just happened is. The "Tell them" columns in sections 5 and 7 say when and where; say it in one or two plain sentences: what happened, the link, and what they will see there.

For example: "Your project is in Artemis: [Open project](<link>). You'll see the Particle Life overview; nothing has run yet." Link the page directly where you can (a run is `<deployment-base-url>/projects/<project-uuid>/discover/<run-id>`), and the project link if that one returns not found. In the browser route the page is already open: say what to look at, and follow `cli-follow-along`'s *Arrive before the change* table.

## 9. Human-only steps

| Step | Agent's job |
|---|---|
| Sign in and create an API key | `cli-setup` owns the order and the message. Say the step is theirs, and wait |
| Connect to GitHub (demo) or a Git provider | Give the `<deployment-base-url>/settings/git` link and wait for "done" |

## 10. When it cannot continue

| Situation | Do |
|---|---|
| The run fails before any version exists, with a model error in its narration (`Invalid request`, `ERR_LLM_GATEWAY`, `UnsupportedParamsError`, `tool_choice`) | Say which model failed and offer one fresh run from the same branch with a model from the top tier in `artemis model groups` (or section 7's step 7 model if another was used); it spends credits again, so start it only on the user's yes. Once only, and never for a build, test or benchmark failure |
| The project URL's deployment is not the one the CLI is signed in to | Say both, and settle it before creating anything |
| No runner can run here, or the user does not want one | Say that nothing can be measured without a machine, and stop |
| The user has no GitHub account, or will not connect one | Say the CLI needs a Git key even for the public demo; offer **just set me up** or their own project instead, and stop the demo |
| The runner lacks the toolchain | Name the tool and the machine; installing it is the user's call |
| Nothing worth measuring | Say so and stop |
| A run fails within seconds with no baseline | `discovery-inspect` |
| The user wants to stop | Give the section 11 report, with ids, so this skill can resume |

Anything else goes to the owning skill: `cli-setup`, `runner-setup`, `repo-command-setup`, `discovery-start` or `discovery-inspect`.

## 11. Close

Show the plan again with everything ticked, then a short readiness report, whether the session finished or stopped early. Every line comes from a check you ran:

- **Agent and skills:** the host, and that the Artemis skills are installed.
- **CLI:** version, deployment, the account when the CLI shows it, and whether it was already there, updated or new.
- **Runner:** name and machine, and whether it was reused, started, or skipped and why.
- **Work:** the project, the branch, the baseline with its numbers, and the Discovery run with a link. For the demo, the baseline and best measured values.
- **Still yours to do:** anything left for the user, or "nothing".

Suggest three next steps: steer the run (`discovery-steer`), chart the results (`discovery-visualize`), or try their own project. After **just set me up**, there is no work line; suggest the Particle Life demo or their own project instead, either of which starts from this skill again.

When they later make a change of their own, `change-validate` checks whether it is really faster.

Say once, while the run is going, that it continues on the platform if the terminal is closed; and at the end, that the runner is still running, with its stop command.

## Checklist

- [ ] State checked first, and the starting point taken from what arrived
- [ ] New users: welcome with the stated defaults and no question before setup; returning users: only where the code lives
- [ ] A switch to own code, setup only or the browser honoured whenever the user asks
- [ ] The plan in the host's task list before any other tool call, each item ticked with its link, and a numbered list at the close
- [ ] Demo: an existing Particle Life project found before importing, and the user asked fresh or continue
- [ ] Demo: a `github_*` key found, or GitHub connected, before the import
- [ ] Own code: an existing project for the repository named in one line, without a question, before importing fresh
- [ ] Just set me up: stopped after the runner, with no project imported and no run started
- [ ] Each step handed to its owning skill, with the ids and settings it needs
- [ ] Changeset id captured, commands run on the branch, metric values seen in the logs
- [ ] A link and what they will see each time something appeared in Artemis
- [ ] Discovery started from the branch, with settings fixed rather than asked
- [ ] Demo run announced only after the credits line and a user reply; otherwise the §6 one-line question asked and answered yes
- [ ] Readiness report given, each line from a check that ran
