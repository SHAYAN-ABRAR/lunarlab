# `lunarlab.reproduce`

Source: [`lunarlab/reproduce.py`](../../lunarlab/reproduce.py)

Reproducibility checks that run without the web interface.

* :func:`run_smoke` runs the whole research pipeline at a tiny budget in an isolated, temporary LunarLab
  home -- configuration, training, checkpoints, reload, validation, frozen final test, export -- and
  verifies every provenance link (configuration identity, checkpoint digests, the tested checkpoint, the
  reward accounting identity). It then repeats the final-test evaluation and requires an exact match, and
  can train the same configuration a second time to test training determinism.
* :func:`export_artifact` packages a run's tested checkpoint, configuration and recorded final-test
  evaluation (byte-identical copies plus their SHA-256 digests) so a third party can re-evaluate it.
* :func:`reproduce_artifact` re-evaluates such a package on the recorded seeds and compares every episode
  with the record.

Exactness. For a fixed checkpoint, seed list, environment version and software stack the evaluation is
deterministic, so a repeat on the same machine must match bit for bit. Across operating systems, CPUs or
PyTorch/Box2D builds, floating-point differences can change a trajectory; such reproductions are reported
episode by episode (with the largest difference) instead of being assumed exact.

### `compare_episodes(recorded: 'list[dict]', reproduced: 'list[dict]', *, tolerance: 'float' = 0.0) -> 'dict[str, Any]'`

Compare two evaluations seed by seed on :data:`COMPARED_FIELDS`.

Returns are compared with ``tolerance`` (absolute; 0 = bit-identical), everything else exactly.

### `episode_key(ep: 'dict') -> 'tuple'`

The compared fields of one episode (``COMPARED_FIELDS``), as a tuple.

### `episodes_digest(episodes: 'list[dict]') -> 'str'`

SHA-256 of the compared fields of every episode, in seed order (exact float representations).

### `export_artifact(run_id: 'str', out: 'Path') -> 'dict[str, Any]'`

Copy a run's tested checkpoint, configuration and first final-test evaluation into ``out``.

Reads the run without modifying it. ``out/artifact.json`` records the digests of the copies (identical
to the originals) and the documented metric, so :func:`reproduce_artifact` can verify both.

### `isolated_home(path: 'Path') -> 'Iterator[Path]'`

Point LUNARLAB_HOME at ``path`` for the duration of the block (restored afterwards).

### `remove_tree(path: 'Path') -> 'None'`

Delete a temporary home, including the read-only frozen checkpoints a final test creates.

### `reproduce_artifact(artifact_dir: 'Path', *, episodes: 'int | None' = None, tolerance: 'float' = 0.0, echo: 'Callable[[str], None]' = <built-in function print>) -> 'dict[str, Any]'`

Verify an exported artifact and re-evaluate its checkpoint on the recorded final-test seeds.

### `run_smoke(workdir: 'Path | None' = None, *, transitions: 'int' = 4096, seed: 'int' = 0, preset_name: 'str' = 'potential', algo: 'str' = 'ppo', training_determinism: 'bool' = False, keep: 'bool' = False, echo: 'Callable[[str], None]' = <built-in function print>) -> 'dict[str, Any]'`

Run the bounded end-to-end pipeline in an isolated home and return a report (``report["ok"]``).

### `weights_digest(path: 'Path') -> 'str'`

SHA-256 of a checkpoint's policy tensors (names, shapes, dtypes, values).

Unlike the checkpoint file's digest it ignores zip metadata such as file times, so two trainings can be
compared across processes and days.

## Constants

- `ARTIFACT_SCHEMA` = `1`
- `COMPARED_FIELDS` = `('length', 'original_return', 'training_return', 'env_outcome', 'pad_landing')`
- `SMOKE_PPO` = `{'n_envs': 2, 'n_steps': 256, 'batch_size': 64}`
- `SMOKE_PROTOCOL` = `{'validation_seeds': [10000, 10001, 10002], 'test_seeds': [20000, 20001, 20002, 20003]}`
