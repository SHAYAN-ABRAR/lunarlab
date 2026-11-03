# LunarLab Linux validation and draft review

**Assistant-executed — 2–3 November 2026.**

Read this report first. Raw outputs are preserved under each run directory; derived tables are in `analysis-final/`. The source archives and manuscript have not been changed. The package includes a focused repair note for Claude.

## Execution outcomes

| Run | Runtime / requested scope | Validator exit | Final report | failed_steps |
|---|---|---|---|---|
| `run-a` | Default threads; requested A | 0 | written | `[]` |
| `run-b` | Default threads; requested B, interrupted | not captured | absent / partial | `None` |
| `run-c` | Default threads; first C, interrupted | not captured | absent / partial | `None` |
| `diagnostic-single-thread-all` | First one-thread attempt, interrupted | not captured | absent / partial | `None` |
| `run-c-final` | Default threads; recovery C, interrupted after 30 original pairs | not captured | absent / partial | `None` |
| `diagnostic-full-final` | OMP/MKL = 1; all 38 study + 18 CartPole replays saved; parent interrupted before comparison | not captured | absent / partial | `None` |
| `run-c-one-thread` | OMP/MKL = 1; complete requested C scope, explicit runtime diagnostic | 1 | written | `['commands']` |

The full-study diagnostic completed its replay stage, not its parent validator. The final C invocation changes numerical-library threading only; it is not an unqualified default-runtime completion. Missing final reports and exits for interrupted runs are not inferred from later executions. The interruption context is retained in `diagnostics/c-one-thread-context.json`.

## Archive integrity

| Input | Bytes | SHA-256 | CRC | Manifest |
|---|---:|---|---|---|
| LunarLab-final-validation-review-2026-11-02-f9615d1.zip | 8,811,631 | `c39733ab3d8a9fd3275385f94762d38e6245328ca387d75d8e6fcd126007e9a0` | passed | 735/735; no missing, changed or unlisted files |
| LunarLab-archive-candidate-2026-11-01-a38d07f.zip | 80,659,343 | `8a02752eed0a86d862fa0365e2cc2ae60a66fe8768293d07c4a57dc7fc7f9cd7` | passed | 2179/2179; no missing, changed or unlisted files |

Candidate MD5: `f323c1b0417ba3a216a338caa5a369ea`. Initial extraction and manifest results are retained. `evidence/integrity_final.json` records the closing verification of the supplied files and extracted originals.

## Every top-level step

| Step | A | C with one thread | Full-study diagnostic (interrupted parent) |
|---|---|---|---|
| checksums | true | true | not captured |
| work_copy | true | true | not captured |
| dependencies | true | true | not captured |
| environment | true | true | not captured |
| platform | true | true | not captured |
| cartpole_records | true | true | not captured |
| figures | true | true | not captured |
| lunarlander_bundle | true | true | not captured |
| lunarlander_statistics | true | true | not captured |
| commands | true | false | not captured |

Every individual command’s `ok` value is in `analysis-final/run-summary.json` and the original `validation.json`. All completed runs use Python 3.12.14 on Linux 6.18.57/glibc 2.39, CPU torch 2.14.1+cpu, NumPy 2.5.4, Box2D 2.3.10, Gymnasium 1.4.0 and Stable-Baselines3 2.9.0. Read-only package-metadata checks match all 63 locked requirements in each fresh environment.

| Run | Checksums | Dependencies / problems | CartPole analysis | Bundle | Recorded statistics |
|---|---|---|---|---|---|
| `run-a` | 2179 | 624 / 0 | 18 runs, 0 problems | 333 members, 38 policies, 6 reward-model packages | 38 policies, 3800 episodes, all_match=True |
| `run-c-one-thread` | 2179 | 624 / 0 | 18 runs, 0 problems | 333 members, 38 policies, 6 reward-model packages | 38 policies, 3800 episodes, all_match=True |

Both CartPole analyses reproduce the stored JSON and Markdown. Main records cover 1,501,440 transitions and pilot records 61,440. These are checks of stored training records, budgets, seeds, selection/tie handling and frozen/test records, not new training.

The 624 dependency checks comprise: study index 72; analysis inputs 54; CartPole protocol 4; frozen checkpoints 36; exported artifacts 108; original comparison 79; follow-up comparison 7; figure inputs 10; learned-reward package files 60; historical bundle files 2; named checkpoint checks 192. The last count includes inventory records for 156 omitted checkpoints, not 192 available checkpoint binaries.

## Figures: values and bytes are separate

- `run-a`: build exit 0, check exit 0; 4 value JSON files identical, 0 different, 0 missing; 14/20 output files byte-identical, 6 different.
  Different output bytes: `architecture.png`, `architecture.svg`, `cartpole_study.png`, `cartpole_study.svg`, `linux_replay.png`, `workflow_comparison.png`.
- `run-c-one-thread`: build exit 0, check exit 0; 4 value JSON files identical, 0 different, 0 missing; 14/20 output files byte-identical, 6 different.
  Different output bytes: `architecture.png`, `architecture.svg`, `cartpole_study.png`, `cartpole_study.svg`, `linux_replay.png`, `workflow_comparison.png`.

The four value files are `architecture.values.json`, `cartpole_study.values.json`, `linux_replay.values.json` and `workflow_comparison.values.json`. The 20 outputs include data/manifests as well as graphics. Figure 2 (`final_test_audit`) is copied from existing rendering; its 20 policy values and four IQMs are independently re-derived and verified. This invocation does not newly render that drawing.

