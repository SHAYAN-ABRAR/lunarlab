# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Task-independent reward accounting.

The invariant LunarLab is built on, for any Gymnasium environment::

    training_reward = original_weight * original_reward + sum(term(transition) for each reward term)

:class:`RewardAccountingWrapper` applies it to every transition and keeps the original reward, every
term and the training reward apart -- undiscounted and discounted -- so a policy can be trained on the
shaped reward while it is always judged by the original one. Reward terms are pure functions of one
:class:`Transition`; this module provides the three term shapes LunarLab's presets use (a per-step
constant, a bonus when the resulting state satisfies a predicate, and potential-based shaping).
Task knowledge (what an episode outcome means) comes from a :class:`~lunarlab.audit.adapters.TaskAdapter`.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import gymnasium as gym
import numpy as np

if TYPE_CHECKING:
    from lunarlab.audit.adapters import TaskAdapter


@dataclass(frozen=True)
class Transition:
    """One environment step (s, a, r_original, s'), with the episode-ending flags."""

    obs: np.ndarray
    action: Any
    original_reward: float
    next_obs: np.ndarray
    terminated: bool
    truncated: bool


@dataclass(frozen=True)
class RewardTerm:
    """A named, pure reward term. ``describe`` (JSON-serialisable) identifies it in provenance records."""

    name: str
    fn: Callable[[Transition], float]
    describe: Mapping[str, Any]

    def __call__(self, t: Transition) -> float:
        return float(self.fn(t))


def per_step(name: str, value: float) -> RewardTerm:
    """A constant added on every transition (e.g. a time penalty with ``value < 0``)."""
    return RewardTerm(name, lambda _t: value, {"type": "per_step", "value": value})


def state_bonus(
    name: str, predicate: Callable[[np.ndarray], bool], bonus: float, *, predicate_id: str
) -> RewardTerm:
    """``bonus`` when the *resulting* state satisfies ``predicate``. A bonus that does not telescope can be
    exploited: LunarLab's flawed hover bonus is this shape."""
    return RewardTerm(
        name,
        lambda t: bonus if predicate(t.next_obs) else 0.0,
        {"type": "state_bonus", "bonus": bonus, "predicate": predicate_id},
    )


def potential_shaping(
    name: str, potential: Callable[[np.ndarray], float], *, alpha: float, gamma: float, potential_id: str
) -> RewardTerm:
    """F(s, s') = alpha * (gamma * Phi(s') - Phi(s)) (Ng, Harada and Russell, 1999).

    A true termination makes s' absorbing, so Phi(s') = 0. A time-limit truncation is not a terminal
    state: the real next observation is used, as in LunarLab's own implementation. With these
    conventions the discounted sum of F over an episode telescopes to alpha * (gamma^T * Phi(s_T) - Phi(s_0)),
    with Phi(s_T) = 0 when the episode terminated.
    """
    if not 0.0 < gamma <= 1.0:
        raise ValueError("gamma must be in (0, 1]")

    def fn(t: Transition) -> float:
        phi_next = 0.0 if t.terminated else float(potential(t.next_obs))
        return alpha * (gamma * phi_next - float(potential(t.obs)))

    return RewardTerm(
        name, fn, {"type": "potential_shaping", "alpha": alpha, "gamma": gamma, "potential": potential_id}
    )


def terms_hash(terms: Mapping[str, RewardTerm], original_weight: float) -> str:
    """Content hash of a reward definition (term descriptions and the original reward's weight)."""
    doc = {
        "original_weight": original_weight,
        "terms": {k: dict(v.describe) for k, v in sorted(terms.items())},
    }
    return hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class EpisodeAudit:
    """Per-episode sums. ``G = sum_t gamma^t r_t`` with t = 0 for the first transition after reset."""

    gamma: float
    length: int = 0
    original_return: float = 0.0
    training_return: float = 0.0
    discounted_original_return: float = 0.0
    discounted_training_return: float = 0.0
    term_returns: dict[str, float] = field(default_factory=dict)
    term_discounted_returns: dict[str, float] = field(default_factory=dict)
    _discount: float = 1.0

    def add(self, original: float, terms: Mapping[str, float], training: float) -> None:
        """Add one transition's original reward, term values and training reward."""
        d = self._discount
        self.length += 1
        self.original_return += original
        self.training_return += training
        self.discounted_original_return += d * original
        self.discounted_training_return += d * training
        for k, v in terms.items():
            self.term_returns[k] = self.term_returns.get(k, 0.0) + v
            self.term_discounted_returns[k] = self.term_discounted_returns.get(k, 0.0) + d * v
        self._discount *= self.gamma

    def summary(self) -> dict[str, Any]:
        """Length and returns (undiscounted and discounted; original, training and per term)."""
        return {
            "length": self.length,
            "original_return": self.original_return,
            "training_return": self.training_return,
            "discounted_original_return": self.discounted_original_return,
            "discounted_training_return": self.discounted_training_return,
            "term_returns": dict(self.term_returns),
            "term_discounted_returns": dict(self.term_discounted_returns),
        }


