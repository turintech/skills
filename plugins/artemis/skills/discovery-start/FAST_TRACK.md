# Fast-track Discovery

Use this companion from [SKILL.md](SKILL.md) when one Discovery on the full benchmark would take too long. It gets to a trustworthy result sooner in two ways: searching on a smaller benchmark first, and running independent searches on separate runners. Create each run with SKILL.md §1.

## Before offering it

SKILL.md ("Long benchmarks") says when to offer it. Exceptions:

- When the user or a calling skill has already chosen a plan, follow it and do not offer again.
- When the slow part is the build, use `workspace-setup` instead. Smaller benchmarks do not shorten a build.
- When a smaller workload would no longer exercise the code being optimised, keep the full benchmark and use only parallel runners.

Before launching, give the user the single-run estimate next to the fast-track one. Count every tier's versions and Benchmark runs, each run's fresh baseline, and the final comparisons. Parallel runners shorten the wait, not the runner work, so do not promise a linear speedup. Let the user choose.

## Tiers

Prepare one Script per tier (small, medium, full) with `repo-command-setup`, following [benchmark tiers](../repo-command-setup/HARNESS.md#long-benchmarks-small-medium-and-full-tiers). Pass each run's tier Script with `--script` and keep it for the whole run. The Discovery agent does not choose the tier or change its workload or correctness gate.

Results from different tiers are not comparable: compare versions only on the same tier Script.

## 1. Small: search

Create the run with the small Script and the agreed version budget. Give each version more than one Benchmark run, for example `--eval-mode until_stable --max-runs 10`, and include them in the estimate. With one Benchmark run per version every verdict stays `pending`, and nothing can be promoted. On the small tier they are cheap. When the run has finished, read falcon's verdicts:

```bash
artemis --output-format json discovery compare "<run-id>"
```

Rank on the metric agreed with the user, using each version's `verdict` and `improvementPct` for it, and quote them as given. Do not compute or weigh numbers yourself.

- **Seed:** the `better` version with the largest improvement.
- **Shortlist:** up to two more `better` versions whose interval (`improvementLowPct` to `improvementHighPct`) overlaps the seed's. The small tier cannot tell these apart.
- **Nothing is `better`:** stop and tell the user. Do not promote a `noise` result.

Report differences on the other metrics to the user rather than trading them off yourself. A metric with readings on both sides but a null `spreadPct` gave the same number every time, so its verdict means nothing: follow `change-validate` §4.

## 2. Medium: refine

`discovery compare` names versions by `versionNumber` and SHA. Find the seed's version ID by its `versionNumber`, then get its branch and commit; a Discovery version ID is not a changeset ID:

```bash
artemis --output-format json discovery versions list "<run-id>" --all
artemis --output-format json discovery versions get "<version-id>"   # changesetId, versionSha
```

Create the run with the medium Script, a smaller version budget, and the seed pinned:

```bash
--source-changeset "<changesetId>" --source-sha "<versionSha>"
```

Only the seed's code is copied. In `--task`, give the goal and constraints, the small run's ID, what each shortlisted version changed and its small-tier verdict, and the directions that failed. The new run measures the seed again as its baseline; once the baseline finalizes, check that its `baselineVersionSha` equals `versionSha`.

The shortlisted versions are not part of this run. Measure them on the medium Script with [Compare outside a run](#compare-outside-a-run) before ruling them out. Pick up to three finalists: the medium run's `better` versions, ranked as in step 1, and any shortlisted version that is `better` than the project's code. The medium run's verdicts are against the seed and the shortlist's are against the project's code, so this step only screens; step 3 compares every finalist against the same baseline.

## 3. Full: confirm

Compare each finalist against the project's code on the full Script, with [Compare outside a run](#compare-outside-a-run). Report the gains from those verdicts only. Run a small final Discovery on the full Script only if the user wants more search.

## Compare outside a run

This follows `change-validate` §2–4, with two differences: the version is on a Discovery branch, and the baseline is the project's code, named by its commit.

`compare` takes the project code's readings by commit from every branch and runner that used the same Script, including the baselines of other Discovery runs. Measure on a copy of the tier Script made for one runner and used only there, so its readings all come from that machine. Create a branch whose starting commit is the project's code, once per project, and a copy of the tier Script for your runner, once per tier and runner:

```bash
artemis --output-format json changeset create --project "<project-uuid>" --name "Project code"
artemis --output-format json project scripts create --project "<project-uuid>" \
  --name "<tier> on <runner-name>" --from "<tier-script-id>"
```

Then measure the two sides in turns, one run per call, posting one start block for the series (`artemis`'s *Start block*: Validation started), on that runner with that copy. Start each validation without `--wait`: the response carries its `id` at once. Wait for it with the loop in `repo-command-setup` §5b, and start the next only when it has finished, never while one is still running. Then read the verdict:

```bash
artemis --output-format json changeset validate "<project-code-changeset-id>" --project "<project-uuid>" \
  --version original --script "<runner-script-id>" --runner "<runner-name>"
artemis --output-format json changeset validate "<version-changeset-id>" --project "<project-uuid>" \
  --version "<version-sha>" --script "<runner-script-id>" --runner "<runner-name>"

artemis --output-format json changeset compare "<version-changeset-id>" --project "<project-uuid>" \
  --script "<runner-script-id>" --baseline "<project-sha>"
```

`<project-sha>` is the project's `gitHash`, which is also the small run's `baselineVersionSha`. Always pass `--baseline`. A branch created from `--source-changeset` has the seed as its starting commit, so without it the comparison is against the seed, not the project's code.

The output has a row only for the version: the project code's readings are on another branch, so `compare` uses them without listing them. If the version's `runnerNames` is not exactly your runner, do not report the verdict. Readings of the project's code taken for one version count for the next. Compare after each pair, and stop when the version's `readings` reaches `recommendedReadings`. Check with the user before going past about 10 Script runs per side. Report the verdict, improvement and interval as given.

## Parallel runners

Extra runners shorten the search, not the measurement. Run independent Discoveries or stages on separate runners, for example two small runs exploring different directions. Each run measures its baseline and versions on its own runner, so its verdicts hold, but verdicts from different runs are not comparable. When several small runs ran in parallel, take each run's seed and choose between them with [Compare outside a run](#compare-outside-a-run) on one runner.

Several machines can serve one Discovery when they register with the same runner name and the same user's API key; another user's key makes a separate group. The run's baseline and versions can then land on different machines, and `artemis runner list` does not show which. Share a name only for accuracy-only benchmarks, or for machines the user confirms are identical in hardware, OS, toolchain and load.

Before starting or reusing another runner, get the user's approval as SKILL.md §1 describes, then follow `runner-setup`. A group showing online does not mean every machine takes work: check the run's executions with `discovery-inspect`.

## Checklist

- [ ] Offered because the estimate was longer than the user wanted to wait, or followed a plan already chosen; the estimates were shown and the user chose
- [ ] One verified Script per tier; each run's `--script` fixed for the run
- [ ] Small run gave each version more than one Benchmark run; seed and shortlist taken from `discovery compare` verdicts on the agreed metric
- [ ] Medium run pinned with `--source-sha`; `baselineVersionSha` checked
- [ ] Shortlisted and final versions compared with `changeset compare --baseline <project-sha>`, both sides on one runner with that runner's copy of the tier Script
- [ ] Verdicts, improvements and intervals quoted from `compare`, nothing computed; identical readings flagged, not reported
- [ ] Every extra runner approved by the user; same-name groups used only for accuracy-only benchmarks or confirmed-identical machines
