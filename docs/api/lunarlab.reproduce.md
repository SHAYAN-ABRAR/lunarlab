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

Exactness here means equality of COMPARED_FIELDS, not a bitwise comparison of entire
trajectories. Operating-system and package-version matching is a coarse diagnostic,
not a guarantee of identical hardware or compiled numerical behavior. Across
platforms, floating-point differences can change trajectories; differences are reported.

A reproduction is classified (:data:`STATUSES`) by four separate properties:

* **artifact integrity** -- the files match their digests, and the configuration, seeds, protocol, reward and
  loaded weights are the recorded ones (always blocking when violated);
* **within-platform reproducibility** -- the selected episode-summary fields are expected to match;
* **cross-platform numerical reproducibility** -- elsewhere, per-episode differences are measured and reported;
* **aggregate regression screening** -- no compared aggregate (mean return; pad-landing, timeout, crash and out-of-bounds
  rates) may differ significantly from the record in a paired comparison over the same seeds
  (:func:`compare_aggregates`). Non-rejection does not establish equivalence or preservation of all conclusions.

### `classify_reproduction(*, integrity_ok: 'bool', comparison: 'dict', aggregates: 'dict', platform: 'dict', tolerance: 'float' = 0.0) -> 'tuple[str, str]'`

The reproduction status (a key of :data:`STATUSES`) and the reason for it.

### `compare_aggregates(recorded: 'list[dict]', reproduced: 'list[dict]', protocol) -> 'dict[str, Any]'`

Aggregate regression screen, not an equivalence or conclusion-stability certificate.

A reproduction re-flies the recorded seeds, so the comparison is paired. The mean original return is tested
with a sign-flip permutation test on the per-seed differences; each outcome rate (pad landing, timeout, crash,
out of bounds) with an exact McNemar test on the episodes whose outcome flipped. Holm's correction keeps the
family-wise false-alarm rate at 5 %. Symmetric numerical noise (episodes flipping both ways, differences
centred on zero) is not flagged; a shift such as a broken policy or environment is. This is a test for
regressions, not a proof of equivalence. Both sides are also aggregated by :func:`lunarlab.evaluation.aggregate`
over the same seeds, with the recorded interval for reference.

### `compare_episodes(recorded: 'list[dict]', reproduced: 'list[dict]', *, tolerance: 'float' = 0.0) -> 'dict[str, Any]'`

Compare two evaluations seed by seed on :data:`COMPARED_FIELDS`.

Returns are compared with ``tolerance`` (absolute; 0 = numeric equality), everything else exactly. Besides the
counts, every episode gets a row (``episodes``: returns and their difference, length, termination and
outcome agreement, final-observation difference) and ``summary`` aggregates them.

### `compare_platforms(recorded: 'dict | None', current: 'dict') -> 'dict[str, Any]'`

Whether this machine has the recording platform's operating system and numerical libraries.

The recorded side is the artifact's ``exported_with`` (for the supplied artifacts, the machine that trained,
tested and exported them). An unknown recorded platform counts as different.

### `episode_key(ep: 'dict') -> 'tuple'`

The compared fields of one episode (``COMPARED_FIELDS``), as a tuple.

### `episodes_digest(episodes: 'list[dict]') -> 'str'`

SHA-256 of the compared fields of every episode, in seed order (exact float representations).

### `export_artifact(run_id: 'str', out: 'Path') -> 'dict[str, Any]'`

Copy a run's tested checkpoint, configuration and first final-test evaluation into ``out``.

Reads the run without modifying it. ``out/artifact.json`` records the digests of the copies (identical
to the originals) and the documented metric, so :func:`reproduce_artifact` can verify both.

### `holm(p_values: 'dict[str, float]', alpha: 'float' = 0.05) -> 'dict[str, bool]'`

Holm's step-down procedure: which hypotheses are rejected at family-wise level ``alpha``.

### `isolated_home(path: 'Path') -> 'Iterator[Path]'`

Point LUNARLAB_HOME at ``path`` for the duration of the block (restored afterwards).

### `mcnemar_p_value(gained: 'int', lost: 'int') -> 'float'`

Exact two-sided McNemar test: ``gained``/``lost`` are the episodes whose outcome flipped each way.

### `platform_key(info: 'dict | None') -> 'dict[str, str | None]'`

The operating system and numerical-library versions of a :func:`lunarlab.sysinfo.version_info` record.

### `remove_tree(path: 'Path') -> 'None'`

Delete a temporary home, including the read-only frozen checkpoints a final test creates.

### `reproduce_artifact(artifact_dir: 'Path', *, episodes: 'int | None' = None, tolerance: 'float' = 0.0, echo: 'Callable[[str], None]' = <built-in function print>) -> 'dict[str, Any]'`

Verify an exported artifact and re-evaluate its checkpoint on the recorded final-test seeds.

The report's ``status`` (see :data:`STATUSES`) separates integrity failures, bit-identical reproduction,
cross-platform numerical differences and aggregate disagreement; ``exit_code`` is what the command returns.

### `run_smoke(workdir: 'Path | None' = None, *, transitions: 'int' = 4096, seed: 'int' = 0, preset_name: 'str' = 'potential', algo: 'str' = 'ppo', training_determinism: 'bool' = False, keep: 'bool' = False, echo: 'Callable[[str], None]' = <built-in function print>) -> 'dict[str, Any]'`

Run the bounded end-to-end pipeline in an isolated home and return a report (``report["ok"]``).

### `sign_flip_p_value(differences: 'list[float]', *, permutations: 'int' = 10000, seed: 'int' = 0) -> 'float'`

Two-sided paired permutation test of a zero mean difference (random sign flips, fixed seed).

### `summarize_episode_rows(rows: 'list[dict]') -> 'dict[str, Any]'`

Agreement fractions and the distribution of per-episode return differences.

### `tensors_digest(params: 'dict') -> 'str'`

SHA-256 of named tensors (names, shapes, dtypes, values), as :func:`weights_digest` computes it.

### `weights_digest(path: 'Path') -> 'str'`

SHA-256 of a checkpoint's policy tensors (names, shapes, dtypes, values).

Unlike the checkpoint file's digest it ignores zip metadata such as file times, so two trainings can be
compared across processes and days.

## Constants

- `ARTIFACT_SCHEMA` = `1`
- `COMPARED_FIELDS` = `('length', 'original_return', 'training_return', 'env_outcome', 'pad_landing')`
- `CONSISTENCY_ALPHA` = `0.05`
- `CONSISTENCY_RATES` = `('pad_landing', 'timeout', 'crash', 'out_of_bounds')`
- `NUMERICAL_STACK` = `('torch', 'numpy', 'Box2D', 'gymnasium', 'stable-baselines3')`
- `OUTCOME_FIELDS` = `('terminated', 'truncated', 'env_outcome', 'pad_landing')`
- `PERMUTATIONS` = `10000`
- `RELATIVE_FLOOR` = `1.0`
- `REPRODUCTION_SCHEMA` = `2`
- `SMOKE_PPO` = `{'n_envs': 2, 'n_steps': 256, 'batch_size': 64}`
- `SMOKE_PROTOCOL` = `{'validation_seeds': [10000, 10001, 10002], 'test_seeds': [20000, 20001, 20002, 20003]}`
- `STATUSES` = `{'exact': {'blocking': False, 'exit_code': 0, 'meaning': 'all selected episode-summary fields match exactly'}, 'within-t…`
