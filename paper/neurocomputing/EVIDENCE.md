# Claim-to-evidence map: Neurocomputing manuscript

- **Scope:** every quantitative or checkable claim in `main.tex`, the file that holds it, and how it was
  checked.
- **Paths:** repository-relative. `E/` is `reports/neurocomputing-2026-10-27/`, the research-strengthening
  evidence. `R/` is `reports/neurocomputing-review-repairs-2026-10-28/`, the repairs made after a review of
  it.
- **Checking:** each number was recomputed from the named file on 28 October 2026. Historical numbers were
  recomputed from the unchanged historical files, or traced to the JMLR evidence map
  (`paper/jmlr-mloss/EVIDENCE.md`) that checked them.
- **Not claimed:** none of this makes the manuscript submission-ready; see `R/READINESS.md`.

## Software and its identity (Sections 2.1 to 2.4, Table 1, availability)

| Claim | Evidence | How checked; limits |
|---|---|---|
| The implementation described is revision `c9b9384` | `git log`; `R/PROGRESS_LOG.md` | `c9b9384` is the last commit that changed library code. It corrects two validation defects in `30bd3f6`, the previously described revision, which is merged into `main` (`d5881cb`). Later commits change only evidence, documentation, tooling and the manuscript |
| No reported result changes with the repairs | `R/regression/w3-repaired/comparison.json`; `R/recovery/verification/` | W3, rerun on `c9b9384`, has identical status vectors, verdicts, exit statuses and episode counts on all 14 fixtures. The CartPole analysis reads JSON records, so the code change cannot alter it. The LunarLander evidence is historical and unchanged (`R/integrity/`) |
| Each experiment's recorded source state | `E/cartpole-study/records/main/study.json` (`software.git`: `e7c3fab`, clean); `E/workflow-comparison/FINDINGS.md` (`5c7a62a`); `E/linux-replay/run-40545198707-dea292c/` (`dea292c`); the LunarLander runs' own metadata | The paper names these separately from the described revision |
| MIT, version 0.1.0, Python 3.12 and 3.13 in CI | `LICENSE`, `lunarlab/__init__.py`, `.github/workflows/ci.yml` | Direct inspection |
| The adapter layer is available to any task with an adapter. Adapters exist for LunarLander-v3 and CartPole-v1. Policies are audited through a function from observation to action, and the study workflow trains only PPO | `lunarlab/audit/adapters.py` (two registered adapters); `lunarlab/audit/evaluate.py::audit_policy`; `lunarlab/audit/study.py::protocol_problems` ("only PPO is supported") | Demonstrated on these two tasks only; untested on others (Section 6) |
| The wrapper refuses a non-finite original reward, term output or weight, and finite values whose episode total would overflow, naming the quantity. A failed episode yields no summary, and steps are refused until reset | `lunarlab/audit/core.py` (`EpisodeAudit.add`, `training_reward`, `RewardAccountingWrapper.step`); `tests/test_audit_contracts.py` (the six overflow tests and the finite-value tests) | Before and after: `R/defects/before-fix-d1f69c6.json` (a completed episode with infinite totals, a bare `OverflowError`) and `after-fix-working-tree.json`. The guarantee covers the values the wrapper checks |
| Versioned provenance: description digest, implementing files' digests and git status, each implementing function's source digest and captured values. It does not fingerprint imported modules, module-level data or library versions, and two lambdas on one line with equal captured values are indistinguishable | `lunarlab/audit/provenance.py` (schema 2); `tests/test_audit_contracts.py` (identity and incomplete-capture tests) | `E/contracts/provenance-identity-*.txt`: schema 1 could not tell the reproduced pair apart; schema 2 tells all three tested pairs apart. The stated limits are in the module documentation |
| Potential shaping is zero-absorbing at termination (also when the time limit coincides) and uses the final observation at truncation; checked against sums calculated by hand | `lunarlab/audit/core.py::potential_shaping`; `tests/test_audit_contracts.py` (Chain environment: discounted sums 4.0 absorbing, 3.6355 truncated, 4.0 with both flags and with a `TimeLimit` coincidence) | Exact-value tests. The invariance theorem is cited, not tested |
| Seed contract: non-empty nonnegative integers, no booleans, floats or numeric strings, no duplicates or overlap, checked before any environment exists | `lunarlab/audit/contracts.py`, `lunarlab/audit/evaluate.py`; `lunarlab/config.py::EvalProtocol` | `E/contracts/`: the old-API probe fails 16 of 17 checks on `932cf1c` (the passing one is a valid-input control) and passes 17 of 17 after the fix |
| SB3 re-seeds environments when a model is built; the layer sets the first-reset seeds afterwards and verifies them | `lunarlab/audit/study.py::train_run`; the seeding test in `tests/test_audit_contracts.py`; `examples/cartpole_audit.py` | `E/contracts/candidates-before-932cf1c.json`. All 18 CartPole runs record effective seeds equal to the protocol's (`R/recovery/verification/`) |
| `audit-artifact verify` runs the equivalents of S1-S7 and S9 on LunarLab's exported artifacts before any episode. `reproduce` adds S10. S8 needs a recorded trajectory and is the library function `check_trajectory` | `lunarlab/audit/study.py::verify_artifact` (file and policy digests, protocol digest and validity with the seed contract, reward definition rebuilt from finite parameters, recorded channels, finite values, accounting identity, outcome schema); `check_trajectory`; `E/workflow-comparison/workflows/w3_lunarlab.py` (which function serves each check) | Exported artifacts carry `policy.zip`, `protocol.json`, `run.json`, `evaluation.json` and `reward.json`, with no trajectory |
| Malformed recorded episodes are reported field by field, never raised or converted, and distinguished from integrity failures | `lunarlab/audit/study.py::check_recorded_episodes`, `verify_artifact` (`kind`, `failed_kinds`); `lunarlab/cli.py` (`MALFORMED-RECORD (blocking)`); `tests/test_audit_study.py` | Before: `TypeError` on null returns (`R/defects/before-fix-d1f69c6.json`). Both kinds block replay with exit 1; numerical differences exit 3 |

