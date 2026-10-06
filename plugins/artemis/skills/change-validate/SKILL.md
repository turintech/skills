---
name: change-validate
description: Check whether a local code change really makes a project faster (or better on any metric), measured on an Artemis runner. Puts the uncommitted change on a new Artemis branch, measures the starting commit and the change the same number of times on the same runner and script, and reports the platform's verdict per metric with its interval and a link to the branch's Scripts tab. Use when the user asks whether their change or their agent's change is faster, wants a before/after benchmark, or wants to validate a local change on a runner.
compatibility: Requires Artemis CLI 1.1.14+ and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.14"
  artemis-platform-min: "3.1.0"
---

# Validate a local change

## At a glance

- **Problem:** Answers "is this change really faster?" with measurements, not a single run: the starting commit and the change are measured the same number of times on the same runner, and the platform says per metric whether the difference is real.
- **Must be available:** An authenticated CLI, an online runner, an imported project whose validation script produces metrics, and a local git checkout of that project with the change in it, uncommitted, on top of the project's commit.
- **Use / don't use:** Use for one change the user or their agent has already made. To have Artemis search for improvements, use `discovery-start`. To judge a Discovery run's versions, use `discovery-inspect`.
- **Next skill:** `changeset pr` ships a change that came out better. `repo-command-setup` fixes a script whose repeats are not independent (section 4).

## Requirements

- `artemis --version` meets `metadata.artemis-cli-min`: `artemis changeset compare --help` must work. Otherwise `cli-setup`.
- An online runner: `artemis runner list`. Otherwise `runner-setup`.
- The project id and a validation script whose benchmark writes metrics: `artemis project scripts list --project <p>`. Otherwise `project-import` and `repo-command-setup`.
- The checkout is the project's repository (`git remote get-url origin` matches the project's `gitUrl`), and its `HEAD` is the commit the project is on (`gitHash` for this project in `artemis --output-format json project list --all`). If `HEAD` differs, the saved change would carry every unrelated difference: say so and ask whether to update the checkout first.

Settings are fixed unless the user asks: the project's script, 5 runs per side, one runner. Do not ask the user to choose them.

## 1. Put the change on a branch

```bash
artemis --output-format json changeset create --project <p> --name "<short description of the change>"
artemis changeset save <changeset-id> --project <p> --from-git -m "<what the change does>"
artemis changeset versions <changeset-id> --project <p>
```

Run it from the repository root (or pass `--root <repo>`). `--from-git` saves every file `git status` reports changed, untracked ones included (build output, `.venv`, local config), and committed work is not saved. Show the user that list first. If anything in it is not part of the change, save only the change's files instead:

```bash
artemis changeset save <changeset-id> --project <p> -m "<what the change does>" <path> <path> --delete <removed-path>
```

The changeset then has two versions: the starting commit (`--version original`, the project's code) and **latest** (with the change). Tell the user the branch exists and link it (section 5).

## 2. Measure both sides the same way

Alternate the sides, so anything that drifts on the machine during the session hits both equally. One run per call, starting commit then latest, five times each:

```bash
artemis changeset validate <changeset-id> --project <p> --version original --script <s> --runner <r> --wait
artemis changeset validate <changeset-id> --project <p> --version latest --script <s> --runner <r> --wait
```

Same runner, same script, same number of runs for both sides, always. After the first pair, say how long one pair took and roughly how long the rest will take. Stop at the first non-zero exit and report it; exit 6 means the run outlasted `--timeout`. A run that fails is not a reading: read its log (`artemis changeset validation logs <validation-id> --project <p>`, or `execution-log-inspect`), and if the change broke the build or the tests, stop and say so. That is the answer.

## 3. Read the verdict

```bash
artemis --output-format json changeset compare <changeset-id> --project <p> --script <s>
```

Before any verdict, check each metric's `spreadPct` (section 4). With readings on both sides and no spread, the runs are not independent: falcon then reports `better` or `worse` with reason `settled`, from an interval with no width. Do not report that verdict; go to section 4.

Report per metric: the starting commit's value (on the `versions[]` row with `isBaseline: true`, whose `verdict` is null), the change's value, the improvement and its interval, and the verdict. **Every number comes from this output. Never compute an average, a percentage, an interval or a verdict yourself**, and never call a result better or worse on your own reading of the values.

| Verdict | Say |
|---|---|
| `better` / `worse` | The change is faster or slower, by the improvement, with the interval |
| `noise` | No difference could be measured. If `recommendedReadings` is set, it is the total readings per side that would settle it, counting those already taken; offer to run more pairs |
| `pending` | Too few runs to tell. Run more pairs and compare again until each side's `readings` reaches `recommendedReadings` |

`readings` counts values, not runs: a benchmark that reports several values per run adds several per run. Compare after each pair instead of working out how many pairs are left. Check with the user before going past about 10 runs per side.

When `recommendedReadings` is null, `recommendedReadingsReason` says why:

- `settled`: the verdict stands.
- `too_small`: no reasonable number of runs would separate them; say the change makes no practical difference.
- `no_effect`: both sides average the same; say so.
- `no_data`: not enough readings to size it yet; run more pairs, then compare again.

## 4. Repeats that are not independent

`spreadPct` is pooled over both sides. If both sides have at least two readings but `spreadPct` is null, every run gave exactly the same number. The runs are not independent measurements (a cached build or result, a benchmark that reports a fixed value, a timer too coarse to see a difference), so the interval means nothing. Say this plainly, report no verdict for that metric, and hand over to `repo-command-setup` to fix the benchmark.

## 5. Hand back

- The verdict per metric, from section 3.
- The branch's Scripts tab in the Web UI: `<deployment>/projects/<project-id>/branches/<changeset-id>/validations`, with every run and the same verdict.
- For a `better` result, offer to open a pull request: `artemis changeset pr <changeset-id> --project <p>`.

## Checklist

- [ ] Checkout matches the project's repository and commit; the saved file list shown and agreed
- [ ] Both sides measured the same number of times, alternating one run per call, on one runner and one script
- [ ] Stopped at the first failed run and read its log; asked before going past about 10 runs per side
- [ ] Verdict, improvement and interval quoted from `changeset compare`, nothing computed
- [ ] Spread checked before any verdict; identical repeats flagged instead of reported
- [ ] Scripts tab link given
