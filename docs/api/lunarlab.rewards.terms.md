# `lunarlab.rewards.terms`

Source: [`lunarlab/rewards/terms.py`](../../lunarlab/rewards/terms.py)

Pure reward-term functions. No environment access, no state.

Every function here is a deterministic function of observations, the action,
the episode-ending flags and the configuration. The wrapper used for training,
the evaluation code and the trajectory re-scorer all call these same functions,
so there is exactly one implementation of each reward term.

### `compute_terms(obs: 'np.ndarray', action: 'int', next_obs: 'np.ndarray', *, terminated: 'bool', truncated: 'bool', config: 'RewardConfig', gamma: 'float', learned_model=None) -> 'dict[str, float]'`

Additional reward terms for one transition (s, a, s').

Returns only the *enabled* terms. The original environment reward is not
included here; the caller adds it:
training = original_weight * original + sum(terms).
``learned_model`` is required when the learned-reward term is enabled.

### `potential(obs: 'np.ndarray', w: 'PotentialWeights') -> 'float'`

Bounded state-only potential, Phi(s) <= 0 with Phi = 0 only at the ideal state.

Phi(s) = -( wx*tanh|x| + wy*tanh|y| + wv*tanh(hypot(vx, vy)) + wa*tanh|angle| + ww*tanh|omega| )

### `potential_shaping(obs: 'np.ndarray', next_obs: 'np.ndarray', *, terminated: 'bool', alpha: 'float', gamma: 'float', weights: 'PotentialWeights') -> 'float'`

F(s, s') = alpha * (gamma * Phi(s') - Phi(s)).

* True termination: s' is absorbing, so Phi(s') is taken as 0.
* Time-limit truncation (``terminated=False``): the episode was cut, not
  finished. The real final observation is used for Phi(s'), matching SB3,
  which bootstraps the value of that same observation.

### `training_reward(original: 'float', terms: 'dict[str, float]', original_weight: 'float' = 1.0) -> 'float'`

The invariant: training_reward = original_weight * original_reward + sum(additional terms).
