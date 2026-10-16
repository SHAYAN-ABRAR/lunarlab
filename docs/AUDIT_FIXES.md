# Audit fixes (2026-10-17)

Repair of the findings of an external audit of commit `3782ab1e8ede7808806040b44e6f07db6747b23e`. Each finding
was reproduced on that commit before anything was changed; each fix has regression tests that failed before
the change and pass after it. Release and migration notes: [MIGRATION.md](MIGRATION.md).

## Baseline

| | |
|---|---|
| Revision | `3782ab1e8ede7808806040b44e6f07db6747b23e` (`main`), clean working tree, no stashes |
| Repair branch | `audit-fixes` (local; nothing committed) |
| Python / Node / npm | 3.12.13 / 26.3.0 / 11.16.0 |
| Gymnasium / Stable-Baselines3 / PyTorch / NumPy | 1.4.0 / 2.9.0 / 2.14.1+cpu / 2.5.4 |
| Tests at baseline | `pytest`: 204 passed. Playwright: 10 passed (previous session, same code) |
| Running processes before the repair | the app (port 8765) and a sandbox (8767), both idle; stopped before any run directory was read |
| Evidence integrity baseline | SHA-256 of all 1,665 files under `runs/`, `data/`, `reports/`, `docs/results/`, `docs/media/`, `demo/api/` (214.5 MB) |

Artifact locations and schemas involved: `runs/<id>/checkpoints/manifest.json` (one entry per checkpoint file:
name, kind, transitions, SHA-256, config hash), `runs/<id>/metadata.json` (segments, `frozen_for_test`,
`test_evaluations`), `runs/<id>/evaluations/*.json` (one result per evaluation, per-episode records included),
`demo/api/demo.json` (export manifest).

---

## 1. DQN continuation (audit §3): confirmed, fixed

**Files.** `lunarlab/continuation.py` (new), `lunarlab/training.py` (`save_model_atomic`, callback `_on_step`,
`_train_locked`), `lunarlab/runs.py` (`is_resumable`, `resolve_resume_checkpoint`), `lunarlab/lineage.py` (new),
`lunarlab/config.py` (`WarmStart`), `lunarlab/server/api.py`, `lunarlab/cli.py`, `frontend/src/pages/RunDetail.tsx`.

**Reproduction** (isolated home, tiny DQN stopped at 512 transitions, then resumed; spying on `DQN.learn`):

| At the start of the resumed `learn()` | Before | After |
|---|---:|---:|
| `num_timesteps` | 512 | 512 |
| replay buffer size | **0** | 512 |
| `exploration_rate` | **0.0** (greedy) | 0.1 (scheduled value) |
| `_n_calls` (target-update phase) | **0** | 512 |

**Root cause.** The resume path called `model.set_parameters()` (online and target networks, Adam state) and
restored `num_timesteps` and `_n_updates`. In SB3 2.9.0 the replay buffer, `_n_calls`, `exploration_rate`,
`_episode_num` and `_current_progress_remaining` live outside the `.zip`. A fresh model starts with an empty
buffer, `exploration_rate = 0.0` until its first `_on_step`, and target updates out of phase. The PPO stop rule
(roll back to the last update) was also applied to DQN, which stores transitions as it collects them.

**Correction.**
- Checkpoint contract: *inference* (weights only), *resumable* (PPO: weights, optimizer, counters; DQN: plus a
  continuation bundle), *warm restart* (a new run). Each manifest entry records `role`, `resumable` and, for
  resumable ones, its `continuation` format and contract text.
- DQN continuation bundle: `<ckpt>.state.json` (strictly validated, pydantic `extra="forbid"`) and
  `<ckpt>.replay.npz` (uncompressed numeric arrays; every `.npy` header is checked for names, shapes and dtypes
  before any data is read; `allow_pickle=False`; object dtypes refused), with sizes and SHA-256 digests in the
  manifest. Stored state: observations, next observations, actions, rewards, dones, timeouts, `pos`, `full`,
  buffer layout (size per env, `n_envs`, shapes, dtypes), `num_timesteps`, `_n_updates`, `_n_calls`,
  `_episode_num`, `exploration_rate`, `_current_progress_remaining`, the schedule basis (planned transitions).
  It is restored before `learn()`, so the first resumed action already explores at the scheduled rate.
