# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Runtime reproductions of the two validation defects found by the independent review.

    python reports/neurocomputing-review-repairs-2026-10-28/defects/reproduce_defects.py

**A. Cumulative overflow.** Every transition value is finite, but the episode totals exceed the
floating-point range (the largest finite double is about 1.798e308). The cases:

- the reviewer's two-step environment with reward 1e308 per step (plain accounting, gamma 0.99);
- two terms of 1e308 in one transition;
- re-scoring of the same transitions;
- the aggregate mean over two finite episode totals of 1.5e308. That mean is representable, but a plain sum
  of the totals is not.

**B. Malformed recorded episodes.** ``check_recorded_episodes`` is given records with null, boolean, text and
missing reward values.

Each case prints what happened: the result, or the exception type and message. Run it before and after a
fix and compare the outputs.
"""

from __future__ import annotations

import json

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from lunarlab.audit import RewardAccountingWrapper, RewardTerm, TaskAdapter, Transition, audit_policy
from lunarlab.audit.core import rescore_transitions
from lunarlab.audit.study import check_recorded_episodes


class Constant(gym.Env):
    """``length`` steps of reward ``reward``; terminates on the last step."""

    observation_space = spaces.Box(-1.0, 1.0, (1,), np.float64)
    action_space = spaces.Discrete(1)

    def __init__(self, reward: float, length: int = 2) -> None:
        self.reward, self.length, self.t = reward, length, 0

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.t = 0
        return np.zeros(1), {}

    def step(self, action):
        self.t += 1
        return np.zeros(1), self.reward, self.t >= self.length, False, {}


def outcome(fn):
    try:
        value = fn()
        return {"result": json.loads(json.dumps(value, default=repr).replace("Infinity", '"inf"'))}
    except Exception as exc:  # noqa: BLE001 - the point is to record whatever happens
        return {"exception": type(exc).__name__, "message": str(exc)[:300]}


def run_episode(env: RewardAccountingWrapper) -> dict:
    env.reset(seed=0)
    record = {"steps": []}
    for _ in range(2):
        try:
            _, reward, terminated, truncated, info = env.step(0)
        except Exception as exc:  # noqa: BLE001
            record["steps"].append({"exception": type(exc).__name__, "message": str(exc)[:300]})
            break
        record["steps"].append({"reward": repr(reward), "audit_episode": info.get("audit_episode")})
        if terminated or truncated:
            break
    try:
        env.step(0)
        record["step_after_end"] = "accepted"
    except Exception as exc:  # noqa: BLE001
        record["step_after_end"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    record["last_episode"] = env.last_episode
    return json.loads(json.dumps(record, default=repr).replace("Infinity", '"inf"'))


def main() -> None:
    out: dict = {}
    out["A1 two steps of 1e308, gamma 0.99"] = run_episode(
        RewardAccountingWrapper(Constant(1e308), gamma=0.99)
    )
    big = {
        name: RewardTerm(name, lambda t: 1e308, {"type": "custom", "id": name}) for name in ("big_a", "big_b")
    }
    out["A2 two terms of 1e308 in one transition"] = run_episode(
        RewardAccountingWrapper(Constant(0.0), big, gamma=0.99)
    )
    zero = np.zeros(1)
    transitions = [Transition(zero, 0, 1e308, zero, i == 1, False) for i in range(2)]
    out["A3 rescore_transitions of the same transitions"] = outcome(
        lambda: rescore_transitions(transitions, {}, gamma=0.99)["summary"]
    )
    adapter = TaskAdapter(
        name="constant",
        version="1",
        env_id="unused",
        env_kwargs={},
        observation_labels=("x",),
        action_labels=("noop",),
        outcome_categories=("ended",),
        classify=lambda end: {"outcome": "ended"},
        factory=lambda **kw: Constant(1.5e308, length=1),
    )
    out["A4 audit_policy aggregate of two episodes of 1.5e308"] = outcome(
        lambda: audit_policy(adapter, lambda o: 0, [1, 2], gamma=0.99)["aggregate"]
    )
    good = {
        "seed": 1,
        "original_return": 3.0,
        "training_return": 3.0,
        "discounted_original_return": 2.9,
        "discounted_training_return": 2.9,
        "term_returns": {},
        "outcome": "ended",
    }
    cases = {
        "B1 null original and training returns": {**good, "original_return": None, "training_return": None},
        "B2 boolean original return": {**good, "original_return": True, "training_return": 1.0},
        "B3 text training return": {**good, "training_return": "3.0"},
        "B4 missing training return": {k: v for k, v in good.items() if k != "training_return"},
        "B5 null discounted (optional) return": {**good, "discounted_training_return": None},
        "B6 valid record": good,
    }
    for label, episode in cases.items():
        out[label] = outcome(
            lambda e=episode: [
                (name, ok, detail)
                for name, ok, detail in check_recorded_episodes(
                    [e], expected_seeds=[1], term_names=[], original_weight=1.0, categories=("ended",)
                )
                if not ok
            ]
        )
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
