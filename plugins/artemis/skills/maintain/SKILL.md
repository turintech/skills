---
name: maintain
description: Run Artemis Maintain end to end on a project — author or import rules, scan the code for issues, triage the findings, fix them with the fix agent, ship each fix as a branch or PR, and resync stale issues as the code moves on. Use when the user wants to scan a project for code-health issues, set up maintain rules, or triage/fix/ship maintain findings, including fixing an issue by experiment with discovery.
---

# Artemis Maintain

Maintain (backed by the **code-warden** service) audits a project against a set
of **rules**, records each finding as an **issue** on a board, and helps you
triage and fix them. The whole flow:

```
rules ──scan──▶ issues ──triage──▶ confirmed ──fix──▶ changeset ──publish/pr──▶ branch / PR
                                                                                    │
                                                              syncs keep the board honest as code changes
```

You can also do all of this by talking to the **maintain agent**
(`artemis maintain chat`). It reads the board and the code, and it can write
rules, raise issues, and start scans and fixes.

The lifecycle of one issue:

```
open ──confirm──▶ true_positive ──fix──▶ changeset ──publish──▶ branch ──pr──▶ pull request
  │
  └──dismiss──▶ false_positive (closed)     └──close──▶ closed (validity untouched)
```

Maintain does **not** need a runner or a benchmark harness: it reads the code,
it doesn't build or execute it. All it needs is an imported project.

## Requirements

- `artemis status` OK on the target deployment.
- An imported project with the code you want scanned (see
  [project-import](../project-import/SKILL.md)). Capture the project **UUID** —
  names collide the moment a project is imported twice, so prefer the UUID in
  anything scripted. `-p/--project` accepts a UUID *or* a name, but a name errors
  on ambiguity.
- For **publish / pr** only: the project's git provider must be connected with
  push access (the same GitHub connection `project-import` relied on). PRs are
  opened against GitHub.
- Optionally `jq`. Snippets below use it to filter `--output-format json`, but it
  is just one option — any JSON filter works (e.g. `python3 -c`).

Every rule and issue carries a human-friendly **display ID** (`RULE-7`,
`ISS-143`) shown for readability, but **all commands take the UUID** as their
argument. Lift `.id`, not `.displayId`, into anything scripted.

## `--model` — optional

The commands that dispatch an agent (`scans run`, `issues fix` and
`maintain chat`) take
`--model`, and it is **optional** — omit it and the backend picks a default.
When you do pass it, it accepts either a catalogue **UUID** *or* a model-type
code, so you don't have to go hunting for a UUID:

```bash
artemis maintain scans run --project <p> --rule <r> --model claude-sonnet-5
```

`artemis model list` shows the legal preset codes.

---

# Phase 1 — Scan

## 1. Get rules in place

A scan runs against one or more **rules**, each describing what to flag. Every
rule belongs to one project. There are three ways to get rules.

### Fastest: import the default catalogue

```bash
artemis maintain rules defaults                       # browse the catalogue first
artemis maintain rules import-defaults --project <p>  # import them all
# ...or cherry-pick:
artemis maintain rules import-defaults --project <p> --rule <default-id-1> --rule <default-id-2>
```

### Write one in markdown

```bash
artemis maintain rules create --project <p> --markdown-file rule.md
artemis maintain rules update <rule-id> --project <p> --markdown-file rule.md   # rewrite
artemis maintain rules update <rule-id> --project <p> --name "No raw SQL"        # rename
```

The file *is* the rule: a name, plus sections for what to scan for, how to fix
it and what to check on review. It is stored as written.

### Describe it and let the maintain agent write it

`rules create` has **no `--prompt` flag**. To get a rule from a description,
ask the maintain agent. It reads the project's code before writing the rule:

```bash
artemis maintain chat --project <p> \
  -m "create a rule that flags SQL built by string concatenation"
```

Confirm what you'll scan against before spending a scan:

```bash
artemis --output-format json maintain rules list --project <p> \
  | jq -r '.docs[] | "\(.displayId // .id)\t\(.isDraft)\t\(.name)"'
```

