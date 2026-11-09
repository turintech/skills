# Task profile: traits, types and equivalence

Never branch on a task's name. Note which of the seven traits below apply, from the code and the goal wording; they decide which checklist rows matter and what to look for. They are for your reading only; never show them to the user. A task nobody listed still gets the whole checklist plus the traits that apply.

## Traits

| Trait | Detected from | Adds |
|---|---|---|
| T1 Timed (speed, latency, throughput) | Goal says faster, latency, throughput, time | Timer on the work until its output is used; warm-up outside; no caching between repetitions; one off-shape case |
| T2 Resource (memory, size, energy) | Goal says memory, RSS, size, footprint | Measure the whole process tree from outside: cgroup `memory.peak`, or `/usr/bin/time -v` maximum resident size, children included. Watch for work offloaded to disk or to a child the measurement misses |
| T3 Tolerant output (numeric, lossy, approximate) | Outputs compared with a tolerance or a quality score | Tolerance justified against a higher-precision reference; special values (NaN, inf, signed zero, denormals, empty) compared exactly; ill-conditioned cases; a margin above any quality floor |
| T4 Learned or fitted state (training, calibration, models in a codec, tuned constants) | Code fits, trains, calibrates or loads a model | Checklist row 9 ranks first. Quality noise across seeds. Model and side files charged to any size metric. Decode or predict from the artefact alone, in a fresh process. Split before fit; no train and test overlap; time-ordered data cut by time; every class kept |
| T5 Stateful or I/O (files, caches, network, database) | Reads files, sockets or a database, or keeps caches | Fresh paths or fresh copies of the same inputs each repetition; cold and warm as separate metrics; load level (concurrency, request rate) matching production for servers and endpoints; no cache surviving between processes or on disk; tail percentiles as their own metrics |
| T6 Accelerator (GPU, NPU, SIMD dispatch) | CUDA, ROCm, OpenVINO, Metal or similar, or the runner has a device | Synchronise the device before the timer stops; warm-up covers compile and autotune; precision mode pinned (TF32, fp16, bf16) and gated; the runner has the device |
| T7 Non-deterministic output (sampling, threads, async) | Output differs run to run | Equivalence over seeds, not equality; seeds logged; the gate's own false-fail rate measured on original against original |

## Common types

Examples to recognise the pattern, not code paths. The checklist is the same for every row.

| Type | Usual traits | Ranking metric | Equivalence | What usually games it | Holdout |
|---|---|---|---|---|---|
| CPU speed | T1 (+T5) | time per unit of work | identical output | memo, shape-keyed fast paths, work moved out of the timer, more cores | new real inputs and shapes |
| Memory | T2 (+T1) | peak RSS of the process tree | identical output; time as a guardrail | offload to disk, uncounted child processes, huge time for small memory | larger real inputs |
| Latency or I/O | T1, T5 | p50 and p99 as separate metrics | identical responses and final state; error rate | warm caches, batching that hurts the tail, dropped requests | replayed real traffic |
| ML training or accuracy | T4, T7 (+T1) | quality at a fixed budget, or time to a quality target | statistically equivalent per class over seeds | training on eval data, fewer epochs at the floor, baked weights, deleting rare classes | data from a later date or another source |
| Compression or codec | T3, T4 | ratio, with codec and model bytes charged | identical round trip (lossless) or a per-class quality floor (lossy) | side channels, models shipped in the decoder, pointers to repository files, floor-hugging | real files of every class |
| Numeric | T3 (+T1, T6) | time at a stated precision | within tolerance of a higher-precision reference; special values exact | lower precision, fast-math, skipped special cases | ill-conditioned and off-shape cases |
| GPU | T6, T1 (+T3) | synchronised kernel or end-to-end time | as numeric, precision mode pinned | async work past the timer, autotune caches, precision drop | new shapes and batch sizes |
| SQL query | T1, T5 (+T7 under concurrency) | client-side time per query, cold and warm apart | result multiset, plus order where the query orders | queries keyed on the scored parameters, cached result tables, changed settings | another snapshot and unscored parameters |

SQL has its own path: [sql.md](sql.md).

## Equivalence rules

Name the rule the benchmark uses (or should use) by the output's traits, and check it runs on inputs Discovery isn't scored on. A fast path keyed on the scored inputs is identical on those inputs and wrong elsewhere, so a gate that checks only the scored inputs is a gap.

| Output | Rule | How to check | Watch for |
|---|---|---|---|
| Exact, deterministic | identical | byte comparison, or sha256 of the canonical serialisation for large outputs; every output of every run | the gate reading a different place than the output is written; hashing only a header |
| Exact but order-free (sets, maps, parallel results, SQL without ORDER BY) | identical after canonicalising | sort, or compare as multisets, with canonical NULL, -0.0, NaN and collation | canonicalising too far (removing duplicates turns a multiset into a set) |
| Floating point | within a stated tolerance | element-wise `abs(a - e) <= atol + rtol * abs(e)` against a higher-precision reference (fp64, or arbitrary precision on small cases); special values exact. Starting points from the libraries' defaults: fp32 rtol 1.3e-6 / atol 1e-5, fp16 1e-3 / 1e-5, bf16 1.6e-2 / 1e-5, fp64 1e-7 / 1e-7 | a tolerance looser than the original's own error against the reference; reordered reductions on ill-conditioned inputs |
| Stochastic | statistically equivalent | original and candidate over at least 5 seeds each; an equivalence test (two one-sided tests) at a margin agreed with the user, per class or segment; the gate's false-fail rate measured on original against original | seeds chosen after seeing results; a mean that hides one class getting worse |
| Lossy by design | quality floor, not equivalence | per-class quality above the floor plus an agreed margin, on real data outside the repository; the user is told "not equivalent, floor X" | sitting just above the floor; rare classes under a sample cut |
| Code or a transformation (compiler passes, code generators, rewriters) | same behaviour, not the same text | run the original's and the candidate's output on a test corpus and compare results; byte equality is too strict | a corpus too small to exercise the changed path |
| Side effects (files, database writes, network calls) | same final state and same external calls | compare the resulting state canonicalised, and a log of external calls | effects moved outside what the gate inspects |

Keep the original implementation as the oracle and compare candidate against it on generated inputs, including edge sizes (0, 1, odd, very large, NaN, empty), not only on stored golden files. Run the reference in a separate process, or on fresh buffers, so a candidate can't return the reference's output.
