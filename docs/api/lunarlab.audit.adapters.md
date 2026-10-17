# `lunarlab.audit.adapters`

Source: [`lunarlab/audit/adapters.py`](../../lunarlab/audit/adapters.py)

Task adapters: what the task-independent audit layer needs to know about one environment.

A :class:`TaskAdapter` supplies the environment factory, observation and action labels, the task's own
episode-outcome definition, the reward terms that make sense for it, optional per-episode diagnostics and
evaluation metrics. Nothing task-specific lives in :mod:`lunarlab.audit.core`.

Two adapters ship with LunarLab:

* ``lunarlander`` -- built from LunarLab's existing functions (environment factory, strict pad-landing
  classification, hover detector, the presets' reward terms), so it behaves exactly like the main pipeline.
* ``cartpole`` -- Gymnasium's ``CartPole-v1`` with its own outcome definition (pole fell, cart left the
  track, or balanced until the time limit). It demonstrates the extension contract; it is not part of the
  published LunarLander study.

### class `EpisodeEnd`

What an adapter's outcome classifier sees at the end of an episode.

`EpisodeEnd(env: 'gym.Env', observations: 'np.ndarray', terminated: 'bool', truncated: 'bool', info: 'Mapping[str, Any]') -> None`


### class `TaskAdapter`

Everything task-specific. ``classify`` must return ``{"outcome": <one of outcome_categories>, ...}``.

`TaskAdapter(name: 'str', version: 'str', env_id: 'str', env_kwargs: 'Mapping[str, Any]', observation_labels: 'tuple[str, ...]', action_labels: 'tuple[str, ...]', outcome_categories: 'tuple[str, ...]', classify: 'Callable[[EpisodeEnd], dict[str, Any]]', term_factories: 'Mapping[str, Callable[..., RewardTerm]]' = <factory>, diagnostics: 'Mapping[str, Callable[[np.ndarray], Any]]' = <factory>, metrics: 'Mapping[str, Callable[[list[dict]], float | None]]' = <factory>, factory: 'Callable[..., gym.Env] | None' = None) -> None`

- method `make_env(self, **kwargs) -> 'gym.Env'`: Create the task's environment (``factory``, or ``gym.make(env_id, **env_kwargs)``).
- method `term(self, name: 'str', **params) -> 'RewardTerm'`: Build one of the task's named reward terms with the given parameters.

### `adapter_names() -> 'list[str]'`

Names of the registered task adapters.

### `cartpole_adapter() -> 'TaskAdapter'`

CartPole-v1 with its own outcome definition: pole fell, cart left the track, or balanced to the time limit.

### `get_adapter(name: 'str') -> 'TaskAdapter'`

Build the registered task adapter ``name``.

### `lunar_lander_adapter() -> 'TaskAdapter'`

LunarLander-v3 with LunarLab's own outcome classifier, hover detector and preset reward terms.

### `rate(outcome: 'str') -> 'Callable[[list[dict]], float | None]'`

Metric factory: the fraction of episodes with this outcome.

### `register_adapter(name: 'str', build: 'Callable[[], TaskAdapter]') -> 'None'`

Register an adapter factory under ``name`` (overwriting an existing registration is refused).

## Constants

- `CARTPOLE_OUTCOMES` = `('balanced_to_time_limit', 'pole_fell', 'cart_left_track', 'unknown')`
