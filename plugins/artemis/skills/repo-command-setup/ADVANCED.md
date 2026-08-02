# Advanced repository command patterns

Use these patterns only when the clean-checkout contract in `SKILL.md` is insufficient. Start by identifying the specific problem being solved:

- **Persistent build workspace solves expensive clean rebuilds.** Reinstalling dependencies, regenerating assets, or recompiling a large project for every version can dominate the optimization budget. A dedicated workspace preserves costly machine-local state while refreshing the source under test.
- **Managed service lifecycle solves benchmarks that require a long-running process.** The command sequence must stop the old service, install the candidate version, start that exact version, wait for readiness, and prevent stale processes from serving the benchmark.
- **ML/GPU workspace solves large assets and scarce hardware state.** Models, datasets, compiled extensions, and environments may be too large to recreate per task, while leaked GPU processes or caches can corrupt later measurements.
- **Metric stabilization solves environment-driven ranking errors.** Thread placement, warm-up state, shared-machine load, and an unsuitable statistic can move measurements more than the code change does.
- **Log control solves upload-bound evaluation latency.** Artemis uploads command output before finalizing an observation; multi-megabyte compile logs can make a successful baseline appear hung.
- **Runner-specific troubleshooting solves differences between a developer checkout and the runner's extracted source.** Missing Git metadata, shell initialization, tools, permissions, or environment activation often explain commands that work locally but fail remotely.

These are escape hatches, not defaults. They introduce machine-specific state and must preserve the identity of the candidate source, correctness gates, metric location, and reproducibility.

## Persistent build workspace

### Problem

Use this when a clean build is prohibitively slow because the project needs expensive dependency installation, generated assets, compilation caches, or a large incremental build tree.

### Pattern

Create a dedicated runner-owned clone or workspace. Never point this pattern at a developer's active checkout. Add an unmistakable marker and refuse destructive cleanup without it.

Example compile command:

```bash
set -euo pipefail
ORIG="$PWD"
WORKSPACE="/srv/artemis/workspaces/my-project"
test -f "$WORKSPACE/.artemis-managed-workspace"
cd "$WORKSPACE"
git reset --hard HEAD
git clean -fd
cp -a "$ORIG/src/." src/
<compile-command>
```

Test and benchmark commands run against the same workspace:

```bash
cd /srv/artemis/workspaces/my-project && <test-command>
```

The benchmark must copy its result back to the directory Artemis is observing:

```bash
set -euo pipefail
ORIG="$PWD"
cd /srv/artemis/workspaces/my-project
rm -f artemis_results.json artemis_results.csv
<benchmark-command>
if test -f artemis_results.json; then
  cp artemis_results.json "$ORIG/"
elif test -f artemis_results.csv; then
  cp artemis_results.csv "$ORIG/"
else
  echo "benchmark produced no Artemis results file" >&2
  exit 1
fi
```

### Safeguards

- Pin and record the workspace's seed commit, dependency lockfiles, compiler, and runtime.
- Copy every path the optimization agent may change; an incomplete copy silently benchmarks old code.
- Invalidate caches when build configuration, generated-code inputs, or toolchain versions change.
- Serialize tasks that share the workspace.
- Ensure a failed copy or build cannot leave a previous binary or metrics file looking current.
- Periodically reproduce the result with a clean build.

## Managed service lifecycle

### Problem

Use this when tests or benchmarks require a server, model endpoint, database, or other long-running process. Rebuilding without lifecycle management can leave the previous candidate serving requests or begin measurement before the new service is ready.

### Pattern

Extend the persistent workspace with explicit ownership, startup, and readiness checks. Prefer a PID file or service manager over broad `pkill -f` matching.

```bash
set -euo pipefail
WORKSPACE="/srv/artemis/workspaces/my-service"
PIDFILE="$WORKSPACE/.artemis-service.pid"

if test -f "$PIDFILE"; then
  PID="$(cat "$PIDFILE")"
  kill "$PID" 2>/dev/null || true
  for _ in $(seq 1 30); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 1
  done
  kill -0 "$PID" 2>/dev/null && {
    echo "old service did not stop" >&2
    exit 1
  }
  rm -f "$PIDFILE"
fi

<refresh-source-and-build>

cd "$WORKSPACE"
nohup <start-server-command> > .artemis-service.log 2>&1 &
echo "$!" > "$PIDFILE"

for _ in $(seq 1 60); do
  curl -fsS http://127.0.0.1:<port>/health >/dev/null && exit 0
  sleep 1
done

echo "service failed readiness check" >&2
cat .artemis-service.log >&2
exit 1
```

### Safeguards

- Bind to a task-specific or reserved port so concurrent runs cannot collide.
- Verify the running process or endpoint identifies the candidate commit when possible.
- Use a real readiness check rather than a fixed sleep.
- Capture startup logs on failure without streaming unbounded logs on success.
- Stop the service after the run when persistence is unnecessary.
- Do not kill processes you did not start.

## ML and GPU workspace

### Problem

Use this when models, datasets, Python environments, compiled kernels, or GPU initialization are too expensive to recreate for each task, or when stale GPU processes and caches affect correctness or timing.

### Pattern

Keep immutable large assets outside the temporary checkout and reference them through explicit environment variables or configuration:

