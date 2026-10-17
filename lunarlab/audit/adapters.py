# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Task adapters: what the task-independent audit layer needs to know about one environment.

A :class:`TaskAdapter` supplies the environment factory, observation and action labels, the task's own
episode-outcome definition, the reward terms that make sense for it, optional per-episode diagnostics and
evaluation metrics. Nothing task-specific lives in :mod:`lunarlab.audit.core`.

Two adapters ship with LunarLab:

* ``lunarlander`` -- built from LunarLab's existing functions (environment factory, strict pad-landing
  classification, hover detector, the presets' reward terms), so it behaves exactly like the main pipeline.
* ``cartpole`` -- Gymnasium's ``CartPole-v1`` with its own outcome definition (pole fell, cart left the
  track, or balanced until the time limit). It demonstrates the extension contract; it is not part of the
  published LunarLander study.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import gymnasium as gym
import numpy as np

from lunarlab.audit.core import RewardTerm, per_step, potential_shaping, state_bonus


@dataclass(frozen=True)
class EpisodeEnd:
    """What an adapter's outcome classifier sees at the end of an episode."""

    env: gym.Env  # the environment below the accounting wrapper (for read-only task internals)
    observations: np.ndarray  # (T + 1, obs_dim): s_0 ... s_T
    terminated: bool
    truncated: bool
    info: Mapping[str, Any]


@dataclass(frozen=True)
class TaskAdapter:
    """Everything task-specific. ``classify`` must return ``{"outcome": <one of outcome_categories>, ...}``."""

    name: str
    version: str
    env_id: str
    env_kwargs: Mapping[str, Any]
    observation_labels: tuple[str, ...]
    action_labels: tuple[str, ...]
    outcome_categories: tuple[str, ...]
    classify: Callable[[EpisodeEnd], dict[str, Any]]
    term_factories: Mapping[str, Callable[..., RewardTerm]] = field(default_factory=dict)
    diagnostics: Mapping[str, Callable[[np.ndarray], Any]] = field(default_factory=dict)
    metrics: Mapping[str, Callable[[list[dict]], float | None]] = field(default_factory=dict)
    factory: Callable[..., gym.Env] | None = None

    def make_env(self, **kwargs) -> gym.Env:
        """Create the task's environment (``factory``, or ``gym.make(env_id, **env_kwargs)``)."""
        if self.factory is not None:
            return self.factory(**kwargs)
        return gym.make(self.env_id, **{**self.env_kwargs, **kwargs})

    def term(self, name: str, **params) -> RewardTerm:
        """Build one of the task's named reward terms with the given parameters."""
        if name not in self.term_factories:
            raise KeyError(
                f"adapter {self.name!r} has no reward term {name!r}; available: {sorted(self.term_factories)}"
            )
        return self.term_factories[name](**params)


_REGISTRY: dict[str, Callable[[], TaskAdapter]] = {}


def register_adapter(name: str, build: Callable[[], TaskAdapter]) -> None:
    """Register an adapter factory under ``name`` (overwriting an existing registration is refused)."""
    if name in _REGISTRY:
        raise ValueError(f"an adapter named {name!r} is already registered")
    _REGISTRY[name] = build


def get_adapter(name: str) -> TaskAdapter:
    """Build the registered task adapter ``name``."""
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise KeyError(f"unknown task adapter {name!r}; registered: {sorted(_REGISTRY)}") from None


def adapter_names() -> list[str]:
    """Names of the registered task adapters."""
    return sorted(_REGISTRY)


def rate(outcome: str) -> Callable[[list[dict]], float | None]:
    """Metric factory: the fraction of episodes with this outcome."""
    return lambda eps: (sum(e.get("outcome") == outcome for e in eps) / len(eps)) if eps else None


# --------------------------------------------------------------------------- #
# LunarLander-v3: LunarLab's own definitions
# --------------------------------------------------------------------------- #


