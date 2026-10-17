# `lunarlab.benchmark`

Source: [`lunarlab/benchmark.py`](../../lunarlab/benchmark.py)

Throughput benchmark: measure before increasing worker counts.

Two measurements per configuration:

* ``env``: raw environment transitions/s with random actions (no learning);
* ``ppo``: PPO collect + update transitions/s with the default PPO settings
  for two rollouts (what training will actually see).

Results are saved to ``data/benchmark.json`` and used for time estimates.

### `run_benchmark(n_envs_list=(1, 2, 4, 8), vec_kinds=('dummy', 'subproc'), env_seconds: 'float' = 3.0, ppo: 'bool' = True, torch_threads: 'int' = 1, echo=<built-in function print>) -> 'dict'`
