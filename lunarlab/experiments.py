"""Experiments: named groups of runs meant to be compared (e.g. presets x seeds).

Stored as ``data/experiments/<experiment_id>.json``. All runs of an experiment
share PPO settings, budget and evaluation protocol by construction.
"""

from __future__ import annotations

from typing import Any

from lunarlab.config import EvalProtocol, PPOConfig, actual_budget, training_for_profile
from lunarlab.rewards.config import RewardConfig, preset
from lunarlab.runs import create_run
from lunarlab.storage import atomic_write_json, data_dir, new_id, read_json, safe_child, utc_now

LARGE_SUITE_RUNS = 6


def experiments_dir():
    p = data_dir() / "experiments"
    p.mkdir(parents=True, exist_ok=True)
    return p


def plan_suite(
    presets: list[str],
    seeds: list[int],
    profile: str,
    *,
    n_envs: int | None = None,
    throughput_tps: float | None = None,
    algo: str = "ppo",
    training_overrides: dict | None = None,
) -> dict[str, Any]:
    ppo = PPOConfig(**({"n_envs": n_envs} if n_envs else {}))
    training = training_for_profile(profile, **(training_overrides or {}))
    rollout = 4 if algo == "dqn" else ppo.rollout_size  # DQN: train_freq 4 x 1 env
    per_run = actual_budget(training.total_transitions, rollout)
    n_runs = len(presets) * len(seeds)
    total = per_run * n_runs
    est = (total / throughput_tps / 3600.0) if throughput_tps else None
    warnings = []
    if n_runs > LARGE_SUITE_RUNS:
        warnings.append(f"This creates {n_runs} training runs ({total:,} transitions in total).")
    if est is not None and est > 2:
        warnings.append(
            f"Estimated time at {throughput_tps:,.0f} transitions/s: about {est:.1f} hours of training, "
            "one run at a time. The laptop must stay awake."
        )
    if len(seeds) < 3:
        warnings.append("Fewer than three training seeds: results will be descriptive only.")
    return {
        "n_runs": n_runs,
        "transitions_per_run": per_run,
        "total_transitions": total,
        "estimated_hours": est,
        "warnings": warnings,
    }


def create_experiment(
    *,
    name: str,
    presets: list[str] | None = None,
    rewards: list[RewardConfig] | None = None,
    seeds: list[int],
    profile: str,
    description: str = "",
    n_envs: int | None = None,
    algo: str = "ppo",
    training_overrides: dict | None = None,
) -> dict[str, Any]:
    reward_list = list(rewards or []) + [preset(p) for p in (presets or [])]
    if not reward_list:
        raise ValueError("an experiment needs at least one reward configuration")
    if not seeds:
        raise ValueError("an experiment needs at least one training seed")
    exp_id = new_id(name or "experiment", prefix="exp")
    ppo = PPOConfig(**({"n_envs": n_envs} if n_envs else {}))
    protocol = EvalProtocol()
    run_ids = []
    for r in reward_list:
        for s in seeds:
            cfg = create_run(
                reward=r,
                training=training_for_profile(profile, **(training_overrides or {})),
                seed=s,
                ppo=ppo,
                protocol=protocol,
                experiment_id=exp_id,
                label=f"{name} · {r.name} · seed {s}",
                algo=algo,
            )
            run_ids.append(cfg.run_id)
    exp = {
        "experiment_id": exp_id,
        "name": name,
        "description": description,
        "created_at": utc_now(),
        "profile": profile,
        "seeds": seeds,
        "rewards": [{"name": r.name, "preset": r.preset, "hash": r.content_hash()} for r in reward_list],
        "algo": algo,
        "ppo": ppo.model_dump(mode="json"),
        "protocol_hash": protocol.protocol_hash(),
        "run_ids": run_ids,
    }
    atomic_write_json(experiments_dir() / f"{exp_id}.json", exp)
    return exp


def load_experiment(experiment_id: str) -> dict[str, Any]:
    p = safe_child(experiments_dir(), f"{experiment_id}.json")
    exp = read_json(p)
    if not exp:
        raise KeyError(f"unknown experiment: {experiment_id}")
    return exp


def list_experiments() -> list[dict[str, Any]]:
    out = []
    for p in sorted(experiments_dir().glob("*.json"), reverse=True):
        e = read_json(p)
        if e:
            out.append(e)
    return out
