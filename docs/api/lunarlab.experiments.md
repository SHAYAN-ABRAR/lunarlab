# `lunarlab.experiments`

Source: [`lunarlab/experiments.py`](../../lunarlab/experiments.py)

Experiments: named groups of runs meant to be compared (e.g. presets x seeds).

Stored as ``data/experiments/<experiment_id>.json``. An experiment is rewards x variants x seeds.
A *variant* fixes the algorithm, its discount factor and the training physics; by default there is
one variant (the chosen algorithm with its reference settings and default physics), which is how
every earlier experiment was built. All runs share the budget, checkpoint/validation cadence and
evaluation protocol by construction. With several algorithms, the budget is rounded up to a
multiple of every algorithm's rollout, so they train on exactly the same number of transitions.

### `build_variants(*, algos: 'list[str] | None' = None, physics: 'str' = 'fixed', physics_config: 'PhysicsRandomization | None' = None, gammas: 'list[float] | None' = None) -> 'list[dict[str, Any]]'`

Every combination of algorithm x discount factor x training physics.

### `create_experiment(*, name: 'str', presets: 'list[str] | None' = None, rewards: 'list[RewardConfig] | None' = None, seeds: 'list[int]', profile: 'str', description: 'str' = '', n_envs: 'int | None' = None, algo: 'str' = 'ppo', training_overrides: 'dict | None' = None, variants: 'list[dict[str, Any]] | None' = None, ppo_overrides: 'dict | None' = None, dqn_overrides: 'dict | None' = None, protocol: 'EvalProtocol | None' = None) -> 'dict[str, Any]'`

``ppo_overrides`` / ``dqn_overrides`` replace the reference settings for every run (e.g. the best
settings of a tuning study); a variant's discount factor still takes precedence. ``protocol`` sets
another evaluation protocol for every run, e.g. a holdout with test seeds never used before.

### `experiments_dir()`

### `list_experiments() -> 'list[dict[str, Any]]'`

### `load_experiment(experiment_id: 'str') -> 'dict[str, Any]'`

### `matched_overrides(profile: 'str', variants: 'list[dict[str, Any]]', n_envs: 'int | None', overrides: 'dict | None') -> 'dict'`

With several algorithms, round the budget up so every one completes whole rollouts at the
same transition count (matched budgets).

### `plan_suite(presets: 'list[str]', seeds: 'list[int]', profile: 'str', *, n_envs: 'int | None' = None, throughput_tps: 'float | None' = None, algo: 'str' = 'ppo', training_overrides: 'dict | None' = None, variants: 'list[dict[str, Any]] | None' = None) -> 'dict[str, Any]'`

## Constants

- `LARGE_SUITE_RUNS` = `6`
- `PHYSICS_VARIANTS` = `{'fixed': [False], 'randomized': [True], 'both': [False, True]}`