- Crash-safe bundles: every component is written to a temporary name, validated, moved to a name the manifest
  does not reference yet (a referenced file is never rewritten; a locked destination gets a unique name), checked
  again, and only then is the manifest entry published (the commit point). Validation-selected checkpoints now
  get one file per selection (`best_validation-<transitions>.zip`) instead of rewriting `best_validation.zip`.
  Replay state is stored only with periodic and stop checkpoints; all but the two most recent DQN continuation
  bundles are pruned (their weights stay).
- Stop boundaries: PPO stops at once and discards the partial rollout; DQN finishes the current rollout and its
  gradient steps and stops at the first step of the next one. Both record `env_interactions` and
  `discarded_interactions` per segment.
- Legacy DQN checkpoints (no continuation state) remain inference checkpoints; resuming from them is refused
  with an explanation. `warm-restart` (CLI, API, UI, explicit confirmation) creates a new run whose networks and
  optimizer state start from the checkpoint, records `lineage` (preserved and reset state), gets a different
  config hash and a `warm restart` comparison variant.
- Resumed runs are not bit-identical to uninterrupted ones (environments restart, random-number streams are not
  restored); this is stated in every resumable entry's contract.

**Tests executed.** `tests/test_dqn_continuation.py` (7: real stop/resume through `train()`, replay contents and
position for partial and wrapped buffers, target network and Adam moments, exploration and target-update phase,
transition accounting, corrupt/missing/incompatible state, numeric-only bounded arrays, legacy refusal and warm
restart, PPO contract and inference). Before the fix: 7 failed; after: 7 passed. Plus Windows lock tests and
browser flows (below).

**Historical data.** The 12 published DQN runs completed; their checkpoints were never resumable and remain
inference checkpoints. No file was changed.

## 2. Final-test freezing (audit §4): confirmed, fixed

**Files.** `lunarlab/freeze.py` (new), `lunarlab/evaluation.py` (`evaluate_run`, `_evaluate_final_test`),
`lunarlab/training.py`, `lunarlab/runs.py` (`load_policy("frozen" | "final-test")`, locked metadata/manifest
updates), `lunarlab/locks.py` (`hold`), `lunarlab/robustness.py`, `lunarlab/recording.py`, `lunarlab/play.py`,
`lunarlab/cli.py` (`run-experiment`, `record-showcase`, `test-status`, `freeze-migrate`), `lunarlab/lineage.py`
(test exposure), `lunarlab/tuning.py`, `lunarlab/server/api.py`, `frontend/src/pages/RunDetail.tsx`.

**Reproduction.**
- A run frozen by its first final test resumed training under the same run ID (no refusal anywhere).
- A final test proceeded while another holder had the run's worker lock (no lock was taken).
- Two simultaneous final tests both completed and both incremented `test_evaluations`.
- The frozen identity was a file *name* (`best_validation.zip`, a mutable alias); robustness, showcase
  recordings and ghost flights resolved that name, so a later replacement would have been followed silently.
- `run-experiment` treated `frozen_for_test` as "tested", so an interrupted final test was never retried.

**Root cause.** Freezing was a metadata flag checked only inside `evaluate_run`, without a lock, without an
immutable artifact, and without separating "frozen" from "tested".

