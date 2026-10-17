# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Audit a policy on any registered task: original-reward evaluation with full reward accounting."""

from __future__ import annotations

import statistics
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import gymnasium as gym
import numpy as np

from lunarlab.audit.adapters import TaskAdapter
from lunarlab.audit.core import RewardAccountingWrapper, RewardTerm


def seed_split_problems(validation: Sequence[int], test: Sequence[int]) -> list[str]:
    """Problems that make a validation/test seed split unusable (empty list: valid).

    Seeds must be plain integers, each list free of duplicates, and the two lists disjoint, so the
    checkpoint selected on validation episodes is never selected on the episodes that test it.
    """
    out = []
    for label, seeds in (("validation", validation), ("test", test)):
        if any(isinstance(s, bool) or not isinstance(s, (int, np.integer)) for s in seeds):
            out.append(f"{label} seeds must be integers")
        if len(set(seeds)) != len(seeds):
            out.append(f"{label} seeds contain duplicates")
    overlap = set(validation) & set(test)
    if overlap:
        out.append(f"validation and test seeds overlap: {sorted(overlap)[:5]}")
    return out


def audit_policy(
    adapter: TaskAdapter,
    policy: Callable[[np.ndarray], Any],
    seeds: Sequence[int],
    *,
    gamma: float,
    terms: Mapping[str, RewardTerm] | None = None,
    original_weight: float = 1.0,
    env_kwargs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run ``policy`` (observation -> action) for one episode per seed and report every reward component.

    The environment is wrapped with ``apply=False``: the policy is scored on the original reward, and the
    training return each reward definition *would* have given is recorded beside it. Each episode's
    original return is cross-checked against the rewards the loop received.
    """
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds contain duplicates")
    env = RewardAccountingWrapper(
        adapter.make_env(**dict(env_kwargs or {})),
        terms,
        gamma=gamma,
        original_weight=original_weight,
        apply=False,
        adapter=adapter,
    )
    episodes = []
    try:
        for seed in seeds:
            obs, _ = env.reset(seed=int(seed))
            received = 0.0
            while True:
                obs, reward, terminated, truncated, info = env.step(policy(obs))
                received += float(reward)
                if terminated or truncated:
                    ep = dict(info["audit_episode"])
                    if abs(received - ep["original_return"]) > 1e-9:
                        raise RuntimeError("the evaluation loop received a modified reward")
                    ep["seed"] = int(seed)
                    episodes.append(ep)
                    break
    finally:
        env.close()
    orig = [e["original_return"] for e in episodes]
    train = [e["training_return"] for e in episodes]
    return {
        "adapter": {"name": adapter.name, "version": adapter.version},
        "environment": {
            "env_id": adapter.env_id,
            "env_kwargs": {**adapter.env_kwargs, **dict(env_kwargs or {})},
            "gymnasium": gym.__version__,
        },
        "reward": {
            "original_weight": original_weight,
            "terms": {k: dict(v.describe) for k, v in (terms or {}).items()},
            "hash": env.reward_hash,
        },
        "gamma": gamma,
        "seeds": [int(s) for s in seeds],
        "episodes": episodes,
        "aggregate": {
            "n_episodes": len(episodes),
            "mean_original_return": statistics.fmean(orig) if orig else None,
            "mean_training_return": statistics.fmean(train) if train else None,
            "outcomes": {c: sum(e["outcome"] == c for e in episodes) for c in adapter.outcome_categories},
            "metrics": {name: fn(episodes) for name, fn in adapter.metrics.items()},
        },
    }
