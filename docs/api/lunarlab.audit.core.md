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

The original reward, every term output and the training reward must be finite. A NaN or infinite value
raises :class:`~lunarlab.audit.contracts.NonFiniteValueError` naming its source and ends the episode:
the wrapper refuses further steps until the next reset, so a partly accounted episode is never
completed or summarised.

`RewardAccountingWrapper(env: 'gym.Env', terms: 'Mapping[str, RewardTerm] | None' = None, *, gamma: 'float', original_weight: 'float' = 1.0, apply: 'bool' = True, adapter: 'TaskAdapter | None' = None) -> 'None'`

- method `reset(self, *, seed: 'int | None' = None, options: 'dict[str, Any] | None' = None)`: Reset and start a new episode audit.
- method `step(self, action)`: Step, compute every term for (s, a, s'), record all components, and return the training reward

### class `RewardTerm`

A named, pure reward term. ``describe`` (JSON-serialisable) identifies it in provenance records.

``term_id`` and ``version`` name the term's implementation for provenance records, and ``components``
lists any further callables its result depends on (a predicate or a potential), so their source files
can be recorded too (:func:`lunarlab.audit.provenance.reward_provenance`). None of the three enters
:func:`terms_hash`. Every output must be a finite real number: NaN or infinity raises
:class:`~lunarlab.audit.contracts.NonFiniteValueError` naming the term.

`RewardTerm(name: 'str', fn: 'Callable[[Transition], float]', describe: 'Mapping[str, Any]', term_id: 'str | None' = None, version: 'str | None' = None, components: 'tuple[Callable, ...]' = ()) -> None`


### class `Transition`

One environment step (s, a, r_original, s'), with the episode-ending flags.

`Transition(obs: 'np.ndarray', action: 'Any', original_reward: 'float', next_obs: 'np.ndarray', terminated: 'bool', truncated: 'bool') -> None`


### `per_step(name: 'str', value: 'float') -> 'RewardTerm'`

A constant added on every transition (e.g. a time penalty with ``value < 0``).

### `potential_shaping(name: 'str', potential: 'Callable[[np.ndarray], float]', *, alpha: 'float', gamma: 'float', potential_id: 'str') -> 'RewardTerm'`

F(s, s') = alpha * (gamma * Phi(s') - Phi(s)) (Ng, Harada and Russell, 1999).

A true termination makes s' absorbing, so Phi(s') = 0; this includes a step on which the environment
reports both ``terminated`` and ``truncated``. A time-limit truncation alone is not a terminal state: the
real next observation is used, as in LunarLab's own implementation. With these conventions the
discounted sum of F over an episode of T transitions telescopes to
alpha * (gamma^T * Phi(s_T) - Phi(s_0)), with Phi(s_T) = 0 when the episode terminated. The identity
concerns that sum; it does not imply that a policy learned with a finite budget is unchanged.

### `rescore_transitions(transitions: 'list[Transition]', terms: 'Mapping[str, RewardTerm]', *, gamma: 'float', original_weight: 'float' = 1.0) -> 'dict[str, Any]'`

Apply a reward definition to a fixed sequence of transitions (a recorded trajectory).

Returns every step's original reward, term values and training reward, and the episode sums. This
answers what the definition pays for those transitions; it says nothing about the policy that training
under that definition would produce.

### `state_bonus(name: 'str', predicate: 'Callable[[np.ndarray], bool]', bonus: 'float', *, predicate_id: 'str') -> 'RewardTerm'`

``bonus`` when the *resulting* state satisfies ``predicate``. A bonus that does not telescope can be
exploited: LunarLab's flawed hover bonus is this shape.

### `termination_bonus(name: 'str', bonus: 'float') -> 'RewardTerm'`

``bonus`` on the transition that ends an episode by a true termination (``terminated``).

It is also paid when that step reports ``truncated`` as well, and never for a time-limit truncation
alone. Where termination means failure (CartPole-v1) this pays for failing: a deliberately flawed
design for audit studies.

### `terms_hash(terms: 'Mapping[str, RewardTerm]', original_weight: 'float') -> 'str'`

Schema-0 hash of a declared reward definition: the first 16 hex characters of SHA-256.

It covers the term descriptions and the original reward's weight, not the code of the term callables:
two terms with equal descriptions and different functions have equal hashes. Its value for a valid
definition is unchanged from earlier records. Descriptions containing NaN, infinity or values that are
not JSON are refused, naming the term. New records also carry the full-digest, versioned record of
:func:`lunarlab.audit.provenance.reward_provenance`.

## Constants

- `TYPE_CHECKING` = `False`
