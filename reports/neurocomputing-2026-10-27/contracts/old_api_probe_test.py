# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""The new contracts, asserted through the public API that already existed at 932cf1c.

Run with pytest against both the unmodified and the fixed source: a failing test on the unmodified source
reproduces a defect, and the same test passing on the fixed source shows the fix. ValueError is caught
because the new error classes subclass it.
"""

from __future__ import annotations

import math

import gymnasium as gym
import numpy as np
import pytest

from lunarlab.audit import RewardAccountingWrapper, RewardTerm, TaskAdapter, audit_policy, get_adapter, terms_hash
from lunarlab.audit import seed_split_problems

COUNT = {"envs": 0}


def counting():
    base = get_adapter("cartpole")

    def factory(**kw):
        COUNT["envs"] += 1
        return gym.make("CartPole-v1", **kw)

    return TaskAdapter(**{**base.__dict__, "factory": factory})


@pytest.mark.parametrize(
    "seeds",
    [[True, False], [1.5, 2.7], [3.0, 4.0], ["7", "8"], [5, -1], [], [1, 1.5], ["9", 9]],
    ids=["bool", "fractional", "integral-float", "string", "negative-after-valid", "empty", "collapse", "str-int"],
)
def test_invalid_seeds_refused_before_an_environment_exists(seeds):
    COUNT["envs"] = 0
    with pytest.raises(ValueError):
        audit_policy(counting(), lambda o: 0, seeds, gamma=0.99)
    assert COUNT["envs"] == 0


@pytest.mark.parametrize(
    "validation, test",
    [([], [3]), ([1], []), ([-1, 2], [3]), ([[1]], [2])],
    ids=["empty-validation", "empty-test", "negative", "unhashable"],
)
def test_split_problems_reported(validation, test):
    assert seed_split_problems(validation, test) != []


@pytest.mark.parametrize("value", [math.nan, math.inf], ids=["nan", "inf"])
def test_non_finite_term_refused(value):
    term = RewardTerm("t", lambda tr: value, {"type": "custom"})
    with pytest.raises(ValueError):
        audit_policy(get_adapter("cartpole"), lambda o: 0, [100], gamma=0.99, terms={"t": term})


def test_non_finite_weight_refused():
    with pytest.raises(ValueError):
        audit_policy(get_adapter("cartpole"), lambda o: 0, [100], gamma=0.99, original_weight=math.nan)


def test_non_finite_description_refused():
    with pytest.raises(ValueError):
        terms_hash({"t": RewardTerm("t", lambda tr: 0.0, {"type": "custom", "scale": math.nan})}, 1.0)


def test_valid_inputs_still_work():
    report = audit_policy(get_adapter("cartpole"), lambda o: int(o[2] > 0), [np.int64(100), 101], gamma=0.99)
    assert report["seeds"] == [100, 101] and report["aggregate"]["n_episodes"] == 2
    w = RewardAccountingWrapper(gym.make("CartPole-v1"), gamma=0.99)
    w.reset(seed=0)
    assert w.step(0)[1] == 1.0