## Replays

| Run | Retained replay reports | Status counts | Invalid numerical-difference labels |
|---|---:|---|---:|
| `run-a` | 20 | `{'exact': 12, 'numerical-difference': 8}` | 0 |
| `run-b` | 5 | `{'aggregate-disagreement': 1, 'numerical-difference': 4}` | 0 |
| `run-c` | 20 | `{'exact': 12, 'numerical-difference': 8}` | 0 |
| `diagnostic-single-thread-all` | 0 | `{}` | 0 |
| `run-c-final` | 20 | `{'exact': 12, 'numerical-difference': 8}` | 0 |
| `diagnostic-full-final` | 58 | `{'exact': 12, 'numerical-difference': 45, 'aggregate-disagreement': 1}` | 0 |
| `run-c-one-thread` | 20 | `{'exact': 12, 'numerical-difference': 8}` | 0 |

For every numerical-difference report, the summarizer checks `integrity_ok=true`, `same_platform=false` and `aggregates.consistent=true`. A non-significant aggregate screen is not an equivalence test. Each per-policy reason and metric is retained in the raw report and replay-summary JSON/CSV.

### All-study diagnostic: individual policy statuses

| Policy/run identifier | Status | Exit | Integrity | Recorded / Linux mean original return |
|---|---|---:|---|---|
| `20261015-223113-baseline-s0-standard-c5af` | numerical-difference | 3 | True | 265.855781 / 265.861546 |
| `20261015-223115-baseline-s1-standard-3b80` | numerical-difference | 3 | True | 272.999194 / 272.983286 |
| `20261015-223115-baseline-s2-standard-5b5d` | numerical-difference | 3 | True | 250.124021 / 250.296253 |
| `20261015-223115-baseline-s3-standard-7b0f` | numerical-difference | 3 | True | 268.322606 / 268.320123 |
| `20261015-223115-baseline-s4-standard-f7f6` | numerical-difference | 3 | True | 271.504395 / 271.518783 |
| `20261015-223115-hover-bonus-s0-standard-3376` | numerical-difference | 3 | True | -21.245551 / -20.765847 |
| `20261015-223115-hover-bonus-s1-standard-9a39` | numerical-difference | 3 | True | -30.334601 / -30.027280 |
| `20261015-223115-hover-bonus-s2-standard-d887` | numerical-difference | 3 | True | -47.801831 / -53.869971 |
| `20261015-223115-hover-bonus-s3-standard-c5ba` | numerical-difference | 3 | True | 38.589067 / 35.568819 |
| `20261015-223115-hover-bonus-s4-standard-cc47` | numerical-difference | 3 | True | -56.956643 / -57.253973 |
| `20261015-223115-potential-s0-standard-0162` | numerical-difference | 3 | True | 261.688365 / 261.703197 |
| `20261015-223115-potential-s1-standard-9f70` | numerical-difference | 3 | True | 228.929490 / 230.000489 |
| `20261015-223115-potential-s2-standard-7f75` | numerical-difference | 3 | True | 256.942776 / 256.799074 |
| `20261015-223115-potential-s3-standard-91e6` | numerical-difference | 3 | True | 277.176751 / 277.169146 |
| `20261015-223115-potential-s4-standard-0b22` | numerical-difference | 3 | True | 268.169188 / 268.166578 |
| `20261015-223115-time-penalty-s0-standard-2582` | numerical-difference | 3 | True | 266.975159 / 267.155527 |
| `20261015-223115-time-penalty-s1-standard-6fc9` | numerical-difference | 3 | True | 262.477104 / 262.467424 |
| `20261015-223115-time-penalty-s2-standard-9f88` | numerical-difference | 3 | True | 269.706234 / 269.689323 |
| `20261015-223115-time-penalty-s3-standard-f398` | numerical-difference | 3 | True | 236.537421 / 234.707665 |
| `20261015-223115-time-penalty-s4-standard-828d` | numerical-difference | 3 | True | 266.527730 / 266.434071 |
| `20261015-224317-dqn-baseline-s0-custom-2fe1` | numerical-difference | 3 | True | 155.364438 / 156.876417 |
| `20261015-224318-dqn-baseline-s1-custom-1fa1` | numerical-difference | 3 | True | 207.589368 / 203.669468 |
| `20261015-224318-dqn-baseline-s2-custom-f083` | numerical-difference | 3 | True | 270.062428 / 270.059747 |
| `20261015-224318-dqn-hover-bonus-s0-custom-aefc` | aggregate-disagreement | 1 | True | 224.069949 / 230.447299 |
| `20261015-224318-dqn-hover-bonus-s1-custom-e122` | numerical-difference | 3 | True | 97.168784 / 95.897704 |
| `20261015-224318-dqn-hover-bonus-s2-custom-9c0f` | numerical-difference | 3 | True | 7.417291 / 7.112639 |
| `20261015-224318-dqn-potential-s0-custom-ee4b` | numerical-difference | 3 | True | 227.178044 / 225.263689 |
| `20261015-224318-dqn-potential-s1-custom-5487` | numerical-difference | 3 | True | 244.855751 / 244.654241 |
| `20261015-224318-dqn-potential-s2-custom-5b10` | numerical-difference | 3 | True | 149.709423 / 149.572100 |
| `20261015-224318-dqn-time-penalty-s0-custom-c4a9` | numerical-difference | 3 | True | 116.759364 / 117.313061 |
| `20261015-224318-dqn-time-penalty-s1-custom-dc89` | numerical-difference | 3 | True | 207.345433 / 201.972358 |
| `20261015-224318-dqn-time-penalty-s2-custom-9494` | numerical-difference | 3 | True | 207.452365 / 203.505315 |
| `20261015-235939-custom-s0-standard-0274` | numerical-difference | 3 | True | 150.982790 / 151.357966 |
| `20261015-235939-custom-s1-standard-b692` | numerical-difference | 3 | True | -304.536227 / -304.536464 |
| `20261015-235940-custom-s0-standard-d28b` | numerical-difference | 3 | True | 196.257253 / 196.001066 |
| `20261015-235940-custom-s1-standard-ce26` | numerical-difference | 3 | True | 221.575331 / 221.565122 |
| `20261015-235940-custom-s2-standard-a299` | numerical-difference | 3 | True | -342.187017 / -342.186781 |
| `20261015-235940-custom-s2-standard-dbc1` | numerical-difference | 3 | True | 182.752214 / 182.972937 |

