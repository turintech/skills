---
name: maintain
description: Run Artemis Maintain end to end on a project. Author or import Rules, Scan the code for Issues, triage them, fix them with the fix agent, in Discovery or with your own coding agent, ship each fix as a branch or PR, and re-sync outdated Issues as the code moves on. Use when the user wants to scan a project for code-health Issues, set up Rules, or triage, fix or ship Issues.
compatibility: Requires Artemis CLI 1.1.14+ and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.14"
  artemis-platform-min: "3.1.0"
---

# Artemis Maintain

## At a glance

- **Problem:** Finds code-health Issues against a project's Rules, then triages them, fixes them and ships each fix as a branch or pull request.
- **Must be available:** An authenticated CLI and an imported project. No runner, except for Fix in Discovery.
- **Requirements:** `artemis --version` is at least `artemis-cli-min` (1.1.14, which has `scans get`, `scans cancel` and display ids); if it is older, load `cli-setup` first.
- **Use / don't use:** Use to scan for Issues, manage Rules, or triage, fix and ship Issues. Don't use it to measure or optimise performance; that is Discovery.
- **Next skill:** None required. Return to `artemis` routing for other work.

Maintain audits a project against its **Rules**, records each violation as an **Issue** on a board, and helps you triage and fix them:

```
Rules --scan--> Issues (Untriaged) --triage--> Triaged --fix--> Branch --publish/pr--> git branch / PR
                                                   re-sync keeps outdated Issues honest as the code changes
```

The board has four **lanes**: `untriaged`, `triaged`, `in_progress`, `done`. A fix's code changes are a **Branch** in the Web UI; the CLI calls it a **changeset** (`artemis changeset diff <id>`, `Changeset ID` in output).

## Requirements

- `artemis status` OK on the target deployment.
- An imported project with the code to scan (load `project-import` if there is none). Prefer the project **UUID** in anything scripted: `-p/--project` takes a UUID or a name, and a name errors once two projects share it.
- For **publish / pr** only: the project's git connection must have push access. Maintain's `publish` and `pr` push to GitHub.
- Optionally `jq`; the snippets use it, but any JSON filter works.

**Ids.** Rules, Issues and Fixes carry display ids (`RUL-12`, `ISS-143`, `FIX-7`). Every `issues` command accepts a display id with `-p <project>`, except `fix` without `--discovery`, which takes the UUID. In scripts, lift `.id`.

**Credits.** Every step but triage is an agent run: a Scan, a fix, Fix in Discovery, a Re-sync and `maintain chat` all spend credits. Before `scans run`, `issues fix` (with or without `--discovery`), `syncs run` or `maintain chat`, tell the user what it will do and that it spends credits, and run it only on their yes. Approving a question card that starts a Scan, a fix or a Discovery run spends credits too: approve a card only after the user's yes.

**Question cards.** When an agent run stops on a question, read it with `artemis chat messages <chat-id>` and answer with `artemis chat answer <chat-id> --answer "..."` or `--approve`. Never reply to a card with `chat send`: the card stays unanswered and the agent asks again.

**`--model`** is optional on `scans run`, `issues fix` and `maintain chat`; omit it and the backend chooses. It takes a catalogue UUID or a model-type code (`artemis model list`).

**Waiting.** Never loop without a limit, and don't sleep between tool calls. Check in one shell command with the sleep inside, run with a 10-minute tool timeout (or in the background); if it is still running, run the same command again. The pattern, for a fix:

```bash
for i in $(seq 16); do   # about 8 minutes
  s=$(artemis --output-format json maintain issues get <issue-id> -p <p> | jq -r '.fixStatus')
  case "$s" in done|failed|cancelled) break;; esac
  sleep 30
done; echo "fixStatus=$s"
```

---

## 1. Get Rules in place

Every Rule belongs to one project.

**Import from the default catalogue.** Pick Rules rather than importing all of them: the catalogue has 22, a Scan takes at most 20, and three (GitHub, JIRA and Sentry issue import) bring in issues from those tools rather than scan the code.

```bash
artemis maintain rules defaults --all
artemis maintain rules import-defaults --project <p> --rule <default-id-1> --rule <default-id-2>
```

