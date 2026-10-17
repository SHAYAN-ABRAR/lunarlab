# `lunarlab.stats`

Source: [`lunarlab/stats.py`](../../lunarlab/stats.py)

Small, explicit statistics helpers.

* Episode-level uncertainty for a mean: percentile bootstrap over evaluation
  episodes with a fixed RNG seed (reproducible).
* Rates: Wilson score interval.

These describe variability *across evaluation episodes of one policy*. They say
nothing about variability across independently trained policies; that is
reported separately, per training seed (see ``lunarlab.compare``).

### `bootstrap_ci_mean(values, *, level: 'float' = 0.95, resamples: 'int' = 5000, seed: 'int' = 0) -> 'list[float] | None'`

Percentile bootstrap interval of the mean of ``values`` with a fixed seed; None for fewer than two values.

### `describe(values: 'list[float] | np.ndarray') -> 'dict'`

Count, mean, sample standard deviation (ddof = 1), median, minimum and maximum (None values when empty).

### `rate(flags: 'list[bool]', level: 'float' = 0.95) -> 'dict'`

A proportion with its count and Wilson interval: ``{"k", "n", "rate", "ci"}``.

### `wilson_interval(k: 'int', n: 'int', level: 'float' = 0.95) -> 'list[float] | None'`

Wilson score interval for the proportion k / n (closed at 0 and 1); None when n = 0.
