# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Real LunarLander-v3: API, adapter, built-in reward decomposition, SB3 VecEnv semantics."""

from __future__ import annotations

import numpy as np
import pytest
from gymnasium.wrappers import TimeLimit
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from lunarlab.config import EvalProtocol, PPOConfig, RunConfig, TrainingConfig
from lunarlab.env import (
    ACTIONS,
    BUILTIN_TERMINAL_CRASH,
    BUILTIN_TERMINAL_REST,
    OBSERVATION_FIELDS,
    check_adapter,
    environment_record,
    make_env,
)
from lunarlab.evaluation import evaluate_policy
from lunarlab.policies import HeuristicPolicy, RandomPolicy
from lunarlab.rewards import potential, preset
from lunarlab.rewards.wrapper import LunarLabRewardWrapper
from lunarlab.storage import utc_now
from lunarlab.training import build_vec_env
from tests.conftest import ScriptedEnv, random_states

pytestmark = pytest.mark.integration


def test_environment_spec_recorded():
    rec = environment_record()
    assert rec["env_id"] == "LunarLander-v3"
    assert rec["env_kwargs"] == {"continuous": False}
    assert rec["max_episode_steps"] == 1000
    assert rec["gravity"] == -10.0 and rec["enable_wind"] is False
    assert "TimeLimit" in rec["wrapper_stack"]
    assert check_adapter()["ok"]


def test_metadata_tables():
    assert [f.key for f in OBSERVATION_FIELDS] == [
        "x",
        "y",
        "vx",
        "vy",
        "angle",
        "angular_velocity",
        "left_contact",
        "right_contact",
    ]
    assert [a.label for a in ACTIONS] == [
        "Do nothing",
        "Fire left orientation engine",
        "Fire main engine",
        "Fire right orientation engine",
    ]


def test_gymnasium_api_shapes():
    env = make_env()
    obs, info = env.reset(seed=1)
    assert obs.shape == (8,) and isinstance(info, dict)
    out = env.step(0)
    assert len(out) == 5 and isinstance(out[2], bool) and isinstance(out[3], bool)
    env.close()


@pytest.mark.parametrize("name", ["baseline", "time-penalty", "hover-bonus", "potential"])
def test_sb3_env_checker_on_wrapper(name):
    env = LunarLabRewardWrapper(make_env(), preset(name), 0.999)
    check_env(env, warn=True)


def test_baseline_wrapper_identical_to_raw_env():
    raw, wrapped = make_env(), LunarLabRewardWrapper(make_env(), preset("baseline"), 0.999)
    rng = np.random.default_rng(0)
    for seed in (3, 4):
        o1, _ = raw.reset(seed=seed)
        o2, _ = wrapped.reset(seed=seed)
        np.testing.assert_array_equal(o1, o2)
        while True:
            a = int(rng.integers(4))
            o1, r1, t1, u1, _ = raw.step(a)
            o2, r2, t2, u2, _ = wrapped.step(a)
            np.testing.assert_array_equal(o1, o2)
            assert r1 == r2 and t1 == t2 and u1 == u2
            if t1 or u1:
                break


def test_builtin_reward_decomposition_matches_env():
    env = LunarLabRewardWrapper(make_env(), preset("baseline"), 0.999, record_steps=True)
    rng = np.random.default_rng(1)
    terminal_seen = set()
    for seed in range(6):
        obs, _ = env.reset(seed=100 + seed)
        while True:
            obs, r, te, tr, _ = env.step(int(rng.integers(4)))
            if te or tr:
                break
        for s in env.steps:
            b = s["builtin"]
            if s["terminated"]:
                assert (
                    b["terminal"] == s["original_reward"] in (BUILTIN_TERMINAL_CRASH, BUILTIN_TERMINAL_REST)
                )
                assert all(
                    b[k] == 0.0
                    for k in ("distance", "speed", "tilt", "leg_contact", "main_engine", "side_engine")
                )
                terminal_seen.add(s["original_reward"])
            else:
                assert abs(b["residual"]) < 1e-3
                assert b["main_engine"] == (-0.3 if s["action"] == 2 else 0.0)
                assert b["side_engine"] == (-0.03 if s["action"] in (1, 3) else 0.0)
    assert terminal_seen


