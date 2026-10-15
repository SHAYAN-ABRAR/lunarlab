"""The single reward wrapper used for training, evaluation telemetry and recording.

Wrapper order used everywhere in LunarLab::

    LunarLander (unmodified reward, Box2D physics)
      └─ PassiveEnvChecker / OrderEnforcing   (added by gym.make)
         └─ TimeLimit(max_episode_steps=1000)  (added by gym.make; sets `truncated`)
            └─ LunarLabRewardWrapper            (this class)
               └─ stable_baselines3 Monitor     (training only)

What each layer observes:

* This wrapper receives the **original** reward from the environment. With
  ``apply=True`` (training) it returns ``original + sum(terms)`` to the layer
  above. With ``apply=False`` (evaluation) it returns the original reward
  unchanged and only *records* what the configured terms would have added.
* SB3's ``Monitor`` sits above this wrapper during training, so its
  ``ep_rew_mean`` is the **training (shaped) return**, not the original return.
  LunarLab therefore logs original and training returns separately from the
  ``info["lunarlab_episode"]`` summary emitted on the final step of each episode.

The wrapper never changes observations, actions, dynamics, ``terminated`` or
``truncated``.
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np

from lunarlab.env import decompose_builtin_reward, probe
from lunarlab.hover import DEFAULT_DETECTOR, HoverThresholds
from lunarlab.outcomes import PadLandingCriteria, classify_outcome
from lunarlab.rewards.accounting import EpisodeAccumulator
from lunarlab.rewards.config import RewardConfig
from lunarlab.rewards.terms import compute_terms, training_reward


class LunarLabRewardWrapper(gym.Wrapper):
    def __init__(
        self,
        env: gym.Env,
        config: RewardConfig,
        gamma: float,
        *,
        apply: bool = True,
        detector: HoverThresholds = DEFAULT_DETECTOR,
        pad_criteria: PadLandingCriteria | None = None,
        record_steps: bool = False,
        step_info: bool = False,
        probe_internals: bool = True,
    ) -> None:
        super().__init__(env)
        if not 0.0 < gamma <= 1.0:
            raise ValueError("gamma must be in (0, 1]")
        self.config = config
        self.gamma = float(gamma)
        self.apply = bool(apply)
        self.pad_criteria = pad_criteria or PadLandingCriteria()
        self.record_steps = record_steps
        self.step_info = step_info
        self.probe_internals = probe_internals
        self._acc = EpisodeAccumulator(gamma=self.gamma, detector=detector)
        self._acc.reset()
        self._prev_obs: np.ndarray | None = None
        self._needs_reset = True
        self.steps: list[dict[str, Any]] = []
        self.initial_obs: np.ndarray | None = None
        self.last_episode: dict[str, Any] | None = None
        self._config_hash = config.content_hash()
        self._learned = None
        if config.learned.enabled:
            from lunarlab.preferences.model import load_reward_model

            self._learned = load_reward_model(str(config.learned.model_id))

    # ------------------------------------------------------------------ #
    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        obs, info = self.env.reset(seed=seed, options=options)
        self._acc.reset()
        self._prev_obs = np.array(obs, dtype=np.float32, copy=True)
        self.initial_obs = self._prev_obs.copy()
        self.steps = []
        self._needs_reset = False
        return obs, info

    def step(self, action):
        if self._needs_reset or self._prev_obs is None:
            raise RuntimeError(
                "LunarLabRewardWrapper.step() called before reset() or after the episode ended"
            )
        a = int(action)
        obs, original, terminated, truncated, info = self.env.step(action)
        original = float(original)
        terms = compute_terms(
            self._prev_obs,
            a,
            obs,
            terminated=bool(terminated),
            truncated=bool(truncated),
            config=self.config,
            gamma=self.gamma,
            learned_model=self._learned,
        )
        shaped = training_reward(original, terms, self.config.original_weight)
        hovering = self._acc.add(original=original, terms=terms, training=shaped, action=a, next_obs=obs)

        info = dict(info)
        if self.step_info:
            info["lunarlab"] = {"original_reward": original, "terms": dict(terms), "training_reward": shaped}

        if self.record_steps:
            self.steps.append(
                {
                    "t": self._acc.length,
                    "action": a,
                    "obs": [float(v) for v in obs],
                    "original_reward": original,
                    "terms": dict(terms),
                    "training_reward": shaped,
                    "cum_original": self._acc.original_return,
                    "cum_training": self._acc.training_return,
                    "builtin": decompose_builtin_reward(self._prev_obs, obs, a, original, bool(terminated)),
                    "hover": hovering,
                    "terminated": bool(terminated),
                    "truncated": bool(truncated),
                }
            )

        if terminated or truncated:
            summary = self._acc.summary()
            summary["reward_applied"] = self.apply
            summary["reward_config_hash"] = self._config_hash
            if self.probe_internals:
                outcome = classify_outcome(
                    bool(terminated),
                    bool(truncated),
                    obs,
                    probe(self.env),
                    self.pad_criteria,
                    leg_contact_seen=summary["leg_contact_steps"] > 0,
                )
                summary.update(outcome.to_dict())
            else:
                summary.update(
                    {"env_outcome": "unknown", "terminated": bool(terminated), "truncated": bool(truncated)}
                )
            summary["final_obs"] = [float(v) for v in obs]
            info["lunarlab_episode"] = summary
            self.last_episode = summary
            self._needs_reset = True

        self._prev_obs = np.array(obs, dtype=np.float32, copy=True)
        return obs, (shaped if self.apply else original), terminated, truncated, info
