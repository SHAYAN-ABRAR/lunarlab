# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Shared fixtures. Every test gets an isolated LunarLab home (no real data touched)."""

from __future__ import annotations

import gymnasium as gym
import numpy as np
import pytest
from gymnasium import spaces


@pytest.fixture(autouse=True)
def lab_home(tmp_path, monkeypatch):
    home = tmp_path / "lunarlab-home"
    home.mkdir()
    monkeypatch.setenv("LUNARLAB_HOME", str(home))
    return home


class ScriptedEnv(gym.Env):
    """Tiny deterministic env with LunarLander's observation/action shapes.

    Observations follow a fixed script; rewards are fixed per step; the episode
    terminates (or is truncated) at a chosen step. Used for exact reward math.
    """

    metadata = {"render_modes": []}

    def __init__(self, observations, rewards, *, terminate_at=None, truncate_at=None):
        super().__init__()
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(8,), dtype=np.float32)
        self.action_space = spaces.Discrete(4)
        self.obs = [np.asarray(o, dtype=np.float32) for o in observations]
        self.rewards = list(rewards)
        self.terminate_at = terminate_at
        self.truncate_at = truncate_at
        self.t = 0

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.t = 0
        return self.obs[0].copy(), {}

    def step(self, action):
        self.t += 1
        obs = self.obs[min(self.t, len(self.obs) - 1)].copy()
        r = float(self.rewards[min(self.t - 1, len(self.rewards) - 1)])
        terminated = self.terminate_at is not None and self.t >= self.terminate_at
        truncated = self.truncate_at is not None and self.t >= self.truncate_at and not terminated
        return obs, r, terminated, truncated, {}


def random_states(n: int, seed: int = 0) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        o = rng.uniform(-1.2, 1.2, size=8).astype(np.float32)
        o[6:] = rng.integers(0, 2, size=2)
        out.append(o)
    return out


@pytest.fixture
def scripted_env_factory():
    return ScriptedEnv
