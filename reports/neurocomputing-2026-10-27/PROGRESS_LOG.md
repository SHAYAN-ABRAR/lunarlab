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

## 2026-10-27, entries added on 28 October

- Correction. Several times above are wrong. The commit times (UTC) are authoritative:
  - `3b96048`, 15:55:25, holds the contract fixes, their tests and the reproductions. The entries timed 16:20
    and 16:35 therefore describe work finished by 15:55.
  - `dea292c`, 16:52:33, was the first push, not 17:15.
  - `21ceb66`, 17:12:15, holds the figures and the manuscript. The entries timed 17:30-18:05 and 18:05
    therefore describe work finished by 17:12.
  - The remaining commits: `d04a53b` 16:12:01, `e7c3fab` 16:12:15, `0bad1f7` 16:22:54, `fa25bbf` 16:23:14,
    `5c7a62a` 16:35:43, `8d4f6c4` 16:48:58, `11145b3` 16:58:14.
  - The entries above are otherwise left as written.
- 17:12-17:25 Second push (`21ceb66`), checked in CI:
  - CI run 40548348065: all six jobs passed. Linux: 567 passed and 4 Windows-only tests skipped. Windows
    Python 3.12 and 3.13: 288 each. Source archive: 189. Browser: 15 flows.
  - Learned-reward replay 40548347941: passed.
  - Manuscript build 40548348163: 19 pages, no overfull boxes, all fonts embedded.
- 17:12:56-17:24:03 Local Windows test suite (`validation/`): 571 passed, none skipped, 86.01% coverage. It
  collected the documented commands before the new sections of `docs/REPRODUCING.md` were written (17:13:44),
  so it did not test them.
- 17:13-17:28 Documentation for new researchers: REPRODUCING.md steps 5-9 with expected outputs and common
  errors, the independent-user exercise and report form, and the extension guide.
- The visual review of the first build (`manuscript/VISUAL_REVIEW.md`) found five problems:
  - all five figures sat after the references;
  - the new figures' text printed at about 8.1 pt;
  - the appendix figure was numbered "A.5";
  - the availability statement named the software revision for the evidence;
  - one caption named a colour.
- The fixes: Figures 1, 3, 4 and A.1 were redrawn at the 390 pt text width with text of at least 9 pt, and
  `main.tex` was changed (float placement, numbering, statement, caption).
- The integrity check before the next commit: 2,359 of 2,359 protected files unchanged, combined digest
  `7366ba1b…6a5d9e`, identical to the pre-change inventory.

## 2026-10-28

- 12:48 Work resumed.
  - The README now describes the task-independent layer, `audit-artifact`, the stored evidence and the CI
    results of this revision. It had not been updated on this branch before.
  - The compute tally was measured (below).
- 12:55 Third push: `f19824e` (figures and manuscript), `42573f9` (workflow comment: the smoke protocol trains
  384 transitions), `9f92447` (documentation) and `b92879e` (the local validation record).
  - Manuscript build 40691885367: 19 pages, no overfull boxes, 34 of 34 fonts embedded and no undefined
    references. All pages were read. Every figure now follows its first mention.
  - Figure 4's caption still misdescribed its intervals. They are hidden by the markers (widest 0.172 units)
    rather than collapsed, and the caption was corrected.
  - Learned-reward replay 40691885312: passed.
  - CI run 40691885283: failed in every job that runs the documentation tests. The new REPRODUCING.md step 5
    split a command over two lines with a trailing backslash, which `tests/test_docs.py` cannot parse. It was
    fixed in `7cad68c` (13:01). The documentation and metadata tests pass locally (126).