A rule marked `[DRAFT]` (`isDraft`) has no scan description yet, and a scan
against it finds nothing. Rules from markdown or from the catalogue are normally
complete; draft rules are also skipped when rules are copied.

> **`rules delete` cascades.** Deleting a rule also removes its issues and
> scans, and cannot be undone. It prompts unless you pass `--force`; there's no
> undo, so don't `--force` a rule someone else authored.

## 2. Run the scan

```bash
artemis maintain scans run --project <p> \
  --rule <rule-id> \
  --count 10 \
  --wait
```

- `--rule` is **required and repeatable** (max 20 rules per scan). Only
  non-draft rules produce findings.
- `--count` (default 5, range 1–1000) is the *target* number of issues to
  surface — a ceiling the agent aims for, not a guarantee.
- `--path` (repeatable) restricts the scan to a subtree; `--commit <sha>` pins
  it to a specific commit instead of project head.
- `--wait` blocks until the scan reaches a terminal state (`done` or `failed`),
  with `--timeout` (default 20m; exit code 6 on expiry). Without `--wait` the
  scan runs in the background and the command returns immediately.

Capture the scan `id` from the JSON. Note there is **no single-scan GET
endpoint** — to check on a backgrounded scan you match its ID in the list:

```bash
artemis --output-format json maintain scans list --project <p> \
  | jq -r '.docs[] | select(.id=="<scan-id>") | .status'
```

## 3. Verify it actually surfaced issues — `done` is not `found something`

**A scan can finish `done` having recorded zero issues.** That's not
necessarily a bug (the code may genuinely be clean for that rule), but a `done`
status alone tells you the scan *ran*, not that it *found* anything. Check the
board:

```bash
artemis --output-format json maintain issues list --project <p> \
  | jq '{total: .totalDocs}'
artemis maintain issues list --project <p> --severity high --status open
```

If a scan you expected to be productive comes back with no issues:

- Confirm the rules were **not drafts** when the scan ran (§1). A scan
  against a draft rule surfaces nothing.
- Check `--path` / `--commit` didn't scope the scan away from the relevant code.
- Try a broader or differently-worded rule; rule phrasing drives recall.

### Or hunt for it in conversation

When you have a specific problem in mind, describing it can work better than a
scan. Narrow it down with the agent over a few turns, then have it raise the
issue:

```bash
artemis maintain chat --project <p> \
  -m "is there anywhere we parse the same response twice?"
```

At a terminal this is a back-and-forth session; send an empty line to end it.
Piped, or with `--output-format json`, it runs **one agent turn** and exits.
Continue with `artemis chat send <chat-id> -m "..."`. `--timeout` (default 10m,
exit code 6) limits each turn. Issues raised this way go on the board like any
others.

---

# Phase 2 — Triage, fix, and ship

## 4. Read the board

```bash
# Everything open, worst first
artemis maintain issues list --project <p> --severity high --status open

# Confirmed true positives that still need a fix, biggest first
artemis maintain issues list --project <p> \
  --validity true_positive --fix-status not_set --sort size_of_fix --order desc

# One issue in full
artemis maintain issues get <issue-id>
```

`issues get` also shows what the board will let you do next:

- `affordances`: `canFix`, `canFixAgain`, `canRetryFix`, `canFixInDiscovery`,
  `canConfirm`, `canArchive`, `canResync`, and so on.
- `allowedTransitions`: the lanes the issue can move to right now.

The backend decides these from the issue's full state, so **read them before
you dispatch anything**. Don't try to work the rules out yourself.

`issues list` filters on `--rule`, `--severity`
(critical|high|medium|low|info), `--status` (open|closed), `--validity`
(true_positive|false_positive|not_set), `--fix-status`
(not_set|pending|in_progress|done|failed|cancelled), `--sync-status`,
`--complexity` (small|medium|large) and `--path-prefix`; it sorts on
`--sort`/`--order` and paginates with `--all`.

## 5. Triage — before you fix

A scan's findings are agent-generated: **triage before you fix.** Not every
finding is a true positive, and firing the fix agent at noise wastes a run.

```bash
artemis maintain issues confirm <issue-id> [<issue-id>...]   # → true_positive
artemis maintain issues dismiss <issue-id> [<issue-id>...]   # → false_positive + closed
artemis maintain issues close   <issue-id> [<issue-id>...]   # → closed, validity untouched
```

