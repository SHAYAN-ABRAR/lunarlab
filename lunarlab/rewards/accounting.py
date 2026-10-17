# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Per-episode accounting of original and training rewards.

The accumulator is reset at every ``reset()`` so no state can leak from one
episode into the next. Discounted sums use the convention G = sum_t gamma^t r_t
with t = 0 for the first transition after reset.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from lunarlab.env import ACTION_KEYS
from lunarlab.hover import HoverThresholds, hover_state
from lunarlab.rewards.config import TERM_KEYS


@dataclass
class EpisodeAccumulator:
    gamma: float
    detector: HoverThresholds
    length: int = 0
    original_return: float = 0.0
    training_return: float = 0.0
    discounted_original: float = 0.0
    discounted_training: float = 0.0
    term_returns: dict[str, float] = field(default_factory=dict)
    term_discounted: dict[str, float] = field(default_factory=dict)
    action_counts: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    hover_steps: int = 0
    longest_hover_streak: int = 0
    bonus_eligible_steps: int = 0
    leg_contact_steps: int = 0
    both_legs_contact_steps: int = 0
    _streak: int = 0
    _discount: float = 1.0

    def reset(self) -> None:
        """Start a new episode: every sum and counter back to zero."""
        self.length = 0
        self.original_return = 0.0
        self.training_return = 0.0
        self.discounted_original = 0.0
        self.discounted_training = 0.0
        self.term_returns = {k: 0.0 for k in TERM_KEYS}
        self.term_discounted = {k: 0.0 for k in TERM_KEYS}
        self.action_counts = [0, 0, 0, 0]
        self.hover_steps = 0
        self.longest_hover_streak = 0
        self.bonus_eligible_steps = 0
        self.leg_contact_steps = 0
        self.both_legs_contact_steps = 0
        self._streak = 0
        self._discount = 1.0

    def add(
        self, *, original: float, terms: dict[str, float], training: float, action: int, next_obs: np.ndarray
    ) -> bool:
        """Record one transition. Returns whether ``next_obs`` is a hover state (detector)."""
        d = self._discount
        self.length += 1
        self.original_return += original
        self.training_return += training
        self.discounted_original += d * original
        self.discounted_training += d * training
        for k, v in terms.items():
            self.term_returns[k] = self.term_returns.get(k, 0.0) + v
            self.term_discounted[k] = self.term_discounted.get(k, 0.0) + d * v
        if terms.get("hover_bonus", 0.0) > 0.0:
            self.bonus_eligible_steps += 1
        self.action_counts[int(action)] += 1
        left, right = next_obs[6] > 0.5, next_obs[7] > 0.5
        self.leg_contact_steps += int(left or right)
        self.both_legs_contact_steps += int(left and right)
        hovering = hover_state(next_obs, self.detector)
        if hovering:
            self.hover_steps += 1
            self._streak += 1
            self.longest_hover_streak = max(self.longest_hover_streak, self._streak)
        else:
            self._streak = 0
        self._discount *= self.gamma
        return hovering

    def summary(self) -> dict:
        """Returns (original, training and per term; undiscounted and discounted), action counts, hover
        and leg-contact statistics of the episode so far.
        """
        n = max(self.length, 1)
        return {
            "length": self.length,
            "original_return": self.original_return,
            "training_return": self.training_return,
            "discounted_original_return": self.discounted_original,
            "discounted_training_return": self.discounted_training,
            "term_returns": dict(self.term_returns),
            "term_discounted_returns": dict(self.term_discounted),
            "actions": {k: c for k, c in zip(ACTION_KEYS, self.action_counts, strict=True)},
            "hover_steps": self.hover_steps,
            "hover_fraction": self.hover_steps / n,
            "longest_hover_streak": self.longest_hover_streak,
            "bonus_eligible_steps": self.bonus_eligible_steps,
            "leg_contact_steps": self.leg_contact_steps,
            "both_legs_contact_steps": self.both_legs_contact_steps,
        }
