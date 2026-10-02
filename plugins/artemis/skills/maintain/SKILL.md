---
name: maintain
description: Run Artemis Maintain end to end on a project — author or import rules, scan the code for issues, triage the findings, fix them with the fix agent, ship each fix as a branch or PR, and re-sync stale issues as the code moves on. Use when the user wants to scan a project for code-health issues, set up maintain rules, or triage/fix/ship maintain findings.
compatibility: Requires Artemis CLI 1.1.8+ and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.8"
  artemis-platform-min: "3.1.0"
---

# Artemis Maintain

## At a glance

- **Problem:** Finds code-health issues against a project's rules, then triages them, fixes them and ships each fix as a branch or pull request.
- **Must be available:** An authenticated CLI and an imported project. No runner or benchmark is needed.
- **Use / don't use:** Use to scan for issues, manage rules, or triage, fix and ship findings. Don't use it to measure or optimise performance; that is Discovery.
- **Next skill:** None required. Return to `artemis` routing for other work.

Maintain (backed by the **code-warden** service) audits a project against a set
of **rules**, records each finding as an **issue** on a board, and helps you
triage and fix them. The whole flow:

```
rules ──scan──▶ issues ──triage──▶ confirmed ──fix──▶ Branch ──publish/pr──▶ git branch / PR
                                                                                    │
                                                              syncs keep the board honest as code changes
```

The lifecycle of one issue:

```
open ──confirm──▶ true_positive ──fix──▶ Branch ──publish──▶ git branch ──pr──▶ pull request
  │
  └──dismiss──▶ false_positive (closed)     └──archive──▶ closed (validity untouched)
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

Every rule and issue carries a human-friendly **display ID** (`RUL-7`,
`ISS-143`) shown for readability, but **all commands take the UUID** as their
argument. Lift `.id`, not `.displayId`, into anything scripted.

## `--model` — optional

Both commands that dispatch an agent (`scans run` and `issues fix`) take
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

A scan runs against one or more **rules** — each a description of what to flag.
Three ways to get them, and every rule is scoped to one project.

### Fastest: import the default catalogue

```bash
artemis maintain rules defaults --all                 # browse the catalogue first
artemis maintain rules import-defaults --project <p> --rule <default-id-1> --rule <default-id-2>
```

Pick the rules rather than importing the whole catalogue: it has 22, a scan takes at
most 20, and three of them (GitHub, JIRA and Sentry issue import) bring in issues from
those tools rather than scan the code.

### Author your own from a prompt

```bash
artemis maintain chat --project <p> \
  -m "create a rule that flags SQL queries built with string concatenation"
```

The maintain agent reads the project's code, writes the rule and puts it on the
board. Check `rules list` before scanning: a rule still marked `[DRAFT]` scans
nothing.

### Author from a markdown definition

```bash
artemis maintain rules create --project <p> --markdown-file rule.md
```

Confirm what you'll scan against before spending a scan:

```bash
artemis --output-format json maintain rules list --project <p> \
  | jq -r '.docs[] | "\(.displayId // .id)\t\(.isDraft)\t\(.name)"'
```

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
- `--count` is the *target* number of issues to surface, up to 100 (the Web
  UI's "Approximate number of issues") — a ceiling the agent aims for, not a
  guarantee.
- `--commit <sha>` pins the scan to a specific commit instead of project head.
  There is no `--path`: a scan covers the whole project. From CLI 1.1.13,
  `--focus "<text>"` points it at part of the code, like the Web UI's "What to
  focus on" box.
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

- Confirm the rules were **not still drafts** when the scan ran (§1) — a scan
  against a draft rule surfaces nothing.
- Check `--commit` didn't pin the scan to a commit without the relevant code.
- Try a broader or differently-worded rule; rule phrasing drives recall.

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

`issues list` filters on `--rule`, `--severity`
(critical|high|medium|low|info), `--status` (open|closed), `--validity`
(true_positive|false_positive|not_set), `--fix-status`
(pending|in_progress|done|failed|cancelled|not_set), `--sync-status`,
`--complexity` (small|medium|large) and `--path-prefix`; it sorts on
`--sort`/`--order` and paginates with `--all`.

## 5. Triage — before you fix

A scan's findings are agent-generated: **triage before you fix.** Not every
finding is a true positive, and firing the fix agent at noise wastes a run.

```bash
artemis maintain issues confirm <issue-id> [<issue-id>...]   # → true_positive
artemis maintain issues dismiss <issue-id> [<issue-id>...]   # → false_positive + closed
artemis maintain issues archive <issue-id> [<issue-id>...]   # → closed, validity untouched
```

All three take **multiple IDs**. `confirm` marks genuine findings so you can
batch-fix them; `dismiss` marks false positives (the Web UI's **False
positive**) and archives them, recording *why* the board shrank; `archive` retires an issue without judging it true/false (won't-fix,
duplicate). `unarchive` puts it back; CLIs before 1.1 call `archive` `close`.

## 6. Fix — dispatch the fix agent

```bash
artemis maintain issues fix <issue-id> [<issue-id>...] [--model claude-sonnet-5]
```

- Takes **multiple issues**; **all their fixes land in one Branch** and the
  agent's work streams into **one fix chat**. Group related issues; keep
  unrelated ones in separate `fix` calls so each gets its own Branch and PR.
- The command returns the Branch's ID (`changesetId` in JSON) and a fix chat
  ID and then **returns
  immediately** — the agent works in the background. Follow it:

```bash
artemis chat messages <fix-chat-id>          # watch the fix agent's tool calls
artemis maintain issues get <issue-id>       # Branch ID, fix status and PR URL fill in
```

**The terminal `fixStatus` is `done`, `failed` or `cancelled` — not `fixed`.** When you poll
`issues get`, wait for `.fixStatus == "done"`; there is no `fixed`/`complete`
state, so a loop that breaks on the wrong string will spin forever against a fix
that already finished. Poll like:

```bash
until fs=$(artemis --output-format json maintain issues get <issue-id> \
             | jq -r '.fixStatus'); \
      [ "$fs" = "done" ] || [ "$fs" = "failed" ] || [ "$fs" = "cancelled" ]; do sleep 20; done