All three take **multiple IDs**. `confirm` marks genuine findings so you can
batch-fix them; `dismiss` is for false positives (records *why* the board
shrank); `close` retires an issue without judging it true/false (won't-fix,
duplicate).

## 6. Fix — dispatch the fix agent

```bash
artemis maintain issues fix <issue-id> [<issue-id>...] [--model claude-sonnet-5]
```

- Takes **multiple issues**; **all their fixes land in one changeset** and the
  agent's work streams into **one fix chat**. Group related issues; keep
  unrelated ones in separate `fix` calls so each gets its own changeset/PR.
- The command returns a `ChangesetID` and a `FixChatID` and then **returns
  immediately** — the agent works in the background. Follow it:

```bash
artemis chat messages <fix-chat-id>          # watch the fix agent's tool calls
artemis maintain issues get <issue-id>       # ChangesetID / FixStatus / PRUrl fill in
```

**The terminal `fixStatus` values are `done`, `failed` and `cancelled`, not
`fixed`.** `pending` and `in_progress` mean the fix is still running. There is
no `fixed` or `complete` state, so a loop that waits for one never ends, even
after the fix has finished. If a fix's worker dies without reporting, the
backend eventually marks the fix `failed`. Poll like:

```bash
until fs=$(artemis --output-format json maintain issues get <issue-id> \
             | jq -r '.fixStatus'); \
      case "$fs" in done|failed|cancelled) true;; *) false;; esac; do sleep 20; done
```

**`done` ≠ produced a real edit — verify the changeset is non-empty before you
ship.** `fix` returning a `ChangesetID` means the agent was *dispatched*, not
that a fix exists; a fix can even reach `fixStatus: done` having written
nothing. The tell is in the `publish`/`pr` output: a `numberOfCommitsAhead` of
`0` (and a description of **"Empty branch with no modifications"**) means the
changeset is empty — publishing it ships nothing useful. If it's empty, don't
ship it: re-run `fix`, and if it's *still* empty, the bug was likely already
fixed upstream (check with a `syncs run`, §8) — the changeset base sitting
several commits *behind* the branch is a hint the finding is stale.

### Retry, and compare attempts

A new `fix` on the same issue doesn't replace the earlier attempt. Each attempt
is a separate **fix run** with its own changeset and chat, and the issue's fix
fields show the latest one. That lets you retry a bad fix, for example with a
different model, and compare the results:

```bash
artemis maintain issues fix <issue-id> --model claude-sonnet-5
artemis maintain issues fix-runs <issue-id>      # every attempt; the latest is marked active
```

Check `affordances.canFixAgain` / `canRetryFix` first.

### Fix by experiment: `--discovery` (not `discovery create`)

Use a discovery run when:

- the user asks to fix an issue **with discovery**,
- the right fix isn't obvious,
- several approaches are worth comparing, or
- the finding is about performance, memory, cost or accuracy.

The board recommends discovery for issues whose fix complexity is `large`. The
run proposes several fixes, builds each one as its own version, and scores them
against the project's baseline. Start it **through the maintain agent**:

```bash
# At a terminal: the maintain agent settles runner, validation script,
# model and version budget with you, then starts the run
artemis maintain issues fix <issue-id> --discovery --project <p>

# Decide the settings up front so the agent doesn't have to ask
artemis maintain issues fix <issue-id> --discovery --project <p> \
  --versions 5 --runner <runner-group> --script <script-name-or-id> \
  --focus "reduce p95 latency"
```

- The UI uses the same route. The agent's `start_discovery_fix` tool starts the
  run from the board and **moves the issues into the working lane**.
- **Don't use `artemis discovery create`** (or the
  [discovery-start](../discovery-start/SKILL.md) skill) for a maintain issue.
  That run isn't linked to any issue, so the board never changes.
- `--project` is required. A run takes **at most 5 issues**, and they must share
  one goal. Split unrelated issues into separate runs.
