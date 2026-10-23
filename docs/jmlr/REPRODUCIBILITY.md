# Reproducibility: what the evidence establishes

Independent review, 19 October 2026; base source `67440c6`. Historical records remain unchanged. A local reporting patch makes the compared fields and the limits of aggregate tests explicit.

## Four different questions

| Question | Evidence and result | What it does not establish |
|---|---|---|
| Artifact integrity | All nine payload files in the three example packages match SHA-256 manifests; loaded weights are checked | Correctness of experimental design or numerical reproduction |
| Exact selected-field agreement | Windows CI matches 300/300 episode summaries on five fields | Bitwise identity of full trajectories, observations, RNG state or all platforms |
| Numerical agreement | Linux differences are measured per episode and in aggregates | An unspecified acceptable-error guarantee |
| Scientific conclusion | These three policies retain the same observed strict-landing rates and similar mean returns | Equivalence of distributions, all conclusions, or all 38 policies |

The five `COMPARED_FIELDS` are length, original return, training return, environment outcome, and strict pad landing. “Exact” uses Python numeric equality; it does not compare every trajectory value or floating-point bit pattern. Legacy JSON keys named `bit_identical` are retained for compatibility, not as a broader claim. Separate trace comparisons inspect recorded actions/observations for a small chosen subset.

## Recorded Windows and published Linux CI results

| Policy | Windows mean original return | Linux CI mean | Exact summary matches on Linux | Strict landing rate on both |
|---|---:|---:|---:|---:|
| PPO baseline seed 0 | 265.8558 | 265.8615 | 0/100 | 96% |
| PPO hover bonus seed 0 | −21.2456 | −20.7658 | 0/100 | 0% |
| DQN baseline seed 0 | 155.3644 | 156.8764 | 0/100 | 29% |

Maximum individual **original-return** differences are approximately 0.277, 11.9 and 192. The older generic maximum field mixes original and training returns: the hover value 126.48 is a training-return discrepancy. It must not be reported as the maximum original-return discrepancy. The local patch retains that legacy field but adds separate maxima and clearer terminal output.

Latest public CI: https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/39147464434 . Detailed historical trace and paired-test records are committed under `reports/jmlr/reproducibility/ci/run-39144191758-4fd30db/`. The final green run's logs corroborate the main reproduction results; the earlier run was not entirely green because of a subsequently fixed frontend race.

## Independent local re-evaluation

All three artifacts were independently evaluated on their 100 stored test seeds, without retraining or modifying checkpoints. Means were 265.8615463, −20.7658475 and 156.8687128; landing rates were 96%, 0% and 29%. The DQN mean differs slightly from published Linux CI, itself evidence that “Linux” is not a complete numerical-platform identity. All three have status `numerical-difference` (exit 3), with integrity intact.

Paired mean-original-return differences (this execution minus recorded Windows) and stored 95% bootstrap intervals:

| Policy | Difference | Interval |
|---|---:|---:|
| PPO baseline | 0.00577 | [−0.00373, 0.01557] |
| PPO hover bonus | 0.47970 | [−0.38861, 1.35168] |
| DQN baseline | 1.50427 | [−2.97862, 6.51676] |

These are conditional checkpoint re-evaluations, not training-seed uncertainty intervals. Reports are in `reports/jmlr/independent-review-2026-10-19/`.

## Recording-machine re-evaluation of the revised source

On 19 October 2026 the revised source (base `67440c6` plus the local review changes) re-evaluated the three packages on the Windows 11 machine that recorded them (Python 3.12.13, the `requirements.lock` environment). All three have status `exact` (exit 0): 300 of 300 episodes match on the five compared summary fields, mean original returns 265.8558, −21.2456 and 155.3644 equal the records, and all nine open-loop traces are identical to the committed Windows reference traces (`trace-artifact` exit 0, no first difference). `reproduce-smoke --training-determinism` exits 0. This repeats the recording platform's selected-field agreement with the corrected reporting code; it does not test another platform. Reports and exit codes: `reports/jmlr/original-machine-2026-10-19/reevaluation/`.

All 38 policies of the published study were exported on the same machine with `export-artifact`, without retraining (`tools/export_study_artifacts.py`). Every exported checkpoint, configuration and recorded evaluation is a byte-identical copy of the run's file, every checkpoint is the one its freeze record names, and recomputing each policy summary and group IQM from the 3,800 recorded episodes reproduces `docs/results/results.json` (`tools/compare_study_summaries.py`; inventory and digests in `reports/jmlr/original-machine-2026-10-19/study-artifacts/`). The 38 packages have not been re-evaluated: the export shows the recorded evidence is complete and self-consistent, not that it reproduces elsewhere. The bundle (28 MB) is supplied for review; it is not yet publicly archived.

## Current status, 24 October 2026: learned-reward dependencies

**Defect.** The independent follow-up of 21 October found that the six learned-reward exports omitted the two reward models that re-score their training return. Those packages passed their own integrity checks but could not be replayed in a fresh data home (`reports/jmlr/independent-followup-2026-10-21/`).

**Original dependencies.** The two model directories, `data/reward_models/rm-20261015-235825-rm-300-4877/` and `rm-20261015-235939-rm-3000-cfd0/`, are present in the original data home. Each `meta.json` and `model.npz` is byte-identical to the committed historical manifest: four files, 58,250 bytes, sizes and SHA-256 recorded in `reports/jmlr/learned-reward-repair-2026-10-24/reward_models_verification.json`. They were copied unchanged; nothing was retrained, refitted or regenerated.

