"""Reward math: invariant, presets, hover predicate, potential shaping, accounting."""

from __future__ import annotations

import math

import numpy as np
import pytest
from pydantic import ValidationError

from lunarlab.hover import DEFAULT_BONUS_ELIGIBILITY, HoverThresholds, hover_state
from lunarlab.rewards import RewardConfig, compute_terms, potential, potential_shaping, preset
from lunarlab.rewards.analysis import geometric_sum, hover_incentive, potential_telescoping
from lunarlab.rewards.config import HoverBonusConfig, PotentialConfig, PotentialWeights, TimePenaltyConfig
from lunarlab.rewards.wrapper import LunarLabRewardWrapper
from tests.conftest import ScriptedEnv, random_states

GAMMA = 0.999


def run_episode(env, actions=None):
    obs, _ = env.reset(seed=0)
    rewards, infos = [], []
    t = 0
    while True:
        a = 0 if actions is None else actions[t % len(actions)]
        obs, r, te, tr, info = env.step(a)
        rewards.append(r)
        infos.append(info)
        t += 1
        if te or tr:
            return rewards, infos


def wrap(env, cfg, gamma=GAMMA, **kw):
    return LunarLabRewardWrapper(
        env, cfg, gamma, probe_internals=False, step_info=True, record_steps=True, **kw
    )


# --------------------------------------------------------------------------- #
# Invariant and baseline
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", ["baseline", "time-penalty", "hover-bonus", "potential"])
def test_training_reward_equals_original_plus_terms(name):
    states = random_states(40, seed=1)
    env = wrap(ScriptedEnv(states, rewards=np.linspace(-3, 3, 39), terminate_at=39), preset(name))
    rewards, infos = run_episode(env)
    for r, info in zip(rewards, infos, strict=True):
        d = info["lunarlab"]
        assert d["training_reward"] == pytest.approx(
            d["original_reward"] + sum(d["terms"].values()), abs=1e-12
        )
        assert r == d["training_reward"]
    ep = infos[-1]["lunarlab_episode"]
    assert ep["training_return"] == pytest.approx(
        ep["original_return"] + sum(ep["term_returns"].values()), abs=1e-9
    )


def test_baseline_adds_nothing():
    states = random_states(20, seed=2)
    original = list(np.arange(19) * 0.5 - 3)
    env = wrap(ScriptedEnv(states, rewards=original, terminate_at=19), preset("baseline"))
    rewards, infos = run_episode(env)
    assert rewards == pytest.approx(original)
    assert all(info["lunarlab"]["terms"] == {} for info in infos)


def test_apply_false_returns_original_but_records_terms():
    states = random_states(10, seed=3)
    original = [1.0] * 9
    env = wrap(ScriptedEnv(states, rewards=original, terminate_at=9), preset("time-penalty"), apply=False)
    rewards, infos = run_episode(env)
    assert rewards == pytest.approx(original)  # evaluation reward untouched
    ep = infos[-1]["lunarlab_episode"]
    assert ep["reward_applied"] is False
    assert ep["term_returns"]["time_penalty"] == pytest.approx(-0.01 * 9)


def test_time_penalty_every_transition_including_terminal():
    states = random_states(6, seed=4)
    env = wrap(ScriptedEnv(states, rewards=[0.0] * 5, terminate_at=5), preset("time-penalty"))
    rewards, _ = run_episode(env)
    assert rewards == pytest.approx([-0.01] * 5)


# --------------------------------------------------------------------------- #
# Hover predicate
# --------------------------------------------------------------------------- #


def hover_obs(**kw):
    base = {"x": 0.0, "y": 0.5, "vx": 0.0, "vy": 0.0, "angle": 0.0, "w": 0.0, "l": 0.0, "r": 0.0}
    base.update(kw)
    return np.array([base[k] for k in ("x", "y", "vx", "vy", "angle", "w", "l", "r")], dtype=np.float64)


def test_hover_predicate_boundaries_inclusive():
    t = DEFAULT_BONUS_ELIGIBILITY
    assert hover_state(hover_obs(), t)
    assert hover_state(hover_obs(y=t.min_height), t)
    assert hover_state(hover_obs(y=t.max_height), t)
    assert hover_state(hover_obs(vx=t.max_abs_vx, vy=-t.max_abs_vy), t)
    assert hover_state(hover_obs(angle=-t.max_abs_angle_rad), t)
    assert hover_state(hover_obs(w=t.max_abs_angular_velocity), t)


@pytest.mark.parametrize(
    "field,value",
    [
        ("y", 0.25 - 1e-6),
        ("y", 1.0 + 1e-6),
        ("vx", 0.1 + 1e-6),
        ("vy", -0.1 - 1e-6),
        ("angle", 0.2 + 1e-6),
        ("w", -0.2 - 1e-6),
        ("l", 1.0),
        ("r", 1.0),
    ],
)
def test_hover_predicate_rejects_outside(field, value):
    assert not hover_state(hover_obs(**{field: value}), DEFAULT_BONUS_ELIGIBILITY)


