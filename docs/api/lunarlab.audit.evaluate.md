# `lunarlab.audit.evaluate`

Source: [`lunarlab/audit/evaluate.py`](../../lunarlab/audit/evaluate.py)

Audit a policy on any registered task: original-reward evaluation with full reward accounting.

### `audit_policy(adapter: 'TaskAdapter', policy: 'Callable[[np.ndarray], Any]', seeds: 'Sequence[int]', *, gamma: 'float', terms: 'Mapping[str, RewardTerm] | None' = None, original_weight: 'float' = 1.0, env_kwargs: 'Mapping[str, Any] | None' = None) -> 'dict[str, Any]'`

Run ``policy`` (observation -> action) for one episode per seed and report every reward component.

The environment is wrapped with ``apply=False``: the policy is scored on the original reward, and the
training return each reward definition *would* have given is recorded beside it. Each episode's
original return is cross-checked against the rewards the loop received.

Error boundary: the seeds (seed contract), the discount, the original-reward weight and every term
description are validated before the environment is created. During the episodes, a non-finite
reward, an outcome outside the adapter's categories or a modified reward raises at once. The function
either returns a report covering every requested seed or raises; it never returns a partial report.

### `seed_split_problems(validation: 'Sequence[int]', test: 'Sequence[int]') -> 'list[str]'`

Problems that make a validation/test seed split unusable (empty list: valid).

Each list must satisfy the seed contract (:data:`~lunarlab.audit.contracts.SEED_CONTRACT`: non-empty,
nonnegative integers, no duplicates, nothing coerced), and the two lists must be disjoint, so the
checkpoint selected on validation episodes is never selected on the episodes that test it.

## Constants

- `SEED_CONTRACT` = `'an evaluation seed is a nonnegative integer (a Python int or NumPy integer scalar, not a bool, float or string), seed l…`