**Fix.** The reviewer's dependency patch was ported unchanged for runtime, CLI, export, reporting and regression tests:
- `export-artifact` bundles `reward_model/model.npz` and `meta.json` with digests, and refuses a missing or inconsistent model.
- `reproduce-artifact` checks the bundled model's identity, digests and metadata digest before evaluating. Any failure is a blocking `integrity-failure` (exit 1) without evaluation.
- Evaluation uses a temporary registry built from the package, with the model cache cleared, never the local registry.
- The study exporter checks every payload the manifest lists.

The findings below are three separate properties:

- **Artifact integrity.** All 38 policies were re-exported. Checkpoint, configuration and recorded-evaluation bytes are unchanged against both `runs/` and the 19 October export. The six learned-reward packages add only the two model files, identical to the originals; the other 32 are unchanged. A legacy package without the model, a missing `model.npz` and a corrupted `meta.json` each produce `integrity-failure`, exit 1, with no episode evaluated (`.../replay/negative-*.json`).
- **Exact summary matching, recording platform.** Replayed from an otherwise empty data home on the Windows 11 recording machine, the six learned-reward policies are `exact`: 600 of 600 episodes match on the five compared fields, including the training return computed by the bundled model. Recorded mean original returns are reproduced (150.9828, −304.5362, −342.1870, 196.2573, 221.5753, 182.7522). With the modified code the three example packages also remain `exact`, with all nine reference traces identical (`.../examples-reevaluation/`).
- **Cross-platform numerical agreement.** Not assessed for the learned-reward packages, which were replayed on Windows only. For the three example packages, CI run 40015498622 at `4116599` reports `numerical-difference` (exit 3) on Linux and `exact` on Windows with Python 3.12 and 3.13 (`reports/jmlr/reproducibility/ci/run-40015498622-4116599/`).

The repaired bundle is supplied for review and is not yet publicly archived.

## Statistical gate and trace interpretation

The current gate applies paired sign-flip tests to mean return and exact McNemar tests to selected outcome rates, with Holm correction within an artifact. Non-rejection is a regression screen, not an equivalence test. The tests can miss meaningful changes. No practical equivalence margins were prespecified. Do not choose margins after seeing these differences and portray them as prospective. Future equivalence analysis should state tolerable changes in return and landing probability before evaluation, explain their research meaning, and include enough independent evidence to resolve them.

The nine sampled open-loop trace comparisons show first simulator differences after 2–24 steps, of order 10^-8, without greedy-action flips when evaluating policy inference on recorded observations. This supports a simulator-numerics explanation for the sampled divergences. It does not identify a particular compiler, architecture or Box2D operation as the unique cause. The Windows perturbation experiments are corroborative interventions, not conclusive identification of Linux build behavior. The reference traces were generated later; they are not full original trajectories for all historical final tests.

The platform key uses OS and numerical-library version strings. It omits some hardware/build information and uses the artifact export context, so equal keys do not prove equal original evaluation environments.

## Continuation and historical preservation

PPO/DQN continuation restores learning state at a checkpoint boundary; DQN replay data are included. Environments and all RNG streams are not restored. Never describe this as guaranteed bit-identical continuation.

The first-pass manifest lists 1,667 protected files. Only 393 are present in the public archive: 391 match byte-for-byte and two derived outcome reports match after reversing LF/CRLF normalization. The remaining 1,274 are absent. This independently verifies neither the complete earlier 1,667-file claim nor the later self-reported 1,699-file claim. It does not show altered results: the two differences are exactly line-ending conversion. This review preserves every historical result and model in its supplied source; a separate final hash inventory records that fact.

**Checked on the original machine, 19–20 October 2026** (`reports/jmlr/original-machine-2026-10-19/integrity_claims_check.json` and `historical_manifest_check.json`): all 1,667 files of the committed manifest are present and byte-identical. The correction-pass statement "1,699 files byte-identical" was a miscount: its scan records (1,782-file baseline, 1,803 after) give 1,708 unchanged files, 74 regenerated deliverables (64 coverage-report files, 10 figure files) and 21 additions, and all 1,708 remain byte-identical. A separate first-pass scan also had 1,699 entries: the 1,667 files plus 32 first-pass deliverables, of which 4 are unchanged, 16 differ only by CRLF→LF conversion at the first commit, 2 benchmark PDFs were re-rendered from unchanged raw data before that commit, and 10 figure files were regenerated in commit `4fd30db`. No experiment record, checkpoint or evaluation is among the changed files.

## Commands

From an installed checkout, write reports to a new directory:

```bash
python -m lunarlab reproduce-artifact --artifact examples/artifacts/ppo-baseline-s0 --report review/ppo-baseline.json
python -m lunarlab reproduce-artifact --artifact examples/artifacts/ppo-hover-bonus-s0 --report review/ppo-hover.json
python -m lunarlab reproduce-artifact --artifact examples/artifacts/dqn-baseline-s0 --report review/dqn-baseline.json
python -m lunarlab reproduce-smoke --training-determinism --report review/smoke.json
```

Exit 0: compared fields match or meet a user-specified return tolerance. Exit 3: measured cross-platform differences without a detected aggregate regression. Exit 1: integrity, same-key unexpected difference, or aggregate regression requiring investigation. Exit 2: usage error. Retain the report and actual exit code; never use an unconditional success fallback to hide failures.
