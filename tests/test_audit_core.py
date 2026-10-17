# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""The task-independent audit layer: accounting identity, adapters, and equivalence with LunarLab's wrapper."""

from __future__ import annotations

import gymnasium as gym
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from lunarlab.audit import (
    EpisodeAudit,
    EpisodeEnd,
    RewardAccountingWrapper,
    TaskAdapter,
    Transition,
    adapter_names,
    audit_policy,
    get_adapter,
    per_step,
    potential_shaping,
    register_adapter,
    seed_split_problems,
    state_bonus,
    terms_hash,
)
from lunarlab.env import make_env
from lunarlab.rewards.config import preset
from lunarlab.rewards.wrapper import LunarLabRewardWrapper

GAMMA = 0.999


def _preset_terms(name: str) -> dict:
    a = get_adapter("lunarlander")
    return {
        "baseline": {},
        "time-penalty": {"time_penalty": a.term("time_penalty")},
        "hover-bonus": {"hover_bonus": a.term("hover_bonus")},
        "potential": {"potential_shaping": a.term("potential_shaping", gamma=GAMMA)},
    }[name]


@pytest.mark.integration
@pytest.mark.parametrize("name", ["baseline", "time-penalty", "hover-bonus", "potential"])
def test_generic_accounting_reproduces_lunarlabs_wrapper_on_lunarlander(name):
    """Same actions, same seeds: every reward, return, term and outcome equals the main pipeline's."""
    rng = np.random.default_rng(7)
    ref = LunarLabRewardWrapper(make_env(), preset(name), GAMMA, apply=True)
    gen = RewardAccountingWrapper(
        make_env(), _preset_terms(name), gamma=GAMMA, apply=True, adapter=get_adapter("lunarlander")
    )
    for seed in (20_000, 20_001, 20_002):
        ref.reset(seed=seed)
        gen.reset(seed=seed)
        while True:
            a = int(rng.integers(0, 4))
            o1, r1, t1, u1, i1 = ref.step(a)
            o2, r2, t2, u2, i2 = gen.step(a)
            assert np.array_equal(o1, o2) and (t1, u1) == (t2, u2)
            assert r1 == pytest.approx(r2, abs=1e-12)
            if t1 or u1:
                e1, e2 = i1["lunarlab_episode"], i2["audit_episode"]
                assert e1["original_return"] == e2["original_return"]
                assert e1["training_return"] == pytest.approx(e2["training_return"], abs=1e-9)
                assert e1["discounted_training_return"] == pytest.approx(
                    e2["discounted_training_return"], abs=1e-9
                )
                for k, v in e2["term_returns"].items():
                    assert e1["term_returns"][k] == pytest.approx(v, abs=1e-9)
                assert e1["landing_category"] == e2["outcome"]
                assert e1["hover_fraction"] == pytest.approx(e2["hover_fraction"])
                break
    ref.close()
    gen.close()


@settings(max_examples=200, deadline=None)
@given(
    states=st.lists(st.lists(st.floats(-5, 5), min_size=3, max_size=3), min_size=2, max_size=40),
    gamma=st.floats(0.5, 1.0),
    alpha=st.floats(0.0, 10.0),
    terminated=st.booleans(),
)
def test_potential_shaping_telescopes_for_any_potential_and_episode(states, gamma, alpha, terminated):
    """sum_t gamma^t F_t = alpha * (gamma^T Phi(s_T) - Phi(s_0)), with Phi(s_T) = 0 on termination."""

    def phi(o):
        return -float(np.abs(o).sum())

    term = potential_shaping("f", phi, alpha=alpha, gamma=gamma, potential_id="-l1")
    obs = [np.asarray(s, dtype=np.float64) for s in states]
    horizon = len(obs) - 1
    total = 0.0
    for t in range(horizon):
        last = t == horizon - 1
        total += gamma**t * term(
            Transition(obs[t], 0, 0.0, obs[t + 1], terminated and last, not terminated and last)
        )
    expected = alpha * ((0.0 if terminated else gamma**horizon * phi(obs[-1])) - phi(obs[0]))
    assert total == pytest.approx(expected, rel=1e-9, abs=1e-7)


@settings(max_examples=200, deadline=None)
@given(
    steps=st.lists(
        st.tuples(st.floats(-100, 100), st.floats(-10, 10), st.floats(-10, 10)), min_size=1, max_size=60
    ),
    gamma=st.floats(0.5, 1.0),
    weight=st.floats(0.0, 2.0),
)
def test_episode_audit_keeps_the_accounting_identity(steps, gamma, weight):
    audit = EpisodeAudit(gamma)
    for original, a, b in steps:
        audit.add(original, {"a": a, "b": b}, weight * original + a + b)
    s = audit.summary()
    assert s["length"] == len(steps)
    assert s["training_return"] == pytest.approx(
        weight * s["original_return"] + sum(s["term_returns"].values()), abs=1e-6
    )
    assert s["discounted_training_return"] == pytest.approx(
        weight * s["discounted_original_return"] + sum(s["term_discounted_returns"].values()), abs=1e-6
    )


def test_wrapper_contract():
    env = gym.make("CartPole-v1")
    w = RewardAccountingWrapper(env, {"step_penalty": per_step("step_penalty", -0.5)}, gamma=0.9, apply=False)
    with pytest.raises(RuntimeError, match="before reset"):
        w.step(0)
    w.reset(seed=0)
    _, r, *_ = w.step(0)
    assert r == 1.0  # apply=False: the original reward is returned unchanged
    w.apply = True
    _, r, *_ = w.step(0)
    assert r == pytest.approx(0.5)
    with pytest.raises(ValueError, match="named"):
        RewardAccountingWrapper(gym.make("CartPole-v1"), {"x": per_step("y", 1.0)}, gamma=0.9)
    with pytest.raises(ValueError, match="gamma"):
        RewardAccountingWrapper(gym.make("CartPole-v1"), gamma=0.0)
    w.close()


