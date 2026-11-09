# SQL query optimisation

Read this when the goal is a faster query, report or database-backed endpoint. The checklist is unchanged; this file says what each row looks like for SQL, so the gaps can be named in SQL terms.

## 1. What may Discovery change

Each answer is a different benchmark. If neither the benchmark nor the user says, assume query only and say so on the "Discovery may change" line; make it a decision only when indexes or schema look in play.

| Scope | Discovery may change | The benchmark must also |
|---|---|---|
| Query only (default) | the SQL text, CTEs, joins, engine hints | nothing extra |
| Query and indexes | the above plus `CREATE INDEX` in a migration file | measure index build time and size as guardrails, and the write path on the indexed tables, so faster reads can't hide slower writes |
| Query, indexes and schema | the above plus denormalisation, materialised views, partitions | measure refresh cost and staleness; check equivalence after a write as well as on a static snapshot |

Indexes and schema are production changes: use them only with the user's yes.

## 2. Data

- **Volume.** Production scale, or a stated fraction that keeps the ratios between table sizes. Plans change with size; a plan that wins on a toy table is not evidence for a large one. Compare `EXPLAIN` on the benchmark with production's plan when the user can share it.
- **Distribution.** Keep the real skew: hot keys, NULL fraction, correlated columns, long tails. Best: a masked production sample. Next: a generator fitted to the engine's column statistics (histograms, most-common values). Uniform synthetic data makes the planner look better than it is, and is a red flag for query or index work.
- **Statistics.** Run `ANALYZE` after loading and again before the original and every candidate, so no rewrite wins on stale statistics. Record the statistics target, and check the planner's row estimates against actual rows; if they are far apart, the benchmark tests the planner's mistake rather than the query.
- **Load.** Ask whether the query runs alone or beside other queries and writes, and benchmark that case. Concurrency tests use the production client count, with a data scale of at least the client count. Vacuum or reset before each run and record autovacuum state.
- **Runtime fit.** Load once per runner into a snapshot or template database and restore it per run (Postgres: `CREATE DATABASE <run> TEMPLATE <snapshot>`). The restore is outside the measured time but counts toward the per-version budget.

## 3. Parameters

- Score a set of parameter values drawn from the real distribution: hot keys, cold keys, a value matching nothing, and the widest range the report allows. Report selective and broad parameters as separate metrics.
- Score a fixed parameter set generated from a logged seed, so baseline and versions are timed on the same values, and have the gate also run the original and the version on a second set from a fresh seed it logs, so both see the same values and a failure can be replayed, and so a query can't be keyed on the scored values.
- When the application uses prepared statements, benchmark through prepared statements too. Postgres moves from custom to generic plans after five executions, so a benchmark of literals measures a different plan. Test both `plan_cache_mode` settings.

## 4. What is timed

- Time the query the way the application runs it: client-side wall time, every row fetched. `EXPLAIN ANALYZE` skips sending rows to the client and adds its own overhead, so it explains a result and is never the metric. Say whether planning time is inside the measurement.
- **Cold and warm are two metrics, never one mean.** Warm: the same query ran first; confirm with `EXPLAIN (ANALYZE, BUFFERS)` that reads went to near zero. Cold: restart the engine (a container per run) or evict by reading a large unrelated table first. Which one ranks is the user's call. Never compare a cold original with a warm candidate.
- Pin the engine's settings in the Script (`work_mem`, parallel workers, JIT, and their equivalents), so a version can't win by changing them.

## 5. Result equivalence

- **Order.** Compare as multisets unless the original orders its result. Then order must match too, ties included: where the original leaves ties unordered, compare each tie group as a multiset. A rewrite that adds or drops ORDER BY changes meaning.
- **Duplicates.** Keep them. UNION ALL to UNION, or an added DISTINCT, must fail.
- **NULLs.** NULL ordering defaults differ between engines and directions. `NOT IN` with a NULL in the subquery returns nothing, so rewriting it as `NOT EXISTS` changes results. `COUNT(col)` skips NULLs; `COUNT(*)` doesn't.
- **Types.** Compare numerics at the column's declared scale; give float aggregates a stated tolerance, because summation order changes the last digits. Same time zone and collation settings on both sides.
- **Inputs the agent can't tune on.** Check on several generated databases (NULLs, duplicates, skew), not one, and on parameter values outside the scored set, including NULL-heavy and empty-result cases. Matching results on test data is necessary but not sufficient.
- **Tested is not proven.** Record a passing rewrite as "tested equivalent, not proven". Where the query fits a prover's SQL subset, a prover can check the winner. An LLM's judgement that two queries are equivalent is never the gate: such judges lean towards saying yes.

## 6. Plan stability

Record the chosen plan (`EXPLAIN (FORMAT JSON)` or the engine's equivalent) for every scored parameter, on the original and on candidates. A win whose plan flips between parameters, or after a fresh `ANALYZE`, is fragile: name it as a risk and rank on the worst parameter, not the mean.

## 7. Engines

The checklist is the same on every engine; only the tools change. Benchmark on the user's engine and major version.

| | Postgres | MySQL | SQL Server | SQLite | DuckDB |
|---|---|---|---|---|---|
| Plan | `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` | `EXPLAIN ANALYZE`, `EXPLAIN FORMAT=JSON` | actual execution plan, Query Store | `EXPLAIN QUERY PLAN` | `EXPLAIN ANALYZE` |
| Statistics | `ANALYZE` | `ANALYZE TABLE`, histograms (8.0+) | `UPDATE STATISTICS` | `ANALYZE` | automatic |
| Cold cache | restart, or a container per run | restart, buffer pool dump at shutdown off | `DBCC DROPCLEANBUFFERS` on test servers only | new process, file reopened | new process |
| Gotchas | generic plans after five executions; JIT | NULLs sort first ascending | parameter sniffing | one writer at a time; runs in process, so time the whole call | runs in process; parallel by default, so pin threads |

## The three quick checks in SQL form

When SKILL.md step 5's quick checks apply: for "worse", add a pointless self-join and the time must rise; for "wrong", drop a WHERE condition and the result check must fail; for "cheat", return the scored database's answer as literals (a `VALUES` list) and the check on a second database or fresh parameters must fail it. Also worth naming as a gap if the check would miss it: rewriting `NOT IN` as `NOT EXISTS` changes results when the subquery yields NULL.

## Suggested metrics

Target files: the `.sql` file or the code holding the query. The regime the user chose to rank by as the main metric; the other regime and the worst parameter secondary; index size secondary when indexes are in scope.
