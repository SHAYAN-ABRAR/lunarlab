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

from lunarlab.audit.contracts import AuditInputError, require_finite

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
    """A named, pure reward term. ``describe`` (JSON-serialisable) identifies it in provenance records.

    ``term_id`` and ``version`` name the term's implementation for provenance records, and ``components``
    lists any further callables its result depends on (a predicate or a potential), so their source files
    can be recorded too (:func:`lunarlab.audit.provenance.reward_provenance`). None of the three enters
    :func:`terms_hash`. Every output must be a finite real number: NaN or infinity raises
    :class:`~lunarlab.audit.contracts.NonFiniteValueError` naming the term.
    """

    name: str
    fn: Callable[[Transition], float]
    describe: Mapping[str, Any]
    term_id: str | None = None
    version: str | None = None
    components: tuple[Callable, ...] = ()

    def __call__(self, t: Transition) -> float:
        return require_finite(self.fn(t), f"reward term {self.name!r} output")


def per_step(name: str, value: float) -> RewardTerm:
    """A constant added on every transition (e.g. a time penalty with ``value < 0``)."""
    require_finite(value, f"per_step term {name!r} value")
    return RewardTerm(
        name,
        lambda _t: value,
        {"type": "per_step", "value": value},
        term_id="lunarlab.audit.per_step",
        version="1",
    )


def state_bonus(
    name: str, predicate: Callable[[np.ndarray], bool], bonus: float, *, predicate_id: str
) -> RewardTerm:
    """``bonus`` when the *resulting* state satisfies ``predicate``. A bonus that does not telescope can be
    exploited: LunarLab's flawed hover bonus is this shape."""
    require_finite(bonus, f"state_bonus term {name!r} bonus")
    return RewardTerm(
        name,
        lambda t: bonus if predicate(t.next_obs) else 0.0,
        {"type": "state_bonus", "bonus": bonus, "predicate": predicate_id},
        term_id="lunarlab.audit.state_bonus",
        version="1",
        components=(predicate,),
    )


def potential_shaping(
    name: str, potential: Callable[[np.ndarray], float], *, alpha: float, gamma: float, potential_id: str
) -> RewardTerm:
    """F(s, s') = alpha * (gamma * Phi(s') - Phi(s)) (Ng, Harada and Russell, 1999).

    A true termination makes s' absorbing, so Phi(s') = 0; this includes a step on which the environment
    reports both ``terminated`` and ``truncated``. A time-limit truncation alone is not a terminal state: the
    real next observation is used, as in LunarLab's own implementation. With these conventions the
    discounted sum of F over an episode of T transitions telescopes to
    alpha * (gamma^T * Phi(s_T) - Phi(s_0)), with Phi(s_T) = 0 when the episode terminated. The identity
    concerns that sum; it does not imply that a policy learned with a finite budget is unchanged.
    """
    require_finite(alpha, f"potential_shaping term {name!r} alpha")
    if not 0.0 < require_finite(gamma, f"potential_shaping term {name!r} gamma") <= 1.0:
        raise ValueError(f"gamma must be in (0, 1], got {gamma!r}")

    def fn(t: Transition) -> float:
        phi_next = 0.0 if t.terminated else float(potential(t.next_obs))
        return alpha * (gamma * phi_next - float(potential(t.obs)))

    return RewardTerm(
        name,
        fn,
        {"type": "potential_shaping", "alpha": alpha, "gamma": gamma, "potential": potential_id},
        term_id="lunarlab.audit.potential_shaping",
        version="1",
        components=(potential,),
    )


def terms_hash(terms: Mapping[str, RewardTerm], original_weight: float) -> str:
    """Schema-0 hash of a declared reward definition: the first 16 hex characters of SHA-256.

    It covers the term descriptions and the original reward's weight, not the code of the term callables:
    two terms with equal descriptions and different functions have equal hashes. Its value for a valid
    definition is unchanged from earlier records. Descriptions containing NaN, infinity or values that are
    not JSON are refused, naming the term. New records also carry the full-digest, versioned record of
    :func:`lunarlab.audit.provenance.reward_provenance`.
    """
    from lunarlab.audit.provenance import definition_document

    doc = definition_document(terms, original_weight)  # validates every description
    return hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()[:16]


def rescore_transitions(
    transitions: list[Transition],
    terms: Mapping[str, RewardTerm],
    *,
    gamma: float,
    original_weight: float = 1.0,
) -> dict[str, Any]:
    """Apply a reward definition to a fixed sequence of transitions (a recorded trajectory).

    Returns every step's original reward, term values and training reward, and the episode sums. This
    answers what the definition pays for those transitions; it says nothing about the policy that training
    under that definition would produce.
    """
    if not 0.0 < require_finite(gamma, "gamma") <= 1.0:
        raise ValueError(f"gamma must be in (0, 1], got {gamma!r}")
    weight = require_finite(original_weight, "original_weight")
    audit = EpisodeAudit(float(gamma))
    steps = []
    for i, t in enumerate(transitions):
        original = require_finite(t.original_reward, f"original reward of transition {i}")
        values = {k: term(t) for k, term in terms.items()}
        training = require_finite(
            weight * original + math.fsum(values.values()), f"training reward of transition {i}"
        )
        audit.add(original, values, training)
        steps.append({"original": original, "terms": values, "training": training})
    return {"steps": steps, "summary": audit.summary()}


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

    The original reward, every term output and the training reward must be finite. A NaN or infinite value
    raises :class:`~lunarlab.audit.contracts.NonFiniteValueError` naming its source and ends the episode:
    the wrapper refuses further steps until the next reset, so a partly accounted episode is never
    completed or summarised.
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
        if not 0.0 < require_finite(gamma, "gamma") <= 1.0:
            raise ValueError(f"gamma must be in (0, 1], got {gamma!r}")
        self.terms = dict(terms or {})
        for key, term in self.terms.items():
            if not isinstance(term, RewardTerm):
                raise AuditInputError(f"reward term {key!r} is a {type(term).__name__}, not a RewardTerm")
            if key != term.name:
                raise ValueError(f"term registered as {key!r} is named {term.name!r}")
        self.gamma = float(gamma)
        self.original_weight = require_finite(original_weight, "original_weight")
        self.apply = bool(apply)
        self.adapter = adapter
        from lunarlab.audit.provenance import definition_sha256

        self.reward_hash = terms_hash(self.terms, self.original_weight)
        self.reward_definition_sha256 = definition_sha256(self.terms, self.original_weight)
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
        try:
            original = require_finite(original, f"original reward at step {self._audit.length}")
            t = Transition(
                self._prev, action, original, np.array(obs, copy=True), bool(terminated), bool(truncated)
            )
            values = {k: term(t) for k, term in self.terms.items()}
            training = require_finite(
                self.original_weight * original + math.fsum(values.values()),
                f"training reward at step {self._audit.length}",
            )
        except Exception:
            self._prev = None  # the episode cannot be completed: refuse further steps until a reset
            raise
        self._audit.add(original, values, training)
        self._observations.append(t.next_obs)
        info = dict(info)
        if terminated or truncated:
            summary = self._audit.summary()
            summary.update(
                terminated=bool(terminated),
                truncated=bool(truncated),
                reward_hash=self.reward_hash,
                reward_definition_sha256=self.reward_definition_sha256,
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
