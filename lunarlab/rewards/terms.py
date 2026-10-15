"""Pure reward-term functions. No environment access, no state.

Every function here is a deterministic function of observations, the action,
the episode-ending flags and the configuration. The wrapper used for training,
the evaluation code and the trajectory re-scorer all call these same functions,
so there is exactly one implementation of each reward term.
"""

from __future__ import annotations

import math

import numpy as np

from lunarlab.hover import hover_state
from lunarlab.rewards.config import PotentialWeights, RewardConfig


def potential(obs: np.ndarray, w: PotentialWeights) -> float:
    """Bounded state-only potential, Phi(s) <= 0 with Phi = 0 only at the ideal state.

    Phi(s) = -( wx*tanh|x| + wy*tanh|y| + wv*tanh(hypot(vx, vy)) + wa*tanh|angle| + ww*tanh|omega| )
    """
    x, y, vx, vy, angle, ang_vel = (float(v) for v in obs[:6])
    return -(
        w.x * math.tanh(abs(x))
        + w.y * math.tanh(abs(y))
        + w.speed * math.tanh(math.hypot(vx, vy))
        + w.angle * math.tanh(abs(angle))
        + w.angular_velocity * math.tanh(abs(ang_vel))
    )


def potential_shaping(
    obs: np.ndarray,
    next_obs: np.ndarray,
    *,
    terminated: bool,
    alpha: float,
    gamma: float,
    weights: PotentialWeights,
) -> float:
    """F(s, s') = alpha * (gamma * Phi(s') - Phi(s)).

    * True termination: s' is absorbing, so Phi(s') is taken as 0.
    * Time-limit truncation (``terminated=False``): the episode was cut, not
      finished. The real final observation is used for Phi(s'), matching SB3,
      which bootstraps the value of that same observation.
    """
    phi_next = 0.0 if terminated else potential(next_obs, weights)
    return alpha * (gamma * phi_next - potential(obs, weights))


def compute_terms(
    obs: np.ndarray,
    action: int,
    next_obs: np.ndarray,
    *,
    terminated: bool,
    truncated: bool,
    config: RewardConfig,
    gamma: float,
    learned_model=None,
) -> dict[str, float]:
    """Additional reward terms for one transition (s, a, s').

    Returns only the *enabled* terms. The original environment reward is not
    included here; the caller adds it:
    training = original_weight * original + sum(terms).
    ``learned_model`` is required when the learned-reward term is enabled.
    """
    del truncated  # truncation needs no special case: see potential_shaping
    terms: dict[str, float] = {}
    if config.time_penalty.enabled:
        terms["time_penalty"] = -float(config.time_penalty.cost_per_step)
    if config.hover_bonus.enabled:
        eligible = hover_state(next_obs, config.hover_bonus.eligibility)
        terms["hover_bonus"] = float(config.hover_bonus.bonus_per_step) if eligible else 0.0
    if config.potential.enabled:
        terms["potential_shaping"] = potential_shaping(
            obs,
            next_obs,
            terminated=terminated,
            alpha=config.potential.alpha,
            gamma=gamma,
            weights=config.potential.weights,
        )
    if config.learned.enabled:
        if learned_model is None:
            raise ValueError("learned reward term enabled but no reward model was supplied")
        terms["learned_reward"] = float(config.learned.scale) * learned_model(obs, int(action), next_obs)
    return terms


def training_reward(original: float, terms: dict[str, float], original_weight: float = 1.0) -> float:
    """The invariant: training_reward = original_weight * original_reward + sum(additional terms)."""
    return float(original_weight) * float(original) + float(sum(terms.values()))
