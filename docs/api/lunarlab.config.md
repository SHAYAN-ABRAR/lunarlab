# `lunarlab.config`

Source: [`lunarlab/config.py`](../../lunarlab/config.py)

Run configuration: PPO settings, budget profiles, evaluation protocol.

Defaults for PPO follow RL Baselines3 Zoo's ``LunarLander-v3`` entry
(hyperparams/ppo.yml: n_steps 1024, batch 64, gae_lambda 0.98, gamma 0.999,
n_epochs 4, ent_coef 0.01, 1e6 steps) with one laptop adaptation:
``n_envs = 4`` instead of 16, so each update uses 4 096 transitions instead of
16 384. These are starting settings, not a promise of solving the task. They
are identical across the primary reward comparisons.

### class `DQNConfig`(_Strict)

DQN settings: RL Baselines3 Zoo's LunarLander-v3 entry (hyperparams/dqn.yml).

Zoo tunes these for a 1e5-transition budget, and that is the budget the comparison study
uses: DQN's update-per-4-steps schedule makes it about 20x slower per transition than PPO
on CPU, so equal-experience runs (1e6) would take hours each. Budgets therefore differ
between the algorithms; comparisons report it.

| Field | Type | Default | Description |
|---|---|---|---|
| `n_envs` | `int` | `1` |  |
| `learning_rate` | `float` | `0.00063` |  |
| `batch_size` | `int` | `128` |  |
| `buffer_size` | `int` | `50000` |  |
| `learning_starts` | `int` | `0` |  |
| `gamma` | `float` | `0.99` |  |
| `target_update_interval` | `int` | `250` |  |
| `train_freq` | `int` | `4` |  |
| `gradient_steps` | `int` | `-1` |  |
| `exploration_fraction` | `float` | `0.12` |  |
| `exploration_final_eps` | `float` | `0.1` |  |
| `net_arch` | `list[int]` | `factory` |  |

- method `compatibility_key(self) -> 'dict'`: Settings that must match for a resume or a fair comparison.
- property `rollout_size`: Transitions collected between updates (``train_freq * n_envs``).

### class `EvalProtocol`(_Strict)

Everything that defines how a policy is measured. Persisted with every evaluation.

Seeds are strict integers (``True``, ``"7"`` or ``3.0`` are refused, never coerced). Semantic rules
(distinct seeds, disjoint validation and test lists, the supported range, the one supported
environment) are reported by :meth:`problems` instead of failing at load time, so historical
artifacts with an invalid protocol can still be opened and inspected; :meth:`require_valid` refuses
such a protocol for any new run, training segment or evaluation.

| Field | Type | Default | Description |
|---|---|---|---|
| `protocol_id` | `str` | `'lunarlab-eval-v1'` |  |
| `env_id` | `str` | `'LunarLander-v3'` |  |
| `env_kwargs` | `dict` | `factory` |  |
| `validation_seeds` | `list[Annotated[int, Strict(strict=True)]]` | `factory` |  |
| `test_seeds` | `list[Annotated[int, Strict(strict=True)]]` | `factory` |  |
| `deterministic` | `bool` | `True` |  |
| `score_threshold` | `float` | `200.0` |  |
| `hover_detector` | `HoverThresholds` | `factory` |  |
| `sustained_hover_min_steps` | `int` | `100` |  |
| `pad_landing` | `PadLandingCriteria` | `factory` |  |
| `ci_level` | `float` | `0.95` |  |
| `bootstrap_resamples` | `int` | `5000` |  |
| `bootstrap_seed` | `int` | `0` |  |

- method `problems(self) -> 'list[str]'`: Why this protocol cannot be used for new work (empty when it is valid).
- method `protocol_hash(self) -> 'str'`: Content hash of the whole protocol (seeds, environment, criteria, statistics settings).
- method `require_valid(self) -> 'None'`: Raise :class:`ProtocolError` if :meth:`problems` reports anything.
- method `seeds_for(self, split: 'str') -> 'list[int]'`: The ``validation`` or ``test`` seed list.

### class `PPOConfig`(_Strict)

