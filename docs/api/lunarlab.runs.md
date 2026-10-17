# `lunarlab.runs`

Source: [`lunarlab/runs.py`](../../lunarlab/runs.py)

Run creation, metadata, checkpoint manifest and event log.

### class `RunError`(RuntimeError)

A run operation that must not proceed (unknown run, frozen run, incompatible checkpoint, …).

`RunError(...)`


### `create_run(*, reward: 'RewardConfig', training: 'TrainingConfig', seed: 'int', ppo: 'PPOConfig | None' = None, protocol: 'EvalProtocol | None' = None, experiment_id: 'str | None' = None, label: 'str' = '', reward_config_id: 'str | None' = None, reward_revision: 'int | None' = None, algo: 'str' = 'ppo', dqn: 'DQNConfig | None' = None, physics: 'PhysicsRandomization | None' = None, warm_start: 'WarmStart | None' = None, lineage: 'dict | None' = None) -> 'RunConfig'`

Create a run directory with its validated configuration and metadata.

Records the configuration, reward and protocol hashes, the planned budget, the environment and a system snapshot
(versions, hardware, source revision). An invalid evaluation protocol is refused.

### `is_resumable(entry: 'dict', algo: 'str') -> 'bool'`

Whether a checkpoint can CONTINUE its run (see docs/ARCHITECTURE.md, checkpoint contract).

PPO: periodic and stop checkpoints (weights, optimizer state, counters; also those written before
the contract was named). DQN: only checkpoints that carry a complete continuation bundle
(replay buffer and algorithm state); older DQN checkpoints are inference checkpoints.

### `legacy_dqn_resume_message(run_id: 'str', name: 'str') -> 'str'`

Why a DQN checkpoint without a continuation bundle cannot be resumed, and what to do instead.

### `load_config(run_id: 'str') -> 'RunConfig'`

The run's validated configuration (``config.yaml``).

### `load_metadata(run_id: 'str') -> 'dict'`

The run's ``metadata.json``.

### `load_policy(run_id: 'str', which: 'str' = 'best', *, deterministic: 'bool' = True)`

Load a run's policy for inference (safe, weights-only).

``which="frozen"`` loads the immutable copy frozen for the final test (verified against its digest);
``which="final-test"`` does the same, and falls back to the validation-selected checkpoint for a run
that has not been frozen yet.

### `log_event(paths: 'RunPaths', level: 'str', message: 'str', **data: 'Any') -> 'None'`

Append one event to the run's ``events.jsonl``.

### `mutate_manifest(paths: 'RunPaths', change: 'Callable[[dict], Any]') -> 'dict'`

Read-modify-write the checkpoint manifest under the run's metadata lock. The manifest is the
commit point of a checkpoint: an entry appears only after every file it names is complete.

### `mutate_metadata(run_id: 'str', change: 'Callable[[dict], Any]') -> 'dict'`

Read-modify-write ``metadata.json`` under the run's metadata lock (safe across processes).

### `read_manifest(paths: 'RunPaths') -> 'dict'`

The run's checkpoint manifest (an empty one before the first checkpoint).

### `register_checkpoint(paths: 'RunPaths', file: 'Path', *, kind: 'str', transitions: 'int', updates: 'int', segment: 'int', extra: 'dict | None' = None) -> 'dict'`

Add a checkpoint file to the manifest with its size, SHA-256, transitions and the caller's extra fields
(under the metadata lock); a ``best_validation`` entry also becomes the manifest's selected checkpoint.

### `resolve_checkpoint(run_id: 'str', which: 'str' = 'best') -> 'tuple[Path, dict]'`

Find a manifest-listed checkpoint and verify its integrity.

``which``: ``best`` (validation-selected), ``final``, ``latest``, or a
checkpoint file name from the manifest.

### `resolve_resume_checkpoint(run_id: 'str', which: 'str', algo: 'str') -> 'tuple[Path, dict]'`

The checkpoint a resume continues from, verified, or a RunError that says what to do instead.

### `update_metadata(run_id: 'str', **updates: 'Any') -> 'dict'`

Merge fields into ``metadata.json`` under the run's metadata lock.

## Constants

- `DQN_CONTINUATION_FORMAT` = `'lunarlab.dqn-continuation'`
- `PPO_CONTINUATION_FORMAT` = `'lunarlab.ppo-continuation'`
