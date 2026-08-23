# Optional workspace examples

These sketches illustrate the requirements in [SKILL.md](SKILL.md). Adapt them to the repository. They are not a required file layout or workflow.

## Cache location

Resolve the runner cache from an environment variable. Do not commit a user's home directory.

```bash
ARTEMIS_CACHE_ROOT="${ARTEMIS_CACHE_ROOT:-${XDG_CACHE_HOME:-$HOME/.cache}/artemis/my-project}"
```

Record the repository URL, seed commit, and toolchain in the cache so a later command can refuse a mismatched tree.

## Capture the task directory

Artemis invokes commands from the candidate checkout. Preserve that directory before changing into the cache:

```bash
ORIG="${ARTEMIS_TASK_ROOT:-$PWD}"
```

Benchmark results must land in `$ORIG`, not only in the cache.

## Sync then rebuild

Checksum comparison keeps incremental-build timestamps for unchanged files. Avoid a broad delete against an extracted checkout that may omit submodules or generated files.

```bash
rsync -a --checksum --no-times "$ORIG/path/" "$ARTEMIS_CACHE_ROOT/source/path/"
# rebuild incrementally in the cache and propagate the real exit code
```

Print enough to connect changed source to rebuilt artifacts.

## Publish results to the task directory

Remove stale files first. Write a validated result back to `$ORIG`:

```bash
rm -f "$ORIG/artemis_results.json" "$ORIG/artemis_results.csv"
# run the headless benchmark against the cache
cp "$ARTEMIS_CACHE_ROOT/artemis_results.json" "$ORIG/artemis_results.json"
```

Stdout is for diagnostics. The results file is the metric channel.
