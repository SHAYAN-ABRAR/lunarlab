# `lunarlab.audit.study`

Source: [`lunarlab/audit/study.py`](../../lunarlab/audit/study.py)

A small, prespecified reward-design study on any registered task, through the task-independent layer.

The workflow, each step leaving a record with digests:

1. **Protocol.** It is written before training, validated by :func:`protocol_problems` and identified by
   the SHA-256 of its canonical JSON. It fixes the reward designs, the learner settings, the budget, the
   training seeds, the training-environment seed roots, the validation and test seeds, the
   checkpoint-evaluation schedule and the selection rule.
2. **Training** (:func:`train_run`). PPO learns from one design's training reward. Every
   ``eval_every_rollouts`` rollouts the current policy is saved and audited with the *original* reward on
   the validation seeds through :func:`~lunarlab.audit.audit_policy`, never on the test seeds.
3. **Selection and freezing.** The prespecified rule picks a checkpoint. That checkpoint, and the final
   checkpoint for the prespecified secondary analysis, are copied to content-addressed read-only files by
   :func:`lunarlab.freeze.immutable_copy`, the same function the main pipeline freezes with.
4. **Final test** (:func:`final_test`). The frozen copy's digest is verified before the policy is loaded.
   The policy is then audited on the test seeds, and every episode is stored.
5. **Artifact** (:func:`export_artifact`, :func:`verify_artifact`, :func:`reproduce_artifact`). It holds the
   frozen policy, the protocol, the training record, the reward provenance and the recorded test evaluation,
   with their digests. Verification checks integrity before any episode runs. Reproduction re-evaluates the
   recorded seeds and classifies the result with the statuses of ``lunarlab reproduce-artifact``.

Seeds: ``PPO(seed=s)`` seeds the learner's random generators (Python, NumPy, PyTorch, action space). The
training environments' first reset uses ``train_env_seed_root + 1000 * s + i`` for environment ``i``. These
roots are set after the model is built, because ``PPO(seed=...)`` re-seeds the environments. Later
training episodes reset without a seed and continue each environment's random stream. Validation and test
episodes are reset with their own fixed seeds.

This module is part of the reusable research core. LunarLander-specific features (the web application,
strict pad-landing categories, the hover diagnostics, the main run registry) are not used.

### `actual_transitions(protocol: 'Mapping[str, Any]') -> 'int'`

The configured budget rounded up to whole rollouts, as PPO collects it.

### `build_terms(adapter: 'TaskAdapter', design: 'Mapping[str, Any]', gamma: 'float') -> 'dict[str, RewardTerm]'`

The design's reward terms, built by the adapter's factories. Potential terms use the learner's gamma.

### `check_file_digests(root: 'str | Path', expected: 'Mapping[str, str]') -> 'list[tuple[str, bool, str]]'`

Each file under ``root`` named in ``expected`` exists and has the recorded SHA-256: (name, passed, detail).

### `check_recorded_episodes(episodes: 'list[dict[str, Any]]', *, expected_seeds: 'list[int]', term_names: 'list[str]', original_weight: 'float', categories: 'tuple[str, ...] | list[str]') -> 'list[tuple[str, bool, str]]'`

Checks of a recorded evaluation that need no policy execution: (name, passed, detail) for each.

**Required fields.** Every episode is an object holding ``REQUIRED_RETURN_FIELDS`` and ``term_returns``
with exactly the design's terms.

**Optional fields.** ``OPTIONAL_RETURN_FIELDS`` and ``term_discounted_returns`` may be absent.

**Values.** Every present reward value must be a finite ``int`` or ``float``: null, booleans, text, NaN and
infinity are refused, never converted to a number. The accounting identity is computed only from
well-formed values.

**Malformed input.** It never raises. Each problem is a failed check naming the episode, the field and what
is wrong.

### `check_trajectory(trajectory: 'Mapping[str, Any]', terms: 'Mapping[str, RewardTerm]', *, gamma: 'float', original_weight: 'float' = 1.0) -> 'list[tuple[str, bool, str]]'`

Re-score a recorded trajectory and compare every step's recorded term values with the re-scored ones.