Retained all-study reports: **38/38**; episodes: **3,800**. Counts must not be called complete unless all 38 are present. These exclude the two additional default published-package replays.

### CartPole: every artifact

| Artifact | A | C with one thread | Full-study diagnostic |
|---|---|---|---|
| `main-failure-bonus-s50` | exact (exit 0) | exact (exit 0) | exact (exit 0) |
| `main-failure-bonus-s51` | exact (exit 0) | exact (exit 0) | exact (exit 0) |
| `main-failure-bonus-s52` | exact (exit 0) | exact (exit 0) | exact (exit 0) |
| `main-failure-bonus-s53` | exact (exit 0) | exact (exit 0) | exact (exit 0) |
| `main-failure-bonus-s54` | exact (exit 0) | exact (exit 0) | exact (exit 0) |
| `main-original-s50` | exact (exit 0) | exact (exit 0) | exact (exit 0) |
| `main-original-s51` | exact (exit 0) | exact (exit 0) | exact (exit 0) |
| `main-original-s52` | exact (exit 0) | exact (exit 0) | exact (exit 0) |
| `main-original-s53` | exact (exit 0) | exact (exit 0) | exact (exit 0) |
| `main-original-s54` | exact (exit 0) | exact (exit 0) | exact (exit 0) |
| `main-upright-potential-s50` | numerical-difference (exit 3) | numerical-difference (exit 3) | numerical-difference (exit 3) |
| `main-upright-potential-s51` | numerical-difference (exit 3) | numerical-difference (exit 3) | numerical-difference (exit 3) |
| `main-upright-potential-s52` | numerical-difference (exit 3) | numerical-difference (exit 3) | numerical-difference (exit 3) |
| `main-upright-potential-s53` | numerical-difference (exit 3) | numerical-difference (exit 3) | numerical-difference (exit 3) |
| `main-upright-potential-s54` | numerical-difference (exit 3) | numerical-difference (exit 3) | numerical-difference (exit 3) |
| `pilot-failure-bonus-s90` | exact (exit 0) | exact (exit 0) | exact (exit 0) |
| `pilot-original-s90` | exact (exit 0) | exact (exit 0) | exact (exit 0) |
| `pilot-upright-potential-s90` | numerical-difference (exit 3) | numerical-difference (exit 3) | numerical-difference (exit 3) |

## Follow-up comparisons and memory telemetry

### run-a / comparison

Runner exit: **0**; step ok: **True**; pairs **42/42**; classes: `{'exact-agreement': 40, 'platform-numerical-difference': 2}`; blocking rows: **0**.

Set checks: `{"w2_w3_status_agreement": {"ok": true, "cases": 14, "disagreeing_or_missing": []}, "faults_rejected_before_execution": {"ok": true, "faults": 12, "not_rejected_before_execution": []}, "w1_unchecked": {"ok": true, "cases": 14, "not_unchecked": []}}`.

- `W2/C0-clean`: this machine differs from the recording platform in os (Windows recorded, Linux here), torch (2.14.1 recorded, 2.14.1+cpu here); S10: numerical-difference: 2 of 100 episodes differ
- `W3/C0-clean`: this machine differs from the recording platform in os (Windows recorded, Linux here), torch (2.14.1 recorded, 2.14.1+cpu here); S10: numerical-difference: 2 of 100 episodes differ; median |return difference| 0, largest 0; outcomes agree in 100%, on a different platform (os, torch differ); no compared aggregate differs significantly from the record

Memory: 0 reported measurements; 42 explicit nulls with status; 0 missing result JSONs; 0 zeros. Missing results are not valid null telemetry.
- Explicit unavailable values report `NoSuchProcess` with the affected PID; every exact status string is retained in `analysis-final/memory-telemetry.csv` and raw stdout.

### run-c-one-thread / comparison

Runner exit: **0**; step ok: **True**; pairs **42/42**; classes: `{'exact-agreement': 40, 'platform-numerical-difference': 2}`; blocking rows: **0**.

Set checks: `{"w2_w3_status_agreement": {"ok": true, "cases": 14, "disagreeing_or_missing": []}, "faults_rejected_before_execution": {"ok": true, "faults": 12, "not_rejected_before_execution": []}, "w1_unchecked": {"ok": true, "cases": 14, "not_unchecked": []}}`.

