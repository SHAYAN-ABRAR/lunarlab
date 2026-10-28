# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Input contracts of the task-independent audit layer: seeds, finite values and canonical JSON.

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
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence, Set
from typing import Any

import numpy as np

SEED_CONTRACT = (
    "an evaluation seed is a nonnegative integer (a Python int or NumPy integer scalar, not a bool, float or "
    "string), seed lists are non-empty ordered sequences without duplicates, and nothing is converted"
)
MAX_LISTED = 5  # offending entries quoted in one message


class AuditInputError(ValueError):
    """An audit input violates its documented contract. Raised before any environment is created."""


class NonFiniteValueError(AuditInputError):
    """A reward, reward-term output, weight or discount is NaN or infinite."""


def _describe(value: Any) -> str:
    return f"{value!r} ({type(value).__name__})"


def _seed_entry_problem(value: Any) -> str | None:
    if isinstance(value, (bool, np.bool_)):
        return "booleans are not seeds"
    if isinstance(value, (int, np.integer)):
        return "negative" if int(value) < 0 else None
    if isinstance(value, str):
        return "not an integer; numeric strings are not converted"
    if isinstance(value, (float, np.floating)):
        return "not an integer; floats are not converted, even when integral"
    return "not an integer"


def seed_problems(seeds: Any, label: str = "seeds") -> list[str]:
    """Why ``seeds`` violates the seed contract (empty list: it satisfies it). Deterministic messages."""
    if isinstance(seeds, (str, bytes, Mapping, Set)):
        return [f"{label} must be an ordered sequence of integers, not {type(seeds).__name__}"]
    if isinstance(seeds, np.ndarray) and seeds.ndim != 1:
        return [f"{label} must be one-dimensional, not an array of shape {seeds.shape}"]
    if not isinstance(seeds, (Sequence, np.ndarray, range)):
        return [f"{label} must be a list, tuple, range or one-dimensional array, not {type(seeds).__name__}"]
    items = list(seeds)
    if not items:
        return [f"{label} must not be empty"]
    bad = []
    for i, value in enumerate(items):
        problem = _seed_entry_problem(value)
        if problem:
            bad.append(f"{label}[{i}] = {_describe(value)}: {problem}")
    out = []
    if bad:
        more = f" (and {len(bad) - MAX_LISTED} more)" if len(bad) > MAX_LISTED else ""
        out.append(f"{label} must be nonnegative integers: " + "; ".join(bad[:MAX_LISTED]) + more)
        return out
    values = [int(v) for v in items]
    seen: set[int] = set()
    duplicates = []
    for v in values:
        if v in seen and v not in duplicates:
            duplicates.append(v)
        seen.add(v)
    if duplicates:
        out.append(f"{label} contain duplicates: {duplicates[:MAX_LISTED]}")
    return out


def normalize_seeds(seeds: Any, label: str = "seeds") -> list[int]:
    """The seeds as a list of Python ints, or :class:`AuditInputError` naming every contract violation."""
    problems = seed_problems(seeds, label)
    if problems:
        raise AuditInputError(f"invalid {label}: " + "; ".join(problems) + f". Contract: {SEED_CONTRACT}")
    return [int(v) for v in seeds]


def split_problems(validation: Any, test: Any) -> list[str]:
    """Contract violations of a validation/test split: each list valid on its own, and the two disjoint."""
    out = seed_problems(validation, "validation seeds") + seed_problems(test, "test seeds")
    if out:
        return out
    overlap = sorted(set(int(v) for v in validation) & set(int(v) for v in test))
    if overlap:
        out.append(f"validation and test seeds overlap: {overlap[:MAX_LISTED]}")
    return out


def require_finite(value: Any, what: str) -> float:
    """``value`` as a finite float, or :class:`NonFiniteValueError` naming ``what``."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise AuditInputError(f"{what} must be a real number, got {_describe(value)}") from None
    if not math.isfinite(number):
        raise NonFiniteValueError(f"{what} must be finite, got {number!r}")
    return number


def _nonfinite_paths(obj: Any, path: str) -> Iterable[str]:
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return
    if isinstance(obj, (int, np.integer)):
        return
    if isinstance(obj, (float, np.floating)):
        if not math.isfinite(float(obj)):
            yield f"{path} = {float(obj)!r}"
        return
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            yield from _nonfinite_paths(v, f"{path}.{k}")
        return
    if isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _nonfinite_paths(v, f"{path}[{i}]")


def require_json_finite(obj: Any, what: str) -> None:
    """Refuse a value that is not JSON-serialisable or contains NaN/infinity, naming the field."""
    bad = list(_nonfinite_paths(obj, what))
    if bad:
        raise NonFiniteValueError("non-finite value in " + "; ".join(bad[:MAX_LISTED]))
    try:
        json.dumps(obj, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise AuditInputError(f"{what} is not JSON-serialisable: {exc}") from None


def canonical_json(obj: Any) -> str:
    """Sorted keys, compact separators, ASCII, and no NaN or infinity (refused, not written)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
