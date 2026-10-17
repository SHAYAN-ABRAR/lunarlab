# `lunarlab.overhead`

Source: [`lunarlab/overhead.py`](../../lunarlab/overhead.py)

Overhead benchmark: what LunarLab's instrumentation costs compared with plain Stable-Baselines3.

Three configurations train the same PPO model on the same environment for the same number of
environment transitions:

* **A ``sb3``** -- plain SB3: ``PPO("MlpPolicy")`` on ``DummyVecEnv([Monitor(gym.make("LunarLander-v3"))] * n)``.
* **B ``accounting``** -- A plus LunarLab's reward wrapper (baseline preset, so the training reward equals the
  original reward): per-transition reward accounting, the episode accumulator and outcome classification.
* **C ``lunarlab``** -- LunarLab's full training pipeline (:func:`lunarlab.training.train`): B plus the run
  directory, episode CSV, metrics, status file, stop polling, periodic checkpoints and validation.

Equivalent in all three: PPO hyperparameters and network (LunarLab's defaults, passed to SB3's ``PPO`` by
:func:`lunarlab.training.build_model`), ``n_envs``, ``DummyVecEnv``, CPU, torch threads, seed, transition budget,
no rendering. C additionally runs validation episodes and writes checkpoints; their wall time and
environment steps are measured separately and reported, never counted as instrumentation overhead.

Each repetition runs in a fresh Python process (so peak memory is per configuration), configurations are
interleaved in a rotating order, and every repetition is kept (none is discarded).

    python -m lunarlab overhead-benchmark --profile smoke        # ~1 minute
    python -m lunarlab overhead-benchmark --profile standard     # ~10 minutes
    python -m lunarlab overhead-benchmark --profile comprehensive --yes   # hours; never started automatically

### `main(argv: 'list[str] | None' = None) -> 'int'`

``python -m lunarlab.overhead``: one measurement in this process (``--worker``), or ``--render`` a folder.

### `render(out: 'Path') -> 'list[str]'`

Re-create ``table.md`` and the figures from a benchmark folder's saved ``raw.jsonl`` (no re-run).

### `run_benchmark(profile: 'str' = 'smoke', *, transitions: 'int | None' = None, repeats: 'int | None' = None, out: 'Path | None' = None, torch_threads: 'int' = 1, seed: 'int' = 0, echo=<built-in function print>) -> 'dict[str, Any]'`

Run every configuration ``repeats`` times in fresh processes; write raw rows, summary, table and figure.

## Constants

- `CONFIGS` = `('sb3', 'accounting', 'lunarlab')`
- `LABELS` = `{'sb3': 'A · plain SB3 (Monitor only)', 'accounting': 'B · + LunarLab reward accounting', 'lunarlab': 'C · full LunarLab…`
- `PROFILES` = `{'smoke': {'transitions': 8192, 'repeats': 2}, 'standard': {'transitions': 102400, 'repeats': 3}, 'comprehensive': {'tra…`
