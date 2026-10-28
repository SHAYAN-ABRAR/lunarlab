# Claim-to-evidence map: Neurocomputing manuscript

- **Scope:** every quantitative or checkable claim in `main.tex`, the file that holds it, and how it was
  checked.
- **Paths:** repository-relative. `E/` stands for `reports/neurocomputing-2026-10-27/`.
- **Checking:** each new number was recomputed from the named file on 28 October 2026. Historical numbers were
  recomputed from the unchanged historical files, or traced to the JMLR evidence map
  (`paper/jmlr-mloss/EVIDENCE.md`) that checked them.
- **Not claimed:** none of this makes the manuscript submission-ready. See `E/READINESS.md`.

## Software (Sections 2.1 to 2.4, Table 1)

| Claim | Evidence | How checked; limits |
|---|---|---|
| Revision `30bd3f6`, MIT, version 0.1.0, Python 3.12 and 3.13 in CI | `git log`, `LICENSE`, `lunarlab/__init__.py`, `.github/workflows/ci.yml` | `30bd3f6` (provenance schema 2) is the last commit on the review branch that changed library code; later commits change evidence, documentation and the manuscript only. The previous code revision, `11145b3`, is kept in `E/ci/run-40546091715-11145b3/` |
| The wrapper refuses a non-finite original reward, term output or weight, naming its source | `lunarlab/audit/contracts.py`, `lunarlab/audit/core.py`; `tests/test_audit_contracts.py` | Tests, and the before/after reproductions in `E/contracts/` (`candidates-before-932cf1c.json`, `candidates-after-fix.json`) |
| Versioned provenance: full description digest; each implementing file's digest and git status; each implementing function's own source digest and captured values; `incomplete` for code typed into a session or a captured value without a JSON form | `lunarlab/audit/provenance.py` (schema 2, `30bd3f6`); `tests/test_audit_contracts.py` (`test_terms_with_equal_descriptions_are_told_apart_by_their_code_or_captured_values`, `test_a_captured_value_without_a_json_form_makes_the_identity_incomplete`, the temporary-git-repository test) | `E/contracts/provenance-identity-11145b3.txt` and `-fixed-working-tree.txt`: schema 1 could not tell apart the reproduced pair (two lambdas paying 1 and 1,000) or two closures of one factory; schema 2 tells all three tested pairs apart. Two lambdas on one line with equal captured values, and code in imported modules, remain unidentified. The legacy 16-hex `terms_hash` is unchanged for valid definitions |
| Potential shaping is zero-absorbing at termination, also when the time limit coincides, and uses the final observation at truncation; checked against sums calculated by hand | `lunarlab/audit/core.py::potential_shaping`; `tests/test_audit_contracts.py` (Chain environment: discounted shaping sum 4.0 when absorbing, 3.6355 when truncated, 4.0 with both flags and with a `TimeLimit` coincidence) | Exact-value tests. The invariance theorem is cited, not tested |
| Seed contract: non-empty nonnegative integers, no booleans, floats or numeric strings, no duplicates or overlap, checked before any environment exists | `lunarlab/audit/contracts.py`, `lunarlab/audit/evaluate.py`; `lunarlab/config.py::EvalProtocol` for the main pipeline | `E/contracts/`: the old-API probe fails 16 of 17 checks on `932cf1c` (the passing one is a valid-input control) and passes 17 of 17 after the fix |
| SB3 re-seeds environments when a model is built; the layer sets the first-reset seeds afterwards and verifies them | `lunarlab/audit/study.py::train_run` (refuses if the effective seeds differ); seeding test in `tests/test_audit_contracts.py`; `examples/cartpole_audit.py` | `E/contracts/candidates-before-932cf1c.json` records `PPO(seed=0)` replacing the example's seed roots 1,000,000 to 1,000,003 with 0 to 3. Later auto-resets continue each environment's stream |
| `lunarlab audit-artifact verify\|reproduce` checks an artifact before any episode runs | `lunarlab/cli.py::cmd_audit_artifact`, `lunarlab/audit/study.py::verify_artifact`; `tests/test_audit_study.py` | 11 tampering cases (`TAMPERING`), each refused before execution, and the CLI exit codes |

## Illustrative LunarLander audit (Section 3, Figure 2, abstract)

