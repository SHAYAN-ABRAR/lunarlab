"""Small, explicit statistics helpers.

* Episode-level uncertainty for a mean: percentile bootstrap over evaluation
  episodes with a fixed RNG seed (reproducible).
* Rates: Wilson score interval.

These describe variability *across evaluation episodes of one policy*. They say
nothing about variability across independently trained policies; that is
reported separately, per training seed (see ``lunarlab.compare``).
"""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np


def describe(values: list[float] | np.ndarray) -> dict:
    a = np.asarray(values, dtype=float)
    n = int(a.size)
    if n == 0:
        return {"n": 0, "mean": None, "std": None, "median": None, "min": None, "max": None}
    return {
        "n": n,
        "mean": float(a.mean()),
        "std": float(a.std(ddof=1)) if n > 1 else 0.0,
        "median": float(np.median(a)),
        "min": float(a.min()),
        "max": float(a.max()),
    }


def bootstrap_ci_mean(
    values, *, level: float = 0.95, resamples: int = 5000, seed: int = 0
) -> list[float] | None:
    a = np.asarray(values, dtype=float)
    if a.size < 2:
        return None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, a.size, size=(resamples, a.size))
    means = a[idx].mean(axis=1)
    lo, hi = np.quantile(means, [(1 - level) / 2, 1 - (1 - level) / 2])
    return [float(lo), float(hi)]


def wilson_interval(k: int, n: int, level: float = 0.95) -> list[float] | None:
    if n <= 0:
        return None
    z = NormalDist().inv_cdf(1 - (1 - level) / 2)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    lo = 0.0 if k == 0 else max(0.0, centre - half)
    hi = 1.0 if k == n else min(1.0, centre + half)
    return [lo, hi]


def rate(flags: list[bool], level: float = 0.95) -> dict:
    n = len(flags)
    k = int(sum(bool(f) for f in flags))
    return {"k": k, "n": n, "rate": (k / n) if n else None, "ci": wilson_interval(k, n, level)}
