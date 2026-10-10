---
name: discovery-recommend
description: Recommend Discovery runs for a repository and prepare them as drafts the user can start by number. Surveys the code, proposes a short ranked list of measurable goals, writes and checks a benchmark for each on one new branch, registers a script per goal, and creates each Discovery parked in setup with the exact commands to start it. Use when the user asks what Artemis could optimise in a repository, wants ideas for Discovery runs, or wants several runs prepared to start later.
compatibility: Requires Artemis CLI 1.1.15+ and Artemis Platform 3.1.0+.
metadata:
  artemis-cli-min: "1.1.15"
  artemis-platform-min: "3.1.0"
---

# Recommend and prepare Discovery runs

## At a glance

- **Problem:** A user with a repository rarely knows which Discovery to run or how to measure it. This skill turns the repository into a short list of runs, each with its own benchmark written and checked, saved as drafts so the user can say "run 1 and 3".
- **Must be available:** an authenticated CLI, an imported project (`project-import`), the repository checked out locally (or downloaded with `changeset download`), and its build and test commands (`repo-command-setup`).
- **Use / don't use:** Use before a goal is chosen, or when the user wants several runs ready to go. When the user already has a goal and a benchmark, use `discovery-start`.
- **Next skill:** `discovery-start` covers the model, budget and credit questions when a draft is launched; `discovery-collaborate` when coding agents should work alongside a run.

## 1. Survey the repository

Read before running anything expensive.

- What the project does, its languages and entry points, how it builds and tests (README, CI config, `Makefile`, `pyproject.toml`, `package.json`, `go.mod`), and any benchmarks, profilers or fixtures it already has.
- Where time, memory or money go: hot loops, parsing and serialisation, database queries, I/O, start-up and imports, slow tests, and for agent or LLM code the number of model turns and the size of each prompt.
- What can prove behaviour is unchanged: tests that pin it, golden outputs, deterministic inputs.
- Known problems on the paths you plan to measure. If the survey turns up a bug, check the tracker for it and add evidence there before filing a new one.
- What has been tried. List the project's runs and read their task text, so no proposal repeats one:

```bash
artemis --output-format json discovery list --project "<project-uuid>" --all \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(r['id'], r['status'], (r.get('taskDescription') or '')[:100]) for r in d.get('docs', d)]"
```

Ask the user once what matters most to them (speed, cost, memory, quality; production or CI) unless they have already said.

## 2. Propose a short ranked list

Propose three to eight runs. Each needs one primary metric with a direction, a guardrail that shows behaviour is unchanged, and a benchmark that runs on a runner in a few minutes. Rank by value to the user first, then by how cleanly the benchmark separates a real gain from noise (deterministic code before live network or LLM calls), then by cost to measure.

Show one table:

| # | Goal | Primary metric (direction) | Guardrail | Files in scope | Benchmark in one line | Expected noise | Time per measurement |
|---|---|---|---|---|---|---|---|

Say plainly when a run needs something you cannot provide, such as production data, credentials, a GPU or a paid API key, and what the user would have to supply. Let the user choose; if they just say go, prepare the top three.

## 3. Write the benchmarks on one branch

Put every chosen benchmark on one new changeset, so each draft starts from the same code:

```bash
artemis --output-format json changeset create --project "<project-uuid>" --name "discovery-benchmarks"
artemis changeset download "<changeset-id>" --project "<project-uuid>" --out "<workspace>"
```

Add one folder per run, `benchmarks/<slug>/`, holding:

