"""Robust aggregate statistics for comparing RL results across training seeds.

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
"""

from __future__ import annotations

import math

import numpy as np

BOOTSTRAP_REPS = 5000


def iqm(values) -> float | None:
    """Interquartile mean, exactly as rliable computes it (scipy.stats.trim_mean(x, 0.25)):
    drop int(0.25 n) values from each end and average the rest."""
    a = np.sort(np.asarray(values, dtype=float))
    n = a.size
    if n == 0:
        return None
    k = int(0.25 * n)
    return float(a[k : n - k].mean())


def bootstrap_ci(values, stat=iqm, *, reps: int = BOOTSTRAP_REPS, level: float = 0.95, seed: int = 0):
    a = np.asarray(values, dtype=float)
    if a.size < 2:
        return None
    rng = np.random.default_rng(seed)
    stats = np.array([stat(a[rng.integers(0, a.size, a.size)]) for _ in range(reps)])
    lo, hi = np.quantile(stats, [(1 - level) / 2, 1 - (1 - level) / 2])
    return [float(lo), float(hi)]


def bootstrap_difference_ci(
    x, y, stat=np.mean, *, reps: int = BOOTSTRAP_REPS, level: float = 0.95, seed: int = 0
):
    """Interval for stat(X) - stat(Y) between two independent groups of runs, resampling each group's
    runs separately."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 2 or y.size < 2:
        return None
    rng = np.random.default_rng(seed)
    d = [
        stat(x[rng.integers(0, x.size, x.size)]) - stat(y[rng.integers(0, y.size, y.size)])
        for _ in range(reps)
    ]
    lo, hi = np.quantile(d, [(1 - level) / 2, 1 - (1 - level) / 2])
    return [float(lo), float(hi)]


def probability_of_improvement(x, y) -> float | None:
    """P(X > Y) + 0.5 P(X = Y) over all pairs of runs (Mann–Whitney U / (n·m))."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size == 0 or y.size == 0:
        return None
    gt = (x[:, None] > y[None, :]).sum()
    eq = (x[:, None] == y[None, :]).sum()
    return float((gt + 0.5 * eq) / (x.size * y.size))


def probability_of_improvement_ci(x, y, *, reps: int = BOOTSTRAP_REPS, level: float = 0.95, seed: int = 0):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 2 or y.size < 2:
        return None
    rng = np.random.default_rng(seed)
    vals = [
        probability_of_improvement(x[rng.integers(0, x.size, x.size)], y[rng.integers(0, y.size, y.size)])
        for _ in range(reps)
    ]
    lo, hi = np.quantile(vals, [(1 - level) / 2, 1 - (1 - level) / 2])
    return [float(lo), float(hi)]


def performance_profile(
    episode_returns_by_run: list[list[float]], taus, *, reps: int = 1000, seed: int = 0
) -> dict:
    """Fraction of episodes with return > τ, pooling a group's runs; band from resampling runs."""
    taus = np.asarray(taus, dtype=float)
    runs = [np.asarray(r, dtype=float) for r in episode_returns_by_run if len(r)]
    if not runs:
        return {"tau": taus.tolist(), "fraction": [], "lo": [], "hi": []}

    def frac(selected):
        pooled = np.concatenate(selected)
        return (pooled[None, :] > taus[:, None]).mean(axis=1)

    point = frac(runs)
    if len(runs) < 2:
        return {"tau": taus.tolist(), "fraction": point.tolist(), "lo": point.tolist(), "hi": point.tolist()}
    rng = np.random.default_rng(seed)
    boot = np.stack([frac([runs[i] for i in rng.integers(0, len(runs), len(runs))]) for _ in range(reps)])
    lo, hi = np.quantile(boot, [0.025, 0.975], axis=0)
    return {"tau": taus.tolist(), "fraction": point.tolist(), "lo": lo.tolist(), "hi": hi.tolist()}


def summarize_groups(groups: dict[str, dict]) -> dict:
    """``groups``: name → {"run_scores": [...], "episode_returns": [[...], ...], "pad_rates": [...]}.

    Returns IQM / mean with run-bootstrap intervals, P(improvement) vs the first group, and
    performance profiles on a shared τ grid.
    """
    names = list(groups)
    out: dict = {"groups": {}, "probability_of_improvement": {}, "reference": names[0] if names else None}
    all_returns = [x for g in groups.values() for run in g["episode_returns"] for x in run]
    lo = math.floor(min(all_returns) / 50) * 50 if all_returns else -300
    hi = math.ceil(max(all_returns) / 50) * 50 if all_returns else 300
    taus = np.linspace(lo, hi, 61)
    for name, g in groups.items():
        scores = g["run_scores"]
        out["groups"][name] = {
            "n_runs": len(scores),
            "run_scores": scores,
            "iqm": iqm(scores),
            "iqm_ci": bootstrap_ci(scores, iqm),
            "mean": float(np.mean(scores)) if scores else None,
            "mean_ci": bootstrap_ci(scores, np.mean),
            "pad_rate_mean": float(np.mean(g["pad_rates"])) if g.get("pad_rates") else None,
            "pad_rate_ci": bootstrap_ci(g["pad_rates"], np.mean) if g.get("pad_rates") else None,
            "profile": performance_profile(g["episode_returns"], taus),
        }
    if names:
        ref = groups[names[0]]["run_scores"]
        for name in names[1:]:
            x = groups[name]["run_scores"]
            out["probability_of_improvement"][name] = {
                "vs": names[0],
                "p": probability_of_improvement(x, ref),
                "ci": probability_of_improvement_ci(x, ref),
            }
    out["note"] = (
        "IQM and intervals are computed over training seeds (bootstrap of runs); performance profiles pool "
        "the evaluation episodes of each group's runs. With few seeds, intervals are wide."
    )
    return out
