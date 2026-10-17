# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Reward configuration, pure term functions, accounting and the reward wrapper."""

from lunarlab.rewards.config import (
    PRESET_NAMES,
    TERM_KEYS,
    HoverBonusConfig,
    PotentialConfig,
    PotentialWeights,
    RewardConfig,
    TimePenaltyConfig,
    all_presets,
    preset,
)
from lunarlab.rewards.terms import compute_terms, potential, potential_shaping, training_reward

__all__ = [
    "PRESET_NAMES",
    "TERM_KEYS",
    "HoverBonusConfig",
    "PotentialConfig",
    "PotentialWeights",
    "RewardConfig",
    "TimePenaltyConfig",
    "all_presets",
    "compute_terms",
    "potential",
    "potential_shaping",
    "preset",
    "training_reward",
]