def test_dummy_vec_env_terminal_observation_is_not_next_reset():
    """SB3 auto-resets: the returned obs belongs to the NEXT episode; the final obs is in info."""
    from lunarlab.rewards import compute_terms

    cfg = preset("potential")
    venv = DummyVecEnv([lambda: Monitor(LunarLabRewardWrapper(make_env(), cfg, 0.999))])
    venv.seed(5)
    obs = venv.reset()
    rng = np.random.default_rng(2)
    checked = 0
    while checked < 3:
        prev = obs.copy()
        obs, rewards, dones, infos = venv.step(rng.integers(0, 4, size=1))
        if not dones[0]:
            continue
        info = infos[0]
        ep = info["lunarlab_episode"]
        term = info["terminal_observation"]
        np.testing.assert_allclose(term, ep["final_obs"], atol=1e-6)
        assert not np.allclose(term, obs[0])  # obs[0] is the next episode's reset observation
        # Monitor (outermost) reports the TRAINING return, not the original return.
        assert info["episode"]["r"] == pytest.approx(ep["training_return"], abs=1e-4)
        if ep["terminated"]:
            terms = compute_terms(prev[0], 0, term, terminated=True, truncated=False, config=cfg, gamma=0.999)
            assert terms["potential_shaping"] == pytest.approx(
                -10.0 * potential(prev[0], cfg.potential.weights)
            )
            original = 100.0 if ep["env_outcome"] == "at_rest" else -100.0
            assert rewards[0] == pytest.approx(original + terms["potential_shaping"], abs=1e-4)
        checked += 1
    venv.close()


def test_vec_env_truncation_flag_and_bootstrap_obs():
    states = random_states(12, seed=3)

    def make():
        inner = TimeLimit(ScriptedEnv(states, rewards=[0.0] * 11), max_episode_steps=5)
        return Monitor(LunarLabRewardWrapper(inner, preset("potential"), 0.99, probe_internals=False))

    venv = DummyVecEnv([make])
    venv.reset()
    for _ in range(4):
        venv.step(np.array([0]))
    _, rewards, dones, infos = venv.step(np.array([0]))
    assert dones[0] and infos[0]["TimeLimit.truncated"] is True
    np.testing.assert_allclose(infos[0]["terminal_observation"], states[5])
    w = preset("potential").potential.weights
    expected = 10.0 * (0.99 * potential(states[5], w) - potential(states[4], w))
    assert rewards[0] == pytest.approx(expected, abs=1e-5)  # truncation: real final obs, not absorbing 0
    venv.close()


def test_training_env_gamma_matches_ppo_gamma():
    cfg = RunConfig(
        run_id="t",
        created_at=utc_now(),
        reward=preset("potential"),
        ppo=PPOConfig(gamma=0.97, n_envs=2, n_steps=64, batch_size=32),
        training=TrainingConfig(),
    )
    venv = build_vec_env(cfg)
    wrapper = venv.envs[0].env
    assert isinstance(wrapper, LunarLabRewardWrapper)
    assert wrapper.gamma == 0.97 and wrapper.apply is True
    venv.close()


def test_heuristic_lands_and_random_does_not():
    p = EvalProtocol()
    seeds = list(range(20_000, 20_010))
    h = evaluate_policy(HeuristicPolicy(make_env()), seeds, protocol=p, reward=None, gamma=0.999)["aggregate"]
    r = evaluate_policy(RandomPolicy(0), seeds, protocol=p, reward=None, gamma=0.999)["aggregate"]
    assert h["pad_landing"]["k"] >= 3
    assert r["pad_landing"]["k"] == 0
    assert h["env_success_at_rest"]["rate"] >= h["pad_landing"]["rate"]


def test_evaluation_is_deterministic_for_fixed_seeds():
    p = EvalProtocol()
    seeds = [20_000, 20_001, 20_002]
    a = evaluate_policy(RandomPolicy(4), seeds, protocol=p, reward=None, gamma=0.999)
    b = evaluate_policy(RandomPolicy(4), seeds, protocol=p, reward=None, gamma=0.999)
    assert [e["original_return"] for e in a["episodes"]] == [e["original_return"] for e in b["episodes"]]


def test_scene_geometry_is_real_and_deterministic():
    from lunarlab.env import scene_for_seed

    a, b = scene_for_seed(20_000), scene_for_seed(20_000)
    assert a == b  # terrain depends only on the reset seed
    assert a != scene_for_seed(20_001)
    xs = [p[0] for p in a["terrain"]]
    assert xs == sorted(xs) and xs[0] == 0.0 and abs(xs[-1] - a["world"]["width"]) < 1e-9
    pad = a["helipad"]
    on_pad = [p[1] for p in a["terrain"] if pad["x1"] <= p[0] <= pad["x2"]]
    # The pad section is flat. Gymnasium smooths heights with 0.33*(sum of 3 neighbours), not 1/3,
    # so the physical ground there is 3.30 while helipad_y is 3.333; the terrain returned is the real edge.
    assert on_pad and max(on_pad) - min(on_pad) < 1e-9
    assert abs(on_pad[0] - 0.99 * pad["y"]) < 1e-9
    o = a["obs_to_world"]
    env = make_env()
    obs, _ = env.reset(seed=20_000)
    lander = env.unwrapped.lander.position
    assert abs(obs[0] * o["x_scale"] + o["x_offset"] - lander[0]) < 1e-4
    assert abs(obs[1] * o["y_scale"] + o["y_offset"] - lander[1]) < 1e-4
    env.close()
