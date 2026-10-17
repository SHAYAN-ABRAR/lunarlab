# `lunarlab.policies`

Source: [`lunarlab/policies.py`](../../lunarlab/policies.py)

Policies that can fly the lander: random, heuristic, and trained PPO.

Trained policies are loaded **without unpickling**. SB3 checkpoints contain a
``data`` entry with cloudpickled Python objects; LunarLab never reads it. It
rebuilds the network from the run's own ``config.yaml`` and loads only the
tensor state (``torch.load(weights_only=True)`` via SB3's
``load_from_zip_file(load_data=False)``). Checkpoints are also only accepted
from a run's manifest, where their SHA-256 was recorded at save time.

### class `HeuristicPolicy`

Gymnasium's hand-coded controller (``lunar_lander.heuristic``). Not learned.

`HeuristicPolicy(env: 'gym.Env') -> 'None'`

- method `act(self, obs: 'np.ndarray') -> 'int'`
- method `reset(self, episode_seed: 'int') -> 'None'`

### class `PPOPolicy`

A trained SB3 network (PPO actor-critic or DQN Q-network) acting greedily or stochastically.

`PPOPolicy(network, *, deterministic: 'bool' = True, label: 'str' = 'PPO', kind: 'str' = 'ppo') -> 'None'`

- method `act(self, obs: 'np.ndarray') -> 'int'`
- method `diagnostics(self, obs: 'np.ndarray') -> 'dict'`: What the network computes for ``obs``, separately from choosing the action: PPO's action
- method `reset(self, episode_seed: 'int') -> 'None'`

### class `Policy`(Protocol)

`Policy(*args, **kwargs)`

- method `act(self, obs: 'np.ndarray') -> 'int'`
- method `reset(self, episode_seed: 'int') -> 'None'`

### class `RandomPolicy`

Uniform random actions from a seeded generator (seed recorded with the episode).

`RandomPolicy(action_seed: 'int' = 0, kind: 'str' = 'random', label: 'str' = 'RANDOM — uniform random actions') -> None`

- method `act(self, obs: 'np.ndarray') -> 'int'`
- method `reset(self, episode_seed: 'int') -> 'None'`

### class `SB3Policy`

A trained SB3 network (PPO actor-critic or DQN Q-network) acting greedily or stochastically.

`SB3Policy(network, *, deterministic: 'bool' = True, label: 'str' = 'PPO', kind: 'str' = 'ppo') -> 'None'`

- method `act(self, obs: 'np.ndarray') -> 'int'`
- method `diagnostics(self, obs: 'np.ndarray') -> 'dict'`: What the network computes for ``obs``, separately from choosing the action: PPO's action
- method `reset(self, episode_seed: 'int') -> 'None'`

### `build_policy_network(ppo_cfg, observation_space, action_space, *, algo: 'str' = 'ppo', dqn_cfg=None)`

Construct a network matching SB3's ``MlpPolicy`` for our config (PPO actor-critic or DQN Q-net).

### `load_policy_weights(path: 'Path', ppo_cfg, observation_space, action_space, *, algo: 'str' = 'ppo', dqn_cfg=None)`

Load a checkpoint's policy tensors into a freshly built network (no unpickling).
