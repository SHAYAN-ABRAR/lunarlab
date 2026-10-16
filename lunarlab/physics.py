"""Training under varied physics: per-episode wind, turbulence and gravity.

``PhysicsRandomizer`` sits directly on the LunarLander environment (below the reward wrapper).
Before each reset it draws the next episode's physics from ``PhysicsRandomization`` and sets them on
the unwrapped environment; Gymnasium reads gravity when the episode's world is created and wind /
turbulence at every step, and draws the terrain and initial push before the wind phase, so the
episode seed still fixes the terrain. The draw is reported in ``info["lunarlab_physics"]`` at reset
and on the final step, and the reward wrapper copies it into the episode summary.

Its generator is seeded from the episode seed of the worker's first reset (the run's recorded
worker seed), then continues across the auto-resets of the vector environment, so a run's sequence
of physics is reproducible.
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np

from lunarlab.config import PhysicsRandomization

PHYSICS_FIELDS = ("wind", "wind_power", "turbulence_power", "gravity")
_STREAM = 0x5EED_9A75  # separates this generator from every other use of the worker seed


def sample_physics(config: PhysicsRandomization, rng: np.random.Generator) -> dict[str, Any]:
    wind = bool(rng.random() < config.wind_probability)
    wind_power = float(rng.uniform(*config.wind_power))
    turbulence = float(rng.uniform(*config.turbulence_power))
    gravity = float(rng.uniform(*config.gravity))
    return {
        "wind": wind,
        "wind_power": wind_power if wind else 0.0,
        "turbulence_power": turbulence if wind else 0.0,
        "gravity": gravity,
    }


def apply_physics(env: gym.Env, physics: dict[str, Any]) -> None:
    u = env.unwrapped
    u.enable_wind = bool(physics["wind"])
    u.wind_power = float(physics["wind_power"])
    u.turbulence_power = float(physics["turbulence_power"])
    u.gravity = float(physics["gravity"])


class PhysicsRandomizer(gym.Wrapper):
    def __init__(self, env: gym.Env, config: PhysicsRandomization) -> None:
        super().__init__(env)
        self.config = config
        self._rng: np.random.Generator | None = None
        self.current: dict[str, Any] | None = None

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        if seed is not None or self._rng is None:
            self._rng = np.random.default_rng([_STREAM, int(seed) if seed is not None else 0])
        self.current = sample_physics(self.config, self._rng)
        apply_physics(self.env, self.current)
        obs, info = self.env.reset(seed=seed, options=options)
        info["lunarlab_physics"] = dict(self.current)
        return obs, info

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        if terminated or truncated:
            info["lunarlab_physics"] = dict(self.current or {})
        return obs, reward, terminated, truncated, info
