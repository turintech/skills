---
name: repo-command-setup
description: Derive, verify, and configure the compile, test, and benchmark commands Artemis needs to execute a repository, including numeric artemis_results metrics. Use when preparing a repository for validation or discovery, making a repo Discovery-ready, authoring a benchmark harness, fixing project commands, or checking that a repo can run on an Artemis runner.
---

# Configure repository commands

## At a glance

- **Problem:** Derives, verifies, and records the self-contained root-level `compile`, `test`, and `benchmark` commands Artemis requires.
- **Must be available:** Either a local checkout with the runner's toolchain or an online runner with an imported or import-ready project, plus agreement on the performance target when it is ambiguous.
- **Use / don't use:** Use to prepare or repair repository commands and verify runner compatibility; when the repository lacks a harness, follow [HARNESS.md](HARNESS.md) first, then continue here.
- **Next skill:** If runner verification needs a project, use `project-import` and return here; otherwise import after local verification, then continue to `discovery-start` or validation.

## Requirements

Either of:

- a local checkout with a toolchain matching what the selected runner actually has, **or**
- an already selected/online Artemis runner, plus a project imported (or ready to import) against this repository — runner-based verification happens after import, since it validates through the platform.

Plus, either way:

- agreement on which performance behaviour matters, when the repository doesn't make it obvious — ask the user rather than guessing.

## Choose the workflow path

If the repository lacks a suitable benchmark and correctness gate, follow [HARNESS.md](HARNESS.md) to author one, verify it locally, then continue here.

Otherwise use the path supported by the available environment:

- **No project or runner yet:** derive and verify locally in a disposable clean checkout, then use `project-import`.
- **Project and runner available:** derive the commands and verify them through `changeset validate` on the selected runner.
- **Runner selected but no project yet:** derive the commands, use `project-import`, then return here for runner verification.

Verification is part of this skill. Skip it only when the user explicitly asks; record that the commands remain unverified.

## Execution contract

Artemis runs three ordered phases from the repository root in a fresh checkout on the selected runner:

- **compile** proves generated code is syntactically valid and buildable;
- **test** rejects behaviorally incorrect changes;
- **benchmark** measures the optimization target and writes numeric metrics.

There is no working-directory, setup-command, or timeout field.

Each command must therefore be:

- **root-relative** — change directory within the command only when necessary;
- **self-contained** — perform its own required activation or setup;
- **headless and non-interactive** — no GUI, prompts, or terminal input;
- **repeatable** — do not depend on an IDE, shell alias, uncommitted file, or previous task;
- **truthful** — return non-zero when its phase fails;
- **runner-compatible** — use tools and paths that exist on the selected runner.

The benchmark must write `artemis_results.json` or `artemis_results.csv` to the command's working directory. Stdout is useful for diagnostics but is not the custom-metric channel.

Do not configure Artemis until all three commands are verified under the execution assumptions it will use.

## 1. Inspect before asking

Use repository search and file inspection to identify:

- language, package manager, and build system;
- existing build, test, benchmark, and CI commands;
- supported runtime and toolchain versions;
- repository scripts that already encode environment setup;
- whether a benchmark harness exists;
- files that must remain unchanged during optimization.

Ask the user only for facts the repository cannot answer, such as the intended runner, unavailable external dependencies, or which performance behavior matters.

Prefer repository-owned scripts over long inline command strings. If setup is non-trivial, add a small script to the repository so local execution and Artemis use the same path.

## 2. Derive the three commands

### Compile

Choose the fastest command that still catches invalid generated changes.

- Compiled code should run the real build for every artifact the task may change.
- Interpreted-only changes may use syntax checking, type checking, or an import check.
- Do not retain an expensive full build when the optimization target cannot affect compiled output.
- Do not weaken compile merely to reduce runtime; verify the lighter gate catches a representative failure.

### Test

Choose tests that protect the behavior the optimization may change.

- Include a focused correctness test for the optimized path.
- Keep the command deterministic and reasonably fast because it runs for every version.
- Ensure a deliberately incorrect implementation makes the command fail.
- Follow [HARNESS.md](HARNESS.md) when the repo does not already have a correctness-gated microbenchmark.

### Benchmark

Measure the requested optimization target directly.

- Keep unrelated startup, downloads, compilation, and data generation outside the timed region.
- Warm up runtimes or kernels where required.
- Use deterministic, representative inputs.
- Emit the metric that should rank versions, with stable units and direction.
- Keep diagnostic output concise enough to avoid delaying task-log upload.

When no harness exists yet, author it with [HARNESS.md](HARNESS.md). This skill then wires and verifies the command.

## 3. Make environment requirements explicit

The runner starts a non-interactive shell. Commands must explicitly select required runtimes and environments:

```bash
source .venv/bin/activate && python -m pytest
conda run -n myenv python benchmarks/run.py
JAVA_HOME=/path/to/jdk17 ./mvnw test
```

Prefer repository-relative environments and wrapper scripts. If a machine-level path is unavoidable, document it as a runner prerequisite and verify it on the selected runner.

Remove prompts with supported non-interactive flags. Do not hide errors with blanket `|| true`; allow only explicitly harmless cleanup operations to fail.