- `W2/C0-clean`: this machine differs from the recording platform in os (Windows recorded, Linux here), torch (2.14.1 recorded, 2.14.1+cpu here); S10: numerical-difference: 2 of 100 episodes differ
- `W3/C0-clean`: this machine differs from the recording platform in os (Windows recorded, Linux here), torch (2.14.1 recorded, 2.14.1+cpu here); S10: numerical-difference: 2 of 100 episodes differ; median |return difference| 0, largest 0; outcomes agree in 100%, on a different platform (os, torch differ); no compared aggregate differs significantly from the record

Memory: 1 reported measurements; 41 explicit nulls with status; 0 missing result JSONs; 0 zeros. Missing results are not valid null telemetry.
- `W3/F01-checkpoint-swapped`: 63631360 bytes; `measured: rss`. This is the program's measurement, not an independently validated process peak.
- Explicit unavailable values report `NoSuchProcess` with the affected PID; every exact status string is retained in `analysis-final/memory-telemetry.csv` and raw stdout.

### run-c-one-thread / comparison-unmodified

Runner exit: **0**; step ok: **False**; pairs **42/42**; classes: `{'failure': 36, 'platform-numerical-difference': 1, 'exact-agreement': 5}`; blocking rows: **36**.

Set checks: `{"w2_w3_status_agreement": {"ok": false, "cases": 14, "disagreeing_or_missing": ["C0-clean", "F01-checkpoint-swapped", "F02-recorded-digest-corrupted", "F03-protocol-mismatch", "F04-dependency-missing", "F05-dependency-changed", "F06-coercible-seed", "F07-overlapping-seeds", "F08-nonfinite-parameter", "F10-inconsistent-totals", "F11-potential-at-truncation", "F12-outcome-schema-mismatch"]}, "faults_rejected_before_execution": {"ok": false, "faults": 12, "not_rejected_before_execution": ["W2/F01-checkpoint-swapped", "W3/F01-checkpoint-swapped", "W2/F02-recorded-digest-corrupted", "W3/F02-recorded-digest-corrupted", "W2/F03-protocol-mismatch", "W3/F03-protocol-mismatch", "W2/F04-dependency-missing", "W3/F04-dependency-missing", "W2/F05-dependency-changed", "W3/F05-dependency-changed", "W2/F06-coercible-seed", "W3/F06-coercible-seed", "W2/F07-overlapping-seeds", "W3/F07-overlapping-seeds", "W2/F08-nonfinite-parameter", "W3/F08-nonfinite-parameter", "W2/F10-inconsistent-totals", "W3/F10-inconsistent-totals", "W2/F11-potential-at-truncation", "W3/F11-potential-at-truncation", "W2/F12-outcome-schema-mismatch", "W3/F12-outcome-schema-mismatch"]}, "w1_unchecked": {"ok": false, "cases": 14, "not_unchecked": ["C0-clean", "F01-checkpoint-swapped", "F02-recorded-digest-corrupted", "F03-protocol-mismatch", "F04-dependency-missing", "F05-dependency-changed", "F06-coercible-seed", "F07-overlapping-seeds", "F08-nonfinite-parameter", "F09-original-channel-absent", "F10-inconsistent-totals", "F11-potential-at-truncation", "F12-outcome-schema-mismatch"]}}`.

- `W2/C0-clean`: this machine differs from the recording platform in os (Windows recorded, Linux here), torch (2.14.1 recorded, 2.14.1+cpu here); S10: numerical-difference: 2 of 100 episodes differ

Memory: 6 reported measurements; 0 explicit nulls with status; 36 missing result JSONs; 0 zeros. Missing results are not valid null telemetry.
- `W1/C1-numerical-difference`: 63082496 bytes; `original program has no availability-status field`. This is the program's measurement, not an independently validated process peak.
- `W2/C0-clean`: 63078400 bytes; `original program has no availability-status field`. This is the program's measurement, not an independently validated process peak.
- `W2/C1-numerical-difference`: 63082496 bytes; `original program has no availability-status field`. This is the program's measurement, not an independently validated process peak.
- `W2/F09-original-channel-absent`: 63123456 bytes; `original program has no availability-status field`. This is the program's measurement, not an independently validated process peak.
- `W3/C1-numerical-difference`: 63082496 bytes; `original program has no availability-status field`. This is the program's measurement, not an independently validated process peak.
- `W3/F09-original-channel-absent`: 63123456 bytes; `original program has no availability-status field`. This is the program's measurement, not an independently validated process peak.