## Illustrative LunarLander audit (Section 3, Figure 2, abstract)

| Claim | Evidence | How checked; limits |
|---|---|---|
| Baseline: IQM 268.6, 488 of 500 landings (97.6%); time penalty 265.3 and 93.6%; potential 262.3 and 94.0% | `docs/results/results.json`, PPO groups with fixed physics, `per_seed[].evaluation` | Recomputed: the integer-boundary trimmed mean of the five policy means, and the landing counts. Historical file unchanged (`R/integrity/`) |
| Hover: IQM −33.1, 0 of 500 landings, 400 timeouts, mean re-scored training return 496.3, mean original return −23.5 | Same file: group `Flawed hover bonus` (`training_return_rescored_mean` 496.33, `mean_original_return` −23.55, `timeout_rate` 0.8) | Recomputed. Final-test re-scoring; the two reward scales differ by design |
| Improvement intervals include 0.5 | Stored intervals [0, 0.72] and [0, 0.76] in `results.json` | From the JMLR evidence map; no equivalence claimed |
| 38 policies, 3,800 episodes, ten groups; recomputation from exported episodes recovers all summaries | `results.json`; `reports/jmlr/original-machine-2026-10-19/study_summary_comparison.json` | Counts recomputed. The recomputation itself is historical (19 October) |
| Protocol: 1,003,520 transitions, seeds 0 to 4, validation 10,000 to 10,009, test 20,000 to 20,099 | Saved run configurations; the JMLR evidence map | Historical, unchanged |
| Figure 2's plotted values | `paper/neurocomputing/figures/final_test_audit.verification.json` | `build_figures.py` re-derives all 20 policy values and four IQMs (exact; IQM within 1e-12) and stops on any difference |

## Audit-workflow comparison (Section 4.1, Figure 3, abstract)

