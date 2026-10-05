# feat(discovery): fast-track results with benchmark stages and parallel runners

Long benchmarks can delay useful Discovery results for hours. **Fast-track Discovery** minimizes time to trustworthy results with two levers: small/medium/full benchmark stages and approved parallel runner capacity. Fast benchmarks keep a single Discovery; existing user plans are respected. Estimates include repetitions, fresh baselines, queue delays and final validation, without promising linear speedups.

The router surfaces the choice, `discovery-start` owns launch and promotion, and `repo-command-setup/HARNESS.md` defines nested tiers and measurement conditions. Each tier has a fixed saved script, stable metric definitions and the correctness gate. New runs copy the selected candidate's code and carry search history in the task prompt; alternatives are remeasured at the next tier and final gains use the original code on the full benchmark.

Work serializes per runner process; independent Discoveries or ready stages can use different runners concurrently. Several processes on different machines can also serve one Discovery under the same exact runner name, as Mike confirmed on 22 September and 5 October 2026. `runner-setup` reconciles the older unique-name wording: names are unique per runner group and shared intentionally only to add capacity. Agents must ask before starting or reusing extra runners and verify active instances through `artemis runner list` and the run's executions.

Speed and memory measurements across different machines are not comparable unless hardware, OS, toolchain and load are identical, or each version is compared with a baseline measured on its own machine. A shared name is not evidence of comparable machines or paired baselines. Accuracy-only benchmarks can use any machine with the required environment.

Checks:

- `ARTEMIS_CLI=/home/mike/.local/bin/artemis scripts/check-skills.sh`: passed, 183 commands checked against `dev-20261004-101040-3e387a3`.
- Existing discovery-visualize suite: 44 tests, 43 passed, one skipped because TypeScript is unavailable. The two Chrome rendering checks needed execution outside the sandbox.
- `git diff --check` passed; reviewed the skill length report. The generic skill-creator validator rejects this repo's existing `compatibility` field; the repo-specific checks pass.
- Reviewed fast benchmarks, unrepresentative subsets, dependent promotions, unapproved extra runners, shared-name instances and heterogeneous timing measurements. No live Discovery or runner was launched.

Per `RELEASING.md`, this is a feature commit for a future minor release. Release versions and compatibility minimums remain unchanged; no new CLI command is required. The repo has no per-change changelog requirement.
