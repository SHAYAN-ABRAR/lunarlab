# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Learned rewards from pairwise preferences: RLHF in miniature.

1. ``data``   — collect short trajectory segments from many policies and label pairs
                with a simulated human (an oracle that prefers the segment with the higher
                original return, with Bradley–Terry noise) or with real human choices.
2. ``train``  — fit a reward model r(s, a, s') so that the preferred segment of each pair
                has the larger summed reward (Bradley–Terry / logistic loss).
3. A reward configuration with ``original_weight = 0`` and ``learned.enabled`` trains PPO on
   the learned reward alone. Evaluation still uses the original environment reward, so any
   gap between "what the model rewards" and "what the task needs" shows up as reward hacking.
"""