PPO hyperparameters (LunarLab's LunarLander-v3 defaults), validated: whole minibatches, bounded network sizes.

| Field | Type | Default | Description |
|---|---|---|---|
| `n_envs` | `int` | `4` |  |
| `n_steps` | `int` | `1024` |  |
| `batch_size` | `int` | `64` |  |
| `learning_rate` | `float` | `0.0003` |  |
| `gamma` | `float` | `0.999` |  |
| `gae_lambda` | `float` | `0.98` |  |
| `n_epochs` | `int` | `4` |  |
| `ent_coef` | `float` | `0.01` |  |
| `vf_coef` | `float` | `0.5` |  |
| `clip_range` | `float` | `0.2` |  |
| `max_grad_norm` | `float` | `0.5` |  |
| `net_arch_pi` | `list[int]` | `factory` |  |
| `net_arch_vf` | `list[int]` | `factory` |  |
| `activation` | `Literal['tanh', 'relu']` | `'tanh'` |  |

- method `compatibility_key(self) -> 'dict'`: Settings that must match for a resume or a fair comparison.
- property `rollout_size`: Transitions collected per rollout (``n_envs * n_steps``).

### class `PhysicsRandomization`(_Strict)

Per-episode variation of wind, turbulence and gravity while TRAINING (off by default).

Before every training episode, the physics are drawn from these ranges by a generator seeded
from that worker's episode seed, so a run is reproducible. An episode has wind with probability
``wind_probability``; wind and turbulence strengths are then uniform in their ranges (both are 0
without wind). Gravity is uniform in its range for every episode. Validation (checkpoint
selection) and the final test always use default physics, for every run.

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | `bool` | `False` |  |
| `wind_probability` | `float` | `0.8` |  |
| `wind_power` | `tuple[float, float]` | `(0.0, 10.0)` |  |
| `turbulence_power` | `tuple[float, float]` | `(0.0, 1.0)` |  |
| `gravity` | `tuple[float, float]` | `(-11.0, -9.0)` |  |

- method `describe(self) -> 'str'`: One-line description of the ranges.

### class `ProtocolError`(ValueError)

An evaluation protocol that must not be used for new runs, training or evaluations.

`ProtocolError(...)`


### class `RunConfig`(_Strict)

Everything that defines a training run: reward, algorithm settings, budget, seed, evaluation protocol,
physics and warm start. :meth:`config_hash` excludes identity and labels.

| Field | Type | Default | Description |
|---|---|---|---|
| `schema_version` | `Literal[1]` | `1` |  |
| `run_id` | `str` | `required` |  |
| `experiment_id` | `str | None` | `None` |  |
| `label` | `str` | `''` |  |
| `created_at` | `str` | `required` |  |
| `env_id` | `str` | `'LunarLander-v3'` |  |
| `env_kwargs` | `dict` | `factory` |  |
| `reward` | `RewardConfig` | `required` |  |
| `reward_config_id` | `str | None` | `None` |  |
| `reward_revision` | `int | None` | `None` |  |
| `ppo` | `PPOConfig` | `factory` |  |
| `training` | `TrainingConfig` | `factory` |  |
| `seed` | `int` | `0` |  |
| `eval_protocol` | `EvalProtocol` | `factory` |  |
| `algo` | `Literal['ppo', 'dqn']` | `'ppo'` |  |
| `dqn` | `lunarlab.config.DQNConfig | None` | `None` |  |
| `physics` | `PhysicsRandomization` | `factory` |  |
| `warm_start` | `lunarlab.config.WarmStart | None` | `None` |  |

- method `algo_settings(self) -> 'dict'`: The active algorithm's settings as a dict.
- method `config_hash(self) -> 'str'`: Hash of everything that defines the experiment (excluding identity and labels).
- property `gamma`: The algorithm's discount (potential-based shaping uses the same value).
- property `n_envs`: Number of training environments of the active algorithm.
- property `planned_transitions`: The requested budget rounded up to whole rollouts (what training will actually run).
- property `requested_transitions`: The requested training budget.
- property `rollout_size`: Transitions per rollout of the active algorithm.
- method `worker_seeds(self, segment: 'int' = 0) -> 'list[int]'`: Training-environment seeds of a segment: base + 1000 * seed + 100 * segment + rank, disjoint from

### class `TrainingConfig`(_Strict)

Budget and cadence of a training run: transitions, checkpoint and validation intervals, vector
environment, device and torch threads.

| Field | Type | Default | Description |
|---|---|---|---|
| `profile` | `Literal['smoke', 'standard', 'extended', 'custom']` | `'smoke'` |  |
| `total_transitions` | `int` | `8192` |  |
| `checkpoint_every` | `int` | `4096` |  |
| `validation_every` | `int` | `4096` |  |
| `vec_env` | `Literal['dummy', 'subproc']` | `'dummy'` |  |
| `device` | `Literal['cpu', 'cuda', 'auto']` | `'cpu'` |  |
| `torch_threads` | `int` | `1` |  |


### class `WarmStart`(_Strict)

A warm restart: a NEW run whose networks (and optimizer state) start from another run's checkpoint.

It is not a continuation of that run. Everything else (replay buffer, counters, exploration schedule,
environment state, random-number streams) starts fresh; ``metadata.json -> lineage`` lists both.

| Field | Type | Default | Description |
|---|---|---|---|
| `parent_run_id` | `str` | `required` |  |
| `checkpoint` | `str` | `required` |  |
| `checkpoint_sha256` | `str` | `required` |  |
| `parent_config_hash` | `str` | `required` |  |


### `actual_budget(requested: 'int', rollout_size: 'int') -> 'int'`

PPO always completes whole rollouts, so it rounds the budget up.

### `resume_compatibility(saved: 'RunConfig', requested: 'RunConfig') -> 'list[str]'`

Reasons a checkpoint of ``saved`` cannot continue as ``requested`` (empty = compatible).

### `training_for_profile(profile: 'str', *, total_transitions: 'int | None' = None, **overrides) -> 'TrainingConfig'`

Build a TrainingConfig from a named profile. A changed budget is labelled ``custom``.

## Constants

- `CONFIG_SCHEMA_VERSION` = `1`
- `DEFAULT_DETECTOR` = `HoverThresholds(min_height=0.1, max_height=1.6, max_abs_angle_rad=0.35, max_abs_vx=0.1, max_abs_vy=0.1, max_abs_angular_…`
- `ENV_ID` = `'LunarLander-v3'`
- `ENV_KWARGS` = `{'continuous': False}`
- `EVAL_SEED_MAX` = `999999`
- `PROFILES` = `{'smoke': {'total_transitions': 8192, 'checkpoint_every': 4096, 'validation_every': 4096, 'label': 'SMOKE — technical pi…`
- `TEST_SEEDS` = `(20000, 20001, 20002, 20003, 20004, 20005, 20006, 20007, 20008, 20009, 20010, 20011, 20012, 20013, 20014, 20015, 20016, …`
- `TRAIN_WORKER_SEED_BASE` = `1000000`
- `VALIDATION_SEEDS` = `(10000, 10001, 10002, 10003, 10004, 10005, 10006, 10007, 10008, 10009)`