```

**`done` ≠ produced a real edit — verify the Branch is non-empty before you
ship.** `fix` returning a Branch ID means the agent was *dispatched*, not
that a fix exists; a fix can even reach `fixStatus: done` having written
nothing. Check before publishing with
`artemis changeset diff <changeset-id> --project <p>`: it lists the files the fix
changed. Don't judge by `numberOfCommitsAhead` or "Empty branch with no
modifications" in `publish`/`pr` output; those read empty for every fix that
hasn't been published yet. If the diff is empty, don't ship it: re-run `fix` (**Retry fix** in the Web UI),
and if it's *still* empty, the bug was likely already fixed upstream (check with
a `syncs run`, §8).

### Prefer your own coding agent? Export the prompt instead

This is the Web UI's **Copy for local agent**.

```bash
artemis maintain issues prompt <issue-id> [<issue-id>...] --project <p>
```

In text mode **only the prompt goes to stdout** (the count goes to stderr), so
it pipes straight into another tool:

```bash
artemis maintain issues prompt <issue-id> --project <p> | my-coding-agent
```

## 7. Ship — branch and/or PR

Both commands require the issue to **already have a fix Branch** (run `fix`
first) and both are idempotent — an already-published Branch keeps its git
branch; an issue that already has a PR reports the existing one instead of
opening a duplicate.

```bash
# Publish the Branch to a git branch, no PR
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
# Re-sync every outdated issue in the project
artemis maintain syncs run --project <p> --wait

# Re-sync only specific issues
artemis maintain syncs run --project <p> <issue-id-1> <issue-id-2> --wait

artemis maintain syncs list --project <p>
```

Like scans, syncs run in the background (`--wait` / `--timeout`, exit 6 on
expiry) and there is **no single-sync GET** — the wait path matches the sync ID
in the list. After a sync, re-read the board (`issues list --sync-status ...`)
before acting on anything old.

## Traps

- **Display ID vs UUID.** Every command argument is the **UUID**; `ISS-143` /
  `RUL-7` are for reading only. Scripts must lift `.id`.
- **Draft rules scan nothing.** A rule still marked `[DRAFT]` surfaces zero issues;
  check `rules list` first.
- **`done` scan ≠ found something.** A scan that ran cleanly can still record 0
  issues — that's "ran", not necessarily "clean". Rule out draft rules or a
  `--focus` aimed elsewhere first (§3).
- **`fix` is async, and its terminal state is `done`.** A returned Branch ID
  means *dispatched*, not *done*. Poll `issues get` until `.fixStatus == "done"`
  (or `"failed"`) before `publish`/`pr` — there is no `fixed`/`complete` value,
  so watching for the wrong string hangs forever on an already-finished fix.
- **`fixStatus: done` can still be an empty Branch.** Check with
  `changeset diff` before publishing, not the `publish`/`pr` output, which reads
  empty for every unpublished fix. No changed files means the agent wrote
  nothing: re-run `fix`; if still empty, the finding is probably already fixed
  upstream (`syncs run`, §8).
- **One Branch per `fix` call.** Multiple issues in a single `fix` share a
  Branch and PR. Split unrelated work into separate `fix` calls up front;
  you can't cleanly un-bundle them afterwards.
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
- [ ] Findings **triaged** (`confirm` / `dismiss` / `archive`) before any `fix`.
- [ ] `fix` agent polled to `fixStatus: done` (not the non-existent `fixed`)
      **before** `publish`/`pr`; unrelated issues in **separate** `fix` calls.
- [ ] Branch confirmed **non-empty** with `changeset diff` before shipping;
      git provider connected.
- [ ] Board **re-synced** (`syncs run`) after the code changed, before trusting
      old findings.
