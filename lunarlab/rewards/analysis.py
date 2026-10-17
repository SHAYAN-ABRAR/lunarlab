# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Back-of-envelope discounted-return reasoning for reward designs.

These are calculators with explicit, editable assumptions. They illustrate why
a design *might* create an incentive; they do not predict what PPO will learn.
PPO's finite-sample behaviour also depends on exploration, the critic's
accuracy, entropy regularisation and the training budget.
"""

from __future__ import annotations

from lunarlab.env import BUILTIN_MAIN_ENGINE_COST


def geometric_sum(per_step: float, gamma: float, n_steps: int) -> float:
    """sum_{t=0}^{n-1} gamma^t * per_step."""
    if n_steps <= 0:
        return 0.0
    if gamma == 1.0:
        return per_step * n_steps
    return per_step * (1.0 - gamma**n_steps) / (1.0 - gamma)


def perpetual_value(per_step: float, gamma: float) -> float:
    """sum_{t=0}^{inf} gamma^t * per_step (finite only for gamma < 1)."""
    if gamma >= 1.0:
        return float("inf") if per_step > 0 else float("-inf") if per_step < 0 else 0.0
    return per_step / (1.0 - gamma)


def hover_incentive(
    *,
    bonus: float,
    gamma: float,
    horizon: int = 1000,
    hover_start: int = 100,
    main_engine_duty: float = 0.5,
    landing_step: int = 300,
    landing_original_return: float = 220.0,
) -> dict:
    """Compare 'hover until the time limit' with 'land' under stated assumptions.

    Assumptions (all editable):
    * hovering starts at ``hover_start`` and is eligible every step afterwards;
    * holding altitude needs the main engine a fraction ``main_engine_duty`` of
      steps, each costing 0.30 of *original* reward (the env's own fuel cost);
    * a landing policy finishes at ``landing_step`` with original return
      ``landing_original_return``.
    The original-reward shaping drift while hovering is ignored.
    """
    net = bonus - main_engine_duty * BUILTIN_MAIN_ENGINE_COST
    n_hover = max(horizon - hover_start, 0)
    naive = bonus * n_hover
    discounted_until_limit = gamma**hover_start * geometric_sum(net, gamma, n_hover)
    # At the time limit SB3 adds gamma * V(s_T). If the critic has learned that
    # hovering continues, V(s_T) ~ net / (1 - gamma): the truncation is treated
    # as "the episode would go on", so the perceived value approaches a perpetuity.
    perceived_with_bootstrap = gamma**hover_start * perpetual_value(net, gamma)
    land_upper = landing_original_return
    land_lower = gamma**landing_step * landing_original_return
    return {
        "inputs": {
            "bonus": bonus,
            "gamma": gamma,
            "horizon": horizon,
            "hover_start": hover_start,
            "main_engine_duty": main_engine_duty,
            "landing_step": landing_step,
            "landing_original_return": landing_original_return,
        },
        "net_per_hover_step": net,
        "naive_undiscounted_bonus": naive,
        "discounted_hover_value_until_limit": discounted_until_limit,
        "discounted_hover_value_with_timeout_bootstrap": perceived_with_bootstrap,
        "effective_horizon_steps": (1.0 / (1.0 - gamma)) if gamma < 1 else None,
        "landing_value_range": [land_lower, land_upper],
        "explanation": (
            "Rewards are discounted by gamma per step, so a bonus far in the future counts less. "
            f"With gamma = {gamma}, the effective horizon is about {round(1 / (1 - gamma)) if gamma < 1 else 'infinite'} steps. "
            "Because SB3 bootstraps the value of the final observation when the 1000-step limit cuts an "
            "episode, a critic that expects hovering to continue values it like an endless stream. "
            "Compare these with the landing value; the larger number suggests which behaviour the "
            "reward favours, not which behaviour PPO will actually find."
        ),
    }


def time_penalty_effect(*, cost: float, gamma: float, steps: int) -> dict:
    """Undiscounted and discounted total of a per-step cost over ``steps`` steps (to compare with the -100
    crash penalty).
    """
    return {
        "undiscounted": -cost * steps,
        "discounted": geometric_sum(-cost, gamma, steps),
        "explanation": (
            "A per-step cost makes longer episodes worse. Compare its total with the -100 crash "
            "penalty: if staying alive costs more than crashing, ending early becomes attractive."
        ),
    }


def potential_telescoping(
    *, alpha: float, gamma: float, phi_start: float, phi_end: float, steps: int, terminated: bool
) -> float:
    """Closed form of sum_t gamma^t * F_t over one episode.

    terminated: gamma^T * 0 - alpha*Phi(s0)       = -alpha * phi_start
    truncated:  gamma^T * alpha*Phi(s_T) - alpha*Phi(s0)
    """
    end = 0.0 if terminated else phi_end
    return alpha * (gamma**steps * end - phi_start)
