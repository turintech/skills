---
name: quickstart
description: Take a user from any onboarding point to a first measured Artemis result, whether they have no setup, a repository that needs a benchmark, or an existing Artemis project URL or id. Use when the user asks to get started with Artemis, wants to prepare and optimize a repository, pastes a project link, or wants to resume an incomplete first run.
compatibility: Production Platform 3.0.3 quickstart requires Artemis CLI 1.0.8 and runner 5.2.1; stable CLI 1.0.9 through 1.0.11 and runner 5.3.0 are not compatible with this flow.
metadata:
  artemis-cli-min: "1.0.8"
  artemis-cli-tested: "1.0.8"
  artemis-runner-tested: "5.2.1"
  artemis-platform-min: "3.0.3"
---

# Quickstart or resume onboarding

## At a glance

- **Problem:** Finds the user's current onboarding state and completes only the missing work needed for a measured validation and first Discovery.
- **Must be available:** A repository or existing Artemis project by the time repository setup begins, network access, and the user for credentials, machine approval, or an ambiguous optimisation goal.
- **Use / don't use:** Use for first-time setup, an import-ready repository, a repository that still needs a harness, or an existing project that has not reached a first measured run. Route an explicit lower-level operation directly to its owning skill.
- **Next skill:** Delegate each missing stage to `cli-setup`, `repo-prepare-fork`, `repo-command-setup`, `project-import`, `runner-setup`, `execution-log-inspect`, `discovery-start`, or `discovery-inspect`.

## Requirements

- The deployment base URL, preferably from a project URL or starter prompt.
- One of: a local repository, a repository URL and branch, an Artemis project URL, or a bare project UUID.
- The user present for human-only credential and runner decisions.

Follow along in the terminal and with links. Give a clickable project or Discovery link as soon as its UUID is known. Do not look for a browser-control skill.

## Operating rule: inspect, resume, delegate

This is an orchestrator, not a second implementation of the downstream skills. Inspect the checkpoints below in order, preserve every verified value, and resume at the first incomplete checkpoint. Never redo a completed import, create a duplicate runner, replace working commands, or launch a second Discovery merely to follow the sequence.

Carry this state between skills:

- deployment base URL and authenticated CLI;
- repository URL, explicit branch, and branch-tip seed SHA;
- project UUID and imported `gitHash`, when present;
- literal compile, test, and benchmark commands;
- metric name, direction, and measured baseline value;
- selected runner and its verified toolchain;
- validation/changeset/process IDs;
- Discovery ID and links.

Ask only about facts that repository and platform inspection cannot answer. Announce what will happen before external writes. Obtain explicit permission before starting a long-lived runner. Never handle a user's API key, token, or password in chat.

For machine-readable CLI output, keep stdout and stderr separate and parse stdout as one complete JSON document. Progress messages are not JSON. If output is contaminated or parsing fails, run a clean read-only fetch and parse that response; do not regex-extract a JSON-looking substring from mixed output.

## 1. Classify the starting point

### Existing project

When the request contains `https://<deployment>/projects/<project-id>`:

1. Extract the deployment and project UUID from the URL.
2. Confirm `artemis status` is authenticated to that deployment.
3. Find the UUID in `artemis --output-format json project list`.
4. Record its Git URL, branch, `gitHash`, import status, stored commands, and any queued or running Discovery.
5. Use `artemis project compare <project-id>` to identify the current imported commit.

A bare UUID needs a deployment. Infer it from the authenticated CLI when unambiguous; otherwise ask for the project URL. Do not import another project. Continue at repository readiness, runner verification, validation, or Discovery—whichever is first incomplete.

Locate a local checkout whose origin matches the project's Git URL. If none is available, offer to clone the imported branch before assessing its benchmark; runner execution can validate commands, but it is not a substitute for inspecting code when commands or readiness are unknown.

### Repository but no project

Inspect the local checkout before asking questions. Record its origin, branch, clean/dirty state, branch-tip SHA, build files, CI, tests, benchmark code, results-file behavior, and README commands. If only a remote URL was supplied, offer to clone it so benchmark readiness can be assessed from code rather than guessed.

Do not assume the current directory is the repository. Compare its origin with the project or requested Git URL. If they differ, say so and ask which checkout to use.

### No repository or project

Welcome the user in four short lines:

1. Artemis uses AI to try improvements to real code and measures every attempt.
2. Measurement runs on the user's own machine through a runner.
3. Setup leads to either a guided example or their own repository.
4. The first run uses five versions; most elapsed time is waiting for measured results.

Recommend Particle Life because it is small, observable, and deliberately optimizable. Ask once whether to use it or the user's repository. Default the guided example to:

- repository: `https://github.com/turintech/particle-life`
- branch: `artemis/ready`

Honor another explicit branch, including `artemis/not-ready`; readiness must be detected, not inferred from the repository name.

After the repository path is chosen, say once that agent-backed operations such as Discovery use account credits and that the balance is in the Web UI header. Say this before the first potentially billed operation, not after one fails. Project import and empty-changeset validation are deterministic setup operations; do not introduce `target add` or another agent-backed detour into them. Do not repeat the notice.

## 2. Establish deployment and CLI state

Check silently:

- `artemis --version` reports 1.0.8 exactly;
- `artemis status` is authenticated to the intended deployment;
- `artemis changeset create --help` succeeds;
- `artemis discovery create --help` offers `--compile-cmd`, `--test-cmd`, and `--benchmark-cmd`;
- `artemis changeset validate --help` offers repeatable `--command`, plus `--version`, `--runner`, and `--wait`.

Use `cli-setup` for missing installation or authentication. Login and API-key entry are the user's steps; give instructions and wait without asking for the secret.

Version ordering is not a compatibility test: stable 1.0.9 through 1.0.11 lack the required changeset commands. If the version is not 1.0.8 or any required command or flag is missing, stop and use `cli-setup`. Do not fall back to `validation run`, install a dev build, or continue because some newer commands happen to exist.

If `discovery create --help` offers `--script` and not `--compile-cmd`, stop. That CLI targets a newer platform than this production flow. Do not pass `--script`, `--source-changeset`, `--eval-mode`, `--eval-runs`, `--llm-metrics`, or `--setup-cmd`.

## 3. Make the repository Discovery-ready

Use `repo-command-setup` to inspect, derive, author when needed, and verify the repository-owned compile, test, and benchmark contract. The repository is ready only when:

- compile catches invalid generated code;
- tests protect the behavior being optimized;
- the benchmark is headless and repeatable;
- it removes stale results and writes fresh numeric `artemis_results.json` or `.csv` at the repository root;
- the metric and direction match the optimization goal.

Read the repository first. Ask once what “better” means only when the code and documentation do not answer it. If there is no meaningful, correctness-gated measurement, say so and stop rather than inventing one.

When a harness or correctness test must be added, `repo-command-setup` owns the edit and clean-checkout verification. The committed code must be on a remote Artemis can read. If the user cannot push to that remote, use `repo-prepare-fork` after obtaining explicit permission. Import or pull the verified commit before runner validation.

### Particle Life preset

Recognize Particle Life from its Git URL or repository content, but inspect the selected commit before applying the preset.

| Item | Preset |
|---|---|
| Compile | `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel` |
| Test | `ctest --test-dir build --output-on-failure` |
| Benchmark | `python3 tools/benchmark.py --no-visualize` |
| Metric | `simulation_fps`, higher is better |
| Target files | `src/simulation.cpp`, `src/simulation.hpp` |
| Task | `Maximize simulation_fps without changing simulation behavior or weakening the correctness tests.` |

If `tools/benchmark.py` exists, inspect it and verify that the benchmark creates a fresh numeric `simulation_fps`; its path alone is not proof.

If it is absent—as on `artemis/not-ready`—do not run Discovery and do not pretend the preset command works. Use `repo-command-setup`'s harness workflow to wrap the existing headless timed binary, add `tools/benchmark.py`, verify it, push it, then import or pull that commit. Resume here afterward.

### Other repositories

Do not copy Particle Life's language, toolchain, metric, task, or target files into another repository. Derive them from that repository through `repo-command-setup`. For example, a Gradle project may need JDK 17 while an interpreted Python project may use syntax compilation without a C++ compiler.

## 4. Import or verify the project

If no project exists, use `project-import` with the exact remote, explicit branch, verified seed SHA, and suitable Git credential. When `importedStatus` is present, wait for `success` and stop on `failed`; when production omits it, use that skill's Git URL, branch, seed `gitHash`, and project inspection checks. Record the UUID and verify the imported `gitHash` matches the seed.

If a project already exists, do not re-import it. If repository code was changed to add or repair the harness, push the change, run `artemis project compare`, then `artemis project pull`. Wait until the project's `gitHash` matches the verified commit. A pre-pull changeset remains pinned to the old code; create a new one for validation.

Give `[Open project](<base-url>/projects/<project-id>)` as soon as the UUID is known.

## 5. Select and verify the runner

Read repository requirements before judging runner suitability. `artemis runner list` showing “online” proves connectivity, not that the machine can build this project.

