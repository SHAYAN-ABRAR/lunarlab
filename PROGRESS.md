# Progress

_Last updated: 2026-10-18._

## Status

| Milestone | State |
|---|---|
| Software (all stages 1–7) | **complete and verified** |
| SMOKE pipeline check on this laptop | done (artifacts listed below) |
| Full experiment: 4 reward designs × 5 seeds, PPO, STANDARD | **done**, final-tested, robustness-tested ([docs/RESULTS.md](docs/RESULTS.md)) |
| Algorithm comparison: 4 designs × 3 seeds, DQN at 100k | **done** |
| Learned rewards (RLHF in miniature): 2 reward models × 3 seeds | **done** |
| Static demo, CI workflow, results write-up | live at https://shayan-abrar.github.io/lunarlab/; CI and demo deploys pass on GitHub |
| Six enhancements (leakage fix, varied physics, active preference learning, Optuna tuning, policy diagnostics, PPO–DQN comparisons) | **built and verified** with tests and smoke experiments; the leakage refit and the active-learning study were measured, the other full studies have not been run ([commands](docs/RESULTS.md#studies-built-but-not-yet-run)) |
| Audit repair (DQN continuation, final-test freezing, outcome classifier v2, protocol validation, Windows CI, provenance, wording) | **done**, committed and verified in CI on GitHub (Linux and Windows) ([docs/AUDIT_FIXES.md](docs/AUDIT_FIXES.md)) |
| JMLR-MLOSS readiness (license, release tooling, coverage, reproducibility, benchmark, comparison, adapter layer, documentation, manuscript scaffold) | **implemented and verified locally** on branch `research/jmlr-mloss-readiness`, not committed ([docs/jmlr/READINESS_REPORT.md](docs/jmlr/READINESS_REPORT.md)); the extended CI has not run on GitHub; manuscript and community evidence need the authors |

## JMLR-MLOSS correction pass (2026-10-18)

An independent review of the pushed readiness work (`2c41b42`, CI run 39069730331, all six jobs green) found
problems that are now corrected on the branch `research/jmlr-mloss-corrections` (uncommitted). Full account:
[docs/jmlr/READINESS_REPORT.md](docs/jmlr/READINESS_REPORT.md).

- **Cross-platform reproducibility:** on Linux none of the 300 published final-test episodes was bit-identical
  (Windows: 300/300). Characterised, not hidden: integrity, within-platform, cross-platform and conclusion
  stability are reported separately; controlled experiments locate the sensitivity in the simulator's compiled
  float code amplified by the closed loop; per-step traces (`trace-artifact`) will confirm it in CI. The means and
  landing rates, and so the published conclusions, are unchanged on Linux.
- **CI** no longer discards reproduction exit codes; a summary lists every outcome and fails on integrity
  errors, same-platform differences and significant aggregate changes.
- **Continuation** wording corrected everywhere: the algorithm state is restored, continuation is not
  bit-identical.
- **Benchmark** repeated on a clean checkout; training-loop overhead and full wall clock reported separately.
- **Tests** for the parallel runner, the served backend, supervisor crash recovery, CLI and HTTP errors; two bugs
  they found are fixed (a crashed worker left its run "running"; CLI tracebacks on invalid or unknown ids).
- **Manuscript** compiled for the first time (isolated Tectonic): four description pages, figures redrawn at print
  size (≥ 9 pt, checked), claims corrected.

| Check (2026-10-18, branch `research/jmlr-mloss-corrections`) | Result |
|---|---|
| `python -m pytest --cov` (Windows 11, Python 3.12) | **493 passed**, 85.8 % statement + branch coverage |
| Fast suite on Python 3.13 (Windows 11) | 417 passed (76 slow tests deselected); `reproduce-smoke` 15/15 |
| `npx playwright test` | 15 passed (Microsoft Edge); both backends shut down through `/api/shutdown` |
| Frontend typecheck / lint / build | `tsc`, `oxlint` and the production build clean |
| Source archive | working-tree archive (318 files, 8.2 MB) installed into a fresh environment: `--version`, `doctor` 10/10, `reproduce-smoke` 14/14, 199 release tests passed |
| Manuscript PDF | 4 description pages + 2 reference pages, 118 KB |
| Evidence integrity | 1,699 files byte-identical to the baseline (runs, data, published results and media, demo snapshot, supplied artifacts, earlier reports and benchmark runs); 0 removed; 21 added (the clean benchmark run and the reproducibility evidence); the coverage report and the figures regenerated |
| CI of the corrections | **not run** (nothing pushed) |

## JMLR-MLOSS readiness (2026-10-17/18)

Work for a possible submission to the JMLR open-source software track; the full report, with the requirements
matrix and the evidence, is in [docs/jmlr/](docs/jmlr/READINESS_REPORT.md).

- **Licensing:** MIT `LICENSE`, SPDX notice in every source file (`tools/spdx_headers.py`), generated
  `THIRD_PARTY_NOTICES.md`, `CITATION.cff`, consistent package metadata (the missing `optuna` dependency added;
  `requires-python` matched to the tested 3.12–3.13).
- **Release:** one authoritative version and `python -m lunarlab --version`; a deterministic source archive
  (`tools/build_source_archive.py`) built twice byte-identically and test-installed into a fresh environment.
- **Reproducibility:** `reproduce-smoke`, `export-artifact`, `reproduce-artifact`; three published final tests
  supplied in `examples/artifacts/` and re-evaluated bit-identically (300/300 episodes) on this machine; training
  bit-identical across processes on this machine.
- **Quality:** coverage measured (82.9 %, from 75.2 %), 449 tests (from 270): property-based tests of the
  shaping and statistics invariants, continuation-loader refusals, the tutorial executed command by command,
  documentation commands parsed, release metadata checked.
- **Benchmark:** `overhead-benchmark`; reward accounting costs about 4 % of PPO training-loop time against plain
  Stable-Baselines3 on this laptop ([docs/jmlr/BENCHMARK_PROTOCOL.md](docs/jmlr/BENCHMARK_PROTOCOL.md)).
- **Generality:** task-independent `lunarlab.audit` layer (LunarLander adapter identical to the pipeline; CartPole
  example).
- **Documentation:** tutorial, developer guide, generated API reference, contributing guide, issue forms; a
  sourced comparison with related software; a scientific review of the published claims (one sentence reworded).
- **Manuscript:** `paper/jmlr-mloss/` scaffold in the official style with verified references and figures from
  stored data; the PDF has not been built (no LaTeX here) and author information is left to the authors.

| Check (2026-10-18, branch `research/jmlr-mloss-readiness`) | Result |
|---|---|
| `python -m pytest --cov` (Windows 11, Python 3.12) | **449 passed**, 82.9 % statement + branch coverage |
| Fast suite on Python 3.13 (Windows 11) | 376 passed; `reproduce-smoke` 14/14 |
| `ruff check` / `ruff format --check` (lunarlab, tests, tools, examples, paper) | clean |
| `npm run typecheck` / `oxlint` / `npm run build` | clean / clean / OK |
| `npx playwright test` | **15 passed** (10 earlier flows + 5 audit flows on a pre-built fixture home) |
| Source archive | byte-identical rebuilds; fresh install: `--version`, `doctor`, `reproduce-smoke` 14/14, 188 release tests passed |
| Evidence integrity (1,667 historical files) | all byte-identical to the baseline taken before this work (combined SHA-256 `651c5e2b…6e04`); only new deliverables added under `reports/jmlr/` |
| CI on GitHub | **not run** (nothing pushed) |

## Audit repair (2026-10-17)

Findings of an audit of commit `3782ab1` were reproduced, fixed with regression tests (each failed before the
fix) and documented in [docs/AUDIT_FIXES.md](docs/AUDIT_FIXES.md); release and migration notes in
[docs/MIGRATION.md](docs/MIGRATION.md).

- **DQN continuation:** resumable DQN checkpoints carry the replay buffer and algorithm state (validated
  numeric archive and JSON, digest-checked); crash-safe checkpoint bundles; DQN stops at rollout boundaries;
  older DQN checkpoints offer a confirmed warm restart (new run, lineage recorded) instead of a fake resume.
- **Final-test freezing:** immutable read-only frozen copy, no further training under the run ID (core, worker,
  API, CLI, UI), run lock for final tests, attempts recorded, incomplete tests retried, legacy migration command,
  test exposure and exploratory labels, `--holdout-seeds`.
- **Outcome classifier v2:** geography kept apart from landing quality; legacy results labelled with derived
  values. Re-examination of all 11,500 published evaluation episodes: no episode changes category.
- **Protocol validation:** strict seed types, distinct and disjoint seed lists, the supported environment; the
  instantiated environment recorded with every evaluation.
- **Windows:** new CI job (install as `setup.ps1`, doctor, Windows-sensitive tests with paths containing
  spaces, PowerShell parse, start/stop scripts) and `tests/test_windows.py`.
- **Provenance:** release vs draft demo exports with full manifest; training, evaluation and analysis code
  revisions recorded.
- **Wording:** no equivalence claims from overlapping intervals; what shaping theory does and does not cover;
  degenerate P(improvement) explained; learned-reward pipeline described accurately.

| Check (2026-10-17) | Result |
|---|---|
| `python -m pytest` | **270 passed** (204 earlier + 66 new) |
| `ruff check lunarlab tests` / `ruff format --check lunarlab tests` | clean |
| `npm run typecheck` / `npm run lint` / `npm run build` | clean / clean / OK |
| `npx playwright test` | **15 passed** (10 earlier flows + 5 audit flows on a pre-built fixture home) |
| Windows CI job's steps, run locally on Windows 11 (fresh venv in a path with spaces) | doctor 10/10; 125 tests passed; scripts parse; start → health → stop OK |
| CI on GitHub, commit `938ad31` | Linux: lint and all tests, frontend, browser end-to-end (15 flows) passed; demo deployed. Windows: install, doctor and 126 tests passed; the PowerShell 7 parse found a defect in `scripts/setup.ps1` from the first commit (fixed in the next commit, see docs/AUDIT_FIXES.md) |
| CI on GitHub, commit `ad1ee9f` | all jobs passed, including Windows (127 tests, PowerShell 7 parse, start → health → stop) |
| Evidence integrity (1,665 files under runs/, data/, reports/, docs/results/, docs/media/, demo/api/) | all byte-identical before/after (combined SHA-256 `91ca8609…737f`); 2 derived report files added |
| Demo snapshot re-exported as a release of `ad1ee9f` (same 3 experiments + 1 run) | no value changed (new fields and provenance only); other evidence byte-identical; all 12 pages of a local demo-mode build load without errors |

## Portfolio extensions (2026-10-15/16)

- **Experiments run and published.** 38 trained policies with final tests and robustness evaluations;
  `docs/RESULTS.md` (findings with intervals, limitations, reproduction commands), figures and tables in
  `docs/results/` generated by `python -m lunarlab results`, a side-by-side GIF from real footage
  (`docs/media/showcase.gif`).
- **Statistics across seeds:** IQM, bootstrap intervals over policies, probability of improvement and
  performance profiles (`lunarlab/rl_stats.py`), on Compare & Diagnose and in reports.
- **Robustness:** wind / turbulence / heavier gravity on frozen checkpoints (`lunarlab/robustness.py`,
  `python -m lunarlab robustness`).
- **DQN** alongside PPO (Zoo settings), with PPO config hashes unchanged so older runs stay resumable.
- **Learned rewards:** preference datasets, Bradley–Terry reward models (NumPy inference, hash-checked,
  no pickle), `original_weight` in the reward invariant, `rlhf-study` / `rlhf-dataset` / `reward-model`
  commands, and the Learned Rewards page for human labels.
- **Fly It Yourself:** keyboard and touch flights stepped by the backend, recorded like any policy, with an
  opponent ghost and a logbook.
- **Parallel experiments** (`--parallel N`), `run-experiment` to resume and final-test an experiment,
  `record-showcase`, `export-demo` and a static demo mode of the UI (`VITE_DEMO=1`), CI and Pages workflows.

## Enhancements (2026-10-16)

1. **Preference validation leakage fixed.** Reward-model validation now splits by whole episode (seeded,
   20%), segments and pairs of one episode stay on one side, human labels that straddle the split are
   excluded, and duplicate labels are refused. Refit on the published dataset: accuracy vs true order 0.685
   (300 labels) and 0.780 (3,000 labels) instead of 0.734 / 0.765, one refit each (correction in RESULTS.md).
2. **Training under varied physics.** Per-episode wind, turbulence and gravity drawn from configurable ranges,
   seeded from the episode seed and logged per episode; `train/suite --physics`, the Training Console, and a
   Compare card for fixed vs randomized training across the calm test and every robustness condition, with
   difference intervals. Smoke-verified; no full study yet.
3. **Active preference learning.** Bootstrap reward-model ensembles; the next pair to label can be the one the
   ensemble disagrees on most, or random (the baseline); labelled pairs are never shown again; labelling
   progress and the strategy are on Learned Rewards. Measured (5 seeds, 1,000 simulated labels):
   disagreement did **not** beat random (RESULTS.md finding 6).
4. **Automatic tuning with Optuna.** PPO/DQN hyperparameters and reward weights, bounded trial budgets,
   studies persisted in SQLite, resume and cancel, median pruning after a warm-up, a trial table and curves,
   and fresh normal runs from the best settings. Validation only: trial runs are refused by the final test.
   Smoke-verified (5 trials).
5. **Policy diagnostics in Flight Replay.** PPO action probabilities, entropy and V(s), DQN Q-values, per step
   and on the shared timeline; older recordings say they have none. Ten new policy recordings on test episode
   20002 (one per group, plus heuristic and random references) carry them in the demo. Cross-check: entropy
   over sampled rollouts 0.721 vs 0.724 logged by SB3.
6. **PPO–DQN comparisons.** Matched transition budgets, learning curves against transitions and wall-clock
   time (Compare toggle; `results` draws `algorithm_comparison.png`), several training seeds per cell, and a
   separate discount-factor ablation (Compare card, `compare`, `results`) with difference intervals. Each
   training segment records how many runs trained at once. Smoke-verified with an 8-run 2 × 2 suite.

## Completed

1. **Workspace and dependencies.** Empty folder, not a git repo. Python 3.14 is the machine default, but
   Box2D/pygame have no cp314 Windows wheels and no C++ toolchain is installed, so the project venv uses the
   already-present uv-managed CPython 3.12.13. Locked with uv (`requirements.lock`): gymnasium 1.4.0, Box2D
   2.3.10, pygame 2.6.1, stable-baselines3 2.9.0, torch 2.14.1+cpu, numpy 2.5.4, pandas 3.0.6, matplotlib
   3.11.2, fastapi 0.143.1, pydantic 2.14.1, uvicorn 0.54.0, imageio-ffmpeg 0.6.0 (ffmpeg 7.1). Frontend:
   Node 26.3, Vite 8.3.4, React 19.3, TypeScript 6.0.3, Tailwind 4.3.3, Recharts 3.10.1, React Router 8.4
   (`frontend/package-lock.json`).
2. **RL core**: environment adapter, reward schema/presets/terms/wrapper, outcome classification, hover
   detector, CLI training with checkpoints, validation selection and cooperative stop/resume, evaluation
   with the original reward, recording, rescoring, comparison, reports.
3. **SMOKE pipeline**: trained, reloaded (weights-only), evaluated, recorded. See artifacts.
4. **Backend**: FastAPI, SQLite metadata, subprocess job supervisor with queue lanes, duplicate prevention,
   graceful stop, force-terminate with ownership verification, restart reconciliation.
5. **Frontend**: Mission Overview, Training Console (+ per-run console), Reward Studio, Flight Replay
   (incl. side-by-side), Compare & Diagnose (incl. reward-hacking diagnostic and reports), Reward Stress
   Test, Learn.
6. **Diagnostics, rescoring, reports, portfolio summary** (evidence-gated).
7. **Verification and docs**: see below; README, docs/, walkthrough.

## Test evidence (executed, all passing; at commit 3782ab1, before the audit repair)

| Check | Result |
|---|---|
| `python -m pytest` | **204 passed** (unit, real LunarLander integration, real PPO and DQN, learned rewards incl. episode split and active learning, varied physics, Optuna tuning with pruning and cancel, policy diagnostics, comparisons and the γ ablation, robustness, statistics, keyboard flights, demo export, showcase media, real worker subprocesses, API) |
| `ruff check lunarlab tests` / `ruff format --check` | clean |
| `npm run typecheck` (tsc -b, strict) | clean |
| `npm run lint` (oxlint, correctness + suspicious) | clean |
| `npm run build` | OK |
| `npx playwright test` (installed Edge, real backend on a disposable home) | **10 passed**: empty state, random-agent replay (3-D view, playback, footage toggle), config revisions, SMOKE job to completion, record+replay trained flight, STANDARD stop → resume → stop, compare/stress-test/learn, a keyboard flight against the heuristic ghost to its recording, learned-rewards and robustness empty states, deterministic 3-D capture mode |
| Static demo (built with `VITE_DEMO=1`, served under `/lunarlab/` with a GitHub-Pages-style 404 fallback) | overview, compare (final test, robust statistics, robustness), deep-linked replay with video, preference labelling with reveal, fly page disabled with an explanation; no console errors; no horizontal overflow at 390 px |
| New screens in Edge against real backends (2026-10-16) | γ-ablation card, transitions / wall-clock curves, fixed-vs-randomized card, launch and suite forms, tuning study with trials, labelling progress and ensemble, active-learning chart, PPO and DQN policy panels; no console errors |
| `python -m lunarlab doctor` | 10/10 OK |
| `scripts\setup.ps1`, `start.ps1 -Background`, duplicate start, `stop.ps1` (Windows PowerShell 5.1) | OK |
| SB3 `check_env` on the wrapper with every preset | no warnings |
| Visual inspection at 1920×1080, 1280×800 and 390×844 | no horizontal overflow, no console errors |
| Reproducibility | two independent SMOKE runs of the same config (supervised worker vs in-process) gave identical validation returns to 6 decimals |
| Throughput (`lunarlab benchmark`) | PPO, 4 in-process envs: ≈5,100 transitions/s in short bursts; sustained 2,100–2,400 for one run, 1,000–1,200 per run with five in parallel |

## Real artifacts in this project

- Demos (shared seed 20000): `data/demos/*random-seed20000*` (crash, −126.9, 99 steps) and
  `*heuristic-seed20000*` (at rest **off the pad**, 155.9, 807 steps; seed 20000 is a hard episode).
- SMOKE suite `exp-20261014-215427-smoke-pipeline-check-2a9a` (4 presets × seed 0, 8,192 transitions each):
  `runs/20261014-2154*-smoke-*/` with checkpoints, validation + frozen final-test evaluations
  (`evaluations/`), and one recorded flight each (`videos/`, `trajectories/`).
  Final-test (100 episodes, original reward): baseline −73.3, time-penalty −72.4, hover-bonus −73.3,
  potential −45.6; 0% pad landings for all. These are **technical tests, not trained agents**. Baseline and
  hover-bonus are identical because the bonus never fired in 8k transitions and both used seed 0, which
  confirms deterministic seeding rather than saying anything about the reward.
- Report: `reports/exp-20261014-215427-smoke-pipeline-check-2a9a/` (`report.html`, `report.md`, 4 figures,
  `portfolio_summary.md`, where all results correctly read "[not yet measured]").
- `data/benchmark.json` (throughput, used for time estimates).

## Added after the first delivery

- **3-D Flight Replay** (`frontend/src/components/Scene3D.tsx`, lazy-loaded three.js 0.186): a reconstruction
  from recorded telemetry on the episode's real terrain (the env's `sky_polys`, stored with new recordings
  and re-derived from the seed for older ones; equality is tested). Chase, wide and orbit cameras, engine
  plumes placed where the env emits its particles, exhaust and dust particles, leg-contact lights, an impact
  burst on crashes, pad lights that turn green only for a strict pad landing, and a HUD. It is labelled as a
  reconstruction; the simulator footage stays one click away on the same timeline.
- Found while building it: Gymnasium's "left leg" flag (obs 6) belongs to the leg on the **+x** side; the
  terrain under the pad is 3.30 (Gymnasium smooths with 0.33 rather than 1/3) while `helipad_y` is 3.333.

## Issues found and fixed during verification

- (2026-10-16) The published learning-curve figure silently averaged potential shaping over 4 of 5 seeds:
  the resumed seed-1 run's `episodes.csv` mixed two column layouts (newer code added a column), which the
  reader skipped. The writer now keeps a file's own header, the reader maps rows by width, the figure was
  regenerated, and RESULTS.md has a correction (tests added).
- (2026-10-16) Right-aligned numeric table headers were left-aligned everywhere (the table's default
  alignment had higher CSS specificity); a rounded −0.4 displayed as "-0".

- (2026-10-15) One STANDARD run (potential shaping, seed 1) failed at 200,704 transitions: replacing
  `best_validation.zip` hit `WinError 5` for longer than the 15 s retry window while the machine was fully
  loaded. Checkpoints now use unique temp names, retry for 60 s, and fall back to a unique file name recorded
  in the manifest instead of failing (test added). The run was resumed from its periodic checkpoint.
- (2026-10-15) Thread oversubscription made reward-model fitting ~30× slower on a busy machine (torch's
  default thread count); fitting now caps torch threads.
- (2026-10-16) The Mission Overview's preset cards only looked at the 12 newest runs (showing "not trained"
  once more runs existed) and averaged runs with different budgets; they now use every run and one budget per
  card. Compare defaults to the final-test split once every evaluated selection has one.

