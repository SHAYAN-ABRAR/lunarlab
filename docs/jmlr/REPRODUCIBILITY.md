# Reproducibility

How another researcher can verify what LunarLab does, which outputs reproduce exactly, and what is not
guaranteed. Every result below was measured on 2026-10-17 on the machine described in
[INITIAL_AUDIT.md](INITIAL_AUDIT.md) (Windows 11, i7-13620H, Python 3.12.13).

## Summary of verified results

| Check | Command | Result on this machine |
|---|---|---|
| End-to-end pipeline, PPO (train → checkpoints → reload → validation → frozen final test → export → repeat) | `reproduce-smoke --training-determinism` | 15/15 checks passed, 6.7 s (`reports/jmlr/artifacts/reproduce-smoke-ppo-windows.json`) |
| Same, DQN with the flawed hover bonus | `reproduce-smoke --algo dqn --preset hover-bonus` | 14/14 passed |
| Same, DQN (replay buffer, exploration schedule) | `reproduce-smoke --algo dqn --training-determinism` | 15/15 passed, 25 s (`…/reproduce-smoke-dqn-windows.json`) |
| Training determinism in one process | `--training-determinism` | identical final weights and identical training episodes (PPO and DQN) |
| Training determinism across processes | `reproduce-smoke` run twice | identical final-weights digest, frozen-weights digest and final-test episode digest (checkpoint *file* digests differ: zip entries carry save times) |
| Published final tests, re-evaluated from supplied artifacts | `reproduce-artifact` | 300 of 300 episodes bit-identical: PPO baseline 265.8558 (96 % pad landing), PPO hover bonus −21.2456 (0 %), DQN baseline 155.3644 (29 %) |

## What is recorded at each step

| Step | Recorded | Where | Verified by |
|---|---|---|---|
| Installation | exact dependency pins; package version and source revision | `requirements.lock`, `requirements-ci.lock`; `python -m lunarlab --version` / `version --json` | `tests/test_project_metadata.py` |
| Configuration | full run configuration; content hashes of the configuration, the reward and the evaluation protocol | `runs/<id>/config.yaml`, `metadata.json` (`config_hash`, `reward_hash`, `eval_protocol_hash`) | smoke check "configuration identity survives a reload"; historical hashes pinned in `tests/test_protocol.py` |
| Environment | environment id and keyword arguments, Gymnasium version, robustness overrides, effective physics read back from the instantiated environment | `metadata.json → environment`; every evaluation's `environment` | evaluations refuse an environment that differs from the protocol's declaration |
| Training | worker seeds (disjoint from evaluation seeds), transitions in environment interactions, discarded interactions at a stop, source revision per segment, versions and hardware | `metadata.json → segments`, `system` | smoke checks "training budget recorded in environment transitions", "worker seeds and source revision recorded" |
| Rewards | original reward, every term and the training reward, per transition (identity checked) and per episode | `info["lunarlab"]`, `episodes.csv` (rounded to 5 decimals), evaluation episodes (full precision) | smoke check "identity holds" (within the CSV rounding bound); `tests/test_rewards.py`, `tests/test_properties.py` |
| Checkpoints | name, kind, transitions, size, SHA-256, configuration hash; DQN continuation bundles | `checkpoints/manifest.json` | smoke check "every checkpoint matches its recorded size, SHA-256 and configuration hash" |
| Validation and selection | validation-seed results; the selected checkpoint and the statistic that selected it | `evaluations/validation-*.json`, manifest `best_validation` | smoke check "validation evaluation uses the original reward" |
| Frozen final test | immutable read-only copy of the selected checkpoint; its digest; every attempt | `checkpoints/frozen/<sha256>.zip`, `metadata.json → frozen_for_test`, `test_attempts` | smoke checks "final test evaluated the frozen copy …", "frozen checkpoint is read-only" |
| Evaluation | per-episode original return, would-be training return, terms, outcome (classifier version), seeds, protocol hash, checkpoint digest, code revision | `evaluations/test-*.json` | smoke check "a repeated final-test evaluation matches the saved one exactly" |
| Continuation vs warm restart | resume = same run (counters, optimizer, DQN replay buffer); warm restart = new run with lineage | `segments`, `lineage`, `config.warm_start` | `tests/test_dqn_continuation.py`, `tests/test_freeze.py` |
| Export | results with source digests; demo snapshots with full provenance (release or draft) | `docs/results/results.json`, `demo/api/demo.json` | `tests/test_provenance.py` |
| Replay | recorded steps with the policy's outputs, the checkpoint digest, the protocol hash | `trajectories/*.json` | `tests/test_video_rescoring.py` |