Production Platform 3.0.3 quickstart uses runner 5.2.1 exactly. Verify the local binary or the runner's reported version before starting or reusing it. Do not run its self-updater or accept the 5.3.0 upgrade prompt; 5.3.0 rejects this flow's ad-hoc validation payload before commands run. Match the intended runner by name and online state rather than relying on fleet totals that may include stale registrations.

Reuse an already confirmed 5.2.1-compatible runner. If several are plausible, ask which to use. If none exists, use `runner-setup`; explain that it is a long-lived process executing repository code on the user's machine and obtain permission before starting it.

Probe the selected runner for the repository's actual toolchain through a short validation. Name missing tools and the machine; do not rewrite correct repository commands to avoid a missing dependency.

## 6. Prove the measurement on the platform

Use `repo-command-setup` to create a fresh empty changeset over the project's current imported commit and run the exact compile, test, and benchmark commands through `changeset validate --version original` on the selected runner. If that command surface is unavailable, return to `cli-setup`; `validation run` is not an equivalent fallback.

Every command must exit zero. Then use `execution-log-inspect` with the validation process `status.id` to confirm a fresh `artemis_results.json` or `.csv` and report the numeric metric in its own units. `changeset validation get` reports process resources and exit codes, not benchmark metrics.

If the metric is missing or stale, return to `repo-command-setup` and validate again. Never start Discovery merely because the benchmark command exited zero.

Store the verified commands with `artemis project commands set` when available so Web UI settings agree. Discovery does not consume those defaults; pass the same literal commands inline.

## 7. Start or resume the first Discovery

First inspect existing project runs. If a matching Discovery is queued, running, awaiting approval, or already completed, give its link and use `discovery-inspect`; do not create another.

For a new onboarding run, supply these decisions rather than asking a new user:

- versions: `5`;
- task, metric, direction, and optional target files from repository readiness, passed inline to `discovery create` when its detected help supports them;
- the same compile, test, and benchmark strings verified above;
- model: inspect `artemis discovery create --help` and `artemis model list`. If this production command requires `--model`, prefer `gpt-5.6-sol`, otherwise another available preset named to the user. If the command supports a platform default, follow `discovery-start` unless the user requested a model.

Do not call `artemis target add` during quickstart. It is agent-backed on this production surface, is not needed for original-code validation, and may consume credits before Discovery.

Use `discovery-start`, pass the selected runner, and give `[Open Discovery](<base-url>/projects/<project-id>/discovery/<run-id>)` immediately. Wait for the baseline and at least one explored version as that skill requires, then hand off interpretation to `discovery-inspect`.

Say once while the run is active:

1. **Code in.** The project is pinned at the verified imported commit; the runner checks out that commit, not the user's working tree.
2. **Run.** Compile, test, and benchmark execute on the runner in that order; the benchmark writes the metric file.
3. **Code out.** Candidates are changesets. `discovery-inspect` reads their diffs, while remote repository updates enter through `project compare` and `project pull`.

## 8. Close or pause cleanly

Report:

- authenticated deployment;
- repository, branch, and imported commit;
- project and Discovery links;
- runner and verified toolchain;
- exact commands;
- validation metric and Discovery baseline/best metric when available;
- winning diff or current run status.

The run continues on the platform if the terminal closes. The runner is still running; give its stop command and say it may stay online for later work. If the user pauses earlier, report completed checkpoints and identifiers so this skill can resume from the first missing one.

## Failure routing

| Situation | Action |
|---|---|
| CLI missing, unauthenticated, or incompatible | `cli-setup`, then return to deployment state |
| No meaningful benchmark or correctness gate | `repo-command-setup`; stop until the repository is ready |
| Repository edits cannot be pushed | `repo-prepare-fork`, after explicit permission |
| Import pending or failed | `project-import`; do not create validation yet |
| Runner offline or missing | `runner-setup`, then re-check platform status |
| Runner lacks the required toolchain | Name the missing dependency and machine; let the user install it or choose another runner |
| Validation fails or emits no metrics | `execution-log-inspect`, then `repo-command-setup`; do not launch Discovery |
| Discovery fails before baseline | `discovery-inspect`, checking Git access and runner status first |

## Completion checklist

- [ ] Starting state classified from inspected facts
- [ ] CLI authenticated to the project or requested deployment
- [ ] Repository goal, correctness gate, commands, metric, and direction verified
- [ ] Project UUID and imported seed commit verified
- [ ] Selected runner confirmed online and compatible
- [ ] Exact commands passed on the runner and fresh numeric metrics found in the task log
- [ ] Existing Discovery reused or a five-version run started with the verified commands
- [ ] User received measured values, links, persistence explanation, and runner stop command
