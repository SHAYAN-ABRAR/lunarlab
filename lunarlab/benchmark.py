"""Throughput benchmark: measure before increasing worker counts.

Two measurements per configuration:

* ``env``: raw environment transitions/s with random actions (no learning);
* ``ppo``: PPO collect + update transitions/s with the default PPO settings
  for two rollouts (what training will actually see).

Results are saved to ``data/benchmark.json`` and used for time estimates.
"""

from __future__ import annotations

import time

import numpy as np

from lunarlab.storage import atomic_write_json, data_dir, utc_now


def _env_throughput(vec_kind: str, n_envs: int, seconds: float) -> float:
    from lunarlab.config import PPOConfig, RunConfig, TrainingConfig
    from lunarlab.rewards.config import preset
    from lunarlab.training import build_vec_env

    cfg = RunConfig(
        run_id="benchmark",
        created_at=utc_now(),
        reward=preset("baseline"),
        ppo=PPOConfig(n_envs=n_envs),
        training=TrainingConfig(vec_env=vec_kind),
    )
    venv = build_vec_env(cfg, kind=vec_kind)
    try:
        venv.seed(0)
        venv.reset()
        rng = np.random.default_rng(0)
        n = 0
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < seconds:
            venv.step(rng.integers(0, 4, size=n_envs))
            n += n_envs
        return n / (time.perf_counter() - t0)
    finally:
        venv.close()


def _ppo_throughput(vec_kind: str, n_envs: int, torch_threads: int) -> float:
    import torch

    from lunarlab.config import PPOConfig, RunConfig, TrainingConfig
    from lunarlab.rewards.config import preset
    from lunarlab.training import build_model, build_vec_env

    torch.set_num_threads(torch_threads)
    ppo = PPOConfig(n_envs=n_envs)
    cfg = RunConfig(
        run_id="benchmark",
        created_at=utc_now(),
        reward=preset("baseline"),
        ppo=ppo,
        training=TrainingConfig(vec_env=vec_kind),
    )
    venv = build_vec_env(cfg, kind=vec_kind)
    try:
        model = build_model(cfg, venv, "cpu")
        total = 2 * ppo.rollout_size
        t0 = time.perf_counter()
        model.learn(total_timesteps=total, log_interval=None)
        return total / (time.perf_counter() - t0)
    finally:
        venv.close()


def run_benchmark(
    n_envs_list=(1, 2, 4, 8),
    vec_kinds=("dummy", "subproc"),
    env_seconds: float = 3.0,
    ppo: bool = True,
    torch_threads: int = 1,
    echo=print,
) -> dict:
    rows = []
    for kind in vec_kinds:
        for n in n_envs_list:
            if kind == "subproc" and n == 1:
                continue
            row = {"vec_env": kind, "n_envs": n, "env_tps": round(_env_throughput(kind, n, env_seconds), 1)}
            if ppo:
                row["ppo_tps"] = round(_ppo_throughput(kind, n, torch_threads), 1)
            rows.append(row)
            echo(
                f"  {kind:<8} n_envs={n:<2}  env {row['env_tps']:>9,.0f} transitions/s"
                + (f"   ppo {row['ppo_tps']:>8,.0f} transitions/s" if ppo else "")
            )
    key = "ppo_tps" if ppo else "env_tps"
    best = max(rows, key=lambda r: r[key]) if rows else None
    default = next((r for r in rows if r["vec_env"] == "dummy" and r["n_envs"] == 4), None)
    result = {
        "created_at": utc_now(),
        "torch_threads": torch_threads,
        "rows": rows,
        "best": best,
        "default_config": default,
        "note": "PPO throughput depends on n_envs because rollout size (n_envs x n_steps) changes. "
        "Primary comparisons keep n_envs=4 regardless; this benchmark is for planning only.",
    }
    atomic_write_json(data_dir() / "benchmark.json", result)
    return result