| Claim | Evidence | How checked; limits |
|---|---|---|
| Protocol, fault inventory, fixtures and programs hashed before any program ran on the fixtures | `E/workflow-comparison/protocol/HASHES.sha256` (16:35:26 UTC), committed in `5c7a62a` before the results commit `8d4f6c4`; run start 16:35:55 | Order shown by commit and file times. Development used fixtures from the pilot policy |
| W2, a separately implemented reference, and W3 agree on every check in all 14 designed cases, rejecting the 12 faults before any episode. W1 attempted none of the checks | `E/workflow-comparison/results/summary.json`, `MATRIX.md`, `raw/` | Recomputed: equal S1-S10 status vectors on all 14 cases, and W2 and W3 executed no episode on any fault. The same developer, assisted by AI tools, wrote the specification and all three programs; no independent team validated them |
| The swapped checkpoint's returns under W1 were indistinguishable | `raw/W1/F01-checkpoint-swapped/stdout.txt` | 500.0 ± 0, as for C0 |
| 65, 277 and 152 counted lines | `E/workflow-comparison/results/code_size.json`; `count_code.py` | Not a measure of researcher time |
| Medians 20.9, 21.0 and 21.7 s; peak memory 288, 289 and 293 MB; no cost difference claimed | `E/workflow-comparison/results/cost/cost.json` | Five randomized blocks, bimodal wall times |

## CartPole study (Section 4.2, Figure 4, abstract)

| Claim | Evidence | How checked; limits |
|---|---|---|
| Three PPO designs; seeds 50 to 54; 100,096 transitions per run; checkpoints every 10,240; 20 validation and 100 test seeds; original-reward selection; frozen and digest-checked before the test | `E/cartpole-study/protocol/` (fixed at 16:08:41 UTC before training); `E/cartpole-study/records/main/runs/*/` | Committed since `417b91a` (`R/recovery/`). Checked from the records for all 18 runs (`R/recovery/verification/VERIFICATION.md`): budgets, effective seeds, schedule, validation means, the selection rule with earliest-tie handling (up to 10 tied checkpoints), frozen digests, test seeds, ordering and aggregates, and 192 checkpoint files |
| Hand calculations and a pilot confirmed the payments | `E/cartpole-study/records/pilot/hand-calculation-check.txt` | 20 episodes: training return = T + 1000 exactly; discounted to 1.1e-13 |
| Original and potential designs: every test episode reached the 500-step limit, for all ten policies; flawed bonus: mean original return 9.31 [9.22, 9.40], no completions in 500 episodes, own training return about 1009 | `E/cartpole-study/results/results.json`, `RESULTS.md` | Recomputed from the committed run records in a fresh extraction: `results.json` equal, `RESULTS.md` byte-identical (`R/recovery/verification/`) |
| At all ten evaluated checkpoints of every flawed-bonus run, the mean original validation return lay between 9.05 and 9.55 | `records/main/runs/failure-bonus-s5*/run.json` (`checkpoints[].validation`) | An observation from 10,240 transitions on. Nothing was recorded before the first checkpoint, so the paper makes no claim about when the behavior was learned |
| Training compute | `records/{main,pilot}/compute.jsonl` | 1,501,440 + 61,440 transitions |

## Engineering and reproducibility (Section 5, Table 2, Figure A.1)

