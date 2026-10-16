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
| `lunarlab/outcomes.py` | terminal-outcome classification and strict pad landing |
| `lunarlab/config.py` | PPO settings, budget profiles, evaluation protocol, run config, resume compatibility |
| `lunarlab/training.py` | PPO training, callback (episodes, heartbeat, diagnostics, checkpoints, validation, stop), resume |
| `lunarlab/evaluation.py` | evaluation with the original reward, aggregation, test freezing |
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

- **Stop** is cooperative: a control file (`runs/<id>/control/stop_requested.json`) is polled about every
  0.25 s. The partially collected rollout is discarded and counters roll back to the last completed PPO
  update. A `stop_*.zip` is written from those weights (the safe boundary). Ctrl+C in a CLI training
  terminal does the same; a second Ctrl+C aborts without a stop checkpoint.
- **Resume** continues the *same* run from a periodic or stop checkpoint, after verifying the file hash
  and that the checkpoint's config hash equals the run's. Cumulative counters are restored, and a new segment
  (parent checkpoint, new worker seeds, PID, job id) is appended to `metadata.json`. Training-episode rows
  that an earlier segment logged after the resume point are excluded from curves.
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

## Storage and reproducibility

Each run directory contains its exact `config.yaml` (immutable), `metadata.json` (config hash, reward
preset, revision and hash, seeds, environment spec, Python/package versions, hardware, git state when
available, segments and lineage, test freeze), `status.json`, `events.jsonl` (rotated after 2 MB),
`episodes.csv`, `metrics.jsonl`, evaluations, checkpoints, trajectories and videos. Status and manifests
use atomic writes. An `episodes.csv` keeps the columns it was created with: a run resumed by a newer LunarLab
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
