---
name: maintain
description: Run Artemis Maintain end to end on a project. Author or import Rules, Scan the code for Issues, triage them, fix them with the fix agent, in Discovery or with your own coding agent, ship each fix as a branch or PR, and re-sync outdated Issues as the code moves on. Use when the user wants to scan a project for code-health Issues, set up Rules, or triage, fix or ship Issues.
compatibility: Requires Artemis CLI 1.1.16+ (below 1.2.0) and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.16"
  artemis-cli-max: "1.2.0"
  artemis-platform-min: "3.1.0"
---

# Artemis Maintain

## At a glance

- **Problem:** Finds code-health Issues against a project's Rules, then triages them, fixes them and ships each fix as a branch or pull request.
- **Must be available:** An authenticated CLI and an imported project. No runner, except for Fix in Discovery.
- **Requirements:** `artemis --version` is at least `artemis-cli-min` (1.1.16, which has `issues cancel` and display ids for `fix --discovery`, on top of 1.1.15's `scans get`, `scans cancel`, `--no-limit` and `--lane`); if it is older, load `cli-setup` first.
- **Use / don't use:** Use to scan for Issues, manage Rules, or triage, fix and ship Issues. Not for Discovery runs (load `discovery-start`) or browser walkthroughs (load `platform-tour`).
- **Next skill:** None required. Return to `artemis` routing for other work.

Maintain audits a project against its **Rules**, records each violation as an **Issue** on a board, and helps you triage and fix them:

```
Rules --scan--> Issues (Untriaged) --triage--> Triaged --fix--> Branch --publish/pr--> git branch / PR
                                                   re-sync keeps outdated Issues honest as the code changes
```

The board has four **lanes**: `untriaged`, `triaged`, `in_progress`, `done`. A fix's code changes are a **Branch** in the Web UI; the CLI calls it a **changeset** (`artemis changeset diff <id>`, `Changeset ID` in output).

## Requirements

- `artemis status` OK on the target deployment.
- An imported project with the code to scan (load `project-import` if there is none). Prefer the project **UUID** in anything scripted. `-p/--project` takes a UUID or a name: commands that change something accept only the UUID or the full name, while read commands also match part of a name and print a note on stderr when they guessed.
- For **publish / pr** only: the project's git connection must have push access. Maintain's `publish` and `pr` push to GitHub.
- Optionally `jq`; the snippets use it, but any JSON filter works.

**Ids.** Rules, Issues and Fixes carry display ids (`RUL-12`, `ISS-143`, `FIX-7`). Every `issues` command accepts a UUID, or a display id with `-p <project>` (a plain `fix` from CLI 1.1.18; before that, give it the UUID); `list`, `prompt`, `publish`, `pr` and `submit-local-fix` take `-p` either way. With `fix --discovery`, `-p` is also needed when `--script` is a name. In scripts, lift `.id`.

**Agent runs.** Every step but triage is an agent run: a Scan, a fix (including **Fix again**), Fix in Discovery, a Re-sync and every `maintain chat` turn. Run the ones the user asked for, and the follow-ups this skill names for them, without asking about credits. Ask first only before agent work that is neither, including approving a question card that would start it.

**Question cards.** When an agent run stops on a question, read it with `artemis chat messages <chat-id>` and answer with `artemis chat answer <chat-id> --answer "..."` or `--approve`. If the user says no, answer with `--reject` so the card doesn't sit waiting. Never reply to a card with `chat send`: the card stays unanswered and the agent asks again.

**`--model`** is optional on `scans run`, `issues fix` and `maintain chat`; omit it and the backend chooses. It takes a catalogue UUID or a model-type code (`artemis model list`).

**Waiting.** Never loop without a limit, and don't sleep between tool calls. Check in one shell command with the sleep inside, run with a 10-minute tool timeout (or in the background; lower the loop count if your shell limit is shorter). If it is still running, run the same command again, at most three times in all. The pattern, for a fix:

```bash
for i in $(seq 16); do   # about 8 minutes
  out=$(artemis --output-format json maintain issues get <issue-id> -p <p>) || { echo "issues get failed"; break; }
  s=$(printf '%s' "$out" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("fixStatus") or "")')
  case "$s" in done|failed|cancelled) break;; esac
  sleep 30
done; echo "fixStatus=$s"
```

After three runs with no change, stop waiting and look at why. For a fix, `artemis --output-format json maintain issues fix-runs <id> -p <p>` lists `.runs[]` with `isActive` and `agentRunStatus`: a failed fix run is not written back, so `fixStatus` can sit at `in_progress` for good. If `agentRunStatus` is `failed` or `cancelled`, or the run's chat (`artemis chat messages <chat-id>`) is waiting on a question card, stop and tell the user; with their yes, a fix that is still running can be stopped (§6). Scans and Re-syncs get the same three-run limit.

Before each wait, and after each run of the loop that ends unfinished, say what Artemis is doing (`artemis`'s *Waiting out loud*): a Scan reads the code against its Rules (link: the Maintain page), a fix writes the change on a Branch (link: the Issue's page), a Re-sync re-checks Issues against the current code (link: the Maintain page). There's no typical time for these yet, so give the limit: about 8 minutes a run, three runs at most. For a Scan, add `issuesFound` when `scans get` shows it.

---

## 1. Get Rules in place

Every Rule belongs to one project.

**Import from the default catalogue.** Pick Rules rather than importing all of them: a Scan takes at most 20, and the issue-import Rules (GitHub, JIRA, Sentry) bring in issues from those tools rather than scan the code.

```bash
artemis maintain rules defaults --all
artemis maintain rules import-defaults --project <p> --rule <default-id-1> --rule <default-id-2>
```

**Author one from a prompt.** The maintain agent reads the code, writes the Rule and puts it on the board:

```bash
artemis maintain chat --project <p> --timeout 8m -m "create a rule that flags SQL queries built with string concatenation"
```

Piped or with `--output-format json`, `maintain chat` takes one turn and prints the chat id. If the agent stops on a question card, answer it as above (`chat answer`); use `artemis chat send <chat-id> -m "..."` only to carry on a conversation the user asked for. If a turn hits `--timeout` the CLI exits 6 but the agent keeps working: follow it with `artemis chat get <chat-id>` rather than starting another turn.

**Author one from markdown:** `artemis maintain rules create --project <p> --markdown-file rule.md`.

A **Draft Rule** scans nothing. Check before you spend a Scan:

```bash
artemis --output-format json maintain rules list --project <p> --all \
  | jq -r '.docs[]? | "\(.displayId // .id)\t\(.isDraft // false)\t\(.name)"'
```

`rules delete` also deletes the Rule's Issues and Scans and cannot be undone. Name the Rule and how many Issues go with it, get the user's yes, then run `rules delete <rule-id> --project <p> --force` (with no terminal, or in JSON mode, it refuses without `--force` and exits 7: that means not confirmed, so ask rather than retry). Never delete a Rule someone else wrote.

## 2. Run the Scan

Once the Rules are in place:

```bash
artemis maintain scans run --project <p> --rule <rule-id> --count 10
```

- `--rule` is required and repeatable, up to 20 Rules per Scan.
- Once it starts, post the start block (`artemis`'s *Start block*): Scan started.
- `--count` is about how many Issues to surface (default 5), the Web UI's "Approximate number of issues": a target, not a guarantee. It takes 1-100, and `--no-limit`, instead of `--count` (the two can't be combined), asks for no limit, as the Web UI does, using more tokens.
- `--focus "<text>"` points the Scan at part of the code, like the Web UI's "What to focus on". `--commit <sha>` scans that commit instead of the project head. There is no `--path`.

The Scan runs in the background; capture its `id`. Check on it with `scans get <scan-id> --project <p>` in the waiting pattern above, breaking on `.status` `done`, `failed` or `cancelled`. Stop a Scan, after the user's yes, with `scans cancel <scan-id> --project <p> --force` (without `--force` it asks, and with no terminal or in JSON mode exits 7); it keeps what it already found. (`--wait --timeout` also exists, but its 20-minute default outlasts an agent's shell.)

