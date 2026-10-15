---
name: discovery-split
description: Split a strong Discovery version into atomic changes and have the Discovery build and measure each one, then combine the changes that earn their place into small pull requests with before and after numbers. Use when a version is good but bundles several ideas, when a reviewer needs to know which edit produced the gain, or when the user wants mergeable pull requests out of a Discovery run.
compatibility: Requires Artemis CLI 1.1.15+ and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.15"
  artemis-platform-min: "3.1.0"
---

# Split a version into atomic changes and turn them into pull requests

## At a glance

- **Problem:** The best version of a run often carries many ideas in one diff. Reviewers cannot tell which edit produced the gain, which ones only help the benchmark, and which ones carry risk, so they accept or reject the whole thing. Splitting it, measuring each part and keeping the parts that earn their place turns one hard review into a few easy ones.
- **Must be available:** an authenticated CLI, a Discovery run with the version to split, and the run's runner online.
- **Use / don't use:** Use on a version whose gain is real (measured, ideally checked with `change-validate`) and whose diff holds more than one idea. Don't use on a version with a single idea; validate and open its pull request directly.
- **Next skill:** `change-validate` for the paired check on the combined result; the run's pull request flow for publishing.

## 1. Read the version

```bash
artemis --output-format json discovery versions get "<version-id>"      # changesetId, versionSha, experimentId
artemis discovery metrics "<run-id>" --stats                            # its measured gain and noise
artemis changeset download "<changeset-id>" --project "<project-uuid>" --version "<sha>" --out "<version-dir>"
```

Compare the version with the run's baseline (`discovery get` gives `baselineChangesetId` and `baselineVersionSha`; download it the same way) and read the whole diff.

## 2. Find the atomic changes

Group the hunks into changes that each carry one idea and could be reviewed on their own: a new data structure, a precomputed value, a fast path, a prefetch, a layout change. Keep a change whole when its hunks only make sense together. For each change write down:

- what it does in one sentence, and the functions and files it touches
- whether it needs another change to compile or to be correct (keep such chains small)
- its risk: behaviour or ordering changes, shared code outside the target area, security-relevant edits such as hashing or bounds checks, and anything that only pays off on the benchmark's inputs

Show the user the list as a table (change, files, depends on, risk) and agree it before spending anything. Five to ten changes is typical.

## 3. Let the Discovery build and measure each change

Add each change to the run as an experiment, with enough detail that the Discovery agent can build exactly that change from the version's diff:

```bash
artemis --output-format json discovery experiments create "<run-id>" --created-by user \
  --title "Split v<N> · <short name>" \
  --hypothesis "Apply only this change from v<N> (changeset <changeset-id> at <sha>) on top of the baseline: <what it does>, in <functions/files>. Nothing else from v<N>. Expected effect: <metric and direction>." \
  --parent "<v<N>'s experiment id>"
artemis discovery experiments update "<experiment-id>" --status queued
```

Queued experiments are the user's selection, so the agent builds them first. Then give the run budget for one version per change plus one for the combination, and tell the agent what to do. Both commands dispatch agent work that spends credits; confirm the count with the user first:

```bash
artemis discovery continue "<run-id>" --versions <changes + 1>
artemis discovery steer "<run-id>" --message "Build each queued 'Split v<N>' experiment as one version on the baseline, copying only the hunks it names from v<N>'s diff (view_diff on changeset <changeset-id>). Do not seed from v<N>. When they are measured, build one more version that combines the changes that beat the baseline by more than the noise and are not marked high risk."
```

The runner measures every version with the run's repetitions. Measure the changes on the baseline, one at a time, so each number is that change's own contribution; their sum can differ from the whole version when changes interact, and the combination version shows the real total.

When a coding agent is working alongside the run (`discovery-collaborate`), it can build some of the parts itself and send them back as versions; the measurement is the same.

## 4. Decide what ships

```bash
artemis discovery metrics "<run-id>" --stats
```

For each change: its gain against the baseline, the spread of its measurements, whether that clears the noise, and its risk. Keep the changes that clear the noise and whose risk the user accepts; drop changes that do nothing, that help only the benchmark, or whose risk outweighs their gain. Confirm the combined version with a paired, alternating comparison against the baseline (`change-validate`).

## 5. Pull requests with before and after

Open one pull request per kept change, or one for the combination when the changes depend on each other. Each description carries:

- what the change does, in plain words, and the files it touches
- the baseline and the change's numbers side by side, with the number of measurements and the spread
- the tests that ran and passed
- its risk and anything a reviewer should check

## Checklist

- [ ] The version's gain is real and its diff holds more than one idea
- [ ] Changes listed with files, dependencies and risk, and agreed with the user
- [ ] One queued experiment per change, each naming the exact change and the source version
- [ ] User agreed to the extra versions and credits before `continue` and `steer`
- [ ] Each change measured on the baseline alone; a combination version built from the winners
- [ ] Combination confirmed with a paired comparison
- [ ] Pull requests carry before and after numbers, measurement counts, tests and risk
