# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Property-based tests of the mathematical invariants the published results rest on.

Reward shaping, reward accounting, the statistics across training seeds and the outcome classifier are checked
on generated inputs rather than a handful of hand-picked cases.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from lunarlab.hover import DEFAULT_DETECTOR
from lunarlab.outcomes import ENV_OUTCOMES, LANDING_CATEGORIES, _category, pad_geography
from lunarlab.rewards.accounting import EpisodeAccumulator
from lunarlab.rewards.config import (
    HoverBonusConfig,
    PotentialConfig,
    PotentialWeights,
    RewardConfig,
    TimePenaltyConfig,
)
from lunarlab.rewards.terms import compute_terms, potential, potential_shaping, training_reward
from lunarlab.rl_stats import bootstrap_ci, iqm, probability_of_improvement
from lunarlab.stats import wilson_interval

finite = st.floats(-3.0, 3.0, allow_nan=False)
lander_state = st.lists(finite, min_size=6, max_size=6).map(
    lambda v: np.array([*v, 0.0, 0.0], dtype=np.float32)
)
weights = st.builds(
    PotentialWeights,
    x=st.floats(0, 10),
    y=st.floats(0, 10),
    speed=st.floats(0, 10),
    angle=st.floats(0, 10),
    angular_velocity=st.floats(0, 10),
)
SETTINGS = settings(max_examples=150, deadline=None)


@SETTINGS
@given(states=st.lists(lander_state, min_size=2, max_size=40), w=weights, gamma=st.floats(0.5, 1.0),
       alpha=st.floats(0, 100), terminated=st.booleans())  # fmt: skip
def test_potential_shaping_telescopes_on_lander_states(states, w, gamma, alpha, terminated):
    """Over an episode, sum_t gamma^t F_t = alpha * (gamma^T Phi(s_T) - Phi(s_0)), Phi(terminal) = 0."""
    horizon = len(states) - 1
    total = 0.0
    for t in range(horizon):
        last = t == horizon - 1
        f = potential_shaping(
            states[t], states[t + 1], terminated=terminated and last, alpha=alpha, gamma=gamma, weights=w
        )
        total += gamma**t * f
    phi_end = 0.0 if terminated else potential(states[-1], w)
    expected = alpha * (gamma**horizon * phi_end - potential(states[0], w))
    assert total == pytest.approx(expected, rel=1e-6, abs=1e-6)


@SETTINGS
@given(s=lander_state, w=weights)
def test_potential_is_bounded_and_zero_only_at_the_ideal_state(s, w):
    phi = potential(s, w)
    total_weight = w.x + w.y + w.speed + w.angle + w.angular_velocity
    assert -total_weight - 1e-9 <= phi <= 0.0
    assert potential(np.zeros(8, dtype=np.float32), w) == 0.0


reward_configs = st.builds(
    lambda tp, cost, hb, bonus, pot, alpha, w0: RewardConfig(
        name="generated",
        time_penalty=TimePenaltyConfig(enabled=tp, cost_per_step=cost),
        hover_bonus=HoverBonusConfig(enabled=hb, bonus_per_step=bonus),
        potential=PotentialConfig(enabled=pot, alpha=alpha),
        original_weight=w0,
    ),
    st.booleans(), st.floats(0, 1), st.booleans(), st.floats(0, 10), st.booleans(), st.floats(0, 100),
    st.sampled_from([0.0, 1.0]),
)  # fmt: skip


@SETTINGS
@given(cfg=reward_configs, steps=st.lists(st.tuples(lander_state, st.integers(0, 3), st.floats(-100, 100)),
                                           min_size=2, max_size=30), gamma=st.floats(0.5, 1.0))  # fmt: skip
def test_accounting_identity_holds_for_any_reward_configuration(cfg, steps, gamma):
    """training = w * original + sum(terms) per transition, and the same identity for (discounted) returns."""
    acc = EpisodeAccumulator(gamma=gamma, detector=DEFAULT_DETECTOR)
    acc.reset()
    for (s, a, original), (s_next, _, _) in zip(steps, steps[1:], strict=False):
        terms = compute_terms(s, a, s_next, terminated=False, truncated=False, config=cfg, gamma=gamma)
        assert set(terms) == set(cfg.active_terms())
        shaped = training_reward(original, terms, cfg.original_weight)
        assert shaped == pytest.approx(cfg.original_weight * original + sum(terms.values()), abs=1e-9)
        acc.add(original=original, terms=terms, training=shaped, action=a, next_obs=s_next)
    out = acc.summary()
    w = cfg.original_weight
    assert out["training_return"] == pytest.approx(
        w * out["original_return"] + sum(out["term_returns"].values()), abs=1e-6
    )
    assert out["discounted_training_return"] == pytest.approx(
        w * out["discounted_original_return"] + sum(out["term_discounted_returns"].values()), abs=1e-6
    )


samples = st.lists(st.floats(-1e4, 1e4, allow_nan=False), min_size=1, max_size=40)


@SETTINGS
@given(x=samples)
def test_iqm_lies_within_the_data_and_ignores_order(x):
    v = iqm(x)
    assert min(x) - 1e-9 <= v <= max(x) + 1e-9
    assert v == pytest.approx(iqm(list(reversed(x))))
    assert iqm([x[0]] * len(x)) == pytest.approx(x[0])


@SETTINGS
@given(x=samples, y=samples)
def test_probability_of_improvement_is_a_probability_and_complementary(x, y):
    p, q = probability_of_improvement(x, y), probability_of_improvement(y, x)
    assert 0.0 <= p <= 1.0
    assert p + q == pytest.approx(1.0)
    if min(x) > max(y):
        assert p == 1.0


@settings(max_examples=40, deadline=None)
@given(x=st.lists(st.floats(-1e3, 1e3, allow_nan=False), min_size=2, max_size=12))
def test_bootstrap_interval_is_ordered_and_within_the_data(x):
    lo, hi = bootstrap_ci(x, reps=200)
    assert lo <= hi
    assert min(x) - 1e-9 <= lo and hi <= max(x) + 1e-9


@SETTINGS
@given(n=st.integers(1, 10_000), data=st.data())
def test_wilson_interval_contains_the_observed_rate(n, data):
    k = data.draw(st.integers(0, n))
    lo, hi = wilson_interval(k, n)
    assert 0.0 <= lo <= k / n <= hi <= 1.0


coord = st.floats(-10, 10, allow_nan=False)


@SETTINGS
@given(legs=st.tuples(coord, coord), x1=coord, x2=coord)
def test_pad_geography_is_order_independent_and_consistent(legs, x1, x2):
    assume(x1 != x2)
    g = pad_geography(legs, x1, x2)
    assert g == pad_geography(legs, x2, x1)
    lo, hi = min(x1, x2), max(x1, x2)
    inside = [lo <= v <= hi for v in legs]
    assert g == ("within" if all(inside) else "straddling" if any(inside) else "outside")
    assert pad_geography((math.nan, legs[1]), x1, x2) == "unknown"


@SETTINGS
@given(env_outcome=st.sampled_from([*ENV_OUTCOMES, "something-else"]), body=st.booleans(), pad=st.booleans(),
       geography=st.sampled_from(["within", "straddling", "outside", "unknown"]))  # fmt: skip
def test_every_episode_gets_exactly_one_known_landing_category(env_outcome, body, pad, geography):
    c = _category(env_outcome, body, pad, geography)
    assert c in LANDING_CATEGORIES
    if c == "strict_pad_landing":
        assert env_outcome == "at_rest" and not body and pad