## 3. Check it found something

`done` means the Scan ran, not that it found anything. `scans get` shows `issuesFound` and whether the target was met. If it found none where you expected some:

- the Rules may still have been drafts when it ran (§1);
- `--commit` or `--focus` may point away from the relevant code;
- a broader or differently worded Rule may do better; the wording drives recall.

## 4. Read the board

The board in the Web UI: `<deployment-base-url>/projects/<project-id>/maintain/issues`. Give the user that link with your summary, and draw the board's chart with it without being asked: severity, and severity by lane (the Maintain issues report in `discovery-visualize`, `references/maintain-report.md`). With no open issues, or one, answer in text and offer the chart.

```bash
artemis maintain issues list --project <p> --severity high                       # open, high severity
artemis maintain issues list --project <p> --validity true_positive --fix-status not_set   # waiting for a fix
artemis maintain issues list --project <p> \
  --validity true_positive --fix-status not_set --sort size_of_fix --order desc
artemis maintain issues get ISS-143 -p <p>
```

`issues list` shows open Issues by default; `--status closed` is the Archive and `--status all` both. It also filters on `--rule`, `--severity`, `--validity`, `--fix-status`, `--sync-status`, `--complexity` and `--path-prefix`, sorts with `--sort`/`--order`, and pages with `--all`. `--lane` filters by board lane.

