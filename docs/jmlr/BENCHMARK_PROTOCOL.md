# Benchmark audit and repeat protocol

The manuscript now uses **only** `reports/jmlr/benchmarks/standard-2026-10-19T180346+0000/`, the repeat with corrected memory sampling described at the end of this document. The earlier `standard-2026-10-18T132206+0000/` run (clean revision `2c41b422e6bab1feb702d4d1901b337f0fcd21a7`), audited below, and the October 17 benchmark are separate measurements and remain unchanged.

## Recomputed historical measurements

Windows 11; Intel i7-13620H; one PyTorch thread; PPO; 102,400 transitions/run; three repetitions/configuration. Shared settings include four environments, 1,024 steps, batch size 64, four epochs, discount 0.999 and 64×64 actor/critic networks. Raw JSONL and metadata identify the actual dependencies.

| Configuration | Transitions/s, mean ± sample SD | Mean loop ratio | Mean wall ratio | Recorded mean process peak |
|---|---:|---:|---:|---:|
| SB3 + Monitor | 2097.75 ± 57.17 | 1.00000 | 1.00000 | 310.52 MB |
| Reward accounting | 2100.76 ± 166.53 | 1.00209 | 1.00209 | 311.45 MB |
| Full LunarLab training workflow | 1985.49 ± 42.34 | 1.05633 | 1.22821 | 323.38 MB |

Ratios compare means of durations, not inverses of mean throughput. The loop interval includes model/environment setup and subtracts timed validation/checkpoint operations for the full workflow. It is not a pure optimizer-only interval. The complete training workflow adds about 22.8% elapsed time in this measurement, including a mean 18,780 validation transitions and 8.29 seconds of evaluation. The approximate 5.6% loop increase and 22.8% workflow increase are different quantities. Three repetitions do not establish a universal upper bound or that accounting is faster than SB3.

## Memory defect and local fix

At the historical revision, configuration C calls `_measure_recording` before reading the process peak. A/B do not generate that replay. Thus the listed memory values cover different process workloads, even though the wall-time interval excludes recording. The manuscript explicitly discloses this; it makes no training-only memory-overhead claim from them.

The local patch samples peak memory before optional recording, and labels its scope in output. The regression test verifies ordering. The process peak still includes imports, setup, training and checkpointing; it is not allocator-specific model memory. Existing values were not rewritten or estimated. Repeat the benchmark on the eventual reviewed source to produce a comparable new measurement.

## Repetition plan

1. Use the intended source revision in an isolated environment with recorded locked dependencies and idle hardware. Record OS/build, CPU, thread count, source cleanliness and actual transition count.
2. Run the existing standard benchmark; keep all nine raw rows, metadata and command output. This is a modest engineering benchmark, not a new scientific comparison between PPO and DQN.
3. Verify identical hyperparameters/budgets; inspect errors and recording scope. Report both means and variability. Do not select only favorable repetitions.
4. Generate the table from the new raw output, preserving the old measurement in its original path. Update manuscript/evidence links to the actual new directory and revision.

```bash
python -m lunarlab overhead-benchmark --profile standard --transitions 102400 --repeats 3 --out review/benchmark
```

Check `--help` on the selected version before running; output locations must be new. No such standard rerun was claimed during this audit. The small benchmark regression workload in tests is not a replacement publication measurement.

## Repeat with corrected memory sampling, 19 October 2026

Run `reports/jmlr/benchmarks/standard-2026-10-19T180346+0000/`, started 18:03:46 UTC on the original machine (Windows 11 build 26300, Intel i7-13620H, 16 logical cores, 16.8 GB, Python 3.12.13 in the `requirements.lock` environment, one PyTorch thread), with the standard profile: `python -m lunarlab overhead-benchmark --profile standard` (102,400 transitions, three repetitions, rotated configuration order, each run in a fresh process). No other workload was started during the run; an editor and idle background applications stayed open. All nine rows completed; hyperparameters and transition counts are identical across configurations.

**Source state.** Base `67440c6` plus the uncommitted review changes; `summary.json` records only `dirty: true`, so the run folder also holds `source_state.json`: the tracked diff (24 files, SHA-256 `919ec79c…`) and a digest of every untracked file, recorded 14 s before the run and re-checked afterwards (unchanged; the only additions were the run's own outputs). Between `2c41b42` (the earlier run) and this source, the training path is unchanged: the package differs in `cli.py`, `divergence.py`, `jobs.py` (job supervisor only) and `reproduce.py`, plus the benchmark's own memory-sampling order in `overhead.py`. If the submitted revision changes training code, run the benchmark again.

| Configuration | Transitions/s, mean ± sample SD | Mean loop ratio | Mean wall ratio | Mean process peak |
|---|---:|---:|---:|---:|
| SB3 + Monitor | 2157.91 ± 22.25 | 1.00000 | 1.00000 | 309.73 MB |
| Reward accounting | 2114.65 ± 29.46 | 1.02052 | 1.02052 | 310.49 MB |
| Full LunarLab training workflow | 2050.53 ± 55.44 | 1.05281 | 1.22103 | 313.92 MB |

The full workflow adds 18,780 validation transitions (mean 7.90 s) and checkpoint writes (mean 0.08 s). Ratios compare means of durations, as above; `benchmark_recomputation.json` in `reports/jmlr/original-machine-2026-10-19/` recomputes every value from `raw.jsonl` for both this run and the 18 October run.

**Memory scope.** Every row records `peak_memory_scope = "process through training and checkpointing, before optional recording"` (Windows peak working set via psutil). All three configurations are therefore measured over the same phases: the full workflow's peak is 4.2 MB (1.4%) above plain SB3, and the 18 October value of 323.38 MB included optional replay generation. Each figure is a whole-process peak including Python, PyTorch and Gymnasium imports, not allocator-level model memory.

**Interpretation.** The timing pattern repeats the 18 October run: about 5% longer training loops for the full workflow (1.053 here, 1.056 then) and about 22% more elapsed time once its validation and checkpointing are included (1.221 here, 1.228 then). Reward accounting alone measured 1.021 here and 1.002 then. With three repetitions per configuration and sample SDs of 1–3% of mean throughput here (up to 8% in the earlier run), the accounting-only overhead is not resolved, and none of these numbers is an upper bound. The run measures one machine and does not replace platform-specific measurement.