def test_terms_hash_identifies_the_reward_definition():
    a = {"p": per_step("p", -0.01)}
    assert terms_hash(a, 1.0) == terms_hash({"p": per_step("p", -0.01)}, 1.0)
    assert terms_hash(a, 1.0) != terms_hash({"p": per_step("p", -0.02)}, 1.0)
    assert terms_hash(a, 1.0) != terms_hash(a, 0.0)
    bonus = state_bonus("b", lambda o: o[0] > 0, 1.0, predicate_id="x>0")
    assert bonus(Transition(np.zeros(1), 0, 0.0, np.ones(1), False, False)) == 1.0
    assert bonus(Transition(np.zeros(1), 0, 0.0, -np.ones(1), False, False)) == 0.0


def test_adapter_registry_and_terms():
    assert {"lunarlander", "cartpole"} <= set(adapter_names())
    with pytest.raises(KeyError, match="unknown task adapter"):
        get_adapter("nope")
    with pytest.raises(ValueError, match="already registered"):
        register_adapter("cartpole", get_adapter)
    with pytest.raises(KeyError, match="no reward term"):
        get_adapter("cartpole").term("hover_bonus")


def test_an_adapter_must_return_one_of_its_declared_outcomes():
    bad = TaskAdapter(
        name="bad",
        version="0",
        env_id="CartPole-v1",
        env_kwargs={},
        observation_labels=("a", "b", "c", "d"),
        action_labels=("l", "r"),
        outcome_categories=("ok",),
        classify=lambda end: {"outcome": "something-else"},
    )
    w = RewardAccountingWrapper(bad.make_env(), gamma=0.99, adapter=bad)
    w.reset(seed=0)
    with pytest.raises(ValueError, match="not one of"):
        while True:
            w.step(0)


def test_cartpole_outcomes_follow_the_environments_own_thresholds():
    cp = get_adapter("cartpole")
    env = cp.make_env()
    obs, _ = env.reset(seed=1)
    observations = [obs]
    while True:  # always push left: the episode ends by a termination, never by the time limit
        obs, _, terminated, truncated, _ = env.step(0)
        observations.append(obs)
        if terminated or truncated:
            break
    out = cp.classify(EpisodeEnd(env, np.asarray(observations), terminated, truncated, {}))
    core = env.unwrapped
    assert out["outcome"] in ("pole_fell", "cart_left_track")
    if out["outcome"] == "pole_fell":
        assert abs(observations[-1][2]) > core.theta_threshold_radians
    timed_out = cp.classify(EpisodeEnd(env, np.asarray(observations), False, True, {}))
    assert timed_out["outcome"] == "balanced_to_time_limit"
    env.close()


def test_seed_split_problems():
    assert seed_split_problems([1, 2], [3, 4]) == []
    assert any("overlap" in p for p in seed_split_problems([1, 2], [2, 3]))
    assert any("duplicates" in p for p in seed_split_problems([1, 1], [3]))
    assert any("integers" in p for p in seed_split_problems([True], [3]))


def test_audit_policy_on_cartpole_is_deterministic_and_records_provenance():
    cp = get_adapter("cartpole")
    shaping = cp.term("upright_potential", gamma=0.99)

    def lean_policy(o):  # push towards the side the pole leans to
        return int(o[2] + 0.5 * o[3] > 0)

    a = audit_policy(cp, lean_policy, [100, 101, 102], gamma=0.99, terms={shaping.name: shaping})
    b = audit_policy(cp, lean_policy, [100, 101, 102], gamma=0.99, terms={shaping.name: shaping})
    assert a["episodes"] == b["episodes"]
    assert a["adapter"] == {"name": "cartpole", "version": "1"}
    assert a["environment"]["env_id"] == "CartPole-v1" and a["environment"]["gymnasium"]
    assert a["reward"]["terms"]["upright_potential"]["type"] == "potential_shaping"
    assert sum(a["aggregate"]["outcomes"].values()) == 3
    for e in a["episodes"]:
        assert e["original_return"] == e["length"]  # CartPole: +1 per step
        assert e["training_return"] == pytest.approx(
            e["original_return"] + e["term_returns"]["upright_potential"]
        )
    with pytest.raises(ValueError, match="duplicates"):
        audit_policy(cp, lean_policy, [1, 1], gamma=0.99)


@pytest.mark.slow
def test_ppo_trains_on_cartpole_through_the_generic_wrapper():
    from stable_baselines3 import PPO
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.vec_env import DummyVecEnv

    cp = get_adapter("cartpole")
    shaping = cp.term("upright_potential", gamma=0.99)

    def make():
        return Monitor(
            RewardAccountingWrapper(
                cp.make_env(), {shaping.name: shaping}, gamma=0.99, apply=True, adapter=cp
            )
        )

    model = PPO(
        "MlpPolicy", DummyVecEnv([make]), n_steps=256, batch_size=64, gamma=0.99, seed=0, device="cpu"
    )
    model.learn(1024)
    report = audit_policy(
        cp,
        lambda o: int(model.predict(o, deterministic=True)[0]),
        [500, 501],
        gamma=0.99,
        terms={shaping.name: shaping},
    )
    assert report["aggregate"]["n_episodes"] == 2
    assert all(e["outcome"] in cp.outcome_categories for e in report["episodes"])
