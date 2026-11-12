---
name: discovery-collaborate
description: Have the user's own coding agents, such as Claude Code and Codex, work alongside a running Discovery. They gather context locally (the code, profilers, the machine), add experiments to the run, claim and build them, and send them back as versions the runner measures like any other, while the Discovery's orchestrator ranks every idea and decides what comes next. Use when the user wants Claude Code or Codex to contribute to a Discovery, when a run should have more and different ideas than its own agent produces, or when a team that lives in a coding agent wants Artemis to measure and keep what their sessions try.
compatibility: Requires Artemis CLI 1.1.15+ and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.15"
  artemis-platform-min: "3.1.0"
---

# Coding agents working alongside a Discovery

## At a glance

- **Problem:** A Discovery's own agent is one source of ideas. A coding agent the user already runs is very good at reading the code and the local profiler, and a second agent brings different ideas again. When they add experiments and versions to the same run, the orchestrator ranks all of them, the runner measures every version the same way, and each agent can build on the best version whoever wrote it.
- **Must be available:** an authenticated CLI on the machine where the coding agents run, the repository checked out there, and a Discovery that is running or about to start (`discovery-start`, or a draft from `discovery-recommend`).
- **Use / don't use:** Use when the user says yes to contributors, or asks for Claude Code or Codex to help a run. For a single quick change with no measurement, a coding agent alone is enough.
- **Previous skill:** `discovery-start` or `discovery-recommend` asks the question below before a run starts.

## The question to ask

Ask once, before the run starts, unless the user has already answered:

> Do you want Claude Code or Codex to also contribute to this Discovery? They gather context from the code and your profiler, propose experiments and write versions, and the Discovery's orchestrator ranks every idea and decides what to build next. More agents give the search more, and more different, ideas, so a better chance of a gain; each contributor spends tokens on its own plan or key. If not, the Discovery's own agents do the work.

Offer: Claude Code, Codex, both, or neither. If the user picks contributors, add this sentence to each run's task before it starts, so the orchestrator builds on outside versions too:

> Other contributors (a Claude Code session and a Codex session) also add experiments and versions to this run; build on the best version whoever wrote it.

## 1. Set up the shared workspace

One folder for the run, with a subfolder per contributor and a shared claims folder:

```bash
mkdir -p "<work>/claims" "<work>/claude" "<work>/codex" "<work>/notes"
```

Write `<work>/PROTOCOL.md` with the run id, the project id, the goal and metric, the tests that must pass, the files that must not change, and the steps below, so every session reads the same rules.

If contributors build or time anything locally on the runner's machine, give each its own cores and keep them off the cores the runner times on (and off their second hardware threads). Local timing is only a sanity check; the runner's measurement is the one that counts.

## 2. Start each contributor

Start each one in its own terminal, in its own folder, with a short brief: the goal, the run id, `PROTOCOL.md`, and that it is extra hands next to the Discovery's agent, not a replacement. For example:

```bash
cd "<work>/claude" && claude "Read ../PROTOCOL.md and contribute to Discovery <run-id> as it describes."
cd "<work>/codex" && codex "Read ../PROTOCOL.md and contribute to Discovery <run-id> as it describes."
```

## 3. Find ideas

Each contributor profiles the current best version, finds where the time goes, and adds well argued experiments to the run:

```bash
artemis discovery experiments create "<run-id>" --created-by user \
  --title "<short idea>" --hypothesis "<why it should help, and how we will know>"
```

Keep `<work>/ideas.md` current so contributors do not propose the same idea twice.

## 4. Claim an experiment

```bash
mkdir "<work>/claims/<experiment-id>"   # atomic: if it fails, someone else has it
```

Prefer your own experiments, then draft or inconclusive ones the Discovery's agent has not built.

## 5. Build it and send it back as a version

1. Find the current best version: `artemis discovery metrics <run-id> --stats` and `artemis discovery versions list <run-id>`; `artemis discovery versions get <version-id>` gives its changeset and SHA. Before any version exists, start from the project base.
2. Make a changeset and download it:
   ```bash
   artemis changeset create --project "<project-uuid>" --name "<contributor>-<short idea>"
   artemis changeset download "<changeset-id>" --project "<project-uuid>" --out "<dir>"
   ```
   Bring the best version's code in: download that version with `--version <sha>` to another folder and copy the changed files over.
3. Implement the idea. Build and run the tests locally on your own cores.
4. Save with explicit file paths, so build output never ends up in the changeset, then read the new SHA:
   ```bash
   artemis changeset save "<changeset-id>" --project "<project-uuid>" --root "<dir>" -m "<what changed>"
   artemis changeset versions "<changeset-id>" --project "<project-uuid>"
   ```
5. Register and run it:
   ```bash
   artemis discovery versions create "<run-id>" --experiment "<experiment-id>" \
     --changeset "<changeset-id>" --sha "<sha>" --rationale "<why, and which version it builds on>"
   artemis discovery versions execute "<version-id>"
   ```
6. Check the result (`discovery versions get`, `discovery versions logs` if it failed), write it in `claims/<experiment-id>/result`, and take the next experiment.

Versions sent from outside may show as proposed or as failing to score even when they were measured; read their numbers with `artemis discovery metrics <run-id> --stats`. The orchestrator tends to build on its own versions, so stack the best ideas onto the best line yourself and say so in the rationale.

## 6. Watch and report

`artemis discovery metrics <run-id> --stats` and `artemis discovery experiments list <run-id>` show where the run stands. When it ends, report the best version, who wrote it, its measured change against the baseline, and anything in the flow that did not work (each contributor keeps `notes/<name>-issues.md`).

## Checklist

- [ ] User asked once and chose contributors; each run's task names them
- [ ] Shared `PROTOCOL.md`, claims folder and one folder per contributor
- [ ] Local work kept off the runner's cores
- [ ] Every outside version registered against an experiment, with its parent named in the rationale
- [ ] Results read from `discovery metrics --stats`, not from local timing
- [ ] Final report names the best version, its author and its measured change
