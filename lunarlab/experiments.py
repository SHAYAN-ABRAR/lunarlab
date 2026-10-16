"""Experiments: named groups of runs meant to be compared (e.g. presets x seeds).

Stored as ``data/experiments/<experiment_id>.json``. An experiment is rewards x variants x seeds.
A *variant* fixes the algorithm, its discount factor and the training physics; by default there is
one variant (the chosen algorithm with its reference settings and default physics), which is how
every earlier experiment was built. All runs share the budget, checkpoint/validation cadence and
evaluation protocol by construction. With several algorithms, the budget is rounded up to a
multiple of every algorithm's rollout, so they train on exactly the same number of transitions.
"""

from __future__ import annotations

import math
from typing import Any

from lunarlab.config import (
    DQNConfig,
    EvalProtocol,
    PhysicsRandomization,
    PPOConfig,
    actual_budget,
    training_for_profile,
)
from lunarlab.rewards.config import RewardConfig, preset
from lunarlab.runs import create_run
from lunarlab.storage import atomic_write_json, data_dir, new_id, read_json, safe_child, utc_now

LARGE_SUITE_RUNS = 6
PHYSICS_VARIANTS = {"fixed": [False], "randomized": [True], "both": [False, True]}


def experiments_dir():
    p = data_dir() / "experiments"
    p.mkdir(parents=True, exist_ok=True)
    return p


