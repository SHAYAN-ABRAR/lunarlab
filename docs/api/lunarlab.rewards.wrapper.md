# `lunarlab.rewards.wrapper`

Source: [`lunarlab/rewards/wrapper.py`](../../lunarlab/rewards/wrapper.py)

The single reward wrapper used for training, evaluation telemetry and recording.

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

### class `LunarLabRewardWrapper`(Wrapper)

Applies a reward configuration on top of LunarLander's original reward and records every component.

With ``apply=True`` (training) ``step`` returns ``original_weight * original + sum(terms)``; with ``apply=False``
(evaluation, recording) it returns the original reward and only records the terms. Observations, actions,
``terminated`` and ``truncated`` are never changed. The last step of each episode carries
``info["lunarlab_episode"]``: original and training returns (undiscounted, discounted and per term), the hover
detector's statistics and the outcome classification.

`LunarLabRewardWrapper(env: 'gym.Env', config: 'RewardConfig', gamma: 'float', *, apply: 'bool' = True, detector: 'HoverThresholds' = HoverThresholds(min_height=0.1, max_height=1.6, max_abs_angle_rad=0.35, max_abs_vx=0.1, max_abs_vy=0.1, max_abs_angular_velocity=None), pad_criteria: 'PadLandingCriteria | None' = None, record_steps: 'bool' = False, step_info: 'bool' = False, probe_internals: 'bool' = True) -> 'None'`

- method `reset(self, *, seed: 'int | None' = None, options: 'dict[str, Any] | None' = None)`: Reset the environment and start a new episode accumulator (nothing carries over between episodes).
- method `step(self, action)`: Step, compute the reward terms for (s, a, s'), record them, and return the training reward

## Constants

- `DEFAULT_DETECTOR` = `HoverThresholds(min_height=0.1, max_height=1.6, max_abs_angle_rad=0.35, max_abs_vx=0.1, max_abs_vy=0.1, max_abs_angular_…`
- `OUTCOME_CLASSIFIER_VERSION` = `2`
