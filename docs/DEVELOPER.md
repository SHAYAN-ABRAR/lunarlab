# Developer guide

For contributors who want to modify or extend LunarLab. The detailed design (wrapper order, stop and resume
semantics, final-test freezing, locks, provenance, security model) is in [ARCHITECTURE.md](ARCHITECTURE.md); the
generated API reference is in [api/](api/README.md); contribution rules are in [../CONTRIBUTING.md](../CONTRIBUTING.md).

## Layout and module responsibilities

| Area | Modules | Responsibility |
|---|---|---|
| Rewards | `rewards/config.py`, `rewards/terms.py`, `rewards/accounting.py`, `rewards/wrapper.py`, `rewards/analysis.py` | strict reward schema and presets; pure term functions; per-episode sums; the single wrapper used for training, evaluation and recording |
| Task-independent auditing | `audit/core.py`, `audit/adapters.py`, `audit/evaluate.py` | the accounting identity for any Gymnasium task; task adapters (LunarLander, CartPole); policy audits |
| Environment and outcomes | `env.py`, `outcomes.py`, `hover.py`, `physics.py` | environment factory and read-only internals; outcome classifier (version 2); hover detector; per-episode physics randomisation |
| Configuration and runs | `config.py`, `runs.py`, `storage.py`, `locks.py` | run, PPO/DQN, training and protocol schemas with hashes; run creation, metadata and checkpoint manifest; paths and atomic writes; cross-process locks |
| Training | `training.py`, `continuation.py`, `policies.py` | SB3 model and environment construction, the training callback, crash-safe checkpoints, DQN continuation bundles, weights-only policy loading |
| Evaluation and freezing | `evaluation.py`, `freeze.py`, `lineage.py`, `robustness.py` | original-reward evaluation and aggregates; immutable final-test checkpoints and attempts; warm restarts and test exposure; robustness conditions |
| Inspection | `recording.py`, `rescoring.py`, `play.py` | video + per-step telemetry; counterfactual re-scoring; human flights |
| Studies | `experiments.py`, `compare.py`, `rl_stats.py`, `stats.py`, `results.py`, `report.py`, `tuning.py`, `preferences/` | experiment groups; comparisons and statistics across seeds; published tables and figures; Optuna tuning; learned rewards |
| Reproducibility | `reproduce.py`, `divergence.py`, `overhead.py`, `sysinfo.py`, `demo.py` | smoke pipeline and artifact re-evaluation (integrity, within- and cross-platform reproduction, conclusion stability; statuses and exit codes); per-step traces locating where two platforms part; overhead benchmark; versions and source revision; static demo export |
| Application | `cli.py`, `jobs.py`, `db.py`, `procs.py`, `parallel.py`, `server/`, `doctor.py` | command line; job supervisor and worker processes; SQLite metadata; local HTTP API; installation checks |
| Frontend | `frontend/src/` | React/TypeScript mission-control UI (same API as the CLI) |
| Maintainer tools | `tools/` | source archive, API reference, SPDX headers, third-party notices, paper figures (with a print-size check), CI reproduction summary, reproducibility experiments |

## The reward wrapper lifecycle

`LunarLabRewardWrapper` sits directly above Gymnasium's `TimeLimit`; during training SB3's `Monitor` sits above it
(so `Monitor` sees the training reward), during evaluation nothing does.

1. `reset(seed)` resets the environment and a fresh `EpisodeAccumulator` (no state carries over).
2. `step(a)` steps the environment, calls `compute_terms(s, a, s', terminated, truncated, config, gamma)` — the same
   pure functions the re-scorer uses — and computes `training = original_weight × original + Σ terms`.
3. The accumulator adds the original, training and per-term rewards (undiscounted and discounted), action counts,
   hover-detector and leg-contact statistics.
4. On the last step it classifies the outcome (`outcomes.classify_outcome`, reading lander internals through
   `env.probe`) and puts the summary in `info["lunarlab_episode"]`.
5. It returns the training reward (`apply=True`) or the original reward (`apply=False`); observations, actions and
   the termination flags are never changed.

## The training-job lifecycle

1. The CLI (`train`, `suite`, `resume`) or the API creates a run (`runs.create_run`: validated `RunConfig`, hashes,
   environment and system snapshot) and, for the web UI, submits a job to the SQLite queue.
2. The supervisor (`jobs.JobSupervisor`) starts an owned worker process `python -m lunarlab worker --job-id <id>`
   in its own process group; the worker calls `training.train`.
3. `train` takes the run's worker lock, refuses frozen runs and invalid protocols, records a new segment (worker
   seeds, source revision, PID), builds the environments and the SB3 model, restores a resume checkpoint (DQN:
   with its continuation bundle) and calls `learn()` with LunarLab's callback.
4. The callback writes every training episode to `episodes.csv`, PPO/DQN diagnostics to `metrics.jsonl`, a
   throttled `status.json`, periodic checkpoints and validation results; it polls the stop-request file.
