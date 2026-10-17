# `lunarlab.evaluation`

Source: [`lunarlab/evaluation.py`](../../lunarlab/evaluation.py)

Evaluation with the unmodified environment reward.

Every policy is evaluated in a fresh ``LunarLander-v3`` with the default physics.
The only wrapper added is :class:`LunarLabRewardWrapper` in ``apply=False``
mode: it hands the **original** reward back unchanged and merely records what the
run's training reward *would* have added (useful for reward-hacking diagnostics).
The same fixed episode seeds are used for every compared policy.

Every result records the environment that actually ran (``environment``: id, keyword arguments,
robustness overrides and the effective physics read back from the instantiated env); an evaluation
under the protocol's own environment refuses to report if that differs from what the protocol
declares. Final tests run under the run's worker lock, on the frozen artifact (``lunarlab.freeze``),
with every attempt recorded.

### class `EvaluationAborted`(RuntimeError)

Raised when an evaluation is stopped on request; nothing is saved.

`EvaluationAborted(...)`


### `aggregate(episodes: 'list[dict]', protocol: 'EvalProtocol') -> 'dict[str, Any]'`

Rates and summaries over episodes. The outcome classifier version is detected from the episodes:
version 2 adds landing categories; ``landed_off_pad`` means ``landed_not_within_pad`` there.

### `evaluate_policy(policy: 'Policy', seeds: 'list[int]', *, protocol: 'EvalProtocol', reward: 'RewardConfig | None', gamma: 'float', progress: 'Callable[[int, int], None] | None' = None, should_stop: 'Callable[[], bool] | None' = None, env_overrides: 'dict | None' = None) -> 'dict[str, Any]'`

Evaluate ``policy`` for one episode per seed on the original reward.

Returns the episodes, the aggregate (rates with Wilson intervals, bootstrap interval of the mean return), the
elapsed time and the instantiated environment; refuses to report if that environment differs from the
protocol's declaration.

### `evaluate_run(run_id: 'str', split: 'str', *, checkpoint: 'str' = 'best', progress: 'Callable[[int, int], None] | None' = None, should_stop: 'Callable[[], bool] | None' = None) -> 'dict[str, Any]'`

Evaluate a run's checkpoint on the validation or final-test seeds and save the result.

The final test (``split="test"``) runs under the run's worker lock: it freezes the selected
checkpoint into an immutable artifact on first use, always evaluates that artifact, and records
the attempt (``started`` -> ``completed`` / ``interrupted`` / ``failed``).

### `list_evaluations(run_id: 'str') -> 'list[dict]'`

Summaries of a run's saved evaluations (validation, test, robustness), in file-name order.

### `make_eval_env(protocol: 'EvalProtocol', reward: 'RewardConfig | None', gamma: 'float', *, render_mode: 'str | None' = None, record_steps: 'bool' = False, env_overrides: 'dict | None' = None) -> 'LunarLabRewardWrapper'`

The evaluation environment: LunarLander wrapped with ``apply=False``, so the policy is scored on the
original reward while every reward term is still recorded.

### `run_episode(env: 'LunarLabRewardWrapper', policy: 'Policy', seed: 'int') -> 'dict'`

Fly one episode from ``seed`` and return its summary. Refuses to report if the loop received anything but
the original reward.

### `summarize_for_index(result: 'dict', *, episodes: 'list[dict] | None' = None) -> 'dict'`

The few numbers stored in SQLite / shown in lists.

Results written by outcome classifier version 1 report ``outcome_classifier_version: 1`` and no
version-2 category rates of their own; ``derived_v2`` then holds rates derived from their stored
episode fields, labelled as derived (the stored file is never changed).

## Constants

- `LANDING_CATEGORIES` = `('strict_pad_landing', 'on_pad_not_strict', 'landed_not_within_pad', 'at_rest_after_body_contact', 'at_rest_geometry_unk…`
- `OUTCOME_CLASSIFIER_VERSION` = `2`
- `TERM_KEYS` = `('time_penalty', 'hover_bonus', 'potential_shaping', 'learned_reward')`