def test_hover_angular_velocity_check_optional():
    t = HoverThresholds(max_abs_angular_velocity=None)
    assert hover_state(hover_obs(w=3.0), t)


def test_hover_thresholds_validate_band():
    with pytest.raises(ValidationError):
        HoverThresholds(min_height=1.0, max_height=0.5)


def test_hover_bonus_paid_on_resulting_state():
    s0 = hover_obs(y=1.5)  # outside band
    s1 = hover_obs(y=0.5)  # inside band
    cfg = preset("hover-bonus")
    assert (
        compute_terms(s0, 0, s1, terminated=False, truncated=False, config=cfg, gamma=GAMMA)["hover_bonus"]
        == 1.0
    )
    assert (
        compute_terms(s1, 0, s0, terminated=False, truncated=False, config=cfg, gamma=GAMMA)["hover_bonus"]
        == 0.0
    )


# --------------------------------------------------------------------------- #
# Potential-based shaping
# --------------------------------------------------------------------------- #


def test_potential_zero_at_ideal_state_and_bounded():
    w = PotentialWeights()
    assert potential(np.zeros(8), w) == 0.0
    bound = -(w.x + w.y + w.speed + w.angle + w.angular_velocity)
    for s in random_states(200, seed=5):
        s = s * 50  # extreme values still bounded via tanh
        assert bound <= potential(s, w) <= 0.0


def test_potential_formula_matches_definition():
    s = np.array([0.3, -0.7, 0.2, -0.4, 0.1, -0.5, 0, 0], dtype=np.float64)
    w = PotentialWeights(x=1, y=2, speed=3, angle=4, angular_velocity=5)
    expected = -(
        1 * math.tanh(0.3)
        + 2 * math.tanh(0.7)
        + 3 * math.tanh(math.hypot(0.2, -0.4))
        + 4 * math.tanh(0.1)
        + 5 * math.tanh(0.5)
    )
    assert potential(s, w) == pytest.approx(expected, abs=1e-12)


def test_shaping_terminal_uses_absorbing_zero_and_truncation_uses_real_obs():
    w = PotentialWeights()
    s, s2 = random_states(2, seed=6)
    alpha = 10.0
    term = potential_shaping(s, s2, terminated=True, alpha=alpha, gamma=GAMMA, weights=w)
    trunc = potential_shaping(s, s2, terminated=False, alpha=alpha, gamma=GAMMA, weights=w)
    assert term == pytest.approx(alpha * (0.0 - potential(s, w)))
    assert trunc == pytest.approx(alpha * (GAMMA * potential(s2, w) - potential(s, w)))
    assert term != pytest.approx(trunc)


def test_shaping_is_not_a_plain_difference():
    w = PotentialWeights()
    s, s2 = random_states(2, seed=7)
    plain = 10 * (potential(s2, w) - potential(s, w))
    assert potential_shaping(s, s2, terminated=False, alpha=10, gamma=0.9, weights=w) != pytest.approx(plain)


@pytest.mark.parametrize("gamma", [0.9, 0.99, 0.999])
def test_discounted_telescoping_terminal(gamma):
    states = random_states(31, seed=8)
    cfg = preset("potential")
    env = wrap(ScriptedEnv(states, rewards=[0.0] * 30, terminate_at=30), cfg, gamma=gamma)
    _, infos = run_episode(env)
    ep = infos[-1]["lunarlab_episode"]
    phi0 = potential(states[0], cfg.potential.weights)
    expected = potential_telescoping(
        alpha=cfg.potential.alpha, gamma=gamma, phi_start=phi0, phi_end=0.0, steps=30, terminated=True
    )
    assert expected == pytest.approx(-cfg.potential.alpha * phi0)
    assert ep["term_discounted_returns"]["potential_shaping"] == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("gamma", [0.9, 0.999])
def test_discounted_telescoping_truncated_keeps_residual_potential(gamma):
    states = random_states(26, seed=9)
    cfg = preset("potential")
    env = wrap(ScriptedEnv(states, rewards=[0.0] * 25, truncate_at=25), cfg, gamma=gamma)
    _, infos = run_episode(env)
    ep = infos[-1]["lunarlab_episode"]
    assert ep["truncated"] and not ep["terminated"]
    phi0 = potential(states[0], cfg.potential.weights)
    phiT = potential(states[25], cfg.potential.weights)
    expected = cfg.potential.alpha * (gamma**25 * phiT - phi0)
    assert ep["term_discounted_returns"]["potential_shaping"] == pytest.approx(expected, abs=1e-9)
    assert abs(phiT) > 1e-6  # the residual is real, not silently zeroed