| Blocking pair | Child exit | stderr last line (full stderr retained) |
|---|---:|---|
| W1/C0-clean | 1 | psutil.NoSuchProcess: process PID not found (pid=219) |
| W3/C0-clean | 1 | psutil.NoSuchProcess: process PID not found (pid=223) |
| W1/F01-checkpoint-swapped | 1 | psutil.NoSuchProcess: process PID not found (pid=235) |
| W2/F01-checkpoint-swapped | 1 | psutil.NoSuchProcess: process PID not found (pid=237) |
| W3/F01-checkpoint-swapped | 1 | psutil.NoSuchProcess: process PID not found (pid=238) |
| W1/F02-recorded-digest-corrupted | 1 | psutil.NoSuchProcess: process PID not found (pid=239) |
| W2/F02-recorded-digest-corrupted | 1 | psutil.NoSuchProcess: process PID not found (pid=241) |
| W3/F02-recorded-digest-corrupted | 1 | psutil.NoSuchProcess: process PID not found (pid=242) |
| W1/F03-protocol-mismatch | 1 | psutil.NoSuchProcess: process PID not found (pid=243) |
| W2/F03-protocol-mismatch | 1 | psutil.NoSuchProcess: process PID not found (pid=245) |
| W3/F03-protocol-mismatch | 1 | psutil.NoSuchProcess: process PID not found (pid=246) |
| W1/F04-dependency-missing | 1 | psutil.NoSuchProcess: process PID not found (pid=247) |
| W2/F04-dependency-missing | 1 | psutil.NoSuchProcess: process PID not found (pid=249) |
| W3/F04-dependency-missing | 1 | psutil.NoSuchProcess: process PID not found (pid=250) |
| W1/F05-dependency-changed | 1 | psutil.NoSuchProcess: process PID not found (pid=251) |
| W2/F05-dependency-changed | 1 | psutil.NoSuchProcess: process PID not found (pid=253) |
| W3/F05-dependency-changed | 1 | psutil.NoSuchProcess: process PID not found (pid=254) |
| W1/F06-coercible-seed | 1 | psutil.NoSuchProcess: process PID not found (pid=255) |
| W2/F06-coercible-seed | 1 | psutil.NoSuchProcess: process PID not found (pid=257) |
| W3/F06-coercible-seed | 1 | psutil.NoSuchProcess: process PID not found (pid=258) |
| W1/F07-overlapping-seeds | 1 | psutil.NoSuchProcess: process PID not found (pid=259) |
| W2/F07-overlapping-seeds | 1 | psutil.NoSuchProcess: process PID not found (pid=261) |
| W3/F07-overlapping-seeds | 1 | psutil.NoSuchProcess: process PID not found (pid=262) |
| W1/F08-nonfinite-parameter | 1 | psutil.NoSuchProcess: process PID not found (pid=263) |
| W2/F08-nonfinite-parameter | 1 | psutil.NoSuchProcess: process PID not found (pid=265) |
| W3/F08-nonfinite-parameter | 1 | psutil.NoSuchProcess: process PID not found (pid=266) |
| W1/F09-original-channel-absent | 1 | psutil.NoSuchProcess: process PID not found (pid=267) |
| W1/F10-inconsistent-totals | 1 | psutil.NoSuchProcess: process PID not found (pid=271) |
| W2/F10-inconsistent-totals | 1 | psutil.NoSuchProcess: process PID not found (pid=273) |
| W3/F10-inconsistent-totals | 1 | psutil.NoSuchProcess: process PID not found (pid=274) |
| W1/F11-potential-at-truncation | 1 | psutil.NoSuchProcess: process PID not found (pid=275) |
| W2/F11-potential-at-truncation | 1 | psutil.NoSuchProcess: process PID not found (pid=277) |
| W3/F11-potential-at-truncation | 1 | psutil.NoSuchProcess: process PID not found (pid=278) |
| W1/F12-outcome-schema-mismatch | 1 | psutil.NoSuchProcess: process PID not found (pid=279) |
| W2/F12-outcome-schema-mismatch | 1 | psutil.NoSuchProcess: process PID not found (pid=281) |
| W3/F12-outcome-schema-mismatch | 1 | psutil.NoSuchProcess: process PID not found (pid=282) |

The unmodified comparison runner can itself exit 0 while its children fail. The repaired validator assesses the rows, preserves stderr and fails the command/overall validation. In this completed C run, all 36 blocking rows retain NoSuchProcess stderr; six original programs returned assessable results. Missing-result set-check failures do not establish that the intended faulty inputs actually executed episodes. Those levels must not be conflated. The frozen originals are not edited to make this sandbox pass.

## Scope and evidence labels

This is an **assistant-executed technical audit**, not a human peer review or evidence of independent researcher adoption. No training, source edits, commits, pushes, contacts, DOI reservations, deposits or submissions were performed. Supplied archives and extracted originals were treated as read-only. Each validator invocation used a new output directory; the validator made its own working copy and fresh Python 3.12 environment.

Labels used here: **executed** means run by this assistant with retained output; **inspected** means code, document or PDF inspection; **CI evidence** means retrieved GitHub records; **historical** means supplied records of previous experiments; **diagnostic** means an explicitly different execution configuration; **pending** means not established. An absent final report is not a pass. A replay accepted as a platform numerical difference is not a statistical equivalence result.

Some later outputs became unavailable when this conversation resumed. The original complete A run and partial B/C output survived. Those partial logs are retained, and their final JSON/exit statuses have not been reconstructed. New recovery runs are identified separately. Details are in `evidence/session-continuity.json`; unavailable prior-session outputs are not counted as deliverable evidence.

## Public source state and revision identities