| Claim | Evidence | How checked; limits |
|---|---|---|
| CI run 40712412847 at `c9b9384`: 594 passed, four Windows-only skips, 86.04% combined coverage; 293 Windows tests on each of 3.12 and 3.13; 15 browser flows; 194 release tests | `R/ci/run-40712412847-c9b9384/ci.log`, `coverage-linux/coverage.json` (8,995 of 10,155 statements, 1,976 of 2,596 branches), `run.json` | Earlier revisions: `30bd3f6`, run 40694880778 (572, 85.95%, 291, 192); `11145b3`, run 40546091715 (567, 85.91%, 288, 189) |
| Thirteen kinds of tampered or malformed artifacts refused before execution | `tests/test_audit_study.py::TAMPERING` | 13 entries |
| Runtime reproductions found contract gaps; a subsequent review found two more, corrected without changing a reported result | `E/contracts/`; `R/defects/`; `R/regression/` | See the rows above |
| The archive of this revision is byte-identical on Linux CI and on the recording machine | `R/ci/run-40712412847-c9b9384/source-archive/SHA256SUMS`; `R/validation/source-archive-c9b9384-windows.SHA256SUMS` and `.log` | Both `3427d9a9…cdf5eac60`. The Windows build installed fresh and passed 194 release tests and 14 of 14 smoke checks |
| Table 2: throughput, ratios 1.021, 1.053 and 1.221, peaks 310, 310 and 314 MB | `reports/jmlr/benchmarks/standard-2026-10-19T180346+0000/`; `reports/jmlr/original-machine-2026-10-19/benchmark_recomputation.json` | Historical (JMLR evidence map) |
| All 38 exports retain the historical bytes | `reports/jmlr/learned-reward-repair-2026-10-24/`; `R/integrity/` | The repaired bundle (335 files) is in the protected inventory and unchanged |
| Three examples: 300 of 300 episodes match on Windows CI and the recording machine | `R/ci/run-40712412847-c9b9384/reproducibility-windows-py3.12/` and `-py3.13/`; `reports/jmlr/original-machine-2026-10-19/reevaluation/` | Selected fields only |
| Six learned-reward policies: 600 of 600 episodes match on the recording machine from an empty data home | `reports/jmlr/learned-reward-repair-2026-10-24/` | Historical; rechecked `exact` from the package validation (`R/validation/`) |
| Linux, three examples: mean differences at most 1.52; largest about 0.28, 11.9 and 192; landing 96%, 0% and 29% | `R/ci/run-40712412847-c9b9384/reproducibility-linux/reproduce-*-linux.json` | Identical to runs 40694880778 and 40546091715 |
| Linux, six learned-reward policies: integrity kept; median differences at most 0.0013 in magnitude; largest 0.007 to 18.3; outcome agreement 99 to 100%; landing unchanged except 35% versus 34%; no Holm-corrected difference | `E/linux-replay/run-40545198707-dea292c/` | Recomputed from per-episode rows. Not a test of equivalence |
| Nine open-loop trace comparisons | `reports/jmlr/reproducibility/traces/`; `R/ci/run-40712412847-c9b9384/reproducibility-linux/divergence-*-linux.json` | Historical analysis; a mechanism class, not a unique cause |
| Every figure is produced by a deterministic script with a manifest; Figure 1's code references are checked | `paper/neurocomputing/figures/build_figures.py`, `MANIFEST.json`, `*.values.json`, `FIGURES.md` | Rebuilt from a fresh extraction with identical plotted values (`R/validation/`) |
| AI tools and versions | `docs/neurocomputing/AI_TOOL_VERSIONS.md` | Session metadata for 27 and 28 October: Claude Code 2.1.299, `claude-opus-5-5` (local transcript, not in the repository) |

## Availability statement

| Claim | Evidence | How checked; limits |
|---|---|---|
| `30bd3f6` is merged into `main`; the repairs are on `research/neurocomputing-review-repairs`, not merged | `git log origin/main` (`d5881cb`, PR #1); the branch | True on 28 October 2026 |
| Protocols, raw episode records, comparison outputs, Linux replay reports and figure manifests are in the repository | `E/`, including `cartpole-study/records/*/runs/` since `417b91a`; `tools/validate_review_package.py` | The dependency check confirms every file the records name is present (`R/validation/`) |
| The six learned-reward packages are in the repository | `examples/learned-reward-artifacts/SHA256SUMS` | 60 files, identical to the repaired bundle's list |
| The CartPole checkpoints and the comparison fixtures' policies accompany the review package | `E/cartpole-study/records/frozen-checkpoints.sha256`; `E/workflow-comparison/protocol/HASHES.sha256` | Outside Git; verified in the package (`R/validation/`) |
| No release or archive identifier exists yet | `R/DEPOSIT.md` | A local deposit candidate exists; nothing was published |