**Author one from a prompt.** The maintain agent reads the code, writes the Rule and puts it on the board:

```bash
artemis maintain chat --project <p> --timeout 8m -m "create a rule that flags SQL queries built with string concatenation"
```

Piped or with `--output-format json`, `maintain chat` takes one turn and prints the chat id. If the agent stops on a question card, answer it as above (`chat answer`); use `artemis chat send <chat-id> -m "..."` only to carry on the conversation.

**Author one from markdown:** `artemis maintain rules create --project <p> --markdown-file rule.md`.

A **Draft Rule** scans nothing. Check before you spend a Scan:

```bash
artemis --output-format json maintain rules list --project <p> --all \
  | jq -r '.docs[] | "\(.displayId // .id)\t\(.isDraft // false)\t\(.name)"'
```

`rules delete` also deletes the Rule's Issues and Scans and cannot be undone. It asks unless you pass `--force`; never `--force` a Rule someone else wrote.

## 2. Run the Scan

After the user's yes:

```bash
artemis maintain scans run --project <p> --rule <rule-id> --count 10
```

- `--rule` is required and repeatable, up to 20 Rules per Scan.
- `--count` is about how many Issues to surface (1-100, default 5), the Web UI's "Approximate number of issues": a target, not a guarantee. `--no-limit` drops the limit, as in the Web UI, and uses more tokens; it can't be combined with `--count`.
- `--focus "<text>"` points the Scan at part of the code, like the Web UI's "What to focus on". `--commit <sha>` scans that commit instead of the project head. There is no `--path`.

The Scan runs in the background; capture its `id`. Check on it with `scans get <scan-id> --project <p>` in the waiting pattern above, breaking on `.status` `done`, `failed` or `cancelled`. Stop a Scan, after the user's yes, with `scans cancel <scan-id> --project <p> --force` (without `--force` it asks, and fails with no terminal); it keeps what it already found. (`--wait --timeout` also exists, but its 20-minute default outlasts an agent's shell.)

## 3. Check it found something

`done` means the Scan ran, not that it found anything. `scans get` shows `issuesFound` and whether the target was met. If it found none where you expected some:

- the Rules may still have been drafts when it ran (§1);
- `--commit` or `--focus` may point away from the relevant code;
- a broader or differently worded Rule may do better; the wording drives recall.

## 4. Read the board

```bash
artemis maintain issues list --project <p> --severity high                       # open, high severity
artemis maintain issues list --project <p> --validity true_positive --fix-status not_set   # waiting for a fix
artemis maintain issues list --project <p> \
  --validity true_positive --fix-status not_set --sort size_of_fix --order desc
artemis maintain issues get ISS-143 -p <p>
```

`issues list` shows open Issues by default; `--status closed` is the Archive and `--status all` both. It also filters on `--rule`, `--severity`, `--validity`, `--fix-status`, `--sync-status`, `--complexity` and `--path-prefix`, sorts with `--sort`/`--order`, and pages with `--all`. A `--lane` filter comes with the next CLI release.

## 5. Triage before you fix

Scan results are agent-written: not every Issue is real, and a fix aimed at a false positive wastes a run. All three commands take several ids:

```bash
artemis maintain issues confirm <id>...   # true positive
artemis maintain issues dismiss <id>...   # mark as a false positive, which also archives it
artemis maintain issues archive <id>...   # off the board, triage unchanged (won't fix, duplicate)
```

`unarchive` puts an archived Issue back.

## 6. Fix

Three routes. Each needs the user's yes first, except the local-agent route, which spends nothing on the platform.

### The fix agent

```bash
artemis maintain issues fix <issue-uuid>... [--model claude-sonnet-5]
```

