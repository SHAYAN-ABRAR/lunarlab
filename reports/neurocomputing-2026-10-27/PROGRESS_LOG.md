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
- 16:12 Pilot (seed 90, 3 x 20,480 transitions, 35 s). The failure-bonus payments match the hand calculation
  on all 20 recorded test episodes: training return T + 1000, and discounted return G(T) to 1e-13. The protocol
  was not changed.
- 16:13-16:20 Main study, 15 runs x 100,096 transitions, from committed source `e7c3fab` (clean tree); the
  data home stayed empty. Original and upright-potential designs: all 10 selected policies balance to the
  500-step limit on all 100 test seeds, a ceiling at which the two designs cannot be distinguished.
  Failure-bonus design: all 5 selected policies fail after about 9 steps (mean original return 9.22-9.44,
  0 completions in 500 test episodes), while their own training return is about 1009. Selection could not
  rescue them, because failing fast was learned before the first checkpoint at 10,240 transitions.
- Compute so far: 1,562,880 new training transitions (main plus pilot) of 2,000,000; about 8 minutes of
  study wall time, plus test-suite runs.
- 16:35-16:42 Comparison run on the main fixtures (`5c7a62a`). W2 and W3 accepted both controls, the clean
  case exact and the numerical-difference case as such. Both rejected all 12 faults through the targeted check
  before any episode ran, and their full status vectors are identical on all 14 cases. W1 attempted none of the
  specification's checks: it evaluated 100 episodes in every case without a warning, with no false alarms.
- 16:43-16:50 Cost: 5 randomized blocks on C0. Medians are 20.9, 21.0 and 21.7 s, but wall time was bimodal
  over time (some runs 10.8-14.4 s), so no precise difference is supported. Peak self working sets are 288,
  289 and 293 MB. Counted custom lines: W1 65, W2 277, W3 152.
- 17:00 Linux replay prepared. WSL is not installed and no Linux machine is available, so the check runs as
  a bounded CI job (`.github/workflows/learned-reward-linux.yml`), whose pass and fail criteria are written in
  its header before any result. The six learned-reward packages (2.3 MB, 60 files, identical to the repaired
  bundle's SHA256SUMS) are copied to `examples/learned-reward-artifacts/` for it. One package replays `exact` on
  this machine from the new location (23 s). `ci.yml` now also runs on `research/**` pushes; the demo-site
  workflow still deploys only from `main`.
- 16:20-16:35 (entry appended at 17:20; an interrupted command had skipped it) Audit-workflow comparison
  designed in `workflow-comparison/protocol/`. Workflows were developed on fixtures from the pilot policy only.
  The development run showed the expected pattern; one W3 change followed it: S6/S7 use the declared term names,
  so they run even when the reward definition cannot be built. Main fixtures from `upright-potential-s50` were
  then built, and the protocol, fixtures and scripts hashed (`protocol/HASHES.sha256`, 16:35:26 UTC) before any
  workflow ran on them.
- 17:15 First push of `research/neurocomputing-audit-evidence` (`dea292c`).
  - Learned-reward replay (Linux), run 40545198707, passed its prespecified criteria. All six policies
    replay with integrity intact as `numerical-difference`, with no significant aggregate shift; median
    per-episode |return difference| ranges 0.0002-0.012, the largest 0.007-18.3. The empty data home stays
    empty. A missing model and a corrupt `meta.json` are refused before any episode. The generic example
    reproduces exactly on Linux.
  - CI run 40545198467 failed at the formatting gate of the Linux job: `lunarlab/audit/study.py` was not
    formatted after `check_file_digests` was added, so the tests never ran there. The same interrupted command
    had also skipped regenerating `docs/api`. The other jobs passed, except the browser job, which was skipped
    because it depends on the Linux job.
- 17:25 CI run 40546091715 on `11145b3`: all six jobs passed. Linux: 567 passed, 4 Windows-only skipped, 85.91%
  combined statement and branch coverage (8,865/10,018 statements, 1,913/2,528 branches). Windows Python 3.12 and
  3.13: 288 each. Source archive: 189. Browser: 15 flows. Logs and artifacts are under `ci/run-40546091715-11145b3/`.
- 17:30-18:05 Figures. Figure 1 (architecture) is drawn from a node list whose every named function is
  checked to exist. Figure 2 is the historical LunarLander figure, copied byte for byte with all 20 plotted values
  re-derived from `docs/results/results.json`. Figure 3 is the comparison matrix, Figure 4 the CartPole study, and
  the appendix figure the Linux replay. Every figure was inspected at reading scale; clipped labels, overlapping
  headers and markers, and text below 9 pt were fixed.
- 18:05 Manuscript imported into `paper/neurocomputing/` from the package (hashes in
  `IMPORTED_FROM_PACKAGE.sha256`), with the new evidence integrated (`manuscript/main.tex.diff`). The local build
  is still blocked by Smart App Control (not bypassed); `.github/workflows/paper.yml` builds it with TeX Live in CI.
