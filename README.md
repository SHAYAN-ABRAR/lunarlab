# LunarLab — Reward Shaping Mission Control

A local-first laboratory for **honest reward-design experiments** on Gymnasium's `LunarLander-v3`
(discrete actions) with Stable-Baselines3 PPO, plus a scientific mission-control web interface.

The story it lets you run, and actually measure:

**watch a random agent fail → train a baseline → introduce a bad reward → investigate reward hacking →
apply a better reward design → compare the actual results.**

Nothing in this project assumes how an experiment will turn out. Every number shown in the UI, the CLI or
a report comes from stored training logs and from evaluations with the **unmodified environment reward**
on fixed episode seeds.

> Status: the software is complete and verified (see [PROGRESS.md](PROGRESS.md)). Only bounded SMOKE runs
> (≈8k transitions each) have been executed. The full multi-seed experiment has **not** been run, so there
> are no claims yet about landing performance or reward hacking.

---

## What it demonstrates

- Reward terms as **pure, tested functions** behind a single Gymnasium wrapper; `training_reward =
  original_reward + Σ additional terms` is checked on every transition.
- Four reward presets: the original baseline, a time-penalty ablation, an **intentionally flawed hover
  bonus**, and **potential-based shaping** `α(γΦ(s′) − Φ(s))` with the PPO discount, an absorbing terminal
  potential, and correct time-limit truncation handling. The discounted telescoping identity is tested.
- An **evaluation protocol** that doesn't flatter the agent: original reward only, disjoint validation and
  test seed sets, deterministic policy, bootstrap and Wilson intervals, separate score / environment-success /
  strict pad-landing / crash / out-of-bounds / time-limit rates, a preset-independent hover detector, and a
  documented reward-exploitation rule.
- A **local job supervisor**: owned worker subprocesses, a queue, cooperative stop at safe boundaries,
  checkpoint resume with lineage, crash reconciliation, and verified process ownership before any kill.
- **Flight Replay** with two synchronized views of every recorded flight: an immersive **3-D reconstruction**
  (WebGL; the recorded position, tilt, engine firings and leg contacts on the episode's real terrain, with
  chase / wide / orbit cameras) and the **actual simulator footage**. Both share frame-accurate telemetry
  (observations, actions, per-step reward decomposition) and side-by-side flights on a shared seed.
- A **Reward Stress Test** that re-scores a recorded trajectory under other reward designs (clearly labelled
  as re-scoring, not prediction).

## Requirements