```bash
MODEL_DIR=/srv/artemis/models/my-model
DATA_DIR=/srv/artemis/datasets/my-benchmark
VENV=/srv/artemis/envs/my-project

test -d "$MODEL_DIR"
test -d "$DATA_DIR"
test -x "$VENV/bin/python"

PYTHONUNBUFFERED=1 \
MODEL_DIR="$MODEL_DIR" \
DATA_DIR="$DATA_DIR" \
"$VENV/bin/python" benchmarks/run.py
```

Keep candidate source and generated binaries in a dedicated workspace, while treating models and datasets as read-only inputs.

### Safeguards

- Pin model and dataset versions or checksums in the repository.
- Record GPU model, driver, runtime, framework, thread settings, and precision.
- Seed random number generators and use representative fixed inputs.
- Warm up kernels before timing.
- Scope cleanup to processes owned by this runner task; never kill every process reported by `nvidia-smi`.
- Reset mutable model state, caches, and output directories between versions.
- Make the optimized path active by default; the benchmark should not rely on an unstated environment flag.
- Use unbuffered output for useful progress without printing per-iteration noise.

## Make metrics comparable across runs

### Problem

Thread placement, runtime warm-up, shared-machine state, and unstable statistics can move benchmark results more than the candidate code does. Artemis then ranks environmental noise as an optimization.

Statistic selection and noise-floor measurement belong to the benchmark harness's own methodology. This section covers the runner-side execution state that must remain consistent after the harness methodology is chosen:

- Set thread counts such as `OMP_NUM_THREADS` and `MKL_NUM_THREADS`.
- When NUMA placement matters, set `OMP_PROC_BIND=close` and `OMP_PLACES=cores`.
- Discard warm-up iterations affected by JIT compilation, kernel selection, page-in, or cache population.
- Keep runner load and resource limits consistent across baseline and generated versions.

Run the complete benchmark repeatedly in fresh processes after changing runner controls. Do not tune the environment or statistic after seeing which candidate wins.

## Control log volume

### Problem

The runner uploads each task log before the platform finalizes the observation. Large compile logs directly add wall-clock latency and can make a completed benchmark look stuck.

Measure before changing verbosity. Useful rough observations from prior runs were:

| Per-task log size | Delay after benchmark exit |
|---|---:|
| Under 100 KB | Seconds |
| Around 5 MB | One or more minutes |
| Around 25 MB | Many minutes |

Common sources are compiler warning cascades, verbose dependency builds, CMake informational output, and echoed recipes.

Locate the runner's per-task log after a representative compile and measure it directly:

```bash
wc -c -l /path/to/runner/task.log
```

Reduce only understood noise:

- CMake: consider `--log-level=WARNING -Wno-dev -DCMAKE_INSTALL_MESSAGE=NEVER`.
- Make: `MAKEFLAGS=-s` suppresses recipe echo; Ninja is already quieter.
- Compiler warning cascades: suppress only warnings confirmed to originate in third-party or compiler headers, and check whether command-line build flags replace rather than extend repository defaults.
- pip: avoid `--quiet` by default. It can hide package-resolution or broken-wheel failures that surface later as misleading import errors.
- Verbose build steps: capture output and print it only on failure.

```bash
set -euo pipefail
BUILD_LOG=".artemis_run/build.log"
mkdir -p "$(dirname "$BUILD_LOG")"
<build-command> >"$BUILD_LOG" 2>&1 || {
  rc=$?
  echo "build failed; showing final log section" >&2
  tail -n 500 "$BUILD_LOG" >&2
  exit "$rc"
}
```

Do not hide package-resolution failures or actual compiler errors merely to reduce upload size.

## Runner checkout has no Git metadata

### Problem

The runner may execute an extracted source tree without `.git`. Build scripts that call `git rev-parse`, `git describe`, or similar commands can work locally by finding a parent repository and fail on the runner.

Preferred fixes:

1. Change the build to accept an explicit version or SHA environment variable.
2. Make the repository script fall back cleanly when Git metadata is unavailable.
3. As a last resort, create a temporary stub repository only when no `.git` exists:

```bash
if ! git rev-parse HEAD >/dev/null 2>&1; then
  git init -q
  git -c user.email=stub@artemis -c user.name=stub \
    commit -q --allow-empty -m stub
fi
```

Do not overwrite a real checkout's Git metadata.

## Troubleshooting

- **Works in an IDE but not on the runner:** make runtime activation and tool paths explicit.
- **Wrong Python, Node, Java, or compiler:** use repository wrappers or a documented absolute runner path.
- **Command hangs:** remove interactive prompts and inspect network or credential waits.
- **Permission denied:** verify the runner user owns the dedicated workspace and outputs.
- **Server starts but benchmark fails:** inspect readiness, port ownership, and service logs.
- **Metrics missing:** remove stale files, verify exact filename and working directory, and ensure every value is numeric.
- **Harness or script bug found only on the runner:** fix in Git, `project pull`, create a new empty changeset, then re-validate — see SKILL.md §5b.
- **Numbers drift:** pin thread counts, discard warm-up iterations, control shared-machine load, and use a statistic validated against repeated runs.

After fixing an advanced case, rerun compile, test, and benchmark in order and record every machine-level prerequisite that remains.