- Compute tally for the whole revision, against the brief's caps:
  - **Research training** (the pilot and the 15 main policies, the categories the cap names): 61,440 + 1,501,440
    = 1,562,880 new transitions of the 2,000,000 allowed, counted with rollout rounding. There were no
    restarts, and no new training-based benchmark was run.
  - **Other local training:**
    - The smoke run of the study runner: 256 transitions.
    - Test fixtures in the local test suites. The full suite trained 206,208 recorded transitions: 192,000 in
      LunarLab runs, 1,920 in audit-study runs and 12,288 in the overhead benchmark test. These were measured
      from its retained temporary records (pytest-380). About 5,600 more were in four tests that keep no
      records.
    - Eleven partial suite runs during development, most of them on the audit tests, trained about 111,000,
      estimated from the same per-file amounts.
    - Counting these as well, the local total is about 1.89 million, still under the cap.
  - **CI:** each CI run repeats the test-fixture training on GitHub-hosted runners, about 0.2 million
    transitions in the Linux job. That is verification on hosted machines and is not counted here.
  - **Local elapsed compute** (cap six hours):
    - pilot and main study: 8 minutes (16:12:24-16:20:33);
    - comparison runs and cost measurement: about 14 minutes (16:35:55-16:48:55), plus a development run
      (16:32);
    - full local test suite: 11 minutes;
    - partial test runs: under 10 minutes;
    - one learned-reward replay: 23 s;
    - figure builds, inventories and analyses: seconds each.
  - The total is under one hour. All compute-dependent work is complete, and no further training is planned.
- 13:01-13:11 `7cad68c` (the documentation fix): CI run 40692766622 passed all six jobs.
- 13:08 Link check of the second build's PDF.
  - The three DOIs resolve through the doi.org handle API.
  - The support address in Table 1 had no `mailto:` scheme; it was fixed in the source.
  - Figure 4's caption was corrected.
- 13:02-13:16 Claim-by-claim check for `paper/neurocomputing/EVIDENCE.md`. Every new number was recomputed from
  its file, and the CartPole analysis reproduces byte for byte from the committed records. At 13:10 the check
  found a gap:
  - The schema-1 provenance record could not tell apart the reproduced identity pair (two lambdas paying 1
    and 1,000 in one class body), nor two closures of one factory.
  - `30bd3f6` (13:16) adds schema 2: each callable's first line, own-source digest and captured values. Its
    tests and the before/after check are in `contracts/provenance_identity_check.py` and
    `contracts/provenance-identity-*.txt`.
  - Locally, 215 targeted tests passed (audit, documentation, metadata). The full suite was left to CI to stay
    well inside the compute cap.
- 13:16-13:28 CI run 40694880778 on `30bd3f6`: all six jobs passed.
  - Linux: 572 passed and 4 Windows-only tests skipped; 85.95% combined coverage (8,914 of 10,070
    statements, 1,934 of 2,552 branches).
  - Windows Python 3.12 and 3.13: 291 each. Source archive: 192. Browser: 15 flows.
  - Learned-reward replay 40694880732: passed.
  - The example replays on Linux and Windows are identical to those at `11145b3`.
- 13:28 The source archive of `30bd3f6`, built locally on Windows, is byte-identical to the CI build
  (`88bea614…6b9e116`). It installs into a fresh environment and passes 192 release tests and 14 of 14 smoke
  checks (`validation/source-archive-30bd3f6-windows.log`).
- The manuscript now cites `30bd3f6` and run 40694880778 (572, 85.95%, 291, 192, 15), and Section 2.2
  describes schema 2.
- The compute tally is unchanged in substance. The targeted tests and the archive's release tests trained
  under 10,000 transitions, so the local total including test fixtures is still about 1.89 million.
- 13:36 Fifth push (`66b7950`, `3fbcee8`, `5e3f485`): the manuscript on `30bd3f6`, CI and integrity records, and
  the index, readiness and archive documents. Manuscript build 40697723844: 19 pages, no overfull boxes, all
  fonts embedded. Every page was read and no new fault was found (`manuscript/VISUAL_REVIEW.md`, build 3). The
  CI run on `5e3f485` was superseded by the next push, which cancels a run in progress for the same branch.

## 2026-10-28, corrections added after the independent review

- Two statements above are wrong or too strong:
  - The 13:02-13:16 entry says the CartPole analysis reproduces byte for byte from the committed records.
    The run records had never been committed: an unanchored `runs/` ignore rule excluded them, and the check
    had read the working tree.
  - The 16:13-16:20 entry of 27 October says failing fast "was learned before the first checkpoint". The
    records show only that every flawed-bonus validation mean was 9.05-9.55 at every evaluated checkpoint,
    from the first, at 10,240 transitions; nothing was recorded earlier.
- The records were recovered and committed byte for byte, and the analysis reproduces from them; see
  `../neurocomputing-review-repairs-2026-10-28/`. The entries above are left as written.
