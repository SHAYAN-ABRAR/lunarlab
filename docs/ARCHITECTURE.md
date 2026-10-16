# Architecture

```
           browser (React + Vite build, served by the backend)
                │  polling JSON over http://127.0.0.1:8765  (no websockets needed)
                ▼
  FastAPI app  (lunarlab/server) ── SQLite: jobs, reward-config revisions, settings
                │  JobManager thread: launch / monitor / stop / reconcile
                ▼
  worker processes:  python -m lunarlab worker --job-id <id>   (one per job, own process group)
                │
                ▼
  lunarlab core ── training · evaluation · recording · rescoring · reports
                │
                ▼
  files: runs/<run_id>/…, data/demos, data/flights, data/preferences, data/reward_models, data/jobs, reports/
```

The CLI (`python -m lunarlab …`) calls the same core functions directly. The RL package never imports the web
server.

## Codebase map

| Path | Responsibility |
|---|---|
| `lunarlab/env.py` | environment construction, observation/action metadata, **read-only internals adapter** (`probe`), built-in reward decomposition |
| `lunarlab/hover.py` | the one hover predicate (used by the hover bonus and the detector, with separate thresholds) |
| `lunarlab/rewards/config.py` | strict reward schema, presets, content hash, design warnings |
| `lunarlab/rewards/terms.py` | pure term functions: potential, shaping, hover bonus, time penalty |
| `lunarlab/rewards/accounting.py` | per-episode accumulator (original/training/discounted returns, actions, hover) |
| `lunarlab/rewards/wrapper.py` | the single reward wrapper (training, evaluation telemetry, recording) |
| `lunarlab/rewards/analysis.py` | discounted-return calculators shown in the Reward Studio |
| `lunarlab/outcomes.py` | terminal-outcome classification (version 2: pad geography kept apart from landing quality) and strict pad landing |
| `lunarlab/continuation.py` | DQN continuation bundles: replay buffer and algorithm state, strictly validated and digest-checked |
| `lunarlab/freeze.py` | final-test freezing: immutable artifact, shared resolver, test attempts, legacy migration |
| `lunarlab/lineage.py` | warm restarts, test exposure registry, evidence role (confirmatory / exploratory) |
| `lunarlab/reclassify.py` | derived outcome-classifier-v2 reports for version-1 evaluation files (never modified) |
| `lunarlab/config.py` | PPO settings, budget profiles, evaluation protocol, run config, resume compatibility |
| `lunarlab/training.py` | PPO training, callback (episodes, heartbeat, diagnostics, checkpoints, validation, stop), resume |
| `lunarlab/evaluation.py` | evaluation with the original reward, aggregation, final tests under the run lock |
| `lunarlab/recording.py` | video + telemetry recording, MP4/JPEG sinks, verification, recording library |
| `lunarlab/rescoring.py` | Reward Stress Test |
| `lunarlab/compare.py` | run summaries, compatibility, per-seed grouping, exploitation rule, training curves |
| `lunarlab/report.py` | Markdown/HTML report, figures, portfolio summary |
| `lunarlab/results.py` | figures and tables for `docs/RESULTS.md` (final-test data only) |
| `lunarlab/rl_stats.py` | IQM, bootstrap intervals over training seeds, probability of improvement, performance profiles |
| `lunarlab/robustness.py` | frozen checkpoints under wind / turbulence / heavier gravity (separate `robustness:<condition>` evaluations) |
| `lunarlab/preferences/` | RLHF in miniature: segment datasets and labels (`data.py`), reward-model inference and registry (`model.py`), Bradley–Terry training (`train.py`) |
| `lunarlab/play.py` | keyboard flights: server-stepped episodes recorded like any policy, opponent ghosts |
| `lunarlab/parallel.py` | several runs of an experiment in parallel worker processes (CLI) |
| `lunarlab/demo.py` | static snapshot of the API for the hosted read-only demo |
| `lunarlab/runs.py`, `storage.py` | run creation, metadata, checkpoint manifest (SHA-256), atomic writes, path safety |
| `lunarlab/jobs.py`, `db.py`, `locks.py`, `procs.py` | job supervisor, SQLite, file locks, verified process discovery |
| `lunarlab/server/` | FastAPI app, request schemas, security middleware, static UI |
| `lunarlab/cli.py`, `doctor.py`, `benchmark.py` | command line, installation checks, throughput benchmark |
| `frontend/src/` | React UI: `pages/` (one per view), `components/` (ui, charts, jobs, launch), `lib/` (API client, types, formatting) |
| `frontend/src/components/Scene3D.tsx` | 3-D flight reconstruction (three.js, lazy-loaded): recorded pose, actions and contacts on the episode's real terrain (`GET /api/recordings/{id}/scene`); also drives live flights and ghosts |
| `frontend/src/components/FlightScene.tsx`, `pages/Fly.tsx` | Fly It Yourself: keyboard/touch controls, live 3-D view, opponent ghost, logbook |
| `frontend/src/pages/LearnedRewards.tsx` | preference labelling (two animated segments, reveal of the true returns), reward-model registry |
| `frontend/src/components/robust.tsx` | Compare cards: aggregate statistics, performance profiles, robustness table |
| `frontend/src/lib/demo.ts` | static demo mode: answers requests from the exported snapshot |
| `tests/` | pytest suite; `frontend/e2e/` Playwright browser flows |