# --------------------------------------------------------------------------- #
# Accounting and episode boundaries
# --------------------------------------------------------------------------- #


def test_accumulator_resets_and_no_cross_episode_leakage():
    states = random_states(12, seed=10)
    cfg = preset("potential")
    env = wrap(ScriptedEnv(states, rewards=[1.0] * 11, terminate_at=11), cfg)
    _, infos1 = run_episode(env)
    _, infos2 = run_episode(env)
    fresh = wrap(ScriptedEnv(states, rewards=[1.0] * 11, terminate_at=11), cfg)
    _, infos3 = run_episode(fresh)
    e1, e2, e3 = (i[-1]["lunarlab_episode"] for i in (infos1, infos2, infos3))
    assert e2["length"] == 11 and e2["original_return"] == pytest.approx(11.0)
    for k in ("training_return", "discounted_training_return", "hover_steps"):
        assert e1[k] == pytest.approx(e2[k]) == pytest.approx(e3[k])
    # The first shaping term of episode 2 uses episode 2's reset obs, not episode 1's final obs.
    first = infos2[0]["lunarlab"]["terms"]["potential_shaping"]
    expected = cfg.potential.alpha * (
        GAMMA * potential(states[1], cfg.potential.weights) - potential(states[0], cfg.potential.weights)
    )
    assert first == pytest.approx(expected)


def test_step_after_episode_end_requires_reset():
    states = random_states(4, seed=11)
    env = wrap(ScriptedEnv(states, rewards=[0.0] * 3, terminate_at=3), preset("baseline"))
    run_episode(env)
    with pytest.raises(RuntimeError):
        env.step(0)


def test_action_counts_and_discounted_original():
    states = random_states(6, seed=12)
    env = wrap(ScriptedEnv(states, rewards=[1, 2, 3, 4, 5], terminate_at=5), preset("baseline"), gamma=0.5)
    _, infos = run_episode(env, actions=[2, 1, 3, 0, 2])
    ep = infos[-1]["lunarlab_episode"]
    assert ep["actions"] == {"noop": 1, "left": 1, "main": 2, "right": 1}
    assert ep["discounted_original_return"] == pytest.approx(1 + 2 * 0.5 + 3 * 0.25 + 4 * 0.125 + 5 * 0.0625)


# --------------------------------------------------------------------------- #
# Configuration schema
# --------------------------------------------------------------------------- #


def test_reward_config_rejects_unknown_fields_and_bad_values():
    with pytest.raises(ValidationError):
        RewardConfig.model_validate({"name": "x", "evil": "__import__('os')"})
    with pytest.raises(ValidationError):
        RewardConfig(name="x", time_penalty=TimePenaltyConfig(enabled=True, cost_per_step=-1))
    with pytest.raises(ValidationError):
        RewardConfig(name="x", potential=PotentialConfig(enabled=True, weights=PotentialWeights(x=-1)))
    with pytest.raises(ValidationError):
        RewardConfig(name="../../etc")
    with pytest.raises(ValidationError):
        RewardConfig(name="x", hover_bonus=HoverBonusConfig(bonus_per_step=1e9))


def test_content_hash_ignores_labels_but_not_reward():
    a = preset("hover-bonus")
    b = a.model_copy(update={"name": "Renamed", "description": "other"})
    assert a.content_hash() == b.content_hash()
    c = RewardConfig.model_validate(
        {**a.model_dump(), "hover_bonus": {**a.hover_bonus.model_dump(), "bonus_per_step": 0.5}}
    )
    assert c.content_hash() != a.content_hash()


def test_presets_have_single_intended_term():
    assert preset("baseline").active_terms() == []
    assert preset("time-penalty").active_terms() == ["time_penalty"]
    assert preset("hover-bonus").active_terms() == ["hover_bonus"]
    assert preset("potential").active_terms() == ["potential_shaping"]


def test_combining_potential_with_other_terms_warns():
    cfg = RewardConfig.model_validate(
        {**preset("potential").model_dump(), "time_penalty": {"enabled": True, "cost_per_step": 0.01}}
    )
    assert any("policy-invariance" in w for w in cfg.warnings())


# --------------------------------------------------------------------------- #
# Discounted-return reasoning helpers
# --------------------------------------------------------------------------- #


def test_geometric_sum_and_hover_incentive():
    assert geometric_sum(1.0, 0.5, 3) == pytest.approx(1 + 0.5 + 0.25)
    assert geometric_sum(2.0, 1.0, 4) == 8.0
    res = hover_incentive(bonus=1.0, gamma=0.999, horizon=1000, hover_start=100, main_engine_duty=0.5)
    assert res["naive_undiscounted_bonus"] == pytest.approx(900)
    assert res["discounted_hover_value_until_limit"] < res["naive_undiscounted_bonus"]
    assert res["discounted_hover_value_with_timeout_bootstrap"] > res["discounted_hover_value_until_limit"]