Missing evidence is never filled in: an evaluation made before a field existed shows it as absent (for example,
`evaluation_code` for evaluations older than the code-revision record), and legacy outcome-classifier results are
labelled as such, with derived values marked derived.

## Commands

### Windows (PowerShell) — executed on this machine

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1        # virtual environment from requirements.lock
.venv\Scripts\python.exe -m lunarlab --version
.venv\Scripts\python.exe -m lunarlab doctor
.venv\Scripts\python.exe -m lunarlab reproduce-smoke --training-determinism --report smoke.json
.venv\Scripts\python.exe -m lunarlab reproduce-smoke --algo dqn --training-determinism
.venv\Scripts\python.exe -m lunarlab reproduce-artifact --artifact examples\artifacts\ppo-baseline-s0 --report baseline.json
.venv\Scripts\python.exe -m lunarlab reproduce-artifact --artifact examples\artifacts\ppo-hover-bonus-s0
.venv\Scripts\python.exe -m lunarlab reproduce-artifact --artifact examples\artifacts\dqn-baseline-s0
.venv\Scripts\python.exe -m pytest -q
```

### Linux (bash)

The installation is the one GitHub Actions runs on `ubuntu-latest` (CPU-only PyTorch, no proprietary packages);
the installation and the test suite as of revision `28dd935` passed there. The new commands of this branch
(`--version`, `reproduce-smoke`, `reproduce-artifact`, `overhead-benchmark`) have **not yet been run on Linux**.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-ci.lock --torch-backend cpu
uv pip install --python .venv/bin/python --no-deps -e .
.venv/bin/python -m lunarlab --version
.venv/bin/python -m lunarlab doctor
.venv/bin/python -m lunarlab reproduce-smoke --training-determinism --report smoke.json
.venv/bin/python -m lunarlab reproduce-artifact --artifact examples/artifacts/ppo-baseline-s0 --report baseline.json
.venv/bin/python -m pytest -q
```

`reproduce-smoke` needs no web interface and no existing data: it creates and removes a temporary LunarLab home
(`--keep` keeps it for inspection) and exits with status 1 if any check fails.

## What reproduces exactly, and what is not guaranteed

- **Same machine, same software stack:** evaluation is bit-identical (300/300 published episodes re-evaluated
  two days later; repeated evaluations in every smoke run); training is bit-identical with LunarLab's defaults
  (CPU, one torch thread, `DummyVecEnv`), within a process and across processes.
- **Different CPU, operating system, PyTorch, NumPy or Box2D build:** not established. Stable-Baselines3 states
  that "completely reproducible results are not guaranteed across PyTorch releases or different platforms".
  Physics and floating-point library differences can change a trajectory after it diverges by one action.
  `reproduce-artifact` therefore reports the comparison episode by episode (count of identical episodes, largest
  return difference) and `--tolerance` makes an approximate comparison explicit, instead of assuming exactness.
- **Not verified for determinism:** more than one torch thread, `SubprocVecEnv`, CUDA, and randomized physics
  across machines.
- **Expected differences:** timestamps, durations, process IDs, checkpoint file digests (zip metadata), and the
  outcome-classifier version of results produced before version 2 (only the fields common to both versions are
  compared).

## Supplied artifacts

`examples/artifacts/` contains three published final tests, copied byte-for-byte from the experiment runs with
`python -m lunarlab export-artifact` (checkpoint, configuration, recorded evaluation, and `artifact.json` with
their SHA-256 digests and the documented metric):

| Folder | Source run | Algorithm, reward | Checkpoint SHA-256 | Documented final test (100 episodes) |
|---|---|---|---|---|
| `ppo-baseline-s0` | `20261015-223113-baseline-s0-standard-c5af` | PPO, original reward | `a3a89f43dd2d…` | mean original return 265.8558, pad landing 96 % |
| `ppo-hover-bonus-s0` | `20261015-223115-hover-bonus-s0-standard-3376` | PPO, flawed hover bonus | `0ee843850038…` | −21.2456, pad landing 0 % (reward exploitation) |
| `dqn-baseline-s0` | `20261015-224317-dqn-baseline-s0-custom-2fe1` | DQN, original reward | `8f1438011d97…` | 155.3644, pad landing 29 % |

`tests/test_reproduce.py` checks their digests, configuration hashes and documented metrics on every test run.
Reproductions on this machine: `reports/jmlr/artifacts/reproduce-*-windows.json`.

## Reporting a reproduction

Use the reproducibility-report issue form, or, without a GitHub account,
[REPRODUCTION_REPORT_TEMPLATE.md](REPRODUCTION_REPORT_TEMPLATE.md). Attach the JSON written by `--report`.