class RewardAccountingWrapper(gym.Wrapper):
    """Applies ``training = w * original + sum(terms)`` and records every component, for any environment.

    ``apply=True`` (training) returns the training reward; ``apply=False`` (evaluation) returns the
    original reward unchanged and only records what the terms would have added. Observations, actions,
    ``terminated`` and ``truncated`` are never changed. On the last step of an episode,
    ``info["audit_episode"]`` holds the episode summary, including the adapter's outcome classification.
    """

    def __init__(
        self,
        env: gym.Env,
        terms: Mapping[str, RewardTerm] | None = None,
        *,
        gamma: float,
        original_weight: float = 1.0,
        apply: bool = True,
        adapter: TaskAdapter | None = None,
    ) -> None:
        super().__init__(env)
        if not 0.0 < gamma <= 1.0:
            raise ValueError("gamma must be in (0, 1]")
        self.terms = dict(terms or {})
        for key, term in self.terms.items():
            if key != term.name:
                raise ValueError(f"term registered as {key!r} is named {term.name!r}")
        self.gamma = float(gamma)
        self.original_weight = float(original_weight)
        self.apply = bool(apply)
        self.adapter = adapter
        self.reward_hash = terms_hash(self.terms, self.original_weight)
        self._audit = EpisodeAudit(self.gamma)
        self._prev: np.ndarray | None = None
        self._observations: list[np.ndarray] = []
        self.last_episode: dict[str, Any] | None = None

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        """Reset and start a new episode audit."""
        obs, info = self.env.reset(seed=seed, options=options)
        self._audit = EpisodeAudit(self.gamma)
        self._prev = np.array(obs, copy=True)
        self._observations = [self._prev]
        return obs, info

    def step(self, action):
        """Step, compute every term for (s, a, s'), record all components, and return the training reward
        (``apply=True``) or the original reward (``apply=False``).
        """
        if self._prev is None:
            raise RuntimeError("step() called before reset() or after the episode ended")
        obs, original, terminated, truncated, info = self.env.step(action)
        original = float(original)
        t = Transition(
            self._prev, action, original, np.array(obs, copy=True), bool(terminated), bool(truncated)
        )
        values = {k: term(t) for k, term in self.terms.items()}
        training = self.original_weight * original + math.fsum(values.values())
        self._audit.add(original, values, training)
        self._observations.append(t.next_obs)
        info = dict(info)
        if terminated or truncated:
            summary = self._audit.summary()
            summary.update(
                terminated=bool(terminated), truncated=bool(truncated), reward_hash=self.reward_hash
            )
            if self.adapter is not None:
                from lunarlab.audit.adapters import EpisodeEnd

                outcome = self.adapter.classify(
                    EpisodeEnd(
                        env=self.env,
                        observations=np.asarray(self._observations),
                        terminated=bool(terminated),
                        truncated=bool(truncated),
                        info=info,
                    )
                )
                if outcome.get("outcome") not in self.adapter.outcome_categories:
                    raise ValueError(
                        f"adapter {self.adapter.name!r} returned outcome {outcome.get('outcome')!r}, "
                        f"not one of {self.adapter.outcome_categories}"
                    )
                summary.update(outcome)
                for name, diag in self.adapter.diagnostics.items():
                    summary[name] = diag(np.asarray(self._observations))
            info["audit_episode"] = summary
            self.last_episode = summary
            self._prev = None
        else:
            self._prev = t.next_obs
        return obs, (training if self.apply else original), terminated, truncated, info