``trajectory`` holds ``observations`` (T + 1 rows), ``actions``, ``original_rewards``, ``terminated`` and
``truncated`` (the final step's flags) and ``term_values`` ({term: T values}).

### `compare_generic_aggregates(recorded: 'list[dict[str, Any]]', reproduced: 'list[dict[str, Any]]', success_outcome: 'str', *, seed: 'int' = 0) -> 'dict[str, Any]'`

Paired aggregate screen over the same seeds: mean original return and the success rate.

Uses the main pipeline's sign-flip permutation test, exact McNemar test and Holm correction. A regression
screen, not an equivalence test.

### `design_of(protocol: 'Mapping[str, Any]', name: 'str') -> 'dict[str, Any]'`

The reward design called ``name``.

### `environment_record() -> 'dict[str, Any]'`

Threads and numerical settings that affect results, for study records.

### `export_artifact(run_dir: 'str | Path', out_dir: 'str | Path', *, which: 'str' = 'selected') -> 'dict[str, Any]'`

Package the frozen policy, protocol, training record, reward provenance and recorded test evaluation.

### `failure_summary(failed_kinds: 'list[str]') -> 'str'`

How a failed verification reads: an integrity failure, malformed records, or both. Each one blocks.

### `final_test(run_dir: 'str | Path', *, which: 'str' = 'selected') -> 'dict[str, Any]'`

Audit the frozen ``selected`` (or ``final``) checkpoint on the protocol's test seeds.

The frozen file's digest and the protocol's digest are verified before the policy is loaded. An existing
test record is never overwritten.

### `load_json(path: 'str | Path') -> 'Any'`

Read a JSON file (UTF-8).

### `make_model(protocol: 'Mapping[str, Any]', venv: 'Any', seed: 'int') -> 'Any'`

The protocol's PPO learner on ``venv``, with learner seed ``seed`` (linear schedules supported).

### `policy_fn(model: 'Any') -> 'Callable[[np.ndarray], Any]'`

The deterministic policy of an SB3 model as an observation -> action callable.

### `protocol_problems(protocol: 'Mapping[str, Any]') -> 'list[str]'`

Why the protocol cannot be used (empty list: it is valid).

### `protocol_sha256(protocol: 'Mapping[str, Any]') -> 'str'`

SHA-256 of the protocol's canonical JSON (sorted keys, compact, no NaN).

### `reproduce_artifact(artifact_dir: 'str | Path', *, echo: 'Callable[[str], None]' = <built-in function print>) -> 'dict[str, Any]'`

Verify an artifact, then re-evaluate its policy on the recorded seeds and classify the result.

Statuses and exit codes are those of :data:`lunarlab.reproduce.STATUSES`. An integrity failure skips the
evaluation: no episode runs.

### `require_valid_protocol(protocol: 'Mapping[str, Any]') -> 'None'`

Raise :class:`AuditInputError` listing every problem of an invalid protocol.

### `rollout_size(protocol: 'Mapping[str, Any]') -> 'int'`

Transitions per PPO rollout (environments x steps per environment).

### `select_checkpoint(checkpoints: 'list[dict[str, Any]]', rule: 'str') -> 'dict[str, Any]'`

Apply the prespecified selection rule to the evaluated checkpoints.

### `train_env_seeds(protocol: 'Mapping[str, Any]', seed: 'int') -> 'list[int]'`

First-reset seeds of the training environments for one training seed.

### `train_run(protocol: 'Mapping[str, Any]', design_name: 'str', seed: 'int', run_dir: 'str | Path', *, echo: 'Callable[[str], None]' = <built-in function print>) -> 'dict[str, Any]'`

Train one policy, evaluate scheduled checkpoints on the validation seeds, select and freeze.

Writes ``run_dir/protocol.json``, ``checkpoints/``, ``frozen/`` and ``run.json``. Refuses an existing run
directory: a run is never retrained in place.

### `verify_artifact(artifact_dir: 'str | Path') -> 'dict[str, Any]'`

Every check of an exported artifact. Nothing is executed: no environment, no policy.

Each check has a ``kind``:

- ``integrity``: the files and their digests, the protocol, the reward definition, the policy's identity
  and the seeds;
- ``record``: whether the recorded evaluation is complete, well formed and internally consistent.

A malformed record (a missing key, a null, boolean or text value, a wrong type) is reported as a failed
``record`` check naming the problem; it never raises. ``failed_kinds`` lists the kinds that failed.

### `verify_frozen(run_dir: 'str | Path', which: 'str' = 'selected') -> 'tuple[Path, dict[str, Any]]'`

The frozen checkpoint's path, after checking its digest against the run record.

## Constants

- `ARTIFACT_FILES` = `('policy.zip', 'protocol.json', 'run.json', 'evaluation.json', 'reward.json')`
- `ARTIFACT_SCHEMA` = `'lunarlab.audit-artifact/1'`
- `COMPARED_FIELDS` = `('length', 'original_return', 'training_return', 'outcome', 'terminated', 'truncated')`
- `OPTIONAL_RETURN_FIELDS` = `('discounted_original_return', 'discounted_training_return')`
- `OPTIONAL_TERM_FIELD` = `'term_discounted_returns'`
- `OUTCOME_FIELDS` = `('terminated', 'truncated', 'outcome')`
- `REQUIRED_RETURN_FIELDS` = `('original_return', 'training_return')`
- `REQUIRED_TERM_FIELD` = `'term_returns'`
- `RUN_SCHEMA` = `'lunarlab.audit-run/1'`
- `SEED_STRIDE` = `1000`
- `SELECTION_RULES` = `{'max-mean-original-validation-return': 'the evaluated checkpoint with the highest mean ORIGINAL return on the validatio…`
- `STUDY_SCHEMA` = `'lunarlab.audit-study/1'`
- `TEST_SCHEMA` = `'lunarlab.audit-test/1'`
