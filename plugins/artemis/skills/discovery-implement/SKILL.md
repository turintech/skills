---
name: discovery-implement
description: "Implement the versions of an Artemis discovery run on your own machine: start a run and have its agent open versions for claim, claim them, write the change, hand it over to be run and scored, and repair it if its run fails. Use when asked to work on, pick up or implement versions of a discovery run, or to run a discovery with the implementation done locally."
compatibility: Requires Artemis CLI 1.1.23+ (below 1.2.0) and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.23"
  artemis-cli-max: "1.2.0"
  artemis-platform-min: "3.1.0"
---

# Implement a discovery run's versions

## At a glance

- **Problem:** Lets a local agent write the code for a discovery run's versions while the run plans, runs and scores them on its runners.
- **Must be available:** An authenticated CLI and a discovery run ID, or a project with a Script and a runner to start one.
- **Requirements:** `artemis --version` is at least `artemis-cli-min` (1.1.23, which has `discovery claims`); if it is older, load the skill and follow `cli-setup` first.
- **Use / don't use:** Use to implement versions yourself; use `discovery-start` for a run the platform implements itself, and `discovery-steer` to redirect a run without writing its code.
- **Next skill:** Use `discovery-inspect` to read the scored versions against the baseline.

A discovery run's agent plans versions and runs and scores every version on the
run's runners. You implement the versions it opens for claim. You never run the
benchmark yourself: hand the commit over and the run measures it.

Every command takes `--output-format json`; use it whenever you read a result.
The run's project id and chat id are in
`artemis discovery get <run-id> --output-format json` (`projectId`, `chatId`).

## 0. Starting a run to implement yourself

Skip this when you were given a run.

```bash
artemis project scripts list --project <project-id>     # pick the script; the default one is marked
artemis runner list                                      # pick the runner
artemis discovery create --project <project-id> --task "<the goal>" --model <model> \
  --script <script-id> --runner <runner> --versions <N> --execution-mode test --output-format json
```

`--execution-mode test` builds and tests each version but scores it on the
AI-judged metrics only. `benchmark` (the default) also measures it. The output
has the run's `id` and `chatId`. Then ask its agent to delegate to you:

```bash
artemis chat send <chat-id> --wait --timeout 9m --message "This is <who you are>. Please open all <N> versions of this run for claim so I can implement them instead of your coders. I'll claim each one, implement it and hand it back for you to run and score."
```

`--wait` returns once the agent has replied, while the run carries on.

A version nobody has claimed 30 minutes after it was opened for claim goes to one of the
run's own coders. If you may be slower than that, say so in the same message:
add "Wait for me: don't hand any of them to a coder." and the agent leaves them.

## 1. Take a version

```bash
artemis discovery claims available <run-id> --wait --timeout 9m   # blocks until one is open for claim
artemis discovery claims take <version-id> --source "<who you are>" --out ./v<N>
```

`available --wait` returns as soon as a version is waiting to be implemented,
or one of yours came back for repair (listed under "Back for you to repair").
It exits 10 when the run has ended, so nothing more will come, and 6 on
timeout: run it again to keep waiting. The agent may open several at once: take them one after another, and
soon: a version nobody takes within 30 minutes goes to one of the run's coders,
unless you asked the agent to wait for you. That is separate from `--timeout`,
which is only how long this command waits for a version to claim.

`--source` is how people and the run's agent will know you, such as
`claude-code on alice's laptop`. `--out` downloads the version's code into a
new directory. When the version builds on another (`sourceVersionId`), `take`
first brings that version's change in, so the directory already has it. If the
download fails after the claim, the error says how to download it again or
release the claim.

A claim lasts 30 minutes from the last command you ran on the version. While
you work, run one at least every 20 minutes, or
`artemis discovery claims renew <version-id>`. A claim that lapses can be taken
by someone else. A refused claim (exit 1) means it is no longer open for claim:
someone got there first ("claimed by ..."), or it waited too long and the run
gave it to a coder. Take another.

Nothing available, or an idea of your own? Ask the run's agent to open a
version for it:

```bash
artemis chat send <chat-id> --wait --timeout 9m --message "Please open a version for <idea> for me to claim and implement"
```

To try an idea yourself without waiting for the agent, register it as a
version of your own under one of the run's experiments:

```bash
artemis discovery versions submit <run-id> --root ./my-idea --experiment <experiment-id> \
  -m "<what changed>" --source "<who you are>"
```

While the run's agent is working, it runs and scores the version; it doesn't
count against the run's budget. Don't run it yourself: a version handed to the
agent is refused with "handed to the run's agent".

In a manual run the agent only opens versions of a queued experiment for claim. While
the run waits for your review, queue the experiment and ask in the same step:

```bash
artemis discovery resume <run-id> --queue <experiment-id> -m "Please open a version of it for me to claim and implement"
```

## 2. Read what it is for

```bash
artemis discovery versions get <version-id> --output-format json
artemis discovery experiments get <experiment-id> --output-format json
```

The version's brief (`llmRationale`) says what to change and why, and its
experiment's hypothesis says what the run is testing. Read both before writing
code.

## 3. Write the change

Edit files under `./v<N>`. Keep the change to what the brief asks. Compile it
or run the tests if that is quick; do not run benchmarks. If the project
doesn't build on your machine, compile what you changed, and say what you
checked in the `-m` message.

## 4. Hand it over

```bash
artemis discovery claims submit <version-id> --root ./v<N> \
  -m "<what you changed, where, and why; what you checked>"
```

This saves the directory, hands the new commit to the run, and tells the run's agent, which runs and scores the version. Files the project's
`.gitignore` leaves out are not saved. A new or changed file that looks like it
holds credentials is refused; name it with `--allow-secret-path <path>` only if
it really belongs in the version. If telling the agent
fails, `submit` exits 1 with "v<N> was handed over, but the run's agent could
not be told": run the same command again, which is safe to repeat. While the
run has the version your claim doesn't run down, so don't renew it; the claim
starts again if the version comes back to you.

Then go back to step 1 for the next one.

## 5. Follow it to a result

```bash
artemis discovery versions get <version-id> --output-format json
artemis discovery compare <run-id>        # every version against the baseline
```

`claims available --wait` already wakes you when a version comes back for
repair, so you don't need to poll each version. Read its `lifecycle`
(`generated`, then `scoring`, while it runs) until it settles:

- `lifecycle: completed`: scored. Its `fitnessScore` and the run's comparisons
  are the result. Done.
- Back to `generating`, with the failure and its log in `failureReason`:
  its run failed and it is yours to repair, under a fresh 30-minute claim. Fix
  the code in the same directory and `claims submit` again. If the failure
  isn't your code's, submit with `--sha` and the same commit to re-run it. If
  it can't be fixed, `claims release` it, which closes it. A repair whose
  claim lapses is closed too.
- `scoring_failed` or `generation_failed`: closed. The reason is in its
  `failureReason`. Nothing more to do.

To read what the run's agent said, `artemis chat messages <chat-id>` shows the
conversation; `--events` shows every event.

## Giving it back

`artemis discovery claims release <version-id>` returns a version you haven't
submitted for someone else to take. Release what you won't finish rather than
letting the claim lapse.
