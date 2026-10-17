# `lunarlab.audit.evaluate`

Source: [`lunarlab/audit/evaluate.py`](../../lunarlab/audit/evaluate.py)

Audit a policy on any registered task: original-reward evaluation with full reward accounting.

### `audit_policy(adapter: 'TaskAdapter', policy: 'Callable[[np.ndarray], Any]', seeds: 'Sequence[int]', *, gamma: 'float', terms: 'Mapping[str, RewardTerm] | None' = None, original_weight: 'float' = 1.0, env_kwargs: 'Mapping[str, Any] | None' = None) -> 'dict[str, Any]'`

Run ``policy`` (observation -> action) for one episode per seed and report every reward component.

The environment is wrapped with ``apply=False``: the policy is scored on the original reward, and the
training return each reward definition *would* have given is recorded beside it. Each episode's
original return is cross-checked against the rewards the loop received.

### `seed_split_problems(validation: 'Sequence[int]', test: 'Sequence[int]') -> 'list[str]'`

Problems that make a validation/test seed split unusable (empty list: valid).

Seeds must be plain integers, each list free of duplicates, and the two lists disjoint, so the
checkpoint selected on validation episodes is never selected on the episodes that test it.