## 5. Triage before you fix

Scan results are agent-written: not every Issue is real, and a fix aimed at a false positive wastes a run. All three commands take several ids:

```bash
artemis maintain issues confirm <id>...   # true positive
artemis maintain issues dismiss <id>...   # mark as a false positive, which also archives it
artemis maintain issues archive <id>...   # off the board, triage unchanged (won't fix, duplicate)
```

`unarchive` puts an archived Issue back.

## 6. Fix

Three routes. If the user hasn't named one, offer them with a recommendation. The local-agent route spends nothing on the platform.

### The fix agent

```bash
artemis maintain issues fix <issue-id>... [--model <model>]
```

- All the Issues in one call land in **one Branch** and one fix chat. Group related Issues; put unrelated ones in separate calls so each gets its own Branch and PR. They can't be split afterwards.
- It returns a `Changeset ID` and a `Fix Chat ID` straight away and works in the background; post the start block (`artemis`'s *Start block*): Fix started, opening the Issue's page (`<deployment-base-url>/projects/<project-uuid>/maintain/issues/id/<issue-uuid>`, the link `maintain issues get` prints). Follow it with `artemis chat messages <fix-chat-id>`, and wait on `fixStatus` with the pattern above.
- The terminal `fixStatus` values are `done`, `failed` and `cancelled`. There is no `fixed` or `complete`.
- `done` can still be an empty Branch. Check `artemis changeset diff <changeset-id> --project <p>` before shipping, and give the user the Branch link (`<deployment-base-url>/projects/<project-uuid>/branches/<changeset-id>/changes`, `cli-follow-along` §2) once it has changes; don't judge by `publish`/`pr` output, which reads empty for every unpublished fix. If the diff is empty, **Fix again** (run `fix` on the Issue again); if it is still empty, the Issue is probably already fixed, so re-sync it (§8).
- Stop a running fix, after the user's yes, with `artemis maintain issues cancel <ISS-n> -p <p> --force` (the Web UI's Stop). It reports `not_running` when nothing is running, and refuses a local attempt and a Fix in Discovery (cancel its run instead).
- Every attempt is kept: `artemis maintain issues fix-runs <id> -p <p>` lists them, and the Issue reflects the latest. Trying a different `--model` on a second attempt loses nothing.

### Fix in Discovery

For a large fix, or one worth measuring, the Web UI's **Fix in Discovery** hands the work to a Discovery run that tries competing fixes and scores them. The command starts the run in one call, from the board: each Issue gets a fix attempt and moves to In Progress. Nothing asks about settings: whatever is left unset takes the project's own settings (execution mode, script, runner, model, Benchmark runs) and a budget of 10 versions. So agree them with the user first, as `discovery-start` does for any run: the model, the number of versions, the runner and script, the Benchmark runs per version (decided as in `discovery-start`), and that the run also scores AI Metrics. Then pass them all:

```bash
artemis maintain issues fix <ISS-n> --discovery --project <p> \
  --model <model> --versions <n> --runner <runner> --script <script> --repeats <runs>
```

