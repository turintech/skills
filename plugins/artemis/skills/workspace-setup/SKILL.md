---
name: workspace-setup
description: Prepare and verify a runner-owned persistent build workspace for Artemis. Use when clean candidate builds are prohibitively expensive, a repository needs incremental builds, or compile/test/benchmark commands must bridge Artemis task checkouts into a stable cache.
---

# Set up a persistent Artemis workspace

Every Artemis version arrives in a fresh checkout, so large projects lose incremental build state and pay a full rebuild for each candidate.

Keep a dedicated built tree on the runner, seeded at the same commit as the project on the platform. The compile command syncs the candidate's changes into that tree and rebuilds incrementally. Test and benchmark use the same tree; the benchmark still publishes results back to the task directory.

That task directory is the runner's candidate checkout (`$PWD` / `output/build`); see [Task output: where your code is downloaded and run](https://docs.artemis.turintech.ai/features/artemis-runner#task-output-where-your-code-is-downloaded-and-run).

This skill explains the requirements. It does not prescribe a helper-script layout. Return to `repo-command-setup` to record and verify the command triple.

See [WORKSPACE.md](WORKSPACE.md) for optional shell sketches.

## Requirements

- Create a dedicated directory on the runner host and build the project there. Do not use a developer's active checkout.
- Seed that tree at the same commit as the project on the platform (`gitHash`, or Discovery `baselineVersionSha` when a run exists). If they differ, stop and resolve that before creating a cache.
- In the Artemis compile command, sync candidate changes into the tree and rebuild incrementally. Sync every path the agent may change; an incomplete copy silently measures old code.
- Run test and benchmark against that same built tree.
- Publish `artemis_results.json` or `.csv` back to the original task directory (`$PWD`). Artemis does not read results from the cache.
- If candidates share one tree, serialize compile through benchmark so another candidate cannot overwrite the binary mid-transaction.
- Start a new cache when the seed commit, toolchain, or incompatible build options change.
- A failed sync or build must not leave a previous binary or stale results file looking current.

## Examples

These sketches show one way to meet the requirements. Adapt them to the repository's build system.

Compile syncs the candidate into the built tree and rebuilds:

```bash
set -euo pipefail
ORIG="$PWD"
WORKSPACE="${ARTEMIS_CACHE_ROOT:?set ARTEMIS_CACHE_ROOT to the runner cache}"
# confirm the workspace is seeded at the platform commit, then:
# sync every path the agent may change from "$ORIG" into "$WORKSPACE"
# rebuild incrementally in "$WORKSPACE"
```

Benchmark measures that tree and copies results back to `$PWD`:

```bash
set -euo pipefail
ORIG="$PWD"
WORKSPACE="${ARTEMIS_CACHE_ROOT:?set ARTEMIS_CACHE_ROOT to the runner cache}"
rm -f "$ORIG/artemis_results.json" "$ORIG/artemis_results.csv"
# run the headless benchmark against "$WORKSPACE"
# copy the fresh numeric results file back to "$ORIG"
test -f "$ORIG/artemis_results.json" || test -f "$ORIG/artemis_results.csv"
```

## Prove the candidate rebuilt

A passing exit code is not enough if the cache rebuilt the seed tree or benchmarked a stale binary. After a representative source edit, the sync should pick it up and the rebuild should change the expected artifact. Restore the edit before recording commands. A representative semantic fault should still fail the test command.

## Hand off

Give `repo-command-setup` the compile, test, and benchmark commands, the cache location, the seed commit, and the proof above. Do not launch Discovery until runner-side validation passes.