def build_variants(
    *,
    algos: list[str] | None = None,
    physics: str = "fixed",
    physics_config: PhysicsRandomization | None = None,
    gammas: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Every combination of algorithm x discount factor x training physics."""
    algos = algos or ["ppo"]
    if physics not in PHYSICS_VARIANTS:
        raise ValueError(f"physics must be one of {', '.join(PHYSICS_VARIANTS)}")
    randomized = (physics_config or PhysicsRandomization()).model_copy(update={"enabled": True})
    PhysicsRandomization.model_validate(randomized.model_dump())  # re-check the ranges
    out = []
    for algo in algos:
        if algo not in ("ppo", "dqn"):
            raise ValueError(f"unknown algorithm {algo!r}")
        for gamma in gammas or [None]:
            for rand in PHYSICS_VARIANTS[physics]:
                parts = [algo.upper()]
                if gamma is not None:
                    parts.append(f"gamma={gamma:g}")
                if physics != "fixed":
                    parts.append("randomized physics" if rand else "fixed physics")
                out.append(
                    {
                        "name": " · ".join(parts),
                        "algo": algo,
                        "gamma": gamma,
                        "physics": randomized if rand else PhysicsRandomization(),
                    }
                )
    return out


def _rollout(variant: dict[str, Any], n_envs: int | None) -> int:
    if variant["algo"] == "dqn":
        return DQNConfig().rollout_size
    return PPOConfig(**({"n_envs": n_envs} if n_envs else {})).rollout_size


def matched_overrides(
    profile: str, variants: list[dict[str, Any]], n_envs: int | None, overrides: dict | None
) -> dict:
    """With several algorithms, round the budget up so every one completes whole rollouts at the
    same transition count (matched budgets)."""
    overrides = dict(overrides or {})
    if len({v["algo"] for v in variants}) > 1:
        step = math.lcm(*{_rollout(v, n_envs) for v in variants})
        total = training_for_profile(profile, **overrides).total_transitions
        overrides["total_transitions"] = -(-total // step) * step
    return overrides


def plan_suite(
    presets: list[str],
    seeds: list[int],
    profile: str,
    *,
    n_envs: int | None = None,
    throughput_tps: float | None = None,
    algo: str = "ppo",
    training_overrides: dict | None = None,
    variants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    variants = variants or build_variants(algos=[algo])
    overrides = matched_overrides(profile, variants, n_envs, training_overrides)
    training = training_for_profile(profile, **overrides)
    budgets = {v["name"]: actual_budget(training.total_transitions, _rollout(v, n_envs)) for v in variants}
    n_runs = len(presets) * len(seeds) * len(variants)
    total = sum(budgets.values()) * len(presets) * len(seeds)
    per_run = max(budgets.values())
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
    if any(v["algo"] == "dqn" for v in variants) and throughput_tps:
        warnings.append("The time estimate uses PPO throughput; DQN trains far fewer transitions per second.")
    return {
        "n_runs": n_runs,
        "transitions_per_run": per_run,
        "total_transitions": total,
        "estimated_hours": est,
        "warnings": warnings,
        "variants": [{"name": v["name"], "transitions_per_run": budgets[v["name"]]} for v in variants],
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
    variants: list[dict[str, Any]] | None = None,
    ppo_overrides: dict | None = None,
    dqn_overrides: dict | None = None,
    protocol: EvalProtocol | None = None,
) -> dict[str, Any]:
    """``ppo_overrides`` / ``dqn_overrides`` replace the reference settings for every run (e.g. the best
    settings of a tuning study); a variant's discount factor still takes precedence. ``protocol`` sets
    another evaluation protocol for every run, e.g. a holdout with test seeds never used before."""
    reward_list = list(rewards or []) + [preset(p) for p in (presets or [])]
    if not reward_list:
        raise ValueError("an experiment needs at least one reward configuration")
    if not seeds:
        raise ValueError("an experiment needs at least one training seed")
    variants = variants or build_variants(algos=[algo])
    overrides = matched_overrides(profile, variants, n_envs, training_overrides)
    exp_id = new_id(name or "experiment", prefix="exp")
    protocol = protocol or EvalProtocol()
    protocol.require_valid()
    from lunarlab.lineage import first_test_exposure

    exposure = first_test_exposure(protocol)
    run_ids = []
    for r in reward_list:
        for v in variants:
            gamma = {"gamma": v["gamma"]} if v.get("gamma") is not None else {}
            base_ppo = {**(ppo_overrides or {}), **({"n_envs": n_envs} if n_envs else {})}
            ppo = PPOConfig(**{**base_ppo, **(gamma if v["algo"] == "ppo" else {})})
            dqn = DQNConfig(**{**(dqn_overrides or {}), **gamma}) if v["algo"] == "dqn" else None
            for s in seeds:
                variant = f" · {v['name']}" if len(variants) > 1 else ""
                cfg = create_run(
                    reward=r,
                    training=training_for_profile(profile, **overrides),
                    seed=s,
                    ppo=ppo,
                    protocol=protocol,
                    experiment_id=exp_id,
                    label=f"{name} · {r.name}{variant} · seed {s}",
                    algo=v["algo"],
                    dqn=dqn,
                    physics=v["physics"],
                )
                run_ids.append(cfg.run_id)
    first = variants[0]
    exp = {
        "experiment_id": exp_id,
        "name": name,
        "description": description,
        "created_at": utc_now(),
        "profile": profile,
        "seeds": seeds,
        "eval_protocol_hash": protocol.protocol_hash(),
        "test_seeds": {
            "first": min(protocol.test_seeds),
            "last": max(protocol.test_seeds),
            "count": len(protocol.test_seeds),
        },
        # Informational: had these test seeds already been used for a final test when this was created?
        "test_seeds_previously_exposed": exposure is not None,
        "rewards": [{"name": r.name, "preset": r.preset, "hash": r.content_hash()} for r in reward_list],
        "algo": first["algo"] if len({v["algo"] for v in variants}) == 1 else "mixed",
        "ppo": PPOConfig(**{**(ppo_overrides or {}), **({"n_envs": n_envs} if n_envs else {})}).model_dump(
            mode="json"
        ),
        **({"dqn": DQNConfig(**dqn_overrides).model_dump(mode="json")} if dqn_overrides else {}),
        "variants": [
            {
                "name": v["name"],
                "algo": v["algo"],
                "gamma": v.get("gamma"),
                "physics": v["physics"].describe(),
            }
            for v in variants
        ],
        "transitions_per_run": training_for_profile(profile, **overrides).total_transitions,
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
