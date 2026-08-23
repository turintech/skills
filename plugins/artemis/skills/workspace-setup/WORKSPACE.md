# Persistent workspace helper contracts

Use these as constraints when adapting helpers to a repository. Do not copy a
template blindly across build systems.

## Shared configuration

`common.sh` should resolve a cache root from an environment variable with a
documented user-cache default, then expose paths beneath it:

```bash
ARTEMIS_CACHE_ROOT="${ARTEMIS_CACHE_ROOT:-${XDG_CACHE_HOME:-$HOME/.cache}/artemis/my-project}"
ARTEMIS_SOURCE="$ARTEMIS_CACHE_ROOT/source"
ARTEMIS_BUILD="$ARTEMIS_CACHE_ROOT/build"
ARTEMIS_INSTALL="$ARTEMIS_CACHE_ROOT/install"
ARTEMIS_MARKER="$ARTEMIS_CACHE_ROOT/.artemis-managed-workspace"
ARTEMIS_LOCK="$ARTEMIS_CACHE_ROOT/workspace.lock"
```

The marker should be structured text containing at least the repository URL,
seed SHA, submodule state, build options and toolchain identity. Do not treat an
empty marker as sufficient proof.

## Candidate root

Repository-owned scripts can locate the candidate from their own path. Commands
that call external scripts must preserve the invocation directory explicitly:

```bash
ARTEMIS_TASK_ROOT="${ARTEMIS_TASK_ROOT:-$PWD}"
export ARTEMIS_TASK_ROOT
```

Resolve paths before `cd`. Reject a task root that does not contain expected
repository files.

## Transaction locking

The same candidate must own compile, test and benchmark. Prefer one worker per
cache. If commands are separate processes, use a runner-level orchestration
wrapper or a lease that persists across all three phases; a lock released at the
end of `compile.sh` does not prevent another candidate replacing the binary
before `test.sh`.

At minimum, helpers should use `flock` for individual mutations:

```bash
exec 9>"$ARTEMIS_LOCK"
flock -x 9
```

Document the remaining cross-command constraint if the platform cannot hold a
single lease across phases.

## Safe synchronization

For a known directory whose deletions are not part of the optimization surface:

```bash
rsync -a --checksum --no-times \
  "$ARTEMIS_TASK_ROOT/path/" "$ARTEMIS_SOURCE/path/"
```

Do not use `--delete` against an extracted checkout that may omit submodules,
generated files or ignored source. If candidate deletions are allowed, compute
them from a trusted baseline-to-candidate manifest and delete only paths inside
an allowlist.

Before building, print concise machine-readable sync records. After building,
record enough evidence to connect changed source to rebuilt artifacts.

## Truthful build status

Do not hide the build exit code behind `tail` or another pipeline:

```bash
set +e
cmake --build "$ARTEMIS_BUILD" --target focused_target --parallel \
  >"$ARTEMIS_CACHE_ROOT/build.log" 2>&1
rc=$?
set -e
if (( rc != 0 )); then
  tail -n 300 "$ARTEMIS_CACHE_ROOT/build.log" >&2
  exit "$rc"
fi
```

## Metric publication

Remove stale files before measurement and publish only a validated completed
file:

```bash
task_root="${ARTEMIS_TASK_ROOT:-$PWD}"
workspace_result="$ARTEMIS_CACHE_ROOT/artemis_results.json"
task_tmp="$task_root/.artemis_results.json.tmp"
task_result="$task_root/artemis_results.json"

rm -f "$workspace_result" "$task_tmp" "$task_result" \
      "$task_root/artemis_results.csv"

cd "$ARTEMIS_SOURCE"
<headless-benchmark-command>
test -s "$workspace_result"
python3 - "$workspace_result" <<'PY'
import json, math, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
rows = data if isinstance(data, list) else [data]
assert rows and all(isinstance(row, dict) and row for row in rows)
for row in rows:
    for value in row.values():
        assert type(value) in (int, float) and math.isfinite(value)
PY

cp "$workspace_result" "$task_tmp"
mv "$task_tmp" "$task_result"
```

The benchmark should print the result path and primary metric for diagnostics.
Stdout is not the metric channel.

## Seed verification

Before every sync, compare recorded metadata with the intended project seed.
When the runner checkout includes Git history, confirm the candidate descends
from the seed. If history is absent, rely on platform-provided seed metadata or
a repository-owned manifest; do not search a parent directory for unrelated
Git metadata.