## Wrapper order and who sees which reward

```
LunarLander (unmodified reward)
 └ PassiveEnvChecker / OrderEnforcing   (gym.make)
   └ TimeLimit(1000)                     (gym.make; sets truncated)
     └ LunarLabRewardWrapper             original → original + Σ terms (training) | original (evaluation)
       └ SB3 Monitor                     training only: its episode "r" and ep_rew_mean are the SHAPED return
         └ DummyVecEnv / SubprocVecEnv   auto-reset; final obs in info["terminal_observation"]
```

The wrapper emits `info["lunarlab_episode"]` (original and training returns, terms, outcome, hover, actions)
on the final step, before the vector env resets. The training callback logs it to `episodes.csv`. Internals
needed for outcomes (body contact, sleep state, helipad flags, leg positions) are read only through
`env.probe`, which is tested against the installed gymnasium (1.4.0).

## Training engine

- PPO `MlpPolicy`, policy and value nets `[64, 64]` with tanh, CPU by default. Defaults follow RL Baselines3
  Zoo's LunarLander-v3 entry with `n_envs = 4` instead of 16, identical for all reward comparisons:
  `n_steps 1024, batch 64, lr 3e-4 (constant), γ 0.999, λ 0.98, 4 epochs, ent_coef 0.01, clip 0.2`.
- Budgets count **environment transitions** (`num_timesteps`). PPO completes whole rollouts (4,096
  transitions), so requested budgets are rounded up and both numbers are recorded.
- `torch.set_num_threads(1)` and `OMP_NUM_THREADS=1` in workers avoid oversubscribing the CPU. The benchmark
  (`lunarlab benchmark`) measured in-process vector envs as faster than subprocess ones for this small
  environment, so `dummy` is the default. `subproc` uses Windows-safe `spawn` and picklable factories.
- PPO diagnostics: SB3 records `train/*` values during `train()` but dumps logs before the *next* update,
  so LunarLab reads `logger.name_to_value` at the next rollout start (with `log_interval=None`) and attributes
  each row to the update that produced it.
- Checkpoints: periodic, `stop`, `final`, and `best_validation` (selected by validation original return).
  Each is written to a uniquely named temp file, atomically replaced (retrying for up to 60 s on Windows
  sharing violations such as antivirus scans), and registered in `checkpoints/manifest.json` with its
  SHA-256. If the destination stays locked for a whole minute, the checkpoint is stored under a unique name
  instead (`best_validation-<transitions>-<hex>.zip`) and the manifest records it; every reader resolves
  checkpoints through the manifest. (Before this fallback existed, one STANDARD run of the study failed on
  such a lock and was resumed from its last periodic checkpoint; its lineage shows the second segment.)
- **Loading never unpickles.** SB3 zips contain cloudpickled objects in their `data` entry. LunarLab rebuilds
  the policy from the run's own `config.yaml` and loads only tensors through
  `load_from_zip_file(load_data=False)` (`torch.load(weights_only=True)`), and only for files listed in a
  manifest whose hash still matches. Resume uses `PPO(...).set_parameters(...)`, which follows the same safe
  path. No endpoint accepts uploaded model files.

### DQN