5. On completion it saves `final.zip` and validates; on a stop request it stops at a safe boundary and saves a
   resumable `stop_*.zip`; on failure it records the error. The segment's end state and transitions are recorded.
6. The supervisor reconciles state after crashes (a worker that disappeared becomes "interrupted").

## Checkpoint formats

- **SB3 zip** (`ckpt_<n>.zip`, `final.zip`, `stop_<n>.zip`, `best_validation-<n>.zip`): SB3's own format. LunarLab
  loads policies weights-only (`policies.load_policy_weights`, no unpickling).
- **Manifest** (`checkpoints/manifest.json`): one entry per file with kind, transitions, updates, segment, SHA-256,
  size, configuration hash, role and resumability; `best_validation` points to the selected checkpoint.
- **DQN continuation bundle** (`<ckpt>.replay.npz` + `<ckpt>.state.json`): the replay buffer and the counters SB3
  keeps outside its zip; strictly validated, digest-checked (`continuation.py`).
- **Frozen artifact** (`checkpoints/frozen/<sha256>.zip`): the read-only copy evaluated by every final test.

## The evaluation lifecycle

`evaluation.evaluate_run(run_id, split)`: validates the protocol, picks the split's seeds, loads the checkpoint
weights-only, evaluates with `apply=False` (one episode per seed), aggregates (rates with Wilson intervals,
bootstrap interval of the mean return, hover and outcome statistics), checks the instantiated environment, and
saves `evaluations/<split>-<checkpoint>-<time>.json` with the protocol hash, checkpoint digest and code revision. A
final test additionally runs under the worker lock, freezes the checkpoint on first use, records the attempt and the
test exposure.

## Persistence

| Where | What |
|---|---|
| `runs/<run_id>/` | `config.yaml`, `metadata.json` (hashes, segments, `frozen_for_test`, `test_attempts`, lineage), `status.json`, `events.jsonl`, `episodes.csv`, `metrics.jsonl`, `evaluations/`, `checkpoints/`, `trajectories/`, `videos/` |
| `data/lunarlab.sqlite` | tables `reward_configs` (saved reward revisions), `jobs` (queue and job states), `settings` |
| `data/experiments/`, `data/jobs/`, `data/demos/`, `data/flights/`, `data/preferences/`, `data/reward_models/`, `data/tuning/` | experiments, job logs, demonstrations, human flights, preference datasets, reward models, Optuna studies |
| `data/test_exposure.jsonl` | every completed final test (exploratory vs confirmatory) |

All JSON is written atomically (temporary file, then replace); metadata read-modify-writes hold a short
cross-process lock. `LUNARLAB_HOME` relocates everything.

## HTTP API and security assumptions

The API serves the web UI only. It binds to 127.0.0.1, has no authentication (one local user), and requires the
header `X-LunarLab: 1` on every state-changing request so that other web pages cannot trigger actions. Request
bodies are validated strictly; run and file names are validated before use as paths. The endpoint list is
[api/http.md](api/http.md) and the schema [api/openapi.json](api/openapi.json).

## Extending

- A reward term, a diagnostic or another environment: [jmlr/EXTENDING_LUNARLAB.md](jmlr/EXTENDING_LUNARLAB.md).
- A CLI command: add a `cmd_*` function and its parser in `cli.py`; document it in a fenced block (the
  documentation test parses every documented command); regenerate `docs/api/cli.md`.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest -q                       # everything (about 5 minutes on a laptop)
.venv\Scripts\python.exe -m pytest -q -m "not slow"         # without real training and video encoding
.venv\Scripts\python.exe -m pytest --cov                    # with statement and branch coverage
```

Markers: `integration` (real LunarLander, fast), `slow` (real PPO/DQN updates or video). Windows-only tests (file
locks, PowerShell scripts) skip elsewhere. Every test runs in its own temporary `LUNARLAB_HOME`
(`tests/conftest.py`), so no test can touch real experiment data.

The browser flows (`frontend/e2e/`, `npx playwright test`) start two backends and shut them down through
`/api/shutdown` when they finish (`e2e/teardown.ts`), so the backends exit normally. To include them in a
coverage measurement, run the Python suite with `--cov` first (it leaves `.coverage`), then, from `frontend/`:

```powershell
$env:COVERAGE_PROCESS_START = (Resolve-Path ..\pyproject.toml); $env:COVERAGE_FILE = (Join-Path (Resolve-Path ..) '.coverage.e2e')
npx playwright test
cd ..; .venv\Scripts\python.exe -m coverage combine --append; .venv\Scripts\python.exe -m coverage report
```

## Releasing

A release is a tag on `main` whose CI run passed, plus the source archive built from it. The exact commands
(maintainer only; nothing is tagged or published automatically) are in
[jmlr/SUBMISSION_CHECKLIST.md](jmlr/SUBMISSION_CHECKLIST.md). The version lives in `lunarlab/__init__.py`;
`CITATION.cff` and `frontend/package.json` must name the same version (`tests/test_project_metadata.py`).