| Claim | Evidence | How checked; limits |
|---|---|---|
| Baseline: IQM 268.6, 488 of 500 landings (97.6%); time penalty 265.3 and 93.6%; potential 262.3 and 94.0% | `docs/results/results.json`, PPO groups with fixed physics, `per_seed[].evaluation` | Recomputed on 28 October: the integer-boundary trimmed mean of the five policy means, and the landing counts. Historical file unchanged (`E/integrity/`) |
| Hover: IQM −33.1, 0 of 500 landings, 400 timeouts, mean re-scored training return 496.3, mean original return −23.5 | Same file: group `Flawed hover bonus`, `across_seeds.training_return_rescored_mean.mean` = 496.33, `mean_original_return.mean` = −23.55, `timeout_rate.mean` = 0.8 | Recomputed. The re-scoring is of final-test episodes; the two reward scales differ by design |
| Improvement intervals include 0.5 | Stored probability-of-improvement intervals [0, 0.72] and [0, 0.76] in `results.json` | From the JMLR evidence map; no equivalence claimed |
| 38 policies, 3,800 episodes, ten groups; recomputation from exported episodes recovers all summaries | `results.json` (10 groups, 38 policies); `reports/jmlr/original-machine-2026-10-19/study_summary_comparison.json` | Group and policy counts recomputed. The recomputation itself is historical (19 October) |
| Protocol: 1,003,520 transitions, seeds 0 to 4, validation 10,000 to 10,009, test 20,000 to 20,099, the stated PPO settings | Saved run configurations; the JMLR evidence map | Historical, unchanged |
| Figure 2's plotted values | `paper/neurocomputing/figures/final_test_audit.verification.json` | `build_figures.py` re-derives all 20 policy values and four IQMs from `results.json` (exact; IQM within 1e-12) and stops on any difference |

## Audit-workflow comparison (Section 4.1, Figure 3, abstract)

| Claim | Evidence | How checked; limits |
|---|---|---|
| Protocol, fault inventory, fixtures and programs hashed before any program ran on the fixtures; development used separate fixtures | `E/workflow-comparison/protocol/HASHES.sha256` (16:35:26 UTC), committed in `5c7a62a` (16:35:43) before the results commit `8d4f6c4`; the run began at 16:35:55 (`run-start.txt`) | Order shown by commit and file times. The development fixtures came from the pilot policy |
| W2 and W3 identical on every check in all 14 cases: C0 accepted with an exact replay, C1 accepted as a numerical difference (exit 3), all 12 faults rejected through the targeted check before any episode | `E/workflow-comparison/results/summary.json` (`rows[].checks[S1..S10].status`, `verdict`, `episodes_executed`), `MATRIX.md`, `raw/<workflow>/<case>/` | Recomputed: the S1 to S10 status vectors are equal on all 14 cases (only free-text details differ); W2 and W3 executed 0 episodes on each fault |
| W1 attempted none of the checks and evaluated 100 episodes in every case; the swapped checkpoint's returns were indistinguishable | Same file, W1 rows (`verdict` `unchecked`, 100 episodes); `raw/W1/F01-checkpoint-swapped/stdout.txt` | W1 reported 500.0 ± 0 on both C0 and F01 |
| 65, 277 and 152 counted lines | `E/workflow-comparison/results/code_size.json`, rule in `count_code.py` | Non-blank, non-comment, non-docstring lines counted with `tokenize`. Not a measure of researcher time |
| Medians 20.9, 21.0 and 21.7 s; peak memory 288, 289 and 293 MB; no cost difference claimed | `E/workflow-comparison/results/cost/cost.json` (`summary.W*.wall_seconds.median`, `peak_self_MB.median` = 288.0, 288.9, 293.4) | Five randomized blocks. Wall times were bimodal, as `FINDINGS.md` records |
| Limits: one task, policy and trajectory; one developer, assisted by AI tools, wrote everything | `E/workflow-comparison/FINDINGS.md` | Stated in the paper |

## CartPole study (Section 4.2, Figure 4, abstract)

| Claim | Evidence | How checked; limits |
|---|---|---|
| Three PPO designs; seeds 50 to 54; 100,096 transitions per run; checkpoints every 10,240; 20 validation and 100 test seeds; selection on original reward; frozen and digest-checked before the test | `E/cartpole-study/protocol/protocol.json` and `PROTOCOL.md`, fixed by `PROTOCOL.sha256` at 16:08:41 UTC before any training; `records/main/runs/*/run.json` | Each `run.json` records the effective seeds, every checkpoint's validation, the selection and the frozen digests |
| RL Baselines3 Zoo's tuned CartPole settings | `E/cartpole-study/protocol/rl-zoo-ppo.yml` and `rl-zoo-ppo.source.txt` | Copied from the cited Zoo commit |
| Hand calculations and a labelled pilot confirmed the payments before the main runs | `E/cartpole-study/records/pilot/hand-calculation-check.txt` | On 20 recorded episodes, training return = T + 1000 exactly, and the discounted return matches to 1.1e-13 |
| Original and potential designs: every test episode reached the 500-step limit, for all ten policies | `E/cartpole-study/results/results.json` (`selected.policies`) | Recomputed from the records: see the next row |
| Flawed bonus: mean original return 9.31, 95% interval 9.22 to 9.40, no completions in 500 episodes, training return about 1009 | Same file; `RESULTS.md` | All 500 episodes end with the pole falling. The interval is a percentile bootstrap over the five policies, conditional on the test seeds |
| Failing quickly was learned before the first evaluated checkpoint | `records/main/runs/failure-bonus-s5*/run.json`, `checkpoints[0].validation.mean_original_return` | 9.05 to 9.55 at 10,240 transitions for all five runs |
| The results reproduce from the committed records | `python E/cartpole-study/analyze.py E/cartpole-study/records/main OUT` | Run on 28 October: `RESULTS.md` byte-identical, `results.json` equal |
| Training compute | `records/{main,pilot}/compute.jsonl` | 1,501,440 + 61,440 transitions; main training 5 min 11 s, testing 2 min |