`RunConfig.algo` selects PPO (default) or DQN. DQN uses RL Baselines3 Zoo's LunarLander entry
(`lr 6.3e-4, batch 128, buffer 50k, learning_starts 0, γ 0.99, target update 250, train_freq 4,
gradient_steps -1, exploration 0.12 → 0.1, net [256, 256]`), the same reward wrapper, evaluation protocol,
checkpointing and safe weight loading (`DQNPolicy` rebuilt from the config, tensors only). PPO run configs
hash exactly as before the field existed, so older runs stay resumable. DQN's diagnostics are recorded every
10k transitions (it updates every 4 steps; logging each update would dominate the log).

### Experiment variants

An experiment is *rewards × variants × seeds*. A variant fixes the algorithm, its discount factor and the
training physics (`lunarlab/experiments.py: build_variants`); the default is a single variant, which is how
earlier experiments were built. With several algorithms the budget is rounded up to a multiple of every
algorithm's rollout, so PPO and DQN train on exactly the same number of transitions. Compare & Diagnose groups
runs by algorithm, reward and variant (discount factor and training physics), and names a group by what sets
it apart from the algorithm's reference setup ("· gamma 0.99", "· randomized physics").

Groups of one reward and training physics that differ in γ, or in the algorithm at one γ, form the
discount-factor ablation (`compare.py: gamma_ablation`): algorithm × γ cells, within-algorithm γ effects,
PPO − DQN at matched γ, and a difference interval that resamples each cell's seeds
(`rl_stats.bootstrap_difference_ci`). Training curves carry `elapsed_s`, the wall-clock time accumulated over
a run's segments (`compare.py: elapsed_seconds`), next to `transitions`.

### Training under varied physics

`PhysicsRandomizer` (`lunarlab/physics.py`) wraps LunarLander directly, below the reward wrapper. It sets
`enable_wind`, `wind_power`, `turbulence_power` and `gravity` on the unwrapped environment before each reset:
Gymnasium reads gravity when the episode's world is created and wind at every step, and draws terrain and the
initial push before the wind phase, so the episode seed still fixes the terrain. The `physics` section of a
run config is part of its hash only when enabled, so fixed-physics runs hash exactly as before (all stored runs
were re-checked), and resuming with different physics is refused.

### Parallel experiments (CLI)