- Windows 10/11 with PowerShell (Linux works as a secondary path, see below).
- **Python 3.12 or 3.13.** Box2D 2.3.10 and pygame 2.6.1 publish Windows wheels only up to 3.13. Python 3.14
  is not supported yet. [uv](https://docs.astral.sh/uv/) is used automatically if installed.
- **Node.js ≥ 22.12** (or ^20.19) to build the UI. Node is not needed to *run* an already built UI.
- No GPU needed: PPO with a 64×64 MLP runs on the CPU, which is the default.

## Install and launch (Windows PowerShell)

```powershell
cd "D:\Rocket"                                                     # your project folder; spaces are fine
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1          # venv, locked deps, UI build, self-check
powershell -ExecutionPolicy Bypass -File scripts\start.ps1          # serves http://127.0.0.1:8765 and opens it
powershell -ExecutionPolicy Bypass -File scripts\stop.ps1           # graceful stop (from another terminal)
```

`-ExecutionPolicy Bypass` applies to that single process; your machine's policy is not changed.
`start.ps1 -Background -NoBrowser` runs the server without a console window.

The app is at **http://127.0.0.1:8765** and binds to loopback only.

### Linux (secondary path)

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.lock
uv pip install --python .venv/bin/python --no-deps -e .
(cd frontend && npm ci && npm run build)
.venv/bin/python -m lunarlab doctor
.venv/bin/python -m lunarlab serve            # http://127.0.0.1:8765
```

On Linux, PyPI's torch wheel includes CUDA libraries (several GB). For a CPU-only install, first run
`uv pip install --python .venv/bin/python torch --index-url https://download.pytorch.org/whl/cpu`.

## First run (about five minutes)

1. **Mission Overview → Watch Random Agent.** Records one real episode of uniformly random actions on the
   shared demonstration seed 20000 and opens it in Flight Replay.
2. **Train Baseline → Smoke → Start.** About 15 s. Watch transitions, throughput, validation and PPO
   diagnostics update in the Training Console. A SMOKE run is a pipeline test, not a trained agent.
3. On the run page: **Evaluate (validation)**, then **Record flight…** on seed 20000, and replay it next to
   the random flight (Flight Replay → Side-by-side).
4. **Reward Studio:** open *Flawed hover bonus*, read the discounted-return calculator, change a threshold
   and save a new revision.
5. When ready for real experiments: **Training Console → Multi-seed experiment suite** (4 presets × 3 seeds,
   STANDARD ≈ 1M transitions each). Run the throughput benchmark first for a time estimate.

## CLI

Everything in the UI is also available from the command line (same core code):

```powershell
.venv\Scripts\python.exe -m lunarlab doctor
.venv\Scripts\python.exe -m lunarlab random-demo --episode-seed 20000
.venv\Scripts\python.exe -m lunarlab heuristic-demo --episode-seed 20000
.venv\Scripts\python.exe -m lunarlab train --preset baseline --profile smoke
.venv\Scripts\python.exe -m lunarlab train --preset hover-bonus --profile standard --seed 42
.venv\Scripts\python.exe -m lunarlab train --preset potential --profile standard --seed 42
.venv\Scripts\python.exe -m lunarlab stop --run-id <id>             # or Ctrl+C once in the training terminal
.venv\Scripts\python.exe -m lunarlab resume --run-id <id>
.venv\Scripts\python.exe -m lunarlab evaluate --run-id <id> --split validation
.venv\Scripts\python.exe -m lunarlab evaluate --run-id <id> --split test      # freezes the selected checkpoint
.venv\Scripts\python.exe -m lunarlab record --run-id <id> --episode-seed 20000
.venv\Scripts\python.exe -m lunarlab compare --experiment-id <id>
.venv\Scripts\python.exe -m lunarlab report --experiment-id <id>
.venv\Scripts\python.exe -m lunarlab runs
.venv\Scripts\python.exe -m lunarlab benchmark
.venv\Scripts\python.exe -m lunarlab rescore --recording-id <id>
.venv\Scripts\python.exe -m lunarlab suite --presets baseline,time-penalty,hover-bonus,potential --seeds 0,1,2 --profile standard
.venv\Scripts\python.exe -m lunarlab sweep --bonus 0.25,0.5,1,2 --seeds 0 --profile standard     # development sweep (validation only)
.venv\Scripts\python.exe -m lunarlab reward export --preset hover-bonus -o my-reward.yaml
.venv\Scripts\python.exe -m lunarlab train --reward-config my-reward.yaml --profile smoke
.venv\Scripts\python.exe -m lunarlab processes                     # list this project's server/worker processes
```

Profiles: `smoke` (8,192 transitions, technical test), `standard` (1,000,000 requested → 1,003,520 actual
transitions, because PPO completes whole rollouts of 4,096), `extended` (3,000,000, explicit launch only).

### Reproducing the full experiment

```powershell
.venv\Scripts\python.exe -m lunarlab benchmark                                   # ~1 min, for time estimates
.venv\Scripts\python.exe -m lunarlab suite --presets baseline,time-penalty,hover-bonus,potential --seeds 0,1,2 --profile standard --yes
.venv\Scripts\python.exe -m lunarlab compare --experiment-id <printed id>
.venv\Scripts\python.exe -m lunarlab report  --experiment-id <printed id>
```

The suite trains 12 runs one at a time, then evaluates each run's validation-selected checkpoint once on the
100 final-test seeds. Measured on the development laptop (i7-13620H), PPO with the default 4 in-process
environments runs at about 5,100 transitions/s, so a STANDARD run takes roughly 5–10 minutes including
validation passes and the whole suite roughly 1–2 hours. The laptop must stay awake.

## Where things are stored

```
data/lunarlab.sqlite        jobs, reward-config revisions, settings (metadata only)
data/demos/                 random / heuristic demonstration flights (mp4 + telemetry json)
data/experiments/           experiment definitions (groups of runs)
data/jobs/<job>/            worker log, status and result of each job
runs/<run_id>/              config.yaml, metadata.json, status.json, events.jsonl, episodes.csv,
                            metrics.jsonl, evaluations/, checkpoints/, trajectories/, videos/
reports/<id>/               report.md, report.html, figures, portfolio_summary.md
```

Nothing is deleted automatically. Checkpoints for a 64×64 MLP are about 150 KB each.

## Documentation

- [docs/REWARDS.md](docs/REWARDS.md): the original reward, the four presets, formulas, assumptions, why
  shaped scores are not comparable, discounted-return reasoning, termination vs truncation.
- [docs/EVALUATION.md](docs/EVALUATION.md): the protocol, outcome definitions (including an environment
  contact-flag quirk), statistics, the reward-exploitation rule, and final-test freezing.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): codebase map, wrapper order, job supervisor, storage,
  security model, shutdown and resume behaviour, and design decisions.
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md): Box2D/SWIG, Python versions, Node, ports,
  antivirus file locks, sleep.
- [docs/PORTFOLIO.md](docs/PORTFOLIO.md): how to produce an evidence-gated portfolio summary.
- [notebooks/walkthrough.py](notebooks/walkthrough.py): a VS Code `# %%` walkthrough using the project code.
- [PROGRESS.md](PROGRESS.md): what is done, test evidence, known issues, next steps.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest                       # 115 tests: unit, integration, real PPO, subprocesses
.venv\Scripts\python.exe -m ruff check lunarlab tests
cd frontend; npm run typecheck; npm run lint; npm run build
npx playwright test                                      # 7 browser flows on real backend (uses installed Edge)
```

## Credits

- Inspired by the reward-shaping article by **Hari (@harixganesh)**.
- [Gymnasium](https://gymnasium.farama.org/) (Farama Foundation): `LunarLander-v3`, Box2D, rendering.
- [Stable-Baselines3](https://stable-baselines3.readthedocs.io/) (DLR-RM): PPO, and
  [RL Baselines3 Zoo](https://github.com/DLR-RM/rl-baselines3-zoo) for reference hyperparameters.
- Schulman et al., *Proximal Policy Optimization Algorithms*, 2017.
- Ng, Harada & Russell, *Policy invariance under reward transformations: Theory and application to reward
  shaping*, ICML 1999.
- PyTorch, NumPy, pandas, Matplotlib, imageio/ffmpeg, FastAPI, Pydantic, React, Vite, Tailwind CSS,
  Recharts, Lucide, IBM Plex.

This is a 2-D simulation benchmark. Nothing here is evidence of real-world rocket-control capability.
