# Learned-reward artifact repair: validation record

Date: 24 October 2026 (measurements on 23–24 October UTC). Machine: the original Windows 11 data home, Python
3.12.13 in the `requirements.lock` environment. Starting commit: `41165997f9cda78bf30b26cf676b9db894c5d9e3`
(`main`, clean). Reviewer package: `LunarLab_JMLR_Publication_Package (1).zip`, SHA-256 `11d3ed05…797a`
(verified).

| Step | Result | Record |
|---|---|---|
| Original reward models | `data/reward_models/rm-20261015-235825-rm-300-4877/` and `rm-20261015-235939-rm-3000-cfd0/`: four files, 58,250 bytes, each equal to the committed historical manifest (`reports/jmlr/artifacts/integrity_baseline.json`) and to the reviewer's `REQUIRED_REWARD_MODELS.json`; each `meta.json` records its model's SHA-256 | `reward_models_verification.json`, `reward_models.SHA256SUMS` |
| Dependency fix | The runtime, CLI, export, reporting and test hunks of the reviewer's `followup-review.patch`, applied to `4116599`; the resulting five files equal the reviewer's replacement files (line-ending-normalised SHA-256). No manuscript, figure, README or older documentation hunk applied | `lunarlab/reproduce.py`, `lunarlab/cli.py`, `tools/export_study_artifacts.py`, `tools/reproduction_summary.py`, `tests/test_artifact_reward_dependencies.py` |
| Focused tests | 52 passed: the 9 new dependency cases plus reporting, reproduction, study-tool and CLI-failure tests | |
| Re-export | 38/38 exported and verified, now checking every manifest-listed payload. Checkpoint, configuration, evaluation and provenance bytes unchanged against `runs/` and the 19 October bundle; the six learned-reward packages add only the two model files, identical to the originals | `bundle_repair_comparison.json`, `study-artifacts/` |
| Replay, empty data home | Six of six `exact` (exit 0), 600/600 episodes on the five compared fields; recorded means reproduced; the empty home stayed empty | `replay/` |
| Negative cases | A legacy package without the model, a missing `model.npz` and a corrupt `meta.json`: `integrity-failure`, exit 1, evaluation not run | `replay/negative-*.json` |
| Example packages, modified code | Smoke test exit 0; three of three `exact`; nine traces identical | `examples-reevaluation/` |
| Full Python suite | 498 passed, 0 failed, 0 skipped (85.90% combined coverage); frontend typecheck, lint and build pass; 15/15 browser flows | `test_summary.json` |
| Static gates | Ruff lint and format, generated API reference current, SPDX headers, manuscript checker (two author markers) | |

Distinct properties. Integrity: files, digests and dependencies are checked. Exact summary matching: on the
recording platform only. Cross-platform numerical agreement: not tested for the learned-reward packages; CI run
40015498622 measured it for the three example packages at `4116599`.

Blocked: the manuscript rebuild. Windows Application Control blocks the unsigned Tectonic binary and no other TeX
engine is installed, so the two outdated sentences are corrected only in a pending diff (`paper/jmlr-mloss/BUILD.md`).
