# `lunarlab.rl_stats`

Source: [`lunarlab/rl_stats.py`](../../lunarlab/rl_stats.py)

Robust aggregate statistics for comparing RL results across training seeds.

Follows the recommendations of Agarwal et al., "Deep Reinforcement Learning at the
Edge of the Statistical Precipice" (NeurIPS 2021), implemented directly here:

* **IQM** (interquartile mean) of per-run scores: the mean of the middle 50% of runs,
  less sensitive to one lucky or unlucky seed than the mean, more efficient than the median;
* **bootstrap confidence intervals over runs** (resampling *training seeds*, the unit that
  is actually random between experiments; not evaluation episodes);
* **probability of improvement** P(X > Y): the chance that a random run of X scores higher
  than a random run of Y (Mann–Whitney statistic), with a bootstrap interval;
* **performance profiles**: the fraction of evaluation episodes whose return exceeds a
  threshold τ, for every τ, with a band from bootstrapping runs.

With only a handful of seeds the intervals are wide. That is the honest result, not a flaw.

### `bootstrap_ci(values, stat=<function iqm>, *, reps: 'int' = 5000, level: 'float' = 0.95, seed: 'int' = 0)`

Percentile bootstrap interval of ``stat`` (the IQM by default) over training runs, resampling runs with
replacement; None for fewer than two runs.

### `bootstrap_difference_ci(x, y, stat=<function mean>, *, reps: 'int' = 5000, level: 'float' = 0.95, seed: 'int' = 0)`

Interval for stat(X) - stat(Y) between two independent groups of runs, resampling each group's
runs separately.

### `iqm(values) -> 'float | None'`

Interquartile mean, exactly as rliable computes it (scipy.stats.trim_mean(x, 0.25)):
drop int(0.25 n) values from each end and average the rest.

### `performance_profile(episode_returns_by_run: 'list[list[float]]', taus, *, reps: 'int' = 1000, seed: 'int' = 0) -> 'dict'`

Fraction of episodes with return > τ, pooling a group's runs; band from resampling runs.

### `probability_of_improvement(x, y) -> 'float | None'`

P(X > Y) + 0.5 P(X = Y) over all pairs of runs (Mann–Whitney U / (n·m)).

### `probability_of_improvement_ci(x, y, *, reps: 'int' = 5000, level: 'float' = 0.95, seed: 'int' = 0)`

Bootstrap interval of P(X > Y), resampling each group's runs separately.

When every run of one group beats every run of the other, the interval collapses (for example [0, 0]): complete
separation in the observed runs, not a zero probability for future runs.

### `summarize_groups(groups: 'dict[str, dict]') -> 'dict'`

``groups``: name → {"run_scores": [...], "episode_returns": [[...], ...], "pad_rates": [...]}.

Returns IQM / mean with run-bootstrap intervals, P(improvement) vs the first group, and
performance profiles on a shared τ grid.

## Constants

- `BOOTSTRAP_REPS` = `5000`
