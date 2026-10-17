# `lunarlab.audit.core`

Source: [`lunarlab/audit/core.py`](../../lunarlab/audit/core.py)

Task-independent reward accounting.

The invariant LunarLab is built on, for any Gymnasium environment::

    training_reward = original_weight * original_reward + sum(term(transition) for each reward term)

:class:`RewardAccountingWrapper` applies it to every transition and keeps the original reward, every
term and the training reward apart -- undiscounted and discounted -- so a policy can be trained on the
shaped reward while it is always judged by the original one. Reward terms are pure functions of one
:class:`Transition`; this module provides the three term shapes LunarLab's presets use (a per-step
constant, a bonus when the resulting state satisfies a predicate, and potential-based shaping).
Task knowledge (what an episode outcome means) comes from a :class:`~lunarlab.audit.adapters.TaskAdapter`.

### class `EpisodeAudit`

Per-episode sums. ``G = sum_t gamma^t r_t`` with t = 0 for the first transition after reset.

`EpisodeAudit(gamma: 'float', length: 'int' = 0, original_return: 'float' = 0.0, training_return: 'float' = 0.0, discounted_original_return: 'float' = 0.0, discounted_training_return: 'float' = 0.0, term_returns: 'dict[str, float]' = <factory>, term_discounted_returns: 'dict[str, float]' = <factory>, _discount: 'float' = 1.0) -> None`

- method `add(self, original: 'float', terms: 'Mapping[str, float]', training: 'float') -> 'None'`: Add one transition's original reward, term values and training reward.
- method `summary(self) -> 'dict[str, Any]'`: Length and returns (undiscounted and discounted; original, training and per term).

### class `RewardAccountingWrapper`(Wrapper)

Applies ``training = w * original + sum(terms)`` and records every component, for any environment.

``apply=True`` (training) returns the training reward; ``apply=False`` (evaluation) returns the
original reward unchanged and only records what the terms would have added. Observations, actions,
``terminated`` and ``truncated`` are never changed. On the last step of an episode,
``info["audit_episode"]`` holds the episode summary, including the adapter's outcome classification.

`RewardAccountingWrapper(env: 'gym.Env', terms: 'Mapping[str, RewardTerm] | None' = None, *, gamma: 'float', original_weight: 'float' = 1.0, apply: 'bool' = True, adapter: 'TaskAdapter | None' = None) -> 'None'`

- method `reset(self, *, seed: 'int | None' = None, options: 'dict[str, Any] | None' = None)`: Reset and start a new episode audit.
- method `step(self, action)`: Step, compute every term for (s, a, s'), record all components, and return the training reward

### class `RewardTerm`

A named, pure reward term. ``describe`` (JSON-serialisable) identifies it in provenance records.

`RewardTerm(name: 'str', fn: 'Callable[[Transition], float]', describe: 'Mapping[str, Any]') -> None`


### class `Transition`

One environment step (s, a, r_original, s'), with the episode-ending flags.

`Transition(obs: 'np.ndarray', action: 'Any', original_reward: 'float', next_obs: 'np.ndarray', terminated: 'bool', truncated: 'bool') -> None`


### `per_step(name: 'str', value: 'float') -> 'RewardTerm'`

A constant added on every transition (e.g. a time penalty with ``value < 0``).

### `potential_shaping(name: 'str', potential: 'Callable[[np.ndarray], float]', *, alpha: 'float', gamma: 'float', potential_id: 'str') -> 'RewardTerm'`

F(s, s') = alpha * (gamma * Phi(s') - Phi(s)) (Ng, Harada and Russell, 1999).

A true termination makes s' absorbing, so Phi(s') = 0. A time-limit truncation is not a terminal
state: the real next observation is used, as in LunarLab's own implementation. With these
conventions the discounted sum of F over an episode telescopes to alpha * (gamma^T * Phi(s_T) - Phi(s_0)),
with Phi(s_T) = 0 when the episode terminated.

### `state_bonus(name: 'str', predicate: 'Callable[[np.ndarray], bool]', bonus: 'float', *, predicate_id: 'str') -> 'RewardTerm'`

``bonus`` when the *resulting* state satisfies ``predicate``. A bonus that does not telescope can be
exploited: LunarLab's flawed hover bonus is this shape.

### `terms_hash(terms: 'Mapping[str, RewardTerm]', original_weight: 'float') -> 'str'`

Content hash of a reward definition (term descriptions and the original reward's weight).

## Constants

- `TYPE_CHECKING` = `False`