## 4. Emit custom metrics

Every metric value must be numeric. Strings, booleans, `null`, and nested objects are rejected or dropped.

Single JSON observation:

```json
{"median_ms": 12.3, "throughput": 81.4}
```

Multiple JSON observations:

```json
[
  {"median_ms": 12.3, "throughput": 81.4},
  {"median_ms": 12.1, "throughput": 82.6}
]
```

Rejected JSON:

```json
{"status": "passed", "passed": true, "git_sha": "abc123", "layers": {"count": 12}}
```

Reduce required state to numeric metrics, for example `"passed": 1`. Do not encode identifiers or arbitrary metadata in the results file.

CSV is also supported when every non-header cell is numeric:

```csv
median_ms,throughput
12.3,81.4
12.1,82.6
```

Use exactly `artemis_results.json` or `artemis_results.csv`. If both exist, JSON takes priority. Keep metric names and units stable across baseline and generated versions.

The benchmark must create the file in the working directory from which Artemis invoked it. Verify that an old result file cannot survive and make a failed benchmark look successful: remove stale output before measuring and write the new result atomically when practical.

## 5. Where to verify

Use the selected runner whenever the project is imported; local success cannot prove compatibility with its toolchain, OS, architecture, or dependencies. Verify locally when no runner or project exists yet, or as a faster preliminary loop. Both paths must prove that all three commands pass, the test catches a representative fault, and the benchmark writes a fresh numeric results file.

### 5a. Verify locally

Use a disposable clean clone or worktree so ignored files and parent-directory state cannot mask missing setup. Do not destructively clean the user's active checkout.

Run the exact commands in order from the repository root:

```bash
<compile-command>
<test-command>
rm -f artemis_results.json artemis_results.csv
<benchmark-command>
test -f artemis_results.json || test -f artemis_results.csv
```

Confirm:

- each command returns zero only on success;
- the test fails for a representative semantic fault;
- the benchmark creates a fresh numeric results file;
- commands do not read a parent `.git`, environment, or build directory accidentally;
- a second run produces a comparable metric;
- output volume is proportionate to useful diagnostics.

Record the literal commands and measured duration of each phase.

### 5b. Verify via the runner

This exercises the commands through the platform, on the real execution environment, instead of guessing that local success transfers. It needs a project already imported (`project-import`) and a runner already online.

Check the installed command surface, then use **`artemis changeset validate`** — the same primitive discovery uses to evaluate generated versions and the baseline:

```bash
artemis changeset validate --help
artemis --output-format json changeset create --project "<project-uuid>"
# → an empty changeset; its one version is the project's current original code

artemis --output-format json changeset validate "<changeset-id>" \
  --project "<project-uuid>" --version original \
  --command "<compile-command>" \
  --command "<test-command>" \
  --command "<benchmark-command>" \
  --runner "<runner-name>" --wait
```

`--version original` resolves the changeset's original version automatically. `--wait` returns the final per-command `exitCode`, runtime, resource usage, and status. Re-check later, or from a different session, with:

```bash
artemis changeset validation get "<validation-id>" --project "<project-uuid>"
```

Confirm every command shows `exitCode: 0`, the intended runner and toolchain were used, and the benchmark created a fresh `artemis_results.json`/`.csv`. The result reports only `exitCode`, `runtime`, `cpu`, and `memory` — never metric values, and never whether the results file was written. Read the command output with `artemis process logs "<process-id>"`, passing `status.id` from the validate response (not the per-command `logId`, which is not fetchable).

If something fails, fix the command and re-run `changeset validate` again (a fresh changeset isn't needed — reuse the same one, `--version original` still resolves the same original code).

If `changeset validate` is unavailable, inspect `artemis validation run --help` for the installed CLI's project-validation workflow and use the runner log for command details. Do not invent compatibility flags.

## 6. Configure Artemis

Use the verified commands unchanged:

- Project settings and `artemis project commands set` provide defaults for Web UI validation flows. `changeset validate` runs commands ad hoc and does not store those defaults; run `artemis project commands set --help` when Web UI defaults are wanted.
- Discovery does not consume those defaults; pass the same commands inline to `discovery create` through `discovery-start`.

Do not maintain two semantically different command sets for validation and discovery.

## Advanced cases

Read [ADVANCED.md](ADVANCED.md) when clean-checkout execution is impractical because of expensive rebuilds, a required long-running service, large ML assets or GPU state, excessive task logs, or runner-only failures. The advanced patterns trade portability for operational feasibility and require explicit safeguards.

## Completion checklist

- [ ] Compile, test, and benchmark commands are exact and recorded.
- [ ] Verification completed locally or on the runner, or explicitly skipped by the user and recorded as outstanding.
- [ ] When verification was performed, all three passed in order from a disposable clean checkout or via `changeset validate --version original` on the runner.
- [ ] Commands are root-relative, headless, non-interactive, and repeatable.
- [ ] Compile catches invalid generated code.
- [ ] Test catches a representative semantic fault.
- [ ] Benchmark writes a fresh numeric `artemis_results.json` or CSV file.
- [ ] Runtime, toolchain, and machine-level prerequisites are documented.
- [ ] Validation and discovery use the same verified commands.
