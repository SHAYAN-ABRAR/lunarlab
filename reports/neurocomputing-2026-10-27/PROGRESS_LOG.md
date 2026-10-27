# Progress log: Neurocomputing research-strengthening work

Times are UTC. Machine: the author's Windows 11 laptop (the original data home).

## 2026-10-27

- 15:30 Base recorded. Branch `main` at `932cf1c7c1bb7ba1d0f5b225c48e830d6a269479` was equal to `origin/main`,
  with a clean working tree and no stashes. The reviewed implementation `444a4c5` is its parent; `932cf1c`
  added documentation only.
- 15:31 Read the handoff package `LunarLab_Neurocomputing_Package (1).zip` (SHA-256 `b2addc8d2f8fab37…4dc37`). All
  of its 72 listed files verified. Its `manuscript/main.tex` is the editorial starting point.
- 15:34 Created branch `research/neurocomputing-audit-evidence` at `932cf1c`.
- 15:34 Pre-change inventory `integrity/inventory-before.json`: 2,359 protected files, combined digest
  `7366ba1b6c19ce4e24ebe1bffb5122444dddef05debe6394eb1ed307876a5d9e`. It covers runs, data, reports, docs/results,
  docs/media, demo/api, examples/artifacts, paper/jmlr-mloss, the repaired 38-policy bundle (335 files) and the
  package's supplementary files (6).
- 15:35 The package's `LunarLab_38_Policy_Study.zip` matches the local repaired bundle on all 335 files.
- 15:40 Contract candidates reproduced at runtime on the unmodified code (`contracts/reproduce_candidates.py`,
  output `candidates-before-932cf1c.json`). `audit_policy` ran booleans, fractional and integral floats, and
  numeric strings as seeds. It ran `[1, 1.5]` and `["9", 9]` as duplicate episodes and returned a
  zero-episode report for `[]`. It played seed 5 of `[5, -1]` before Gymnasium refused `-1`.
  `seed_split_problems` accepted empty and negative lists and raised `TypeError` on an unhashable entry.
  `PPO(seed=0)` replaced the CartPole example's training seed roots 1,000,000-1,000,003 with 0-3, and later
  resets were unseeded. Two terms with equal descriptions and payments of 1 and 1,000 had the same 16-hex
  `terms_hash`. NaN or infinite terms and weights produced "complete" reports that are not strict JSON, and a
  NaN in a term description was hashed.
- 16:20 Fixed in `lunarlab/audit`. `contracts.py` holds one seed contract (nonnegative integers, never
  coerced, refused before any environment exists), the finite-value checks and canonical JSON.
  `provenance.py` holds a versioned reward-provenance record: a full definition digest, defining-file digests
  and git status, and "incomplete" for code it cannot locate. The legacy `terms_hash` is unchanged for valid
  definitions. The wrapper now refuses non-finite values, naming their source, and stops the episode.
  `rescore_transitions` was added. The CartPole example now sets its environment seed roots after
  constructing PPO.
- 16:35 `tests/test_audit_contracts.py` checks these behaviours against a tiny deterministic environment with
  hand-calculated sums. It covers potential shaping at termination, at truncation and with both flags, including
  a `TimeLimit` coincidence. The old-API probe (`contracts/old_api_probe_test.py`) failed 16 of 17 checks on
  `932cf1c`; the remaining one is a valid-input control. It passed 17 of 17 on the fixed tree.
- 16:05 Generic study workflow `lunarlab/audit/study.py`. It covers protocol validation, PPO training with
  scheduled original-reward validation, the prespecified selection rule, and freezing through the main
  pipeline's `freeze.immutable_copy`, now public. It adds digest-checked final tests and artifacts that verify
  integrity before execution. Reproduction reuses `reproduce.compare_episodes` (now with task-independent
  fields) and `classify_reproduction`. CLI: `lunarlab audit-artifact verify|reproduce`. The CartPole adapter
  gains the deliberately flawed `failure_bonus` (generic `termination_bonus`). `tests/test_audit_study.py`
  runs the whole workflow at 128 transitions and checks 11 tampering cases, each refused before any episode.
- 16:08 CartPole protocol fixed before any training (`cartpole-study/protocol/PROTOCOL.sha256`). Main study:
  3 designs x seeds 50-54, 100,096 transitions per run. Pilot: seed 90, 20,480 transitions per run, its own
  validation and test seeds.
- 16:15 Smoke run of `examples/cartpole_study.py` on the tiny test protocol: every phase works, both artifacts
  verify, and the data home stays empty.
