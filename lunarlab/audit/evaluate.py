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
from lunarlab.audit.contracts import SEED_CONTRACT, normalize_seeds, require_finite, split_problems
from lunarlab.audit.core import RewardAccountingWrapper, RewardTerm
from lunarlab.audit.provenance import definition_document, reward_provenance


def seed_split_problems(validation: Sequence[int], test: Sequence[int]) -> list[str]:
    """Problems that make a validation/test seed split unusable (empty list: valid).

    Each list must satisfy the seed contract (:data:`~lunarlab.audit.contracts.SEED_CONTRACT`: non-empty,
    nonnegative integers, no duplicates, nothing coerced), and the two lists must be disjoint, so the
    checkpoint selected on validation episodes is never selected on the episodes that test it.
    """
    return split_problems(validation, test)


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

    Error boundary: the seeds (seed contract), the discount, the original-reward weight and every term
    description are validated before the environment is created. During the episodes, a non-finite
    reward, an outcome outside the adapter's categories or a modified reward raises at once. The function
    either returns a report covering every requested seed or raises; it never returns a partial report.
    """
    seeds = normalize_seeds(seeds)
    if not 0.0 < require_finite(gamma, "gamma") <= 1.0:
        raise ValueError(f"gamma must be in (0, 1], got {gamma!r}")
    definition_document(dict(terms or {}), original_weight)  # validates the declared definition
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
            obs, _ = env.reset(seed=seed)
            received = 0.0
            while True:
                obs, reward, terminated, truncated, info = env.step(policy(obs))
                received += float(reward)
                if terminated or truncated:
                    ep = dict(info["audit_episode"])
                    if abs(received - ep["original_return"]) > 1e-9:
                        raise RuntimeError("the evaluation loop received a modified reward")
                    ep["seed"] = seed
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
            "definition_sha256": env.reward_definition_sha256,
            "provenance": reward_provenance(terms, original_weight, adapter=adapter),
        },
        "gamma": gamma,
        "seeds": seeds,
        "seed_contract": SEED_CONTRACT,
        "episodes": episodes,
        "aggregate": {
            "n_episodes": len(episodes),
            "mean_original_return": statistics.fmean(orig),
            "mean_training_return": statistics.fmean(train),
            "outcomes": {c: sum(e["outcome"] == c for e in episodes) for c in adapter.outcome_categories},
            "metrics": {name: fn(episodes) for name, fn in adapter.metrics.items()},
        },
    }