def lunar_lander_adapter() -> TaskAdapter:
    """LunarLander-v3 with LunarLab's own outcome classifier, hover detector and preset reward terms."""
    from lunarlab.env import ACTION_KEYS, ENV_ID, ENV_KWARGS, OBS_KEYS, make_env, probe
    from lunarlab.hover import DEFAULT_BONUS_ELIGIBILITY, DEFAULT_DETECTOR, hover_state
    from lunarlab.outcomes import LANDING_CATEGORIES, PadLandingCriteria, classify_outcome
    from lunarlab.rewards.config import PotentialWeights
    from lunarlab.rewards.terms import potential

    criteria = PadLandingCriteria()

    def classify(end: EpisodeEnd) -> dict[str, Any]:
        legs = end.observations[1:, 6:8] > 0.5  # leg-contact flags of every resulting state
        record = classify_outcome(
            end.terminated,
            end.truncated,
            end.observations[-1],
            probe(end.env),
            criteria,
            leg_contact_seen=bool(legs.any()),
        )
        d = record.to_dict()
        return {"outcome": d["landing_category"], **d}

    def hover_fraction(observations: np.ndarray) -> float:
        states = observations[1:]
        return float(np.mean([hover_state(o, DEFAULT_DETECTOR) for o in states])) if len(states) else 0.0

    return TaskAdapter(
        name="lunarlander",
        version="1",
        env_id=ENV_ID,
        env_kwargs=dict(ENV_KWARGS),
        observation_labels=tuple(OBS_KEYS),
        action_labels=tuple(ACTION_KEYS),
        outcome_categories=tuple(LANDING_CATEGORIES),
        classify=classify,
        term_factories={
            "time_penalty": lambda cost=0.01: per_step("time_penalty", -float(cost)),
            "hover_bonus": lambda bonus=1.0: state_bonus(
                "hover_bonus",
                lambda o: hover_state(o, DEFAULT_BONUS_ELIGIBILITY),
                float(bonus),
                predicate_id="lunarlab.hover.hover_state(DEFAULT_BONUS_ELIGIBILITY)",
            ),
            "potential_shaping": lambda gamma, alpha=10.0: potential_shaping(
                "potential_shaping",
                lambda o: potential(o, PotentialWeights()),
                alpha=float(alpha),
                gamma=float(gamma),
                potential_id="lunarlab.rewards.terms.potential(PotentialWeights())",
            ),
        },
        diagnostics={"hover_fraction": hover_fraction},
        metrics={
            "strict_pad_landing_rate": rate("strict_pad_landing"),
            "crash_rate": rate("crash"),
            "timeout_rate": rate("timeout"),
        },
        factory=lambda **kw: make_env(**kw),
    )


# --------------------------------------------------------------------------- #
# CartPole-v1: its own outcome definition, read from the environment's thresholds
# --------------------------------------------------------------------------- #

CARTPOLE_OUTCOMES = ("balanced_to_time_limit", "pole_fell", "cart_left_track", "unknown")


def cartpole_adapter() -> TaskAdapter:
    """CartPole-v1 with its own outcome definition: pole fell, cart left the track, or balanced to the time limit."""

    def classify(end: EpisodeEnd) -> dict[str, Any]:
        core = end.env.unwrapped
        x, _x_dot, theta, _theta_dot = (float(v) for v in end.observations[-1])
        if end.truncated and not end.terminated:
            outcome = "balanced_to_time_limit"
        elif end.terminated and abs(theta) > core.theta_threshold_radians:
            outcome = "pole_fell"
        elif end.terminated and abs(x) > core.x_threshold:
            outcome = "cart_left_track"
        else:
            outcome = "unknown"
        return {"outcome": outcome, "final_pole_angle_rad": theta, "final_cart_position": x}

    def upright_potential(o: np.ndarray) -> float:
        return -abs(float(o[2])) / (12 * 2 * np.pi / 360)  # 0 when upright, -1 at the failure angle

    return TaskAdapter(
        name="cartpole",
        version="1",
        env_id="CartPole-v1",
        env_kwargs={},
        observation_labels=("cart_position", "cart_velocity", "pole_angle", "pole_angular_velocity"),
        action_labels=("push_left", "push_right"),
        outcome_categories=CARTPOLE_OUTCOMES,
        classify=classify,
        term_factories={
            "upright_potential": lambda gamma, alpha=1.0: potential_shaping(
                "upright_potential",
                upright_potential,
                alpha=float(alpha),
                gamma=float(gamma),
                potential_id="-|pole_angle| / 12 degrees",
            ),
            "step_penalty": lambda cost=0.01: per_step("step_penalty", -float(cost)),
        },
        metrics={"time_limit_rate": rate("balanced_to_time_limit"), "pole_fell_rate": rate("pole_fell")},
    )


register_adapter("lunarlander", lunar_lander_adapter)
register_adapter("cartpole", cartpole_adapter)