`suite --parallel N` and `run-experiment --parallel N` run up to N runs of one experiment at a time, each in
its own `python -m lunarlab train-run` process with one torch/OMP thread, logs in `runs/<id>/worker.log`.
Interrupted or failed runs resume from their latest checkpoint on the next `run-experiment`, and every
unfrozen run is then evaluated once on the final-test seeds. On the 10-core development laptop, 5 PPO runs
in parallel sustained about 1,000–1,200 transitions/s each. Workers get `LUNARLAB_PARALLEL_SLOTS=N` (the job
supervisor sets its lane's limit), and each training segment stores it as `parallel_slots`: wall-clock
learning curves are only comparable between runs that trained under the same load.

## Stop, resume and lineage

### Checkpoint contract

| Kind | Contents | Use |
|---|---|---|
| **Inference checkpoint** | SB3 `.zip`, loaded weights-only (`final`, `best_validation-<n>`) | evaluate, record, replay, fly against |
| **Resumable training checkpoint** | PPO: `.zip` (policy, value net, optimizer state) + counters in the manifest. DQN: the same plus a continuation bundle (below) | continue the **same** run (`periodic`, `stop`) |
| **Warm restart** | a *new* run whose networks and optimizer state start from a checkpoint | further training under a new run ID, compared separately |

Each manifest entry records `role`, `resumable` and, for resumable ones, `continuation` (format and the
contract in words). PPO periodic/stop entries written before this contract was named remain resumable under
the same terms; DQN entries without a continuation bundle are inference checkpoints only.

**DQN continuation bundle** (`lunarlab/continuation.py`). SB3 2.9.0 keeps the online and target Q-networks
and the Adam state in the `.zip`, but the replay buffer and several counters outside it. Stored next to every
periodic and stop DQN checkpoint: `<ckpt>.replay.npz` (observations, next observations, actions, rewards, dones,
timeouts, only the filled rows) and `<ckpt>.state.json` (`pos`, `full`, buffer layout and dtypes, `n_envs`,
`num_timesteps`, `_n_updates`, `_n_calls` (target-update phase), `_episode_num`, `exploration_rate`,
`_current_progress_remaining`, the schedule basis, SB3 version, the replay archive's digest). Loading: sizes and
SHA-256 digests against the manifest; the JSON validated strictly; every `.npy` header checked for name, shape
and dtype before any array data is read (bounded memory, `allow_pickle=False`, object dtypes refused); layout
checked against the model; values checked (finite observations and rewards, 0/1 flags, actions in range). The
state is applied before `learn()`, so the first resumed action already uses the scheduled exploration rate. A
digest proves integrity against the manifest, not that a file from elsewhere is trustworthy; no API endpoint
accepts these files. All but the two most recent continuation bundles of a run are pruned (weights kept).

**Crash-safe bundles** (`training.save_model_atomic`). Every component is written to a temporary name and
validated, then moved to a name the manifest does not reference (a referenced file is never rewritten, so a
validation-selected checkpoint is `best_validation-<transitions>.zip`, one per selection; a destination that
stays locked, e.g. by an antivirus scan, gets a unique name), re-checked against its digest, and only then is
the manifest entry published under the metadata lock: the commit point. A failure at any step removes the
temporary files and registers nothing, so the previous checkpoints stay valid.

### Stop and resume

- **Stop** is cooperative: a control file (`runs/<id>/control/stop_requested.json`) is polled about every
  0.25 s. The safe boundary is the start of a rollout, right after the previous update. PPO stops at once: the
  partially collected rollout is discarded and counters roll back to the last completed update. DQN has already
  stored that rollout's transitions in its replay buffer, so it finishes the rollout and its gradient steps and
  stops at the first step of the next one (that single step is neither stored nor trained on). Either way the
  segment records `env_interactions` and `discarded_interactions`, and a `stop_*` checkpoint is written at the
  boundary. Ctrl+C in a CLI training terminal does the same; a second Ctrl+C aborts without a stop checkpoint.
- **Resume** continues the *same* run from a resumable checkpoint, after verifying the file hash, the
  continuation bundle (DQN) and that the checkpoint's config hash equals the run's. Cumulative counters (and,
  for DQN, the replay buffer, target-update phase and exploration state) are restored, and a new segment
  (parent checkpoint, new worker seeds, PID, job id, code revision) is appended to `metadata.json`.
  Training-episode rows that an earlier segment logged after the resume point are excluded from curves.
- **Warm restart** (`lineage.create_warm_restart`; CLI `warm-restart --confirm`, API `POST
  /api/runs/{id}/warm-restart` with `confirm: true`, a confirmation dialog in the UI) creates a new run with
  `RunConfig.warm_start` (parent run, checkpoint, digest) and `metadata.json -> lineage` listing what was
  preserved and what was reset. Its config hash differs from the parent's, and comparisons give it its own
  `warm restart` variant. A warm restart of a tested run is labelled exploratory.
- Changing the reward (or PPO settings) is a **new experiment**, not a continuation, and is refused for resume.
- A resumed run is **not bit-for-bit identical** to an uninterrupted one: environment states, the rollout
  in progress and RNG streams at the interruption are not restored (new worker seeds are used on purpose).
  Uninterrupted runs with the same seed reproduce exactly: two independent SMOKE runs of the same config
  gave identical validation returns to six decimals.

## Job supervisor

- States: `queued → starting → running → (stop_requested) → stopped | completed | failed | interrupted`.
- Lanes: `train` (train/resume) and `analysis` (evaluate/record/demo/report/benchmark), one slot each, so
  video and evaluation never pile up next to training.
- Duplicate prevention: one active job per run (checked in a SQLite transaction), idempotency keys per UI
  action, a per-run OS file lock held by the worker, and a single-instance lock (`data/backend.lock`) for the
  backend itself.
- Each job records PID, process creation time, timestamps, heartbeat (from the worker's `status.json`),
  progress, exit code, result and a log tail. UI updates are polled (1–5 s); training never waits for a
  browser.
- **Force-terminate** happens only after verifying PID, creation time and a command line containing the
  job id. A stale PID in the database is never enough.
- **Reconciliation at startup:** live workers are re-adopted, dead ones are closed from their final status
  files or marked `interrupted`, and jobs queued before the restart wait for an explicit "Resume queue".

### Shutdown behaviour

- Closing the browser changes nothing: workers keep running while the backend and laptop run.
- Ctrl+C in the backend console, or `scripts/stop.ps1`, triggers a graceful shutdown. Running jobs are asked
  to stop at a safe boundary (state `interrupted`, resumable), and the server waits up to 45 s.
- If the backend crashes, workers keep running in their own process group; the next start re-adopts them.
- While the laptop sleeps, all processes are suspended and continue on wake. Nothing runs while it is off.
  A heartbeat older than 60 s is shown as a warning.

## Learned rewards (RLHF in miniature)

```
policies (random, heuristic, PPO checkpoints at 100k/300k/600k/final of baseline and hover-bonus runs)
  → 40-step segments (data/preferences/<dataset>/segments.npz, episode seeds from 30,000)
  → pairs labelled by a Bradley–Terry simulated human on the true segment return (beta = 0.05)
    (+ optional human labels from the UI, data/preferences/<dataset>/human_labels.jsonl)
  → fixed train/validation split by whole episode (segments of one episode overlap, so they never straddle it)
  → reward model r(s, a, s') : MLP 20-64-64-1 tanh, BCE on summed segment rewards, early stopping
    (data/reward_models/<model>/model.npz + meta.json with SHA-256; immutable)
  → reward config with original_weight 0 and the learned term only → PPO → evaluation on the true reward
```

Human labels are sorted by where their two segments lie: both in training episodes → used for training; both in
validation episodes → reported as accuracy against people; one on each side → never used (counted in the model's
metadata). Pairs shown in the labelling UI come from training episodes only.

The invariant generalizes to `training_reward = original_weight × original_reward + Σ terms` (weight 1 for
all presets). Reward models are evaluated in NumPy inside the wrapper; their weights are plain arrays loaded
with `allow_pickle=False` after a hash check, so a reward model cannot execute code.

### Active preference learning

`lunarlab/preferences/active.py` adds reward-model **ensembles** (several networks fitted on bootstrap
resamples of the same labels; the reward is the mean of the members' normalized outputs, saved as one
hash-checked `model.npz`) and two ways to choose the next pair: `random` (the baseline) and `disagreement`
(among 2,000 random candidate pairs of training segments, the one where the members' Bradley–Terry
probabilities P(A preferred) have the largest standard deviation). A pair is never labelled twice, in either
order: selection excludes labelled pairs and the label endpoint refuses duplicates (409).

* `python -m lunarlab rlhf-active` simulates the loop for both strategies over several seeds with the
  Bradley–Terry labeller, deterministic per pair (the same pair always gets the same answer, whichever
  strategy asks), from the same initial random labels per seed, and saves the learning curves (accuracy vs
  true order on a fixed set of validation pairs) with the dataset in `active/`. `--register` keeps the final
  ensembles as reward models; `rlhf-study --reward-models <ids>` then trains PPO on them.
* In the UI, *Learned Rewards* shows the chosen strategy, labelling progress (labels, labels usable for
  training, labels since the ensemble was fitted) and the disagreement score of the current pair. *Fit
  ensemble* runs a `reward_ensemble` job on your labels from training episodes (optionally plus simulated
  ones) and makes it the dataset's labelling ensemble (`labelling.json`).

## Automatic tuning (Optuna)

`lunarlab/tuning.py` defines a bounded search space (PPO or DQN settings and the reward weights of the chosen
preset; bounds sit inside each config's own validation limits), a TPE sampler and a median pruner. A study
lives in `data/tuning/<study_id>/`: `study.json` (definition), `optuna.sqlite3` (Optuna's RDB storage) and
`status.json`. Trials train in the tuning process through `train(run_id, on_validation=...)`: after each
validation the callback reports to Optuna and can ask the run to stop at the next safe boundary (pruned or
cancelled). Cancelling (`tune-cancel`, the UI, or stopping the `tune` job) also signals the running trial's run
directly, so it stops within seconds rather than at its next validation. Resuming loads the storage, marks
trials left RUNNING by a crashed session as failed, and continues until `n_trials` trials have completed or
been pruned. `tune` jobs use the training lane, so they never run alongside another training job.

## Keyboard flights

`POST /api/flights` creates a session that holds one `EpisodeRecorder` (the same class `record_episode`
uses): the evaluation environment with the original reward, a video sink and the telemetry rows. The page
sends the actions due since its last request (`POST /api/flights/{id}/step`, at most 50 per request, one
request in flight); the server steps the real physics and returns the new rows, which the 3-D engine plays
with a two-frame buffer. When the episode ends the recording is verified and saved in `data/flights/` with
policy kind `human`. Sessions expire after 10 idle minutes (at most 4 at a time). An opponent's whole flight
on the same seed is computed up front without rendering and drawn as a translucent ghost.

## Static demo

`python -m lunarlab export-demo --experiment-ids …` calls the API in-process and writes every GET response
the UI needs (plus precomputed comparisons, recording videos and sample preference pairs) to `demo/api/`,
filtered to the chosen experiments and with absolute local paths scrubbed. A frontend build with
`VITE_DEMO=1` answers requests from those files (`frontend/src/lib/demo.ts`) and disables everything that
would need the backend. `.github/workflows/pages.yml` publishes it to GitHub Pages;
`scripts/build-demo.ps1` builds and serves the same thing locally.

## Policy diagnostics in recordings

`SB3Policy.diagnostics(obs)` evaluates the same network the action came from, in `torch.no_grad()`:
`get_distribution(obs)` (probabilities and entropy) and `predict_values(obs)` for PPO, `q_net(obs)` for DQN.
`record_episode` stores the result in the telemetry row of the step it decided (`row["policy"]`) and adds a
`policy_diagnostics` description to the telemetry. Flight Replay shows the current step's distribution or
values next to the action and charts them on the shared, click-to-seek timeline; recordings without the
fields (older ones, demonstrations, keyboard flights) simply have no policy charts.

## Showcase media

`python -m lunarlab showcase` composes recorded flights side by side, as a GIF or an animated WebP. By default
it uses each recording's simulator footage. For the 3-D version, `frontend/tools/capture3d.mjs` first opens
each replay with `?capture=1`: the engine's display loop stops, a simulated clock replaces wall time, and
every frame advances playback by a fixed step (`startCapture` / `captureFrame` in `Scene3D.tsx`), so the
same recording always renders the same frames, independent of the machine's frame rate.

## Final-test freezing, locks and test exposure

The first final-test evaluation of a run (under its worker lock) copies the selected checkpoint to
`checkpoints/frozen/<sha256>.zip`, verifies the copy and makes it read-only, and records
`metadata.json -> frozen_for_test` (schema 2: artifact, digest, transitions, config, reward and protocol
identities, the source manifest entry). Afterwards:

- the run never trains again under its run ID: `_train_locked` refuses under the worker lock (so a job
  accepted earlier cannot bypass a freeze), the API answers 409 and the CLI exits with an explanation;
- the final test, robustness evaluations, showcase recordings and ghost flights all load the frozen bytes
  through `freeze.resolve_final_checkpoint`, which verifies the digest every time; a missing or altered
  artifact is refused, never replaced by another checkpoint;
- every attempt is recorded in `metadata.json -> test_attempts` (`started`, then `completed`, `interrupted` or
  `failed`). Only a completed attempt counts as a final test (`freeze.test_status`, `pending_final_tests`);
  `run-experiment` and the UI retry incomplete ones on the same frozen checkpoint.

**Locks.** `runs/<id>/.worker.lock` is held for the whole of a training segment and of a final-test evaluation
(including the freeze): a run cannot be frozen while it trains, and two final tests cannot overlap (the second
is refused as busy). `runs/<id>/.metadata.lock` guards each read-modify-write of `metadata.json` and the
checkpoint manifest, for a few milliseconds, across processes. Order: the worker lock may be held while taking
the metadata lock, never the reverse, so they cannot deadlock. Locks are OS file locks released if the holder
dies.

**Legacy freeze records** (schema 1: a checkpoint name and digest) resolve only while that file still has the
recorded bytes. `python -m lunarlab freeze-migrate` (dry run first) creates the immutable copy explicitly and
logs it; it never substitutes another checkpoint.

**Test exposure.** Every completed final test is appended to `data/test_exposure.jsonl` with its test seeds.
`lineage.evidence_role` labels a run **exploratory** when its design was influenced by an already-seen final
test: a warm restart of a tested run, or a run created by `tune-apply` on test seeds that had already been used
(any overlap counts). `--holdout-seeds START:COUNT` (on `suite` and `tune-apply`) defines a protocol with
untouched test seeds for confirmatory results.

## Outcome classification and protocol validity

Outcome classifier version 2 (`lunarlab/outcomes.py`, see EVALUATION.md) records `pad_geography`,
`landing_category`, `strict_failures`, leg and pad coordinates and `outcome_classifier_version` in every new
episode, aggregate and result. Version-1 results are never rewritten: `evaluation.summarize_for_index` marks
them and adds `derived_v2` rates derived from their stored episode fields, and `reclassify-outcomes` writes a
separate derived report with the source files' digests.

`EvalProtocol` seeds are strict integers; `problems()` reports duplicates, validation/test overlap, seeds
outside 0..999,999 and any environment other than `LunarLander-v3` with `{continuous: False}`. Historical
configurations still load and are marked; no invalid protocol can create a run, train or evaluate. Every
evaluation records the instantiated environment (`env.instantiated_environment`: id, kwargs, robustness
overrides, effective physics) and refuses to report under the protocol's environment if it differs from the
declaration.

## Provenance

- training: the source revision at run creation (`metadata.json -> system.git`) and per segment
  (`segments[i].code`);
- evaluation: `code` in every result file written from now on;
- analysis: `generated_by.analysis_code` in `docs/results/results.json` when regenerated;
- demo export: manifest schema 2 (`demo.py`): `kind` release or draft, full export revision, dependency-lock
  digests, metric/protocol/schema versions, per-run sources and every exported file's SHA-256. A release export
  refuses a dirty or unattributable tree (changes inside the output folder do not count); `--draft` labels the
  snapshot a draft. Snapshots exported earlier keep the provenance they were written with.

## Storage and reproducibility

Each run directory contains its exact `config.yaml` (immutable), `metadata.json` (config hash, reward
preset, revision and hash, seeds, environment spec, Python/package versions, hardware, git state when
available, segments and lineage, test freeze), `status.json`, `events.jsonl` (rotated after 2 MB),
`episodes.csv`, `metrics.jsonl`, evaluations, checkpoints (with DQN continuation bundles and, once frozen,
`checkpoints/frozen/<sha256>.zip`, read-only), trajectories and videos. Status and manifests use atomic writes. An `episodes.csv` keeps the columns it was created with: a run resumed by a newer LunarLab
that logs more columns writes its rows in the file's own layout. One published run was resumed before that
rule and has rows of two widths; the reader maps each row by its width instead of skipping the file. SQLite holds only metadata and is never written per physics step. Timestamps are stored
in UTC and displayed in local time. Nothing is deleted automatically.

## Local security model

There are no accounts; the safeguards are local-web hygiene:

- binds to 127.0.0.1; `TrustedHostMiddleware` rejects non-loopback Host headers (DNS rebinding);
- mutating requests need `X-LunarLab: 1` and a same-origin (or absent) `Origin`;
- strict Pydantic schemas with bounds and enums, and unknown fields rejected;
- every file path is built with `safe_child` (one validated name per segment, resolved inside its base);
  run, job and report ids are pattern-checked;
- no `shell=True`; workers start from an argument list;
- YAML import uses `yaml.safe_load` and the reward schema; no expression is ever evaluated.

## Design decisions

| Decision | Reason |
|---|---|
| Python 3.12 venv (uv-managed) | Box2D 2.3.10 / pygame 2.6.1 have Windows wheels only up to 3.13; the machine's default 3.14 cannot install them without a C++ toolchain |
| `Box2D==2.3.10` instead of gymnasium's `box2d-py` extra | provides the same `Box2D` module as prebuilt wheels; `box2d-py` is source-only (SWIG + MSVC) |
| CPU, `DummyVecEnv`, 1 torch thread | measured fastest for a 64×64 MLP on this laptop; GPU optional (`--device cuda` with a CUDA torch build) |
| Polling, not websockets | robust across reconnects; the UI never sits in the training loop |
| Files as ground truth, SQLite as index | CLI and web share one data model; large artifacts never enter SQLite |
| H.264 MP4 with a keyframe every 25 frames | browser-playable, frame-accurate seeking; JPEG-frame fallback is verified in tests |
| 3-D view reconstructed from telemetry, footage kept | LunarLander is 2-D; the 3-D view uses only recorded data on the simulation plane (pose, actions, contacts, the env's own terrain `sky_polys` and flags) and labels depth, lighting, particles and model as illustrative |
| Validation every 50k transitions on 10 seeds | checkpoint selection on original reward at modest cost (~20 passes per STANDARD run) |
| DQN at Zoo's 100k-transition budget | DQN updates every 4 steps and ran at ~100 transitions/s per process here, so 1M transitions would take hours per run; comparisons show the different budgets |
| Simulated preferences (Bradley–Terry on the true return) | makes the RLHF experiment reproducible and lets accuracy be measured against the noise-free order; human labels are supported and stored separately |
| Robustness on 50 test seeds per condition | identical terrain and initial push across conditions isolate the effect of the physics change |
| Static snapshot instead of a hosted backend | the demo costs nothing to host, cannot be abused, and shows exactly the stored results |
