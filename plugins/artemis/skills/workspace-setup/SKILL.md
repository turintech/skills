---
name: workspace-setup
description: Prepare and verify a runner-owned persistent build workspace for Artemis. Use when clean candidate builds are prohibitively expensive, a repository needs incremental CMake/GPU/ML builds, or compile/test/benchmark commands must bridge Artemis task checkouts into a stable cache.
---

# Set up a persistent Artemis workspace

## At a glance

- **Problem:** Every Artemis version arrives in a fresh checkout, while large
  projects need a stable source/build tree to reuse an incremental build.
- **Must be available:** Exact repository URL, branch and baseline SHA; runner
  host/toolchain; paths the agent may edit; compile, test and benchmark intent.
- **Next skill:** Return to `repo-command-setup` to verify the exact command
  triple on the runner.

This skill owns the bridge between the candidate checkout and persistent state.
It does not choose the benchmark metric or launch Discovery.

## Execution model

Keep these locations distinct and record all three:

1. **Candidate checkout:** ephemeral Artemis task directory; command invocation
   starts here and `$PWD` identifies the version being evaluated.
2. **Persistent workspace:** runner-owned source, build, install and dependency
   state, seeded from the project's exact baseline SHA.
3. **Results publication directory:** the original command invocation directory;
   the benchmark must publish `artemis_results.json` or `.csv` here.

Never use a developer's active checkout as the persistent workspace.

## 1. Inspect before changing anything

Determine:

- project repository, branch, imported `gitHash` and Discovery
  `baselineVersionSha` when a run exists;
- build system, submodules, generated inputs, install prefix and toolchain;
- files the optimization agent may add, edit, rename or delete;
- focused build targets and correctness tests;
- immutable models, datasets and environments that may remain outside source;
- expected cold and incremental build times;
- runner concurrency and available locking tools.

If the imported SHA and intended baseline differ, stop and resolve that before
creating a cache.

## 2. Add repository-owned helpers

Prefer a small directory such as `harness/artemis/` or `<POC>/artemis/`:

```text
artemis/
├── README.md
├── common.sh
├── setup-workspace.sh
├── compile.sh
├── test.sh
└── benchmark.sh
```

See [WORKSPACE.md](WORKSPACE.md) for the required contracts and shell patterns.
Use environment variables for machine-specific roots; do not commit a user's
home directory.

### Setup helper

It must:

- require explicit repository URL and seed SHA, or derive them only when
  unambiguous and print the resolved values;
- clone a dedicated source tree, initialize required submodules and configure a
  stable build directory;
- perform the initial focused build;
- record seed SHA, submodule state, build options and toolchain identity;
- create an unmistakable managed-workspace marker only after setup succeeds.

Use a new cache root when the seed, submodule state, toolchain or incompatible
build option changes.

### Compile helper

It must:

- capture the candidate root before changing directory;
- refuse to operate without the managed marker and matching recorded seed;
- acquire an exclusive lock covering source sync, build, test and benchmark;
- synchronize every path the agent may change, including additions/deletions;
- preserve incremental-build timestamps for unchanged content;
- build the focused artifacts and propagate the real exit code;
- log which candidate files changed and which artifacts rebuilt.

For content overlays, prefer checksum comparison and do not infer deletions from
a thinner extracted checkout. If deletion support is required, derive it from a
trusted manifest/diff rather than broad `rsync --delete`.

### Test and benchmark helpers

Both must consume artifacts from the same synchronized workspace. The benchmark
must remove stale result files in both workspace and invocation directory, run
headlessly, validate numeric output, and atomically publish the final result
back to the invocation directory.

## 3. Make shared state safe

- Use one workspace per concurrent worker, or serialize the full
  compile→test→benchmark transaction with a lock.
- A per-command lock is insufficient if another candidate can compile between
  this candidate's compile and benchmark.
- Scope cleanup to the managed workspace and processes started by these helpers.
- Never use broad process killing or destructive cleanup outside a verified
  managed root.

## 4. Verify identity, not only exit codes

Verify from a disposable candidate checkout or through
`artemis changeset validate`:

1. Baseline compile, focused test and benchmark pass.
2. A harmless edit in an allowed source file is reported by synchronization and
   rebuilds the expected object/artifact.
3. The resulting test/benchmark uses that rebuilt artifact, not a stale install.
4. Restoring the source rebuilds back to baseline.
5. A representative semantic fault is rejected by the test command.
6. Two clean benchmark runs each publish a fresh numeric result in the task
   invocation directory.
7. A second worker cannot mutate the workspace during the transaction.

Record literal commands, phase durations, seed SHA, runner/toolchain identity,
sync evidence and rebuilt artifact evidence.

## 5. Hand off

Return to `repo-command-setup` with:

```text
Candidate checkout:
Persistent workspace:
Results publication directory:
Repository / branch / seed:
Managed marker:
Locking strategy:
Allowed synchronized paths:
Compile command:
Test command:
Benchmark command:
Cold setup duration:
Incremental duration:
Identity proof:
Fault-gate proof:
Metric publication proof:
```

Do not launch Discovery until runner-side validation passes.

## Completion checklist

- [ ] Persistent source is dedicated and pinned to the Artemis baseline SHA.
- [ ] Marker and metadata identify seed, submodules, toolchain and build options.
- [ ] Repository-owned helpers contain no user-specific absolute paths.
- [ ] Synchronization covers the full allowed edit surface without unsafe delete.
- [ ] One candidate owns the workspace for compile, test and benchmark.
- [ ] Representative candidate edit rebuilt the expected artifact.
- [ ] Representative semantic fault failed the test gate.
- [ ] Two clean benchmark runs published fresh numeric task-root results.
- [ ] Exact commands and prerequisites were handed to `repo-command-setup`.
