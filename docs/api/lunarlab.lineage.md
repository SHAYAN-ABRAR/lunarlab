# `lunarlab.lineage`

Source: [`lunarlab/lineage.py`](../../lunarlab/lineage.py)

Run lineage: warm restarts, test exposure and the evidence role of a run's final-test result.

A **warm restart** is a new run whose networks (and optimizer state) start from another run's
checkpoint. It is never presented as a continuation: it gets its own run ID, its configuration hash
differs (``RunConfig.warm_start``), so comparisons never group it with uninterrupted runs, and its
metadata lists which state was preserved and which was reset.

**Test exposure.** Once a final-test result of a protocol's test seeds has been seen, those seeds are
no longer unseen for decisions made afterwards. ``data/test_exposure.jsonl`` records every completed
final test per test-seed set. A run derived from a tested run (a warm restart of it), or created from
a tuning study that started after the test seeds were exposed, is labelled **exploratory**: its result
on the same seeds is not a new held-out test. A confirmatory claim needs an untouched holdout, i.e. a
protocol whose test seeds have never been used (see docs/EVALUATION.md).

### `create_warm_restart(run_id: 'str', checkpoint: 'str' = 'latest', *, confirm: 'bool', label: 'str | None' = None) -> 'RunConfig'`

Create (do not train) a new run initialised from ``run_id``'s checkpoint. Needs ``confirm=True``.

### `evidence_note(meta: 'dict[str, Any]') -> 'str | None'`

Why a run's results are exploratory (post-test lineage, or tuning on already-used test seeds), or None.

### `evidence_role(meta: 'dict[str, Any]') -> 'str'`

``confirmatory`` unless the run's design was influenced by an already-seen final test.

### `first_test_exposure(protocol: 'EvalProtocol') -> 'dict | None'`

The first recorded final-test result that used ANY of this protocol's test seeds, if any.

Overlap counts, not only the identical set: a "holdout" that shares seeds with a test set whose
results were already seen is not untouched. Runs tested before this registry existed are found
through their test evaluation files too.

### `record_test_exposure(protocol: 'EvalProtocol', run_id: 'str', evaluation_file: 'str') -> 'None'`

Note that a final-test result on these test seeds now exists (append-only).

### `resolve_warm_start(cfg: 'RunConfig') -> 'Path'`

The parent checkpoint file a warm restart starts from, verified against the recorded digest.

### `test_seed_set_hash(protocol: 'EvalProtocol') -> 'str'`

Order-independent identity of a protocol's test seeds, used by the test-exposure registry.

## Constants

- `PRESERVED` = `{'ppo': ['network weights (policy and value networks)', 'optimizer state'], 'dqn': ['network weights (online and target …`
- `RESET` = `{'ppo': ['transition and update counters (start at 0, full training budget)', 'environment state (new episodes)', 'rando…`