**Correction.**
- The first final test (under the run's worker lock, the lock training holds) copies the selected checkpoint to
  `checkpoints/frozen/<sha256>.zip` (verified, read-only) and records `frozen_for_test` schema 2 (artifact,
  digest, config, reward and protocol identities, source entry).
- A frozen run never trains again: refused in the worker under the lock (so jobs accepted earlier cannot bypass
  it), in the API (409) and in the CLI (clean error, exit 1).
- One resolver (`freeze.resolve_final_checkpoint`) serves the final test, robustness, recordings and ghosts; it
  verifies the digest on every use and refuses a missing or altered artifact.
- `metadata.json -> test_attempts` records each attempt as started / completed / interrupted / failed; only a
  completed attempt counts (`freeze.test_status`, `pending_final_tests`); retries use the same frozen bytes.
- Lock ownership and order: the worker lock `.worker.lock` (training, freezing, final tests) may be held while
  taking the short metadata lock `.metadata.lock` (metadata and manifest read-modify-write); never the reverse.
- Test exposure: every completed final test is appended to `data/test_exposure.jsonl`. Warm restarts of tested
  runs and runs created by `tune-apply` on already-used test seeds are labelled *exploratory*; `--holdout-seeds`
  defines an untouched holdout (overlap with any used seed counts as used).
- Legacy (schema 1) freeze records still resolve while the named file has the recorded bytes;
  `freeze-migrate` creates the immutable copy explicitly and logs it; nothing is substituted when bytes differ.

**Tests executed.** `tests/test_freeze.py` (8: core/CLI/API/worker refusal, alias replacement with tested bytes
unchanged, race with a training lock holder, two simultaneous final tests, interrupted test not counted and
retried on the same checkpoint, missing/tampered artifact, legacy records and migration, post-test lineage).
Before: 8 failed; after: 8 passed. `tests/test_tuning.py` exposure tests, `tests/test_protocol.py` holdout test,
`tests/test_windows.py` (read-only artifact, second process holding the lock), browser flow 3.

**Historical data.** 43 runs carry schema-1 freeze records. Checked read-only with the new code: the tested
bytes of all 43 are intact, so all resolve. None was migrated (a user decision, see MIGRATION.md).

## 3. Outcome classification (audit §5): confirmed, fixed

**Files.** `lunarlab/outcomes.py`, `lunarlab/rewards/wrapper.py`, `lunarlab/evaluation.py` (`aggregate`,
`summarize_for_index`), `lunarlab/reclassify.py` (new), `lunarlab/recording.py`, `frontend/src/components/ui.tsx`
(`OutcomeBadge`), `frontend/src/pages/Compare.tsx`, `frontend/src/pages/RunDetail.tsx`.

**Reproduction.** With both legs between the flags: final angle 0.6 rad gave `landed_off_pad = True`; no leg
contact seen gave `landed_off_pad = True`; a NaN leg position also gave `landed_off_pad = True` (a guess). The
UI badge read "at rest (off pad)" for every at-rest episode that was not a strict pad landing.

**Root cause.** `landed_off_pad = at_rest_clean and not pad` mixed geography with landing quality.

**Correction.** Classifier version 2: `pad_geography` (within / straddling / outside / unknown, never guessed),
`landing_category` (strict pad landing, on pad not strict, landed not within the pad, at rest after body contact,
at rest with unknown geometry, crash, out of bounds, timeout, unknown), `strict_failures`, leg and pad
coordinates, `outcome_classifier_version: 2` on every new episode, aggregate and result. The strict pad-landing
definition is unchanged (tested). Version-1 files are never relabelled in place: summaries mark them legacy and
add `derived_v2` rates computed from their stored fields; `reclassify-outcomes` writes a separate derived report
with each source file's SHA-256.

**Tests executed.** `tests/test_outcomes_v2.py` (clean on-pad, tilted on-pad, no contact, off pad, straddling,
body contact, crash/out-of-bounds/timeout/unknown, NaN/inf geometry, invalid pad bounds, strict definition
unchanged, legacy reclassification, aggregates, real LunarLander episode). Before: import error (no versioned
classifier); after: all pass. Existing classifier tests: unchanged and passing. Browser flow 5.

**Historical data.** Derived recount of the published evaluations ([results/outcome_reclassification_v2.md](results/outcome_reclassification_v2.md)):
191 files, 11,500 episodes, 5,071 strict pad landings; 1,625 "landed off pad" under v1 and the same 1,625
under v2; **0 relabelled**. The defect existed but did not affect this data. Files unchanged.

## 4. Evaluation protocol validation (audit §6): confirmed, fixed

**Files.** `lunarlab/config.py` (`EvalProtocol.problems`, `require_valid`, `ProtocolError`), `lunarlab/runs.py`,
`lunarlab/training.py`, `lunarlab/evaluation.py`, `lunarlab/env.py` (`instantiated_environment`),
`lunarlab/compare.py`, `lunarlab/server/api.py`.

**Reproduction.** All accepted: duplicate validation seeds, `True` coerced to seed 1, overlapping validation and
test seeds, `"7"` and `3.0` coerced to seeds, a declared `gravity=-5` the environment factory never applied,
`env_id="CartPole-v1"`.

**Correction.** Seeds are strict integers (no coercion). Distinct seeds, disjoint validation/test lists, the range
0..999,999 (below training worker seeds) and the one supported environment are checked by `problems()`;
historical configs still load (and are marked), but no invalid protocol can create a run, train or evaluate.
Every evaluation records the instantiated environment (id, kwargs, overrides, effective physics) and refuses to
report when it differs from the protocol's declaration; robustness overrides are recorded separately. No field
was added to the protocol or run config hash inputs except `warm_start`, which is excluded when unset.

**Tests executed.** `tests/test_protocol.py` (valid default, duplicates, overlap, ranges, strict types, empty
lists, unsupported environment and kwargs, refusal for new runs, historical invalid protocol inspectable but not
usable, published config hashes pinned, declared vs actual environment, protocol difference warning, holdout
rules). Before: 15 failed, 4 passed (the 4 that already held); after: all pass.

**Historical data.** All 44 run configurations are valid; their recorded config hashes are unchanged (pinned for
a published PPO and DQN run in the tests).

## 5. Windows regression coverage (audit §7): confirmed gap, added

**Files.** `.github/workflows/ci.yml` (new `windows` job), `tests/test_windows.py` (new).

The job installs exactly as `scripts/setup.ps1` does (the Linux job's `--torch-backend cpu` failed offline on
Windows because it looks for torch on PyTorch's own index), runs `lunarlab doctor` (Box2D, reset/step, rendering,
H.264 encoding, SQLite, torch), the Windows-sensitive tests with temporary paths containing spaces, a PowerShell
parse of every script, and `start.ps1` / `stop.ps1` against Windows PowerShell 5.1.

**Windows workflow added: yes.** Before the push, every step was executed locally on Windows 11: a fresh virtual
environment in a folder whose path contains spaces, `doctor` 10/10, the job's test selection (125 passed), the
script parse (Windows PowerShell 5.1), and start → health → stop on port 8799 with an isolated home.
`tests/test_windows.py`: 9 passed locally (fault-injected locks, a real second process holding a destination
file, a failed bundle save registering nothing, the read-only frozen artifact, a second process holding the run
lock, atomic JSON replacement, stop/resume and final test under a path with spaces, the script parse, escape
sequences that PowerShell 7 reads differently).

**First run on GitHub** (commit `938ad31`): install, `doctor` and the job's tests (126 passed) succeeded; the
PowerShell 7 parse step failed on a defect in `scripts/setup.ps1` that dates from the first commit and that the
local 5.1 parse could not see (table below), so the start/stop step did not run. Fixed in the following commit.

## 6. Provenance (audit §8): confirmed, improved

**Files.** `lunarlab/demo.py`, `lunarlab/training.py` (per-segment `code`), `lunarlab/evaluation.py` (per-result
`code`), `lunarlab/results.py` (`generated_by`), `lunarlab/cli.py` (`export-demo --draft`),
`frontend/src/App.tsx`, `frontend/src/lib/demo.ts`.

**Before.** The export recorded a short commit and a dirty flag only; there was no release/draft distinction, no
file digests, no lock digests, no versions, no per-run code revisions; evaluations recorded no code revision.

**Correction.** Release exports refuse an unattributable or dirty tree (changes inside the output folder are
ignored); `--draft` allows it and labels the snapshot a draft (also in the demo banner). Manifest schema 2:
full export revision, dependency-lock digests, outcome/protocol/schema versions, every exported file's SHA-256,
per run the creation-time and per-segment training-code revisions and the evaluation files used (digest,
classifier version, evaluation-code revision where recorded). Results JSON records the analysis-code revision.

**Tests executed.** `tests/test_provenance.py` (3), the existing export test (now a draft).

**Historical data.** During the repair `demo/api/` was not re-exported (its manifest recorded commit `7f25084` with
`uncommitted_changes: true`, which the demo banner showed as a draft). Once the repair was committed it was
re-exported as a release snapshot of revision `ad1ee9f`, with the same experiments and runs: no value changed (the
new fields and the provenance manifest were added), and every other evidence file was byte-identical before and
after the export.

## 7. Scientific wording (audit §9): confirmed, corrected

README, RESULTS.md, REWARDS.md, the Learn and Learned Rewards pages, and the Compare statistics card:
- "solve the task as well as" → no clear evidence of improvement, and no established equivalence;
- "did what the theory promises" → what the theorem covers and does not;
- learned reward "alone" → its only training signal, while selection and simulated labels use the true reward;
- the estimator, resampling unit and a degenerate-interval explanation added wherever 0.00 [0.00, 0.00] appears.

No number was changed. RESULTS.md has a dated correction section for the outcome classifier.

## Other defects found and fixed during the repair

| Defect | Fix |
|---|---|
| `best_validation.zip` was rewritten in place before the manifest changed (a crash in between left a mismatched entry) | one file per selection; referenced files are never rewritten |
| Metadata read-modify-write from several processes could lose updates | short cross-process metadata lock |
| CLI refusals (frozen run, invalid protocol, missing state) surfaced as tracebacks | clean `error:` message, exit 1 |
| Run Detail labelled every validation-selected entry "validation-selected" | only the current one; earlier ones "earlier best" |
| The e2e home could not be deleted once it contained a read-only frozen artifact | cleanup clears the read-only flag |
| `reclassify-outcomes` ignored `--run-ids` together with `--experiment-ids` | both combined |
| `start.ps1` / `stop.ps1` used the project folder's `data\` for `backend.log` and `backend.json` even when `LUNARLAB_HOME` pointed elsewhere (found when a launch test with an isolated home overwrote the project's one-line `backend.log`; restored byte-for-byte, SHA-256 verified) | both scripts use `LUNARLAB_HOME\data` when it is set |
| `scripts/setup.ps1` wrapped a command in Markdown backticks inside a double-quoted string. Windows PowerShell 5.1 silently dropped them; PowerShell 7 reads `` `u `` as the start of a Unicode escape, so the whole script failed to parse there (found by the new Windows CI job) | single quotes; the parse test also uses `pwsh` when installed, and a new test flags `` `u `` and `` `e `` in double-quoted strings with the 5.1 tokenizer |

## Protection of existing evidence

All repair work and tests used isolated temporary homes; no published experiment was re-run, no model weights,
evaluation files, trajectories or recordings were modified, and no migration was applied to real data.

| Check | Result |
|---|---|
| SHA-256 of every file under `runs/`, `data/`, `reports/`, `docs/results/`, `docs/media/`, `demo/api/` before the repair | 1,665 files, combined digest `91ca86093d11901fcba6e3f8ebae40573dd6e13cece0766da1b858109493737f` |
| The same files after the repair | 1,665 unchanged, 0 changed, 0 missing; combined digest identical |
| Added | `docs/results/outcome_reclassification_v2.json` and `.md` (derived, with source digests) |
| Incident | a local launch test of `start.ps1` with an isolated home overwrote the project's one-line `data/backend.log` (a server banner, not evidence); it was restored byte-for-byte (SHA-256 verified) and the script was fixed |
| Release re-export of `demo/api/` after the repair (revision `ad1ee9f`) | 51 of its 382 files rewritten with added fields and the new manifest, no value changed; the other 1,285 evidence files byte-identical before and after |
| Read-only checks on real data with the repaired code | 44 runs load; 43 legacy freeze records resolve with intact tested bytes; 38 published runs show a completed final test; 199 evaluation files reported as classifier v1; `freeze-migrate --all --dry-run`: 43 migratable |

## Verification summary

See the final section of [MIGRATION.md](MIGRATION.md) for the commands. Executed: full `pytest`, `ruff check`,
`ruff format --check`, `npm run typecheck`, `npm run lint`, `npm run build`, Playwright (15 flows including the
5 new audit flows), the Windows job's steps locally. On GitHub (commit `938ad31`): the Linux jobs (lint and all
tests, frontend, browser end-to-end) and the demo deployment passed; the Windows job's first run found the
`setup.ps1` defect above.
