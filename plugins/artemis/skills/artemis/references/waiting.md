# Starting and waiting on Artemis work

Every skill that starts work in Artemis follows this page: post the start block, say what Artemis is doing, and wait in bounded loops. Read it by path; you don't need to load the `artemis` skill.

## Start block

Post it right after a command starts work in Artemis, and before waiting on it; when the command runs with `--wait`, post it just before. One block per start, as reply text with nothing around it: no banners or ASCII art.

```text
Artemis · Discovery started
Project   <project name>
Goal      <taskDescription>
Versions  <n> · model <model> · LLM council <review models>
Open      <link>
```

Title `Artemis · <kind> started`, or `Artemis · Discovery continued` after `discovery continue`. Pad the labels to one column. Rows by kind:

| Kind | Rows |
|---|---|
| Discovery, Fix in Discovery | Project, Goal (`taskDescription`), Versions (count · model · LLM council, as passed; leave out `· LLM council …` when no review models were passed), Benchmark runs (only when `--eval-runs` or `--max-runs`, or for Fix in Discovery `--repeats`, was passed) |
| Discovery continued | Project, Versions (`+<n>`, budget now `numVersions`) |
| Scan | Project, Rules (names), Target (`<n>` issues, or `no limit`), Model |
| Fix | Project, Issues (display ids), Model |
| Validation | Project, Version (`original`, `latest` or the SHA), Script (name), Runner. A series of validations (pairs, turns) gets one block at its start |

Take values from the command's response and from what you passed: names, not ids, and model codes, not catalogue UUIDs. Get a missing project name from `artemis --output-format json project get <project-id>` (`.name`, CLI 1.1.16+), or on older CLIs from `artemis --output-format json project list --all` (the entry whose `id` matches). Leave out a row you don't know; never guess.

`Open` is last and a bare full URL, since links don't render inside a code block: the base URL `artemis status` reports plus the path in `cli-follow-along` §2's table (a validation: `<deployment-base-url>/projects/<project-id>/branches/<changeset-id>/validations`). When the path for your kind isn't listed here or in the calling skill, or the deployment's path shape isn't known, use the project link: `<deployment-base-url>/projects/<project-id>`.

## Waiting out loud

While Artemis works, never go quiet and never paste a raw status line on its own. Each wait gets two kinds of line:

1. **Before the wait:** what Artemis is doing, where, how long it should take, and the start block's `Open` link. Shape: `Artemis is <doing X> on <runner>; this usually takes about <N> min. Follow it at <link>.`
2. **After each check loop that ends unfinished:** the time since the start block, the status and any count the response gives, and how much longer you will check. Shape: `Artemis is still <doing X>, <M> min in: <status>, <count>. I'll check for up to <K> more minutes.`

Take the expected time only from a measurement: the phase durations `repo-command-setup` §5a records, an earlier run of the same script in this session, or a figure the calling skill measured. With none, say there's no typical time yet and give the check limit instead (`I'll check for up to <K> min`); never invent a figure.

## Bounded waits

Wait in one shell call with the sleep inside it: a check every 30 seconds, at most 16 checks (8 minutes). Give that call a 10-minute shell timeout, or run it in the background; lower the count if your shell's limit is shorter. Never a foreground `sleep` between tool calls, and never a loop without a limit. If the CLI call inside the loop fails, the loop stops and says so instead of waiting out the 8 minutes.

If it is still unfinished after the second loop, stop and find out why with `execution-log-inspect` (or the owning skill's own check), then tell the user. Never start the same work again to get unstuck. A Discovery run's own long waits, and Maintain's three-run limit, are set in `discovery-start` and `maintain`.

A Script run (a validation) waits with the loop in [script-run §3](../../script-run/SKILL.md#3-wait), read by path, on `changeset validation get`, never `changeset validate --wait`: when `--wait` times out (exit 6) or a status check fails, the CLI exits without printing the validation's id, and no command lists a branch's validations, so the run can no longer be followed.
