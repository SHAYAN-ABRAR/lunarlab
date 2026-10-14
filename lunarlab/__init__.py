"""LunarLab — Reward Shaping Mission Control.

A local-first toolkit for running honest reward-design experiments on
Gymnasium's ``LunarLander-v3`` (discrete actions) with Stable-Baselines3 PPO.

The package is usable without the web application:

* ``lunarlab.env``        environment construction + read-only internals adapter
* ``lunarlab.rewards``    reward configuration schema, pure term functions, wrapper
* ``lunarlab.outcomes``   terminal-outcome classification and the hover detector
* ``lunarlab.training``   PPO training with checkpoints, validation and stop/resume
* ``lunarlab.evaluation`` evaluation with the unmodified environment reward
* ``lunarlab.recording``  video + telemetry recording of real episodes
* ``lunarlab.rescoring``  re-scoring saved trajectories under other reward configs
* ``lunarlab.cli``        ``python -m lunarlab ...``
"""

__version__ = "0.1.0"