- It prints the `Discovery Run ID` straight away (`discoveryRunId` with `--output-format json`). Post the start block (`artemis`'s *Start block*): Fix in Discovery started, opening the run.
- `--repeats` sets the run's Benchmark runs per version. With `--execution-mode skip` (no runner) nothing is measured: leave out `--runner`, `--script` and `--repeats`.
- Fix in Discovery always scores AI Metrics: the board's endpoint has no switch for them and the CLI no flag. If the user says no to them when agreeing the settings, start the run with `discovery-start` instead.
- An offline-runner warning (given only for a `--runner` you name) does not stop the start: once the `Discovery Run ID` prints, get the runner up within about 5 minutes (`runner-setup`) or the baseline fails.
- A refusal starts nothing and says why. With no default script or runner on the project (422), pass `--script` or `--runner` as the CLI says; use `--execution-mode skip` only if the user agreed to an unmeasured run.
- One Issue the board can't fix refuses the whole call (409, "Nothing was started"). A fix already running: wait for it, or with the user's yes stop it (`issues cancel`, §6, or for a Fix in Discovery `artemis discovery cancel <run-id>`, with `discoveryRunId` from `issues fix-runs`). Out of date: re-sync it (§8). Archived or dismissed: check `issues get`; if it was dismissed as a false positive drop it, otherwise `unarchive` it if the user wants it fixed. No longer matching the code: drop it. Then run the rest again.
- Up to 5 Issues per run, all from one project, and only Issues that share one goal. Follow the run with the `discovery-inspect` skill.

### Your own coding agent

The Web UI's **Copy for local agent**:

```bash
artemis maintain issues prompt <id>... --project <p> | my-coding-agent
```

In text mode only the prompt goes to stdout. While that agent works in the user's checkout, put its progress on the board and bring the fix back as a Branch:

```bash
artemis maintain issues transition <id> --to in_progress --source local_agent -p <p>
artemis maintain issues submit-local-fix <id>... --project <p>  # uploads the changed files, moves them to done
```

- Leave the fix uncommitted, on the project's current head: it uploads what differs from `HEAD`, so committed work shows no changes, and it refuses if the checkout has moved past the commit the fix is based on.
- It sends modified tracked files only. Add new files with `--include-untracked`, or name exact files with `--path`.
- Issues fixed by one edit go in one call, so they share the Branch.
- `--keep-open` attaches the Branch without moving the Issue to done.
- Then link the Branch, from the Issue's `changesetId` (`maintain issues get`), as for the fix agent.
- Don't move an Issue to `done` by hand when you have a fix to attach: once it is done, no Branch can be attached.

## 7. Ship: branch and/or PR

`issues publish` and `issues pr` both need the Issue to have a fix Branch, and both are idempotent: a published Branch keeps its git branch, and an Issue that already has a PR reports it rather than opening another.

```bash
artemis maintain issues publish <id> --project <p>   # git branch, no PR
artemis maintain issues pr <id> --project <p>        # publish if needed, then open a PR
```

`pr` takes its title and description from the Issue and targets the branch the project was imported on, falling back to `main`; override with `--title`, `--description` and `--base`. The git branch is named after the Issue's display id plus a random number, like `artemis/iss-143-04217`.

A Fix in Discovery leaves no Branch on the Issue; its versions are in the Discovery run. Find the run with `artemis --output-format json maintain issues fix-runs <id> -p <p> | jq -r '[.runs[] | select(.discoveryRunId)] | last | .discoveryRunId // empty'`, pick a version with `discovery-inspect`, and open a PR from that version's `changesetId` with `artemis changeset pr <changeset-id> --project <p>`. `changeset pr` refuses a branch that already has a PR.

## 8. Re-sync outdated Issues

The code moves on: an Issue may already be fixed, have moved, or no longer apply. Each Issue has a **sync status**: `current`, `outdated` (its file or its Rule changed) or `obsolete`; `issues list --sync-status` filters on it. A **Re-sync** re-checks Issues against the current code. It is an agent run:

```bash
artemis maintain syncs run --project <p>                     # every outdated Issue
artemis maintain syncs run --project <p> <issue-id>...       # only these
artemis maintain syncs list --project <p>
```

Syncs run in the background like Scans. There is no `syncs get`: match the sync id in `syncs list` (status `done`, `failed` or `cancelled`) within the waiting pattern. Then re-read the board (`issues list --sync-status outdated`) before acting on old Issues.

## Checklist

- [ ] CLI at least 1.1.16; project UUID confirmed.
- [ ] Rules in place and none still drafts.
- [ ] Agent runs started for what the user asked, with no credits question; the user said yes before agent work they didn't ask for, `issues cancel` and `rules delete`.
- [ ] For Fix in Discovery, the model, versions, runner and script, Benchmark runs and AI Metrics were agreed with the user and passed as flags.
- [ ] The Scan reached `done`, and `issuesFound` is checked, not assumed.
- [ ] Issues triaged before any fix; unrelated Issues in separate `fix` calls.
- [ ] Waited on `fixStatus` with a bounded check, at most three runs, then checked `fix-runs` and the chat.
- [ ] The Branch is non-empty (`changeset diff`) before `publish`/`pr`; git connection can push.
- [ ] Outdated Issues re-synced before trusting old ones.