- `run.sh` (or the language's equivalent), the benchmark command. It runs the real code path by importing the project's modules or calling its CLI or API, never a copy of the code. It uses fixed inputs and seeds, warms up, then measures several repetitions.
- It writes `artemis_results.json` at the repository root, fresh on every run, with numeric values only (`repo-command-setup` §4): the primary metric as a median, one spread metric, and the guardrail as `1` or `0` (for example `output_matches` or `tests_passed`). A failed guardrail still writes the file, with the guardrail at `0`.
- Fixed inputs small enough to commit, or a seeded generator.
- `README.md`: what it measures, how to run it locally, and what would count as gaming it.

Run each benchmark locally twice before saving, one benchmark at a time (they all write the same results file). Tell the user before running anything heavy on their machine. Then check:

- The results file parses, the guardrail is `1`, and the two runs agree within the noise you quoted. A fresh checkout is slower on its first run (bytecode, caches), so warm up before the timer starts.
- The benchmark exercised the path you meant. Read its log for warnings: a missing tool or a fallback can make a benchmark fast because it skipped the work. Build external tools the way production builds them.
- The baseline is worth optimising. If the measured work already takes a fraction of a second, or is a small share of what users wait for, drop the run and say why. A run that cannot move a number users notice is not worth its credits.
- It takes a few minutes at most; shrink the workload if not.
- Secrets such as API keys come from the environment or a file on the runner, never from the branch.

A guardrail that compares output needs a reference: generate it once from the unchanged code and commit it (for example a hash per input), so every version is compared with the original behaviour.

Save the branch with only the benchmark files. Run `artemis` from outside the workspace or pass `--config`: the CLI reads a `.env` in the current directory as its own configuration, and many repositories have one. A workspace made by `changeset download` is not its own git repository, so name the paths (or pass none, and the save compares the workspace with what was downloaded); keep tool binaries, cloned inputs and results files out:

```bash
artemis --output-format json changeset save "<changeset-id>" --project "<project-uuid>" \
  --root "<workspace>" -m "Benchmarks for the recommended Discovery runs" \
  benchmarks/<slug>/run.sh benchmarks/<slug>/README.md ...
```

Record the returned version SHA; every draft uses it.

## 4. Register a script per run

```bash
artemis --output-format json project scripts create --project "<project-uuid>" \
  --name "<slug>" \
  --description "<primary metric and guardrail>" \
  --setup-cmd "<install or build>" \
  --setup-cmd "<the tests that must keep passing>" \
  --benchmark-cmd "bash benchmarks/<slug>/run.sh" \
  --measure none
```

`--measure none` keeps the command's own runtime out of the metrics, because the benchmark reports what it measures. To prove a script works on the runner before any credits are spent, validate it there; this uses runner time only, so ask first:

```bash
artemis changeset validate "<changeset-id>" --project "<project-uuid>" \
  --version "<sha>" --script "<script-id>" --runner "<runner-name>" --wait
```

## 5. Create each run as a draft

```bash
artemis --output-format json discovery create --project "<project-uuid>" --setup \
  --task "<goal>. Primary metric <name> (<lower|higher> is better). <guardrail> must stay 1. Do not change benchmarks/ or the tests." \
  --source-changeset "<changeset-id>" --source-sha "<sha>" \
  --script "<script-id>" \
  --target-files "<path>" --target-files "<path>" \
  --versions <n> --llm-metrics=false --execution-mode benchmark --eval-mode fixed --eval-runs <n> \
  [--runner "<runner-name>"] [--model "<model>"] \
  --setup-step confirm
```

Park the draft on `confirm` when the runner, script and model are all set; otherwise park it on the first step that still needs a choice. `--llm-metrics=false` scores every version on measured metrics only, including versions sent by coding agents. Set the measurements per version from the noise you saw locally (`--eval-mode fixed --eval-runs <n>`): three for steady benchmarks, five or more for ones that call a live model, whose turns and tokens vary from run to run.

Finish with one table the user can act on, and the command that starts each draft:

| # | Goal | Draft link | Script | Still to choose |
|---|---|---|---|---|

A draft's link is `<deployment-base-url>/projects/<project-uuid>/discover/setup/<run-id>`.

## 6. When the user says "run 1 and 3"

For each chosen draft, confirm the model, the version budget, the measurements per version and the credit spend as `discovery-start` describes. Ask once whether Claude Code or Codex should also contribute, as `discovery-collaborate` describes; if yes, add its sentence to each chosen run's task. Then:

```bash
artemis discovery update "<run-id>" --model "<model>" --runner "<runner-name>" --versions <n>
artemis --output-format json discovery setup trial-run "<run-id>"   # wait as in discovery-start
artemis discovery setup complete "<run-id>"
```

Runs on one runner queue and run one after another, so several drafts can be completed together and the runner works through them. Put drafts on different runners to run them at the same time. Give the user each run's link. If the user chose contributors, start them once the runs are exploring (`discovery-collaborate`).

## Checklist

- [ ] Repository surveyed and existing runs read; no proposal repeats one
- [ ] Every proposal has a primary metric with a direction, a guardrail and a benchmark of a few minutes
- [ ] User chose which runs to prepare
- [ ] Benchmarks on one changeset, each writing numeric `artemis_results.json` with the guardrail; each run locally twice, one at a time, with consistent results and no warnings that it skipped work
- [ ] Runs whose baseline is already too cheap to matter dropped, with the reason given
- [ ] One script per run, `--measure none`; validated on a runner if the user agreed
- [ ] Each draft created with `--setup`, `--source-changeset`/`--source-sha`, `--script` and `--llm-metrics=false`, and its task says not to change the benchmarks or tests
- [ ] Table of drafts with links and what is still to choose
- [ ] No draft started without the user's yes on model, versions and credits
- [ ] User asked whether Claude Code or Codex should contribute; their answer reflected in each run's task
