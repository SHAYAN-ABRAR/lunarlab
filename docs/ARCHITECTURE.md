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
  files: runs/<run_id>/…, data/demos, data/jobs, reports/        (ground truth for run content)
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
| `lunarlab/runs.py`, `storage.py` | run creation, metadata, checkpoint manifest (SHA-256), atomic writes, path safety |
| `lunarlab/jobs.py`, `db.py`, `locks.py`, `procs.py` | job supervisor, SQLite, file locks, verified process discovery |
| `lunarlab/server/` | FastAPI app, request schemas, security middleware, static UI |
| `lunarlab/cli.py`, `doctor.py`, `benchmark.py` | command line, installation checks, throughput benchmark |
| `frontend/src/` | React UI: `pages/` (one per view), `components/` (ui, charts, jobs, launch), `lib/` (API client, types, formatting) |
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
  Each is written to a temp file, atomically replaced (with retries for Windows sharing violations such as
  antivirus scans), and registered in `checkpoints/manifest.json` with its SHA-256.
- **Loading never unpickles.** SB3 zips contain cloudpickled objects in their `data` entry. LunarLab rebuilds
  the policy from the run's own `config.yaml` and loads only tensors through
  `load_from_zip_file(load_data=False)` (`torch.load(weights_only=True)`), and only for files listed in a
  manifest whose hash still matches. Resume uses `PPO(...).set_parameters(...)`, which follows the same safe
  path. No endpoint accepts uploaded model files.

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

## Storage and reproducibility

Each run directory contains its exact `config.yaml` (immutable), `metadata.json` (config hash, reward
preset, revision and hash, seeds, environment spec, Python/package versions, hardware, git state when
available, segments and lineage, test freeze), `status.json`, `events.jsonl` (rotated after 2 MB),
`episodes.csv`, `metrics.jsonl`, evaluations, checkpoints, trajectories and videos. Status and manifests
use atomic writes. SQLite holds only metadata and is never written per physics step. Timestamps are stored
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
| Validation every 50k transitions on 10 seeds | checkpoint selection on original reward at modest cost (~20 passes per STANDARD run) |