- All the Issues in one call land in **one Branch** and one fix chat. Group related Issues; put unrelated ones in separate calls so each gets its own Branch and PR. They can't be split afterwards.
- It returns a `Changeset ID` and a `Fix Chat ID` straight away and works in the background. Follow it with `artemis chat messages <fix-chat-id>`, and wait on `fixStatus` with the pattern above.
- The terminal `fixStatus` values are `done`, `failed` and `cancelled`. There is no `fixed` or `complete`.
- `done` can still be an empty Branch. Check `artemis changeset diff <changeset-id> --project <p>` before shipping; don't judge by `publish`/`pr` output, which reads empty for every unpublished fix. If the diff is empty, **Fix again** (run `fix` on the Issue again); if it is still empty, the Issue is probably already fixed, so re-sync it (§8).
- Every attempt is kept: `artemis maintain issues fix-runs <id> -p <p>` lists them, and the Issue reflects the latest. Trying a different `--model` on a second attempt loses nothing.

### Fix in Discovery

For a large fix, or one worth measuring, the Web UI's **Fix in Discovery** hands the work to a Discovery run that tries competing fixes and scores them:

```bash
artemis maintain issues fix <issue-uuid> --discovery --project <p> \
  --runner <runner> --script <script> --versions 5 --repeats 3 --timeout 8m
```

- It needs a runner and a script (or `--execution-mode skip` for no runner) and spends credits per version; say both before the yes.
- It goes through the maintain agent, which settles the run's settings; flags you pass are handed over so it doesn't ask. Piped, it takes one turn; if it stops on a question card, answer with `chat answer` (§ Question cards), and approve a card that starts the run only after the user's yes.
- Up to 5 Issues per run, and only Issues that share one goal. Follow the run with the `discovery-inspect` skill.

### Your own coding agent

The Web UI's **Copy for local agent**:

```bash
artemis maintain issues prompt <id>... --project <p> | my-coding-agent
```

In text mode only the prompt goes to stdout. While that agent works in the user's checkout, put its progress on the board and bring the fix back as a Branch:

```bash
artemis maintain issues transition <id> --to in_progress --source local_agent -p <p>
artemis maintain issues submit-local-fix <id> --project <p>     # uploads the changed files, moves it to done
```

- Leave the fix uncommitted, on the project's current head: it uploads what differs from `HEAD`, so committed work shows no changes, and it refuses if the checkout has moved past the commit the fix is based on.
- It sends modified tracked files only. Add new files with `--include-untracked`, or name exact files with `--path`.
- `--keep-open` attaches the Branch without moving the Issue to done.
- Don't move an Issue to `done` by hand when you have a fix to attach: once it is done, no Branch can be attached.

## 7. Ship: branch and/or PR

Both need the Issue to have a fix Branch, and both are idempotent: a published Branch keeps its git branch, and an Issue that already has a PR reports it rather than opening another.

```bash
artemis maintain issues publish <id> --project <p>   # git branch, no PR
artemis maintain issues pr <id> --project <p>        # publish if needed, then open a PR
```

`pr` takes its title and description from the Issue and targets the project's default branch; override with `--title`, `--description` and `--base`. The git branch is named `artemis/<issue-slug>-<n>`.

## 8. Re-sync outdated Issues

The code moves on: an Issue may already be fixed, have moved, or no longer apply. A **Re-sync** re-checks Issues against the current code. It is an agent run, so run it after the user's yes:

```bash
artemis maintain syncs run --project <p>                     # every outdated Issue
artemis maintain syncs run --project <p> <issue-id>...       # only these
artemis maintain syncs list --project <p>
```

Syncs run in the background like Scans. There is no `syncs get`: match the sync id in `syncs list` (status `done`, `failed` or `cancelled`) within the waiting pattern. Then re-read the board (`issues list --sync-status outdated`) before acting on old Issues.

## Checklist

- [ ] CLI at least 1.1.14; project UUID confirmed.
- [ ] Rules in place and none still drafts.
- [ ] The user said yes before each Scan, fix (agent, Discovery), Re-sync, `maintain chat` and card approval.
- [ ] The Scan reached `done`, and `issuesFound` is checked, not assumed.
- [ ] Issues triaged before any fix; unrelated Issues in separate `fix` calls.
- [ ] Waited on `fixStatus` with a bounded check, not an endless loop.
- [ ] The Branch is non-empty (`changeset diff`) before `publish`/`pr`; git connection can push.
- [ ] Outdated Issues re-synced before trusting old ones.
