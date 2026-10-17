# `lunarlab.training`

Source: [`lunarlab/training.py`](../../lunarlab/training.py)

PPO training: checkpoints, validation-based selection, cooperative stop, resume.

Budgets are counted in **environment transitions** (``model.num_timesteps``,
which SB3 increments by ``n_envs`` per vector step), never in vector-step calls.
PPO completes whole rollouts, so the actual budget is rounded up to a multiple
of ``n_envs * n_steps`` and recorded.

Stopping is cooperative. The supervisor (or Ctrl+C in a terminal) creates
``control/stop_requested.json``; the callback notices within ~0.25 s. The safe
boundary is the start of a rollout, right after the previous update:

* PPO stops at once; the partially collected rollout is discarded (never trained
  on), counters roll back to the last update, and the discarded environment
  interactions are recorded in the segment (``discarded_interactions``).
* DQN stores every transition in its replay buffer as it goes and trains after
  each rollout of ``train_freq`` steps, so it keeps collecting until the current
  rollout is complete and trained on, and stops at the first step of the next
  one: that single step (one interaction per environment) is neither stored nor
  trained on, and is recorded as discarded.

Checkpoints are written as bundles (``save_model_atomic``): every file goes to a
temporary name, is validated, moved into place under a name the manifest does
not yet reference, and only then is the manifest entry published, which is the
commit point. A failed or interrupted save leaves the previous checkpoints valid.
Periodic and stop checkpoints are resumable (DQN ones carry the replay buffer and
algorithm state, see ``lunarlab.continuation``); validation-selected and final
checkpoints are inference checkpoints.

### class `TrainingContext`

TrainingContext(cfg: 'RunConfig', paths: 'RunPaths', segment: 'int', job_id: 'str | None', started_at: 'str', target: 'int', on_validation: 'Callable[[int, float], bool] | None' = None)

`TrainingContext(cfg: 'RunConfig', paths: 'RunPaths', segment: 'int', job_id: 'str | None', started_at: 'str', target: 'int', on_validation: 'Callable[[int, float], bool] | None' = None) -> None`


### `build_model(cfg: 'RunConfig', venv, device: 'str')`

SB3's own ``PPO`` or ``DQN`` with the run's hyperparameters, network and seed (LunarLab adds no learning code).

### `build_vec_env(cfg: 'RunConfig', kind: 'str | None' = None)`

The run's vectorised training environments: ``n_envs`` copies of LunarLander (with the optional physics
randomiser) under ``LunarLabRewardWrapper(apply=True)`` and ``Monitor``, in a DummyVecEnv or a SubprocVecEnv.

### `request_stop(paths: 'RunPaths', *, reason: 'str' = 'user', source: 'str' = 'api', job_id: 'str | None' = None) -> 'None'`

Ask a running worker to stop at its next safe boundary.

``job_id`` addresses a specific supervised job. A worker that starts *after* a request for its
own job was written honours it immediately instead of discarding it as stale.

### `resolve_device(requested: 'str') -> 'str'`

``cpu``, or ``cuda`` when requested (``cuda``/``auto``) and available; requesting ``cuda`` without it is an error.

### `save_model_atomic(model, paths: 'RunPaths', name: 'str', *, kind: 'str', transitions: 'int', segment: 'int', config_hash: 'str', extra: 'dict | None' = None, continuation: 'str | None' = None, total_timesteps_basis: 'int | None' = None) -> 'dict'`

Write a checkpoint bundle crash-safely; the manifest entry is published last (the commit point).

``continuation``: ``None`` for an inference checkpoint, ``"ppo"`` or ``"dqn"`` for a resumable one
(DQN adds its replay buffer and algorithm state, ``lunarlab.continuation``).

### `train(run_id: 'str', *, resume: 'bool' = False, checkpoint: 'str' = 'latest', job_id: 'str | None' = None, quiet: 'bool' = False, on_validation: 'Callable[[int, float], bool] | None' = None) -> 'int'`

Train (or continue) a run. Returns a worker exit code.

## Constants

- `DQN_CONTINUATION_FORMAT` = `'lunarlab.dqn-continuation'`
- `DQN_CONTRACT` = `'online and target Q-networks, optimizer state, replay buffer (with position and wrap state), transition, update and tar…`
- `DQN_DIAG_EVERY` = `10000`
- `EPISODE_FIELDS` = `['episode', 'segment', 'env_index', 'transitions', 'wall_time_s', 'original_return', 'training_return', 'length', 'env_o…`
- `EXIT_BUSY` = `2`
- `EXIT_COMPLETED` = `0`
- `EXIT_FAILED` = `1`
- `EXIT_INTERRUPTED` = `4`
- `EXIT_STOPPED` = `3`
- `KEEP_CONTINUATIONS` = `2`
- `PHYSICS_FIELDS` = `('wind', 'wind_power', 'turbulence_power', 'gravity')`
- `PPO_CONTINUATION_FORMAT` = `'lunarlab.ppo-continuation'`
- `PPO_CONTRACT` = `'policy and value networks, optimizer state, transition and update counters; a partial rollout at a stop is discarded an…`
- `PPO_DIAGNOSTIC_KEYS` = `('train/approx_kl', 'train/clip_fraction', 'train/entropy_loss', 'train/policy_gradient_loss', 'train/value_loss', 'trai…`
- `REPLACE_TIMEOUT_S` = `60.0`
- `TERM_KEYS` = `('time_penalty', 'hover_bonus', 'potential_shaping', 'learned_reward')`
