# `lunarlab.freeze`

Source: [`lunarlab/freeze.py`](../../lunarlab/freeze.py)

Final-test freezing: one immutable tested artifact per run, shared by every final-test consumer.

Freezing happens at the first final-test evaluation, under the run's worker lock (the same lock
training holds, so a run can never be frozen while it trains, and two final tests never overlap):

1. the selected checkpoint is resolved and its digest verified against the manifest;
2. its bytes are copied to ``checkpoints/frozen/<sha256>.zip`` (content-addressed, written to a
   temporary name, verified, made read-only) and recorded in ``metadata.json -> frozen_for_test``
   (schema 2) with the configuration, reward and protocol identities.

Afterwards the run never trains again under its run ID (``training._train_locked`` refuses), and the
final test, robustness evaluations, showcase recordings and ghost flights all load the frozen bytes
through :func:`resolve_final_checkpoint`, never a mutable name such as ``best_validation.zip``.

Freezing is not testing: ``metadata.json -> test_attempts`` records each attempt as ``started``,
``completed``, ``interrupted`` or ``failed``. Only a completed attempt (or, for runs tested before
attempts were recorded, a stored test evaluation of the frozen bytes) counts as a completed final
test; an interrupted or failed one is retried on the same frozen checkpoint.

Legacy records (schema 1: checkpoint name and digest only) still resolve while the named file still
has the recorded bytes. :func:`migrate_legacy_freeze` creates the immutable copy explicitly and logs
it; when the bytes are gone, nothing is substituted and the historical results stay historical.

### `completed_test_count(meta: 'dict', run_id: 'str') -> 'int'`

Completed final tests of the frozen checkpoint, including test files written before attempts were recorded.

### `entry_for_frozen(info: 'dict') -> 'dict'`

A manifest-like entry describing the frozen checkpoint (for results and labels).

### `finish_attempt(run_id: 'str', attempt: 'int', state: 'str', **info: 'Any') -> 'None'`

Mark a final-test attempt completed, interrupted or failed, and update the completed-test count.

### `freeze_for_test(run_id: 'str', checkpoint: 'str' = 'best') -> 'dict'`

Freeze ``checkpoint`` for the final test. The caller must hold the run's worker lock.

### `frozen_artifact_for(run_id: 'str', sha256: 'str') -> 'Path | None'`

The run's frozen artifact if it holds exactly these bytes (used by warm restarts).

### `immutable_copy(src: 'Path', dst: 'Path', sha: 'str') -> 'Path'`

Copy ``src`` (whose SHA-256 must be ``sha``) to ``dst``, verify the copy and make it read-only.

An existing ``dst`` is kept only if it already holds those bytes; otherwise nothing is overwritten. The
copy is written to a temporary name and renamed after its digest is checked, so a partly written file
never appears under ``dst``. Used for the main pipeline's frozen final-test checkpoints and for the
generic audit study (:mod:`lunarlab.audit.study`).

### `migrate_legacy_freeze(run_id: 'str') -> 'dict'`

Create the immutable copy for a schema-1 freeze record, only if the tested bytes are intact.

Never substitutes another checkpoint; reports instead. Logged in the run's event log.

### `pending_final_tests(run_ids: 'list[str]') -> 'list[str]'`

Runs that finished training but have no completed final test (frozen-only counts as pending).

### `resolve_final_checkpoint(run_id: 'str', *, require_frozen: 'bool' = False) -> 'tuple[Path, dict]'`

What final-test consumers evaluate: the frozen bytes if the run is frozen, otherwise (unless
``require_frozen``) the validation-selected checkpoint, labelled as not yet frozen.

### `resolve_frozen_checkpoint(run_id: 'str') -> 'tuple[Path, dict]'`

The frozen artifact of a run, verified against its digest (RunError if absent or altered).

### `start_attempt(run_id: 'str', sha256: 'str') -> 'int'`

Record a final-test attempt of the frozen checkpoint as started; returns its index.

### `test_status(run_id: 'str') -> 'dict'`

Frozen identity, every attempt, and whether a completed final test exists.

## Constants

- `FROZEN_SCHEMA` = `2`