## Engineering and reproducibility (Section 5, Table 2, Figure A.1)

| Claim | Evidence | How checked; limits |
|---|---|---|
| CI run 40694880778 at `30bd3f6`: 572 passed, four Windows-only skips, 85.95% combined coverage; 291 Windows tests on each of 3.12 and 3.13; 15 browser flows; 192 release tests | `E/ci/run-40694880778-30bd3f6/ci.log`, `coverage-linux/coverage.json` (8,914 of 10,070 statements, 1,934 of 2,552 branches), `run.json` | Read from the log and the coverage totals. At the previous code revision `11145b3` (run 40546091715): 567, 85.91%, 288 and 189 |
| Eleven kinds of tampered artifacts refused before execution | `tests/test_audit_study.py::TAMPERING` | 11 entries |
| Runtime reproductions found contract gaps that the tests now cover | `E/contracts/` | See the seed-contract and provenance rows above |
| The archive of this revision is byte-identical on Linux CI and on the recording machine | `E/ci/run-40694880778-30bd3f6/source-archive/SHA256SUMS`; `E/validation/source-archive-30bd3f6-windows.SHA256SUMS` and `.log` | Both `88bea614…6b9e116`. The Windows build also installed into a fresh environment and passed 192 release tests and the 14-check smoke reproduction |
| Table 2: throughput, ratios 1.021, 1.053 and 1.221, peaks 310, 310 and 314 MB | `reports/jmlr/benchmarks/standard-2026-10-19T180346+0000/`; recomputation in `reports/jmlr/original-machine-2026-10-19/benchmark_recomputation.json` | Historical (JMLR evidence map); one machine, three repetitions |
| All 38 exports retain the historical bytes | `reports/jmlr/learned-reward-repair-2026-10-24/`; `E/integrity/` | The repaired bundle (335 files) is in the protected inventory and unchanged by this work |
| Three examples: 300 of 300 episodes match on Windows CI and on the recording machine | `E/ci/run-40694880778-30bd3f6/reproducibility-windows-py3.12/` and `-py3.13/` (each `exact`, 100 of 100; the same at `11145b3`); `reports/jmlr/original-machine-2026-10-19/reevaluation/` | The selected fields only, not full trajectories |
| Six learned-reward policies: 600 of 600 episodes match on the recording machine from an empty data home | `reports/jmlr/learned-reward-repair-2026-10-24/` | Historical (24 October); one package was rechecked `exact` from `examples/learned-reward-artifacts/` on 27 October |
| Linux, three examples: mean differences at most 1.52; largest single differences about 0.28, 11.9 and 192; landing rates 96%, 0% and 29% | `E/ci/run-40694880778-30bd3f6/reproducibility-linux/reproduce-*-linux.json` | Recomputed: mean differences 0.006, 0.48 and 1.512; maxima 0.277, 11.879 and 191.7; rates unchanged. Identical in run 40546091715 at `11145b3` |
| Linux, six learned-reward policies: integrity kept, all numerical differences; median differences at most 0.0013 in magnitude; largest 0.007 to 18.3; outcome agreement 99 to 100%; landing rates unchanged except 35% versus 34%; no Holm-corrected aggregate difference | `E/linux-replay/run-40545198707-dea292c/reproduce-*-linux.json`, `replay-summary-linux.json`, `exit-codes.txt` | Recomputed from the per-episode rows: signed medians −0.00123 to +0.00021; maxima 0.007, 0.013, 1.036, 10.03, 11.70 and 18.35; no metric significant. Not a test of equivalence |
| Nine open-loop trace comparisons show early simulator-state differences with unchanged greedy actions | `reports/jmlr/reproducibility/traces/` and the divergence reports; `E/ci/run-40694880778-30bd3f6/reproducibility-linux/divergence-*-linux.json` | Historical analysis (JMLR evidence map). A mechanism class, not a unique cause |
| Every figure is produced by a deterministic script with a manifest; Figure 1's code references are checked | `paper/neurocomputing/figures/build_figures.py`, `MANIFEST.json`, `*.values.json`; `check_manuscript.py` | `build_figures.py` checks each named function with `importlib`; `check_manuscript.py --final` compares the figure digests with the manifest |
| AI tools and versions | `docs/neurocomputing/AI_TOOL_VERSIONS.md` | For this revision, the session metadata (Claude Code 2.1.299, model `claude-opus-5-5`, 27 and 28 October) was read from the local transcript. The transcript is not in the repository |

## Availability statement

| Claim | Evidence | How checked; limits |
|---|---|---|
| The six learned-reward packages are in the repository | `examples/learned-reward-artifacts/` and its `SHA256SUMS` | 60 files, identical to the repaired bundle's `SHA256SUMS` |
| The evidence is on the review branch, not merged or released | `git branch -r`; this folder | True on 28 October 2026 |
| The CartPole checkpoints accompany the review package | `E/cartpole-study/records/frozen-checkpoints.sha256` | 36 digests. The files are outside Git |
| No public archive deposit yet | `E/ARCHIVE.md` | Stated as unresolved |