- LunarLander's per-leg contact flag can read 0 while a sleeping lander rests on the pad (terrain-segment
  begin/end ordering). The strict pad-landing rule was changed to "leg contact seen during the episode"
  (documented, tested).
- Windows `os.replace` of a fresh checkpoint failed with `WinError 5` (antivirus scan); all checkpoint
  replacements now retry. Buffered training episodes are now flushed even if training fails.
- Stop clicked while a resume job was still *starting* was discarded by the worker's stale-request
  cleanup; stop requests now carry the job id and are honoured at start (regression test added).
- Chart palette re-validated for colour-vision deficiencies (blue/violet failed all-pairs); presets now use a
  validated set plus dash/marker secondary encoding. Matplotlib figures match.
- Mobile overflow from implicit grid tracks; fixed with `minmax(0, …)` tracks.

## Known limitations

- Few seeds (5 per PPO design, 3 per DQN and learned-reward group): see the limitations in
  [docs/RESULTS.md](docs/RESULTS.md).
- In the published runs DQN ran at Zoo's 100k-transition budget and PPO at 1M; matched-budget runs and the
  discount-factor ablation are built and smoke-tested but have not been run at full scale.
- Wall-clock curves of the published runs cannot be compared fairly: how many runs trained at once was not
  recorded then (it is now).
- Active learning was compared on reward-model accuracy only, with a simulated labeller.
- Preference labels in the study come from a simulated human; human labels are collected and can be mixed
  in (`--include-human`) but no study with real labels has been run.
- A resumed run is not bit-for-bit identical to an uninterrupted run (documented; one study run was resumed).
- GPU training is optional and untested here (CPU torch build installed; CPU is faster for this MLP).

## Next steps

- Run the studies listed in [docs/RESULTS.md](docs/RESULTS.md#studies-built-but-not-yet-run) (γ ablation at
  matched budgets, varied physics, active labels carried through to PPO, tuning) and add their results.
- Push to publish the refreshed demo snapshot (`demo/api`).
- Optional: label a few hundred pairs yourself on Learned Rewards and train a reward model with
  `--include-human` to compare real and simulated preferences.
