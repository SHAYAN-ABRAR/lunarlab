# `lunarlab.tuning`

Source: [`lunarlab/tuning.py`](../../lunarlab/tuning.py)

Automatic tuning with Optuna: algorithm hyperparameters and reward weights, on validation only.

A *study* searches a bounded space for one algorithm and one reward preset:

* every trial is a normal LunarLab run (marked ``tuning`` in its metadata) trained with the sampled
  settings for ``trial_transitions`` transitions and the same training seed as every other trial of the
  study (common random numbers: differences come from the settings);
* the run's periodic validations (default physics, the protocol's validation seeds, original reward) are
  reported to Optuna; after a warm-up, a median pruner may stop trials that fall behind;
* a trial's value is its best validation mean original return, the same criterion that selects a run's
  checkpoint. Trial runs are **never** evaluated on the final-test seeds (``evaluate_run`` refuses);
  ``apply_best`` creates fresh, normal runs from the best settings, and only those are final-tested.

Studies persist in ``data/tuning/<study_id>/`` (``study.json``, ``optuna.sqlite3``, ``status.json``) and
can be resumed; cancelling stops the running trial at its next safe boundary.

### class `TuningCancelled`(Exception)

`TuningCancelled(...)`


### class `TuningError`(RuntimeError)

`TuningError(...)`


### `allowed_params(algo: 'str', preset_name: 'str') -> 'list[str]'`

### `apply_best(study_id: 'str', *, seeds: 'list[int]', profile: 'str' = 'standard', experiment_name: 'str | None' = None, protocol=None) -> 'dict[str, Any]'`

Create normal (not tuning) runs with the best trial's settings, ready to train and final-test.

### `build_configs(spec: 'dict[str, Any]', values: 'dict[str, Any]') -> 'tuple[PPOConfig, DQNConfig | None, RewardConfig]'`

The algorithm settings and reward of a parameter assignment (applied over the study's base).

### `cancel_file(study_id: 'str') -> 'Path'`

### `create_study(*, name: 'str', algo: 'str' = 'ppo', preset_name: 'str' = 'baseline', params: 'list[str] | None' = None, n_trials: 'int' = 20, trial_transitions: 'int' = 200000, validation_every: 'int' = 25000, warmup_transitions: 'int | None' = None, startup_trials: 'int' = 4, sampler_seed: 'int' = 0, training_seed: 'int' = 900, base_ppo: 'dict | None' = None, base_dqn: 'dict | None' = None) -> 'dict[str, Any]'`

Define and persist a study. Nothing trains until ``run_study``.

### `list_studies() -> 'list[dict[str, Any]]'`

### `load_spec(study_id: 'str') -> 'dict[str, Any]'`

### `request_cancel(study_id: 'str') -> 'dict[str, Any]'`

Stop the study: the running trial stops at its next safe boundary; the study can be resumed.

### `run_study(study_id: 'str', *, n_trials: 'int | None' = None, timeout_s: 'float | None' = None, should_stop: 'Callable[[], bool] | None' = None, echo: 'Callable[[str], None]' = <built-in function print>) -> 'dict[str, Any]'`

Run (or resume) a study until its trial budget, the timeout, or a cancel request.

### `study_dir(study_id: 'str') -> 'Path'`

### `study_summary(study_id: 'str') -> 'dict[str, Any]'`

### `tuning_dir() -> 'Path'`

## Constants

- `DEFAULT_PARAMS` = `{'ppo': ['ppo.learning_rate', 'ppo.ent_coef', 'ppo.gae_lambda'], 'dqn': ['dqn.learning_rate', 'dqn.exploration_fraction'…`
- `DEFAULT_TRAINING_SEED` = `900`
- `OBJECTIVE` = `'best validation mean original return (default physics, validation seeds)'`
- `REWARD_PARAMS` = `{'baseline': [], 'time-penalty': ['reward.time_penalty.cost_per_step'], 'hover-bonus': ['reward.hover_bonus.bonus_per_st…`
- `SPACE` = `{'ppo.learning_rate': {'type': 'float', 'low': 0.0001, 'high': 0.001, 'log': True}, 'ppo.ent_coef': {'type': 'float', 'l…`
