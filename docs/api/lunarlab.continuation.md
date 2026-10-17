# `lunarlab.continuation`

Source: [`lunarlab/continuation.py`](../../lunarlab/continuation.py)

Resumable DQN checkpoints: replay buffer and algorithm state next to the SB3 weights.

Checkpoint contract (docs/ARCHITECTURE.md):

* **inference checkpoint**: an SB3 ``.zip`` loaded weights-only; enough to evaluate, record or replay.
* **resumable training checkpoint**: continues the same run. PPO needs the ``.zip`` (policy and
  optimizer state) and the counters in the manifest; its partial rollout at a stop is discarded and
  recorded. DQN additionally needs everything below.
* **warm restart**: a *new* run initialised from a checkpoint's weights (``lunarlab.lineage``).

What SB3 2.9.0 keeps outside the ``.zip`` for DQN, and this module therefore stores:

* the replay buffer (``observations``, ``next_observations``, ``actions``, ``rewards``, ``dones``,
  ``timeouts``, plus ``pos`` and ``full``);
* ``num_timesteps``, ``_n_updates`` (gradient steps), ``_n_calls`` (the target-network update phase:
  the target is synchronised when ``_n_calls % (target_update_interval // n_envs) == 0``),
  ``_episode_num``, ``exploration_rate`` and ``_current_progress_remaining``;
* the schedule basis (the planned transitions the exploration schedule is computed over).

The online and target Q-networks and the Adam state are inside the ``.zip`` (``policy`` and
``policy.optimizer`` state dicts) and are restored by ``set_parameters``.

Storage is a strictly validated JSON file and an uncompressed ``.npz`` of numeric arrays. Before any
array is read, every member's ``.npy`` header is checked (no object dtypes, exactly the expected
names, shapes and dtypes), so a damaged or hostile file cannot make LunarLab allocate arbitrary
memory or unpickle anything; the files must also match the SHA-256 digests in the manifest. A digest
proves integrity against the manifest, not that an arbitrary file from elsewhere is trustworthy.

### class `ArraySpec`(_Strict)

Shape and dtype of one replay-buffer array, checked before any array data is read.

| Field | Type | Default | Description |
|---|---|---|---|
| `shape` | `list[int]` | `required` |  |
| `dtype` | `str` | `required` |  |


### class `ContinuationError`(RunError)

A continuation bundle is missing, damaged or incompatible with the run.

`ContinuationError(...)`


### class `ContinuationState`(_Strict)

What SB3's DQN keeps outside its zip file, validated strictly: counters, target-update phase,
exploration rate, schedule progress, and the replay buffer's layout and digest.

| Field | Type | Default | Description |
|---|---|---|---|
| `format` | `Literal['lunarlab.dqn-continuation']` | `required` |  |
| `version` | `Literal[1]` | `required` |  |
| `sb3_version` | `str` | `required` |  |
| `num_timesteps` | `int` | `required` |  |
| `n_updates` | `int` | `required` |  |
| `n_calls` | `int` | `required` |  |
| `episode_num` | `int` | `required` |  |
| `exploration_rate` | `float` | `required` |  |
| `current_progress_remaining` | `float` | `required` |  |
| `total_timesteps_basis` | `int` | `required` |  |
| `learning_starts` | `int` | `required` |  |
| `target_update_interval` | `int` | `required` |  |
| `n_envs` | `int` | `required` |  |
| `replay` | `ReplayState` | `required` |  |
| `replay_sha256` | `str` | `required` |  |


### class `ReplayState`(_Strict)

Layout and position of the replay buffer in a DQN continuation bundle.

| Field | Type | Default | Description |
|---|---|---|---|
| `buffer_class` | `Literal['ReplayBuffer']` | `required` |  |
| `buffer_size` | `int` | `required` |  |
| `n_envs` | `int` | `required` |  |
| `pos` | `int` | `required` |  |
| `full` | `bool` | `required` |  |
| `rows` | `int` | `required` |  |
| `optimize_memory_usage` | `bool` | `required` |  |
| `handle_timeout_termination` | `bool` | `required` |  |
| `obs_shape` | `list[int]` | `required` |  |
| `action_dim` | `int` | `required` |  |
| `arrays` | `dict[str, lunarlab.continuation.ArraySpec]` | `required` |  |


### `apply_dqn_continuation(model, state: 'dict', arrays: 'dict[str, np.ndarray]') -> 'None'`

Restore a DQN model's replay buffer and counters from :func:`dqn_continuation_payload` output.

### `describe_entry(entry: 'dict', algo: 'str') -> 'dict[str, Any]'`

What a checkpoint can be used for, in words the UI and CLI show.

### `dqn_continuation_payload(model, *, total_timesteps_basis: 'int') -> 'tuple[dict, dict[str, np.ndarray]]'`

The JSON-able state and the filled replay rows of a DQN model, at a safe boundary.

### `inspect_npz(path: 'Path') -> 'dict[str, tuple[tuple[int, ...], np.dtype]]'`

Shapes and dtypes from every member's ``.npy`` header, without reading array data.

### `load_replay_npz(path: 'Path', *, expected: 'dict[str, tuple[tuple[int, ...], str]]') -> 'dict[str, np.ndarray]'`

Load exactly the ``expected`` arrays after checking every header (``allow_pickle=False``).

### `prune_continuations(paths: 'RunPaths', *, keep: 'int', now: 'str') -> 'list[str]'`

Remove the replay/state files of all but the ``keep`` most recent resumable DQN checkpoints.

Only superseded *training state* is removed; the checkpoint weights stay and remain usable for
inference. Their manifest entries say when the continuation was pruned and stop being resumable.

### `read_continuation(paths: 'RunPaths', entry: 'dict') -> 'tuple[dict, dict[str, np.ndarray]]'`

Verify and load a manifest entry's continuation bundle (state, replay arrays).

### `restore_dqn_continuation(model, paths: 'RunPaths', entry: 'dict', *, total_timesteps_basis: 'int') -> 'dict'`

Load a resumable DQN checkpoint's bundle into ``model`` (after ``set_parameters``).

### `stage_dqn_continuation(model, directory: 'Path', stem: 'str', *, total_timesteps_basis: 'int') -> 'dict'`

Write the state and replay files to temporary names in ``directory`` and validate them.

Returns the staged paths, their intended final names and digests. Nothing is final until
the caller moves the files into place and publishes the manifest entry (the commit point).

### `verify_continuation_files(paths: 'RunPaths', entry: 'dict') -> 'None'`

Cheap integrity check of a bundle's files (presence, size, SHA-256) without loading arrays.

### `write_replay_npz(path: 'Path', arrays: 'dict[str, np.ndarray]') -> 'None'`

Uncompressed (ZIP_STORED) ``.npz`` of plain numeric arrays.

## Constants

- `DQN_CONTINUATION_FORMAT` = `'lunarlab.dqn-continuation'`
- `FORMAT` = `'lunarlab.dqn-continuation'`
- `MAX_REPLAY_BYTES` = `4000000000`
- `REPLAY_ARRAYS` = `('observations', 'next_observations', 'actions', 'rewards', 'dones', 'timeouts')`
- `VERSION` = `1`
