# Tutorial: a reward-design audit from the command line

This tutorial uses the command-line interface and the Python API (the web interface does the same things
through the same code). Commands are shown for Windows PowerShell; on Linux replace `.venv\Scripts\python.exe`
with `.venv/bin/python`. Every `python -m lunarlab` command below is executed, in this order, in a fresh
LunarLab home by `tests/test_tutorial.py` (the setup script is the installation step CI runs). The budgets are
deliberately tiny, so the *numbers* you see are pipeline checks, not trained agents.

To keep your own data separate while you follow along, point LunarLab at a scratch folder first:

```powershell
$env:LUNARLAB_HOME = "$env:TEMP\lunarlab-tutorial"     # Linux: export LUNARLAB_HOME=/tmp/lunarlab-tutorial
```

## 1. Install and verify

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
.venv\Scripts\python.exe -m lunarlab --version
.venv\Scripts\python.exe -m lunarlab doctor
.venv\Scripts\python.exe -m lunarlab reproduce-smoke
```

`--version` prints the version and the exact source revision; `doctor` checks Box2D, the environment, rendering,
video encoding, SQLite and PyTorch; `reproduce-smoke` runs the whole pipeline (train, checkpoint, reload, validate,
freeze, test, export) at a tiny budget in a temporary home and verifies every provenance link.

## 2. A first baseline run

```powershell
.venv\Scripts\python.exe -m lunarlab train --preset baseline --profile smoke --seed 0
.venv\Scripts\python.exe -m lunarlab runs
```

`train` prints the run ID (for example `20261017-…-baseline-s0-smoke-1a2b`). The run folder
`runs/<run_id>/` now holds `config.yaml` (everything that defines the run), `metadata.json` (configuration hash,
seeds, versions, source revision), `episodes.csv` (every training episode with its **original** and **training**
return and each reward term), `metrics.jsonl` and `checkpoints/` (with SHA-256 digests).

## 3. Evaluate: validation first, the final test once

```powershell
.venv\Scripts\python.exe -m lunarlab evaluate --run-id <run_id> --split validation
.venv\Scripts\python.exe -m lunarlab evaluate --run-id <run_id> --split test
.venv\Scripts\python.exe -m lunarlab test-status --run-id <run_id>
```

Evaluation always uses the unmodified environment reward. Checkpoints are selected on the validation seeds
(10,000–10,009); the first final test (seeds 20,000–20,099) freezes the selected checkpoint as a read-only copy,
and the run never trains again under its ID. `test-status` shows the frozen checkpoint and every test attempt.

## 4. A custom reward

```powershell
.venv\Scripts\python.exe -m lunarlab reward export --preset potential -o my-reward.yaml
# edit my-reward.yaml: for example change potential.alpha, or enable time_penalty
.venv\Scripts\python.exe -m lunarlab reward validate --file my-reward.yaml
.venv\Scripts\python.exe -m lunarlab train --reward-config my-reward.yaml --profile smoke --seed 0
```

A reward configuration is data, validated against a fixed schema (no code is evaluated). The training reward is
`original_weight × original reward + Σ enabled terms`, checked on every transition. `reward validate` reports
problems and warnings, for example that a bonus which does not telescope changes the optimal policy.

## 5. Diagnose reward exploitation

A smoke-sized run is too short to learn anything, so use a policy from the published study. The supplied
artifact `ppo-hover-bonus-s0` was trained with the deliberately flawed hover bonus:

```powershell
.venv\Scripts\python.exe -m lunarlab reproduce-artifact --artifact examples\artifacts\ppo-hover-bonus-s0 --episodes 10
.venv\Scripts\python.exe -m lunarlab reproduce-artifact --artifact examples\artifacts\ppo-baseline-s0 --episodes 10
```

Both re-run the recorded final-test episodes and compare them with the record. The first output line names the
result: `EXACT` (exit status 0) on Windows with the locked libraries, `NUMERICAL-DIFFERENCE` (exit status 3, not a
failure) on other platforms, where episodes differ numerically but no aggregate differs significantly; what each
status means is in [REPRODUCING.md](REPRODUCING.md). The recorded evaluation
(`examples/artifacts/ppo-hover-bonus-s0/evaluation.json`) shows the exploit: all 100 test episodes end at the time
limit (`env_outcome` = `timeout`), the lander hovers in 73 % of its steps on average (`hover_fraction`), and the
hover-bonus reward it was trained on would have paid 678.9 per episode (`training_return`) while the task's
original reward gives −21.2 (`original_return`). The baseline policy comes to rest in 97 of 100 episodes, with
identical training and original returns (265.9). This gap between the training and the original return, together
with a hover detector that does not depend on the reward preset, is how LunarLab exposes exploitation (the rule
is documented in `docs/EVALUATION.md`).

## 6. Record and inspect a real trajectory

```powershell
.venv\Scripts\python.exe -m lunarlab record --run-id <run_id> --episode-seed 20000
.venv\Scripts\python.exe -m lunarlab rescore --recording-id <recording_id> --presets baseline,hover-bonus,potential
```

`record` flies one episode with the run's selected checkpoint and saves video plus per-step telemetry (reward
terms, the policy's action probabilities). `rescore` re-scores that same flight under other reward designs,
term by term, without retraining. In the web interface (`scripts\start.ps1`) the recording opens in Flight Replay.

## 7. Compare runs across seeds

```powershell
.venv\Scripts\python.exe -m lunarlab suite --presets baseline,hover-bonus --seeds 0,1 --profile smoke --yes
.venv\Scripts\python.exe -m lunarlab compare --experiment-id <experiment_id>
.venv\Scripts\python.exe -m lunarlab report --experiment-id <experiment_id>
```

`suite` creates an experiment, trains every run, then runs each final test once. `compare` reports, per reward
design, the interquartile mean over training seeds with a bootstrap interval, the probability of improvement over
the baseline, outcome rates and the hover detector; `report` writes Markdown and HTML with figures to
`reports/<id>/`.

## 8. Export results and share an artifact

```powershell
.venv\Scripts\python.exe -m lunarlab results --experiment-ids <experiment_id> --out my-results
.venv\Scripts\python.exe -m lunarlab export-artifact --run-id <run_id> --out my-artifact
.venv\Scripts\python.exe -m lunarlab reproduce-artifact --artifact my-artifact
```

`results` regenerates tables, figures and a JSON summary from the stored evaluations; `export-artifact` copies a
tested checkpoint with its configuration and recorded final test (and their digests) so someone else can re-run
it with `reproduce-artifact`. A policy trained with a learned reward also carries its reward model and metadata
(`reward_model/`), which `reproduce-artifact` checks and uses in a temporary registry. A learned-reward package
without them is refused before any evaluation (exit 1); the local model registry is never used instead.

## 9. The same from Python

```python
from lunarlab.config import TrainingConfig
from lunarlab.evaluation import evaluate_run
from lunarlab.rewards.config import preset
from lunarlab.runs import create_run
from lunarlab.training import train

cfg = create_run(reward=preset("potential"), seed=0,
                 training=TrainingConfig(profile="custom", total_transitions=8192,
                                         checkpoint_every=4096, validation_every=4096))
train(cfg.run_id, quiet=True)
result = evaluate_run(cfg.run_id, "validation")
for ep in result["episodes"][:3]:
    print(ep["seed"], ep["original_return"], ep["training_return"], ep["term_returns"], ep["landing_category"])
```

The task-independent audit layer works on other Gymnasium environments too (see
[jmlr/EXTENDING_LUNARLAB.md](jmlr/EXTENDING_LUNARLAB.md)):

```powershell
.venv\Scripts\python.exe examples\cartpole_audit.py --transitions 4096
```

## 10. When something goes wrong

[TROUBLESHOOTING.md](TROUBLESHOOTING.md) covers Box2D and Python versions, Node, ports, antivirus file locks and
sleep. CLI refusals print `error: …` with the reason (for example, training a frozen run). The full command
reference is [api/cli.md](api/cli.md).
