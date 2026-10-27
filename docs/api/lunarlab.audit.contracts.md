# `lunarlab.audit.contracts`

Source: [`lunarlab/audit/contracts.py`](../../lunarlab/audit/contracts.py)

Input contracts of the task-independent audit layer: seeds, finite values and canonical JSON.

Every check here runs before an environment is created or an episode is played, and every failure names
the offending input. Nothing is coerced: a value either satisfies its contract as given or is refused.

* **Seeds.** An evaluation seed is a nonnegative integer given as a Python ``int`` or a NumPy integer
  scalar. Booleans (``True`` is an ``int`` in Python), floats such as ``3.0`` or ``1.5``, strings such as
  ``"7"`` and negative values are refused. A seed list is non-empty, ordered (a list, tuple, range or
  one-dimensional integer array, not a set or a string) and free of duplicates.
* **Finite values.** Original rewards, reward-term outputs, the original-reward weight and the discount
  must be finite real numbers; NaN and infinity are refused with the term or field named.
* **Canonical JSON.** Reward descriptions and provenance records are serialised with sorted keys, compact
  separators and no NaN or infinity, so a digest of them is well defined.

### class `AuditInputError`(ValueError)

An audit input violates its documented contract. Raised before any environment is created.

`AuditInputError(...)`


### class `NonFiniteValueError`(AuditInputError)

A reward, reward-term output, weight or discount is NaN or infinite.

`NonFiniteValueError(...)`


### `canonical_json(obj: 'Any') -> 'str'`

Sorted keys, compact separators, ASCII, and no NaN or infinity (refused, not written).

### `normalize_seeds(seeds: 'Any', label: 'str' = 'seeds') -> 'list[int]'`

The seeds as a list of Python ints, or :class:`AuditInputError` naming every contract violation.

### `require_finite(value: 'Any', what: 'str') -> 'float'`

``value`` as a finite float, or :class:`NonFiniteValueError` naming ``what``.

### `require_json_finite(obj: 'Any', what: 'str') -> 'None'`

Refuse a value that is not JSON-serialisable or contains NaN/infinity, naming the field.

### `seed_problems(seeds: 'Any', label: 'str' = 'seeds') -> 'list[str]'`

Why ``seeds`` violates the seed contract (empty list: it satisfies it). Deterministic messages.

### `split_problems(validation: 'Any', test: 'Any') -> 'list[str]'`

Contract violations of a validation/test split: each list valid on its own, and the two disjoint.

## Constants

- `MAX_LISTED` = `5`
- `SEED_CONTRACT` = `'an evaluation seed is a nonnegative integer (a Python int or NumPy integer scalar, not a bool, float or string), seed l…`
