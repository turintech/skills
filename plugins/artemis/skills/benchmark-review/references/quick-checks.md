# Quick checks

Run these only when SKILL.md section 3, step 4 says they apply. They take 2 to 4 minutes, 6 at most. Each one edits a scratch copy where a version would and runs the commands once. Nothing runs in the user's checkout. Every "not checked by running" below goes into the reply with its reason in brackets: the step that stopped and why.

## 1. Copy the checkout

Tell the user in one progress line, such as "Running three quick checks, a few minutes." It is not part of the reply in SKILL.md section 5. Then make one work folder for the whole review outside the checkout, `<work>` (`mktemp -d` works on Linux and macOS), and copy the checkout's files into `<work>/copy` (see SKILL.md for the tools it needs):

```bash
git -C "<checkout>" ls-files -z -co --exclude-standard > "<work>/files" &&
  rsync -a -r --from0 --ignore-missing-args --files-from="<work>/files" "<checkout>/" "<work>/copy/"
```

If the copy fails, stop, delete `<work>` and say "not checked by running". The copy is not a git repository: when a build or test needs git, the baseline run fails, so give that as the reason.

## 2. Run the untouched copy once

Write the commands to `<work>/cmds.sh`, each of the Script's setup commands in its own `( )`, in order, then each benchmark command; leave out empty slots and teardown. When a command writes outside the checkout and lets you move it (a cache path in an environment variable, say), put the override at the start of that command's `( )`, pointing into `<work>`; copy an existing cache there first if you like.

```bash
cat > "<work>/cmds.sh" <<'EOF'
(<setup 1>) && (<setup 2>) && rm -f artemis_results.json artemis_results.csv && (<benchmark 1>) && { test -f artemis_results.json || test -f artemis_results.csv; }
EOF
(cd "<work>/copy" && timeout 40 sh "<work>/cmds.sh")
```

When the ranking metric is the benchmark command's runtime, the benchmark writes no results file. Put its commands in `<work>/bench.sh` and time them instead; the metric is the `real` seconds in `<work>/time.txt`, which also holds the benchmark's own error output:

```bash
cat > "<work>/cmds.sh" <<'EOF'
(<setup 1>) && (<setup 2>) && /usr/bin/time -p sh "<work>/bench.sh" 2> "<work>/time.txt"
EOF
(cd "<work>/copy" && timeout 40 sh "<work>/cmds.sh")
```

Without `/usr/bin/time` (minimal Debian and Ubuntu images lack the `time` package), use bash's own in its place, which writes the same `real` line: `bash -c 'time -p sh "<work>/bench.sh"' 2> "<work>/time.txt"`.

On macOS, use `gtimeout` from coreutils. This run is the reference the checks compare against, and every later run overwrites what it writes. Copy its results file (or `time.txt`) and the output files the correctness check or a guard reads to `<work>/reference-out` now; the checks compare against that copy. Note the ranking metric now, and after each check: every run replaces it.

Stop, delete `<work>` and say "not checked by running" when this run fails (a generated or ignored input missing, say) or the timeout fires; don't blame the benchmark for either.

If `git -C "<checkout>" rev-parse HEAD` isn't the commit the measured run used (`Version:` in `changeset validation get`, or `baselineVersionSha` in `artemis --output-format json discovery get <run-id>`), or `git -C "<checkout>" status --porcelain` lists changes, say so on the "Checked by running" line. With neither id in the conversation, skip the commit comparison, but still report uncommitted changes.

## 3. One check at a time

Edit the copy where a version would: the target files, or with none set, the code under test. When several files could be it, pick the one a version would most likely change. Run `cmds.sh` the same way, in a subshell, under `timeout` set to 90 seconds or the time left before the 6 minutes, whichever is less, then undo the edit before the next check by copying the file back from the checkout with plain `cp` (not `cp -p`), so a build sees it changed, and delete any file the check added.

Once 6 minutes have passed since the copy, stop, delete `<work>`, and call any check not yet run "not checked by running".

When an edit fails the build or the test for a reason that isn't the point of the check (a test that pins the very setting you changed, say), undo it and try one other edit, unless less than 90 seconds are left. If that fails the same way, that check is "not checked by running". A check that times out is "not checked by running" too.

- **worse:** make the target clearly worse on the user's goal: about twice the time of the code the user wants faster, as a whole, for a speed goal, never a sleep in a loop; clearly bigger output for a size goal. The metric must move the right way. When the metric that ranks versions isn't the target, say what it did instead.
- **wrong:** return a wrong answer. The correctness check must fail, wherever it runs: the test command or a check inside the benchmark.
  - Aim it at the user's guard, just past the strictness they named (one output off for "exactly the same", say), so a gate looser than the guard shows here. When one edit can't land just past it, any wrong answer the guard should catch will do; say how far past it landed, since a near miss wasn't tested.
  - When the benchmark falls back to another option that still passes (a bigger size, another configuration), make the answer wrong in every option it can choose.
  - If the check passes, test the guard yourself: compare the copy's output with `<work>/reference-out` for an exact guard, or work out the guard's own number (agreement, accuracy) against it for a floor. If it breaks the guard, the gate missed a wrong answer: that's the surprise. If it doesn't, the edit wasn't wrong and isn't a finding: try one other wrong edit, and if that doesn't break the guard either, say the check may not reach the edited code. An edit that wasn't wrong but moved the metric a lot is still worth a decision when it shows the benchmark rewards something the goal doesn't.
  - Skip this one when the ranking metric *is* the correctness measure, such as accuracy: "worse" already covers it. A metric held to a correctness floor, such as a size that must keep 95% agreement, still gets it.
- **cheat:** make the target return the answer for exactly the scored inputs without doing the work: a stored or hardcoded result keyed on the input's size, shape or name, or the scored data itself embedded in the target. Aim it at the defence the benchmark relies on most (a perturbed or fresh copy, a holdout, a sandbox). When the check runs inside the target itself, a target that reports the original's results (from `<work>/reference-out`) without doing the work is the cheat. When Discovery may edit the scorer, its checks or their expected outputs, the cheapest cheat may be an edit there instead (scoring every output with the original's own answers, or changing a number the score is computed from): aim at that. The gate must fail it, or the metric must show no gain beyond its noise; with noise not measured, any gain counts as the cheat winning. Keep it to one small edit and one run.

## 4. Clean up

Whenever the checks end, early stops included, delete `<work>`.