- Settings passed as flags go to the agent, which then doesn't ask about them:
  `--versions` (the backend defaults to 10), `--model`, `--runner` (a runner
  group), `--script` (name or ID) and `--focus` (an extra steer for the run's
  goal). The agent asks about any setting you leave out, but only if there is a
  real choice. A project with one runner, one script or one model uses it
  without asking.
- Usually leave `--execution-mode` unset; the agent works it out from the
  script (`benchmark` if the script produces metrics, `test` if it doesn't).
  `--execution-mode skip` runs without a runner, so **no version gets a
  score**.
- The agent shows the run for approval before it starts. Without a terminal
  (piped, or `--output-format json`), the command runs **one agent turn** and
  exits. Read the agent's questions from the output, reply with
  `artemis chat send <chat-id> -m "..."`, and repeat until it says the run has
  started. Passing every setting as a flag usually avoids the questions.
  `--timeout` (default 10m, exit code 6) limits each turn.
- A project with no validation script can't measure anything, so the run is
  refused. The agent offers to write a script for you. `--execution-mode skip`
  also gets past this, but then no version gets a score.
- Issues that already have a fix running are skipped rather than fixed twice.
- Check `affordances.canFixInDiscovery` from `issues get` before you start.
- A discovery run takes much longer than a coding fix. To follow it, read the
  issue's `FixChatID` from `issues get`, then run
  `artemis chat messages <fix-chat-id>`. Use the
  [discovery-inspect](../discovery-inspect/SKILL.md) skill to look at the
  versions it produces.
- The `--discovery` flag needs a recent CLI. Check
  `artemis maintain issues fix --help`.

### Prefer your own coding agent? Export the prompt instead

```bash
artemis maintain issues prompt <issue-id> [<issue-id>...] --project <p>
```

In text mode **only the prompt goes to stdout** (the count goes to stderr), so
it pipes straight into another tool:

```bash
artemis maintain issues prompt <issue-id> --project <p> | my-coding-agent
```

Keep the board up to date while that agent works, and **upload the result**.
Otherwise the issue is marked done with no changeset behind it:

```bash
artemis maintain issues transition <issue-id> --to in_progress --source local_agent
# ...agent edits the local checkout...
artemis maintain issues submit-local-fix <issue-id> --project <p> [-m "Guard the null case"]
```

- `submit-local-fix` uploads your working-tree changes to a new changeset on
  the issue, through the API (nothing is pushed to git). After that, `publish`
  and `pr` work the same as for a fix Artemis made.
- By default it sends **modified tracked files only**. Add new files with
  `--include-untracked`, or list exact files with `--path` (repeatable). Don't
  sweep up untracked files blindly: the working directory can contain build
  output and the `.env` that holds the API key.
- The checkout must be on the changeset's base commit. The command refuses to
  run otherwise; `--force` overrides that.
- Running it again creates a new attempt with a new changeset.

## Lanes: move an issue by hand

The board has four lanes: `untriaged`, `triaged`, `in_progress` and `done`.
You can move an issue to any lane listed in its `allowedTransitions`:

```bash
artemis maintain issues transition <issue-id> --to done     # --source manual (default) | local_agent
artemis maintain issues transitions <issue-id>              # how it got here, oldest first
```

The board refuses moves that conflict with work in progress:

- Nothing can move while a fix is running.
- An issue with a changeset reaches `done` when the fix reports back, not by
  hand.
- To reopen a fix Artemis completed, run `fix` again; don't drag it out of
  `done`.
- Moving an issue to `done` yourself tells Artemis you've dealt with it, so
  check `affordances` before trying to fix it with Artemis later.

## 7. Ship — branch and/or PR

Both commands require the issue to **already have a fix changeset** (run `fix`
first) and both are idempotent — an already-published changeset keeps its
branch; an issue that already has a PR reports the existing one instead of
opening a duplicate.

```bash
# Publish the changeset to a branch, no PR
artemis maintain issues publish <issue-id> --project <p>

# Publish (if needed) AND open a PR in one step
artemis maintain issues pr <issue-id> --project <p>
```

`pr` defaults its title/description from the issue and targets the project's
default branch; override with `--title` / `--description` / `--base`. The branch
is auto-named `artemis/<issue-slug>-<n>`.

## 8. Keep the board honest — syncs

The code moves on. A finding from last week may already be fixed, may have moved
to a new line, or may no longer apply. A **sync** re-evaluates issues against the
current code so the board doesn't rot.

```bash
# Resync every outdated issue in the project
artemis maintain syncs run --project <p> --wait

# Resync only specific issues
artemis maintain syncs run --project <p> <issue-id-1> <issue-id-2> --wait

artemis maintain syncs list --project <p>
```

Like scans, syncs run in the background (`--wait` / `--timeout`, exit 6 on
expiry) and there is **no single-sync GET** — the wait path matches the sync ID
in the list. After a sync, re-read the board (`issues list --sync-status ...`)
before acting on anything old.

## Traps

- **Display ID vs UUID.** Every command argument is the **UUID**; `ISS-143` /
  `RULE-7` are for reading only. Scripts must lift `.id`.
- **No `rules create --prompt`.** Rules come from `--markdown-file`, the
  default catalogue, or `maintain chat`. A `[DRAFT]` rule has no scan
  description and finds nothing.
- **`done` scan ≠ found something.** A scan that ran cleanly can still record 0
  issues — that's "ran", not necessarily "clean". Rule out draft rules / path
  scoping first (§3).
- **`fix` runs in the background.** A returned `ChangesetID` means the fix was
  *dispatched*, not that it is finished. Poll `issues get` until `.fixStatus` is
  `done`, `failed` or `cancelled` before you `publish` or `pr`. There is no
  `fixed` or `complete` value, so waiting for one never ends.
- **`fixStatus: done` can still be an empty changeset.** Check the `publish`/`pr`
  output: `numberOfCommitsAhead: 0` / "Empty branch with no modifications" means
  the agent wrote nothing — don't ship it. Re-run `fix`; if still empty, the
  finding is probably already fixed upstream (`syncs run`, §8).
- **One changeset per `fix` call.** Multiple issues in a single `fix` share a
  changeset and PR. Split unrelated work into separate `fix` calls up front;
  you can't cleanly un-bundle them afterwards.
- **Discovery fixes use `issues fix --discovery`.** `discovery create` starts
  a run that isn't linked to any issue, so the board never changes. The
  `--discovery` route goes through the maintain agent, like the UI, and moves
  the issues. At most 5 issues per run, all with the same goal.
- **Piped `chat` / `fix --discovery` runs one turn only.** Continue with
  `artemis chat send <chat-id>`; don't assume the run has started until the
  agent says it has.
- **Upload local fixes.** A fix made outside Artemis and only moved to `done`
  has no changeset behind it. Use `submit-local-fix`.
- **`publish`/`pr` need a connected git provider.** Both push to GitHub; a
  project imported without push-capable git auth fails at the push step, not at
  `fix`.
- **No single-scan / single-sync GET.** Status for a backgrounded scan or sync
  is found by matching its ID in the corresponding `list`, not a `get`.

## Checklist

- [ ] Project UUID confirmed (not just a name).
- [ ] Rules in place and **not `[DRAFT]`** — `rules list` is clean.
- [ ] `scans run` reached `done` (not `failed`); `issues list` shows a non-zero
      board — a `done` scan with 0 issues is "ran", not necessarily "clean".
- [ ] Findings **triaged** (`confirm` / `dismiss` / `close`) before any `fix`.
- [ ] `affordances` checked before dispatching (`canFix` / `canFixInDiscovery`).
- [ ] `fix` polled until `fixStatus` is `done`, `failed` or `cancelled` (there
      is no `fixed`) **before** `publish`/`pr`; unrelated issues in
      **separate** `fix` calls.
- [ ] Discovery fixes started with `issues fix --discovery --project <p>` (at
      most 5 issues with one goal), never `discovery create`; the agent's
      questions answered until it says the run has started.
- [ ] Local fixes uploaded with `submit-local-fix`, not just moved to `done`.
- [ ] Changeset confirmed **non-empty** (`numberOfCommitsAhead` > 0, not an
      "Empty branch") before shipping; git provider connected.
- [ ] Board **resynced** (`syncs run`) after the code changed, before trusting
      old findings.