**CI evidence, refreshed 3 November 2026:** [PR #3](https://github.com/SHAYAN-ABRAR/lunarlab/pull/3) merged at 2026-11-02 15:27:47 UTC. Current `main` is `05ca17f7308e4e0d34773371d1abe229ea6fdf0f`. [Main CI 41471828824](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/41471828824) completed successfully; all six jobs succeeded. [Branch CI 41469293319](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/41469293319) also succeeded at `f9615d1`. This is distinct from the tests executed in this audit.

The candidate remains the supplied `a38d07f` archive. The manuscript identifies the library implementation as `c9b9384`, the validator revision as `954607b`, and historical experiment revisions separately. **Executed:** all 62 library files in the candidate match the supplied `c9b9384` source archive. Do not replace every revision with `main`: that would obscure which implementation, experiment and package were tested. The statement that PR #3's branch is unmerged is now stale.

## Interpretation of the Linux evidence

The checks support archive integrity and exact recomputation of the recorded policy summaries and ten group IQMs. This validates transcription and analysis of stored results; it does not reproduce policy training. The LunarLander bootstrap confidence intervals were not recomputed by this validator.

The default published-artifact mode runs two LunarLander packages: a PPO hover-bonus example and one learned-reward policy. It does not rerun all three examples or all six learned-reward packages. Do not convert a successful A run into a claim about all 38 policies. Historical nine-policy CI evidence remains separately identified.

The default-thread partial B run already found a blocking result for `dqn-flawed-hover-bonus/20261015-224318-dqn-hover-bonus-s0-custom-aefc`: integrity passed, but the original-return mean changed from **224.06994853107503** to **230.24694369083645**. The paired mean difference was **6.176995159761403**, with a reported 95% interval **[1.2978154259522012, 12.62374294678863]** and unadjusted p **0.008899110088991101**; it failed the implemented Holm-adjusted within-policy screen. Strict landing changed from 84% to 88%; the largest individual return difference was about 227.68. A higher return still fails an agreement check. Neither data corruption nor a specific numerical cause follows from this result.

The preserved single-policy diagnostic limited OMP/MKL threading to one and reproduced the same compared episode records and aggregate result. It therefore did not remove this failure. The later full-study diagnostic replay stage also flags this policy: Linux mean 230.44729895787546, difference 6.377350426800416, paired interval [1.5763015911835385, 12.768412652090857], unadjusted p 0.0032996700329967. These are separate executions, not interchangeable numerical records. The full-study replay stage is complete, but its parent validator was interrupted before its final comparison/report. It does not retrospectively complete the default-thread B invocation. These observations under overlapping jobs are not a performance benchmark.

**Diagnostic, executed:** all 38 LunarLander replay reports retain integrity; 37 are numerical-difference and one is aggregate-disagreement. The main PPO reward-exploitation observation survives: the five hover policies still have 0 strict landings in 500 episodes (400 recorded timeouts, 402 here), while baseline policies retain 488/500 strict landings. The per-policy-mean IQMs are approximately -34.89 for hover and 268.57 for baseline in this replay. `analysis-final/replay-group-observations.json` keeps all ten original groups separate. These descriptive checks neither establish equivalence nor turn the unequal PPO/DQN budgets into a controlled algorithm comparison.

The aggregate screen adjusts its compared metrics within each policy, not a new family containing every metric of all 38 policies. A gate failure should be disclosed and investigated, but it is not by itself proof of a persistent distribution shift. Likewise, a non-significant screen does not establish equivalence. Preserve thresholds and historical artifacts; report both central behavior and tail differences.

For CartPole, the preserved complete A run has 12 exact artifacts and six numerical differences, all in the upright-potential design (main seeds 50–54 and pilot seed 90). Across their 1,560 evaluated episodes, original returns, lengths and outcomes agree; differences concern the training-return field. The largest absolute training-return difference is about 0.01999749. These accepted labels require intact integrity, a different recorded platform and no aggregate disagreement.

## Read-only code spot-checks

**Executed:** the original protocol manifest verifies **79/79** entries, and the follow-up manifest verifies **7/7**. `derive_v2_programs.py --check` exits 0. The two requested modules, `tests/test_followup_comparison.py` and `tests/test_validator_failures.py`, pass **89 tests** on Linux (exit 0, 9.41 s). This is not a rerun of the entire project suite.

**Inspected:** the 189-line `comparison-v2/CHANGES.diff` is confined to optional memory telemetry and the associated result fields, assignments and comments. It does not alter scientific inputs, checks, thresholds or evaluation behavior. The original hashed programs remain unchanged.

**Fault confirmed:** `source/tools/validate_review_package.py`, lines 334–340, gives both `uv pip install` calls the log name `venv-pip-install.log`. The local package installation overwrites the dependency-install log. Existing logs are included as found; the overwritten stream cannot be recovered. Use distinct deterministic names in a future revision and test that both logs survive. The package's own SUMMARY already acknowledges this issue; this audit verifies it rather than claiming a new discovery.

The comparison adapter correctly treats a result missing because of process failure separately from an acceptable numerical difference. A legacy literal outcome field can still contain `false alarm`; the follow-up's platform-aware class is the operative classification. Do not report that preserved legacy field as the final Linux classification.

## Manuscript inspection and minimal proposed edits

**Inspected:** all 21 rendered pages of `manuscript-build/main.pdf`, SHA-256 `ebd27ba80c0491f8590dd4fbbf25da4ca7f65f724ffd4b4e02b8420808850d2f`. Rendered pages and the inspection record are included. No clipped figure labels, overlapping text or body-text margin overrun was observed. Figures 1–4 and A.1 are readable. Page 18 has substantial white space, and page 21 contains only the final three lines of reference 12; these are cosmetic pagination issues to revisit after adding declarations. No unverified page-limit rule is imposed.

Confirmed present: Shayan Abrar; lowercase `shayanabrar7@gmail.com`; AIUB affiliation and address; the self-funding/no-specific-grant statement; acknowledgment of AIUB's institutional support; and exactly **“The author declares no competing interests.”** The acknowledgment does not claim university funding. No manuscript or PDF was rewritten in this audit.

Paths and line numbers below refer to the supplied candidate, not a future `main` checkout. `P` means `source/paper/neurocomputing/`.

| Location and exact passage | Minimal change proposed | Reason and evidence |
|---|---|---|
| `P/main.tex:198`: “checks that every file a record names is present with its recorded digest” | Replace with “checks distributed dependencies against their recorded digests and verifies the inventory of omitted intermediate checkpoints”. | The 624 dependency checks include metadata for 156 intermediate checkpoints that are intentionally not distributed. Do not imply their binaries were checked. Align `EVIDENCE.md` and `START_HERE.md`. |
| `P/main.tex:212`: “which has not been merged” | State that this work was merged through PR #3 as `05ca17f` on 2 November 2026. | Direct GitHub evidence. Keep the library, validator, candidate and experiment revisions distinct. |
| `P/main.tex:212`: “The MIT-licensed source, documentation, recorded result summaries, three complete example packages and the six learned-reward packages” | Split the MIT source/documentation claim from artifact availability; identify model/data licences only after the author decides. | The archive's model/data licence is still a proposal. The present opening can be read as applying MIT to everything listed. |
| `P/main.tex:212`: “were trained from a working tree based on ... that held uncommitted changes” | Retain; optionally add “The retained provenance does not reconstruct that modified training tree.” | All 38 training records report the dirty `32823f3` base. Digest-checked exports do not identify all uncommitted training code. |
| `P/main.tex:195`: “Evidence from nine policies does not establish cross-platform agreement for the whole study.” | Retain the historical scope; add a separate dated sentence for the new Linux audit and its blocking policy, using the completed/diagnostic counts in this report. | Existing nine-policy findings remain historical. Do not overwrite them or imply every new replay passes. |
| `P/main.tex:200`: “Every figure is produced by a deterministic script” | For precision, use “Figures are produced by scripted workflows, with plotted values checked against stored records”; document separately that the final-test audit drawing is copied and its values re-derived during this validator run. | Six output files differ in bytes across platforms, while plotted values match. Figure 2's rendering is reused, not newly rendered by this invocation. |
| `P/main.tex:70`, Figure 1 caption | After confirming attribution, add the tool/version and its role in producing the explanatory diagram. | Current Elsevier explanatory-image disclosure policy; the general methods paragraph is not a caption disclosure. Do not guess which tool/version authored this specific figure. |
| `P/main.tex:223–225`, commented declaration input | Complete the draft only after author confirmation, then insert it in the submission file before the bibliography, after the appendix if that placement is retained. Add confirmed CRediT roles. | It is currently absent from the PDF. The comment says “immediately before the references”, but the appendix intervenes at the current insertion point. |

The corrected Section 4.1 clean-control sentence and Section 5.2 distinction between integrity, selected-field agreement and behavioral observations are supported within their stated scope. Section 5.3 candidly describes substantial AI involvement. The adapter layer is demonstrated on two environments, and W2 is a separately implemented reference rather than an independent research team's replication. The benchmark distinguishes training-loop overhead from elapsed-workflow overhead. These qualifications should remain.

The paper is a coherent software contribution, with useful preserved artifacts and auditable failure cases. Its main scientific limits remain two environments, a designed fault suite, few training seeds, no demonstrated outside human use, and incomplete reconstruction of the historical dirty training tree. Green CI does not remove these limits. No acceptance probability is assigned.

## Author drafts: AI disclosure and CRediT

**Official policy inspected on 3 November 2026:** [Elsevier generative-AI policies](https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals), date line **“Policy updated June 2026.”** The policy requires a separate manuscript-preparation disclosure identifying tools, purposes and oversight; research/code use belongs in Methods. Explanatory-image captions should identify the AI tool, version and role. Data visualizations must derive faithfully from research data through reproducible methods, with tool/version/developer information in Methods. Human authors retain responsibility; AI is not an author.

**Inspected:** `P/AI_USE_INVENTORY.md` usefully distinguishes development, execution, writing and figure work. Its Claude versions/model identifier and private-transcript counts are supplied development claims; the underlying private transcripts were not available for this audit. OpenAI model identifiers are not retained; do not invent them. The manuscript's description of the assistant's role must not be reduced to spelling assistance when code, planning and interpretation were involved.

`P/AI_Disclosure_For_Submission.tex` remains an unfinished author draft. Resolve its `AUTHOR TO CONFIRM` items using actual records and actual human review. Do not assert that the author checked sources, validated code or approved conclusions unless the author has done so. The present Methods paragraph is useful but does not complete the separate preparation disclosure. The caption issue is a concrete remaining edit, not a requirement to regenerate data or figures with image-generating AI.

`P/CREDIT_CHECKLIST.md` should remain a checklist until the author confirms roles. Sole authorship does not establish every CRediT role, and AI-generated implementation does not automatically negate genuine human supervision or validation. Treat the checklist's categorical exclusions of funding acquisition for self-funding and supervision for sole authorship as prompts for factual assessment, not universal journal rules. [NISO's implementation guidance](https://credit.niso.org/implementing-credit/) allows multiple applicable roles and omission of irrelevant ones; its [funding acquisition](https://credit.niso.org/contributor-roles/funding-acquisition/) and [supervision](https://credit.niso.org/contributor-roles/supervision/) descriptions concern actual activities. Do not infer either role here or select roles merely to make the contribution appear larger.

## Licensing and deposit draft review

**Executed:** the licence mapper reproduces the supplied map byte for byte: 2,178 inventoried files, zero unmapped. The archive has 2,180 files; the inventory and top-level checksum file are not enumerated in that map, although a candidate-document rule purports to cover them. State this scope or explicitly cover those two files. Mapping completeness is not a determination of legal rights.

**Inspected faults and qualifications:**

1. `source/THIRD_PARTY_NOTICES.md:3–6` says the repository does not copy third-party source, but the candidate includes `elsarticle.cls` and `elsarticle-num.bst`. Their own headers retain LPPL terms. Correct both the notice and its generator; distinguish redistributed style files from installed dependencies. Use the actual header licence version rather than treating the files as MIT.
2. In `archive/LICENSING_PROPOSAL.md:23`, source-archive containers are labelled MIT. Their embedded models, data, manuscript and third-party components still need their applicable terms. A container label must not override the component exceptions. Choose model/data and manuscript/review-material treatment explicitly; this audit makes no licence choice for the author.
3. `LICENSING_PROPOSAL.md:43–44` says “the rest of the candidate is unchanged” after editing `LICENSES.md`. Scientific files can remain unchanged, but the inventory, checksum manifest and ZIP digests must be rebuilt consistently. Never reuse the supplied archive hash for a modified deposit.
4. `archive/ZENODO_METADATA.md:3–5` incorrectly equates the wrapped REST deposit payload with a `.zenodo.json` file. The supplied JSON has an outer `metadata` object and `_status` marker. Produce a route-specific payload; do not pass this draft unchanged to either route. Its deliberately invalid `license` placeholder is a useful guard, not a valid submission value.
5. `archive/DEPOSIT_INSTRUCTIONS.md:4–5` says published files cannot be changed. [Current Zenodo instructions](https://help.zenodo.org/docs/deposit/create-new-upload/) allow self-service file edits within 45 days. Nevertheless, preserving cited bytes and creating a new version for substantive changes is the appropriate project practice. The candidate is comfortably below the documented 50 GB/100-file limits when deposited as a ZIP plus instructions. A reserved DOI is not a published or resolving archive.
6. [Zenodo's licence guidance](https://help.zenodo.org/docs/deposit/describe-records/licenses/) supports mixed licences in its interface. The [documented legacy deposit API](https://developers.zenodo.org/) uses a single licence identifier field. Do not invent a concatenated identifier to represent multiple licences. Select the actual submission route and make the file-level terms explicit.
7. Set the actual publication date; add an ORCID only if the author has one. The creator, AIUB affiliation, self-funded description, software relationship and version-plus-exact-revision approach are sensible draft choices. No article DOI exists yet. Update the metadata's nine-policy-only Linux limitation using this audit's qualified findings, not an “all passed” statement.

No upload, draft, reservation or deposit has been made by this assistant. The candidate is a reviewable local package, not a public archive.

## What remains unverified

- The original training executions, the entire historical modified working tree, and recording-machine Windows results were not rerun here. Windows claims remain historical/CI evidence, identified as such.
- The original default-thread B validator and earlier default-thread C invocations have no retained overall exit or final JSON. Their partial raw outputs are useful but do not certify an end-to-end pass. The full-study one-thread diagnostic has all 38 replay results, but its parent also stopped before the final comparison and report.
- This audit did not rerun the full project suite, browser suite, Windows jobs, benchmark or training studies. The 89 executed tests are the two modules requested. Current GitHub job success is CI evidence, not assistant execution.
- No new LunarLander bootstrap intervals, formal equivalence study or causal attribution of numerical divergence was established. No independence from earlier test-set knowledge is guaranteed.
- Private AI-development transcripts, actual human review, CRediT roles, licence choices and the eventual archive deposit are not established by the supplied drafts. No independent researcher adoption is demonstrated by this assistant's work.
- No later author-approved manuscript build has been inspected. DOI timing, OSP length limits, timelines and presentation conditions remain unanswered in the supplied correspondence.

## Ranked remaining work

### Technical and editorial work

1. **Record and characterize the blocking Linux DQN replay.** Keep its historical evaluation and passing integrity checks intact. Publish the new execution as a separate report. A focused trace comparison for the largest-difference seeds can help distinguish policy and simulator effects; new training is unnecessary. A reproducibility limitation can be scientifically acceptable when disclosed, but a false claim that every policy passes is not.
2. **Preserve installation evidence and narrow overbroad verification language.** Repair the log-name collision, rerun that setup check, and correct the dependency/checkpoint wording. Keep failures from the unmodified comparison visible; do not change the frozen programs merely to obtain a pass.
3. **Correct the licensing notices and deposit instructions.** Apply only the author's chosen terms, rebuild inventory/checksums, then validate the exact final candidate. Carry forward the Linux outcomes and original evidence rather than editing them.
4. **Complete minimal manuscript edits and rebuild.** Update the merged status, separate the revisions/licences, add truthful declarations and the diagram caption, and then inspect the new PDF. The inspected 21-page PDF cannot certify a later build. Adjust the isolated final reference lines only after the content is final.

### Author decisions and confirmations

1. Choose the record/model terms and whether manuscript and received review material belong in the deposit; approve the final archive. After authorization, publish and verify its actual bytes and resolving identifier, then cite it. A deposit date or DOI has not been assumed.
2. Complete genuine human review and confirm the AI disclosure and specific figure attribution. Confirm CRediT roles from work actually performed. This audit does not assert these confirmations on the author's behalf.
3. Approve highlights, cover letter, metadata and final submission materials. The author's supplied Elsevier correspondence confirms the article type **Software publication**, no publication fee under **Subscription**, optional paid open access, and no OSP-specific template. Page/word limits, DOI timing, review timelines and presentation requirements remain unanswered. Do not infer those answers from silence or from a general fee statement.

Independent human use would strengthen evidence of usefulness but is not fabricated here, nor assigned an invented numerical minimum. These assistant executions are not such use. The package is technically much more reviewable than a manuscript-only submission; it is still a working publication package pending the items above.

