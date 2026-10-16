"""Policies that can fly the lander: random, heuristic, and trained PPO.

Trained policies are loaded **without unpickling**. SB3 checkpoints contain a
``data`` entry with cloudpickled Python objects; LunarLab never reads it. It
rebuilds the network from the run's own ``config.yaml`` and loads only the
tensor state (``torch.load(weights_only=True)`` via SB3's
``load_from_zip_file(load_data=False)``). Checkpoints are also only accepted
from a run's manifest, where their SHA-256 was recorded at save time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import gymnasium as gym
import numpy as np


class Policy(Protocol):
    kind: str  # "random" | "heuristic" | "ppo"
    label: str

    def reset(self, episode_seed: int) -> None: ...
    def act(self, obs: np.ndarray) -> int: ...


@dataclass
class RandomPolicy:
    """Uniform random actions from a seeded generator (seed recorded with the episode)."""

    action_seed: int = 0
    kind: str = "random"
    label: str = "RANDOM — uniform random actions"

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng(self.action_seed)

    def reset(self, episode_seed: int) -> None:
        self._rng = np.random.default_rng([self.action_seed, episode_seed])

    def act(self, obs: np.ndarray) -> int:
        return int(self._rng.integers(0, 4))


class HeuristicPolicy:
    """Gymnasium's hand-coded controller (``lunar_lander.heuristic``). Not learned."""

    kind = "heuristic"
    label = "HEURISTIC — Gymnasium's hand-coded controller (not trained PPO)"

    def __init__(self, env: gym.Env) -> None:
        from gymnasium.envs.box2d.lunar_lander import heuristic

        self._heuristic = heuristic
        self._env = env.unwrapped

    def reset(self, episode_seed: int) -> None:
        pass

    def act(self, obs: np.ndarray) -> int:
        return int(self._heuristic(self._env, obs))


def build_policy_network(ppo_cfg, observation_space, action_space, *, algo: str = "ppo", dqn_cfg=None):
    """Construct a network matching SB3's ``MlpPolicy`` for our config (PPO actor-critic or DQN Q-net)."""
    import torch.nn as nn
    from stable_baselines3.common.policies import ActorCriticPolicy

    if algo == "dqn":
        from stable_baselines3.dqn.policies import DQNPolicy

        return DQNPolicy(
            observation_space,
            action_space,
            lr_schedule=lambda _: dqn_cfg.learning_rate,
            net_arch=list(dqn_cfg.net_arch),
        )
    act = {"tanh": nn.Tanh, "relu": nn.ReLU}[ppo_cfg.activation]
    return ActorCriticPolicy(
        observation_space,
        action_space,
        lr_schedule=lambda _: ppo_cfg.learning_rate,
        net_arch={"pi": list(ppo_cfg.net_arch_pi), "vf": list(ppo_cfg.net_arch_vf)},
        activation_fn=act,
    )


def load_policy_weights(
    path: Path, ppo_cfg, observation_space, action_space, *, algo: str = "ppo", dqn_cfg=None
):
    """Load a checkpoint's policy tensors into a freshly built network (no unpickling)."""
    import torch
    from stable_baselines3.common.save_util import load_from_zip_file

    _, params, _ = load_from_zip_file(str(path), load_data=False, device="cpu")
    if not params or "policy" not in params:
        raise ValueError(f"{path.name} does not contain policy parameters")
    net = build_policy_network(ppo_cfg, observation_space, action_space, algo=algo, dqn_cfg=dqn_cfg)
    net.load_state_dict(params["policy"])
    net.set_training_mode(False)
    net.to(torch.device("cpu"))
    return net


class SB3Policy:
    """A trained SB3 network (PPO actor-critic or DQN Q-network) acting greedily or stochastically."""

    kind = "ppo"

    def __init__(self, network, *, deterministic: bool = True, label: str = "PPO", kind: str = "ppo") -> None:
        self.kind = kind
        self.network = network
        self.deterministic = deterministic
        self.label = label

    def reset(self, episode_seed: int) -> None:
        pass

    def act(self, obs: np.ndarray) -> int:
        action, _ = self.network.predict(obs, deterministic=self.deterministic)
        return int(np.asarray(action).item())

    def diagnostics(self, obs: np.ndarray) -> dict:
        """What the network computes for ``obs``, separately from choosing the action: PPO's action
        probabilities, their entropy (nats) and the critic's state value; DQN's Q-values."""
        import torch

        with torch.no_grad():
            obs_t, _ = self.network.obs_to_tensor(obs)
            if self.kind == "dqn":
                q = self.network.q_net(obs_t)[0].cpu().numpy()
                return {"q": [round(float(v), 4) for v in q]}
            dist = self.network.get_distribution(obs_t)
            probs = dist.distribution.probs[0].cpu().numpy()
            return {
                "probs": [round(float(x), 5) for x in probs],
                "entropy": round(float(dist.entropy()[0]), 5),
                "value": round(float(self.network.predict_values(obs_t)[0, 0]), 4),
            }


PPOPolicy = SB3Policy  # backwards-compatible name
