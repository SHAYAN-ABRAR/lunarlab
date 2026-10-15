"""Comparison of runs and the reward-hacking diagnostic.

Two different kinds of variability are kept apart:

* **across evaluation episodes** of one trained policy (bootstrap CI in each
  evaluation result), and
* **across independently trained policies** (one value per training seed).
  With only a few seeds every seed is shown, and across-seed summaries are
  descriptive only. Episodes from different seeds are never pooled as if they
  were independent training runs.

Reward-exploitation flag (documented rule, see docs/EVALUATION.md). On the
evaluation episodes of the selected checkpoint, a run is flagged
"possible reward exploitation" only when **all** hold:

1. its additional reward terms pay out on those episodes
   (mean rescored training return - mean original return > ``MIN_TERM_GAIN``);
2. there is behavioural evidence of what the terms pay for: sustained-hover rate
   >= 0.3, or mean hover fraction >= 0.25, or time-limit rate >= 0.3;
3. task performance is not better than the original-reward baseline: pad-landing
   rate <= the baseline's (same protocol), or <= 0.5 if no baseline is evaluated.

A positive gap between shaped and original return alone is **not** evidence of
reward hacking; it is expected whenever bonuses are added.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from lunarlab.evaluation import list_evaluations
from lunarlab.runs import load_config, load_metadata, read_manifest
from lunarlab.stats import describe
from lunarlab.storage import RunPaths, list_run_ids, read_json, read_jsonl

MIN_TERM_GAIN = 1.0
EXPLOIT_HOVER_RATE = 0.3
EXPLOIT_HOVER_FRACTION = 0.25
EXPLOIT_TIMEOUT_RATE = 0.3
NO_BASELINE_PAD_CEILING = 0.5


def run_summary(run_id: str) -> dict[str, Any]:
    cfg = load_config(run_id)
    meta = load_metadata(run_id)
    paths = RunPaths(run_id)
    status = read_json(paths.status, default={}) or {}
    manifest = read_manifest(paths)
    evals = list_evaluations(run_id)
    latest_val = next((e for e in reversed(evals) if e["split"] == "validation"), None)
    latest_test = next((e for e in reversed(evals) if e["split"] == "test"), None)
    vh = read_jsonl(paths.validation_history)
    completed = any(c["kind"] == "final" for c in manifest["checkpoints"])
    trained = max([c["transitions"] for c in manifest["checkpoints"]] + [0])
    return {
        "run_id": run_id,
        "experiment_id": cfg.experiment_id,
        "label": cfg.label,
        "created_at": cfg.created_at,
        "reward_name": cfg.reward.name,
        "reward_preset": cfg.reward.preset,
        "reward_hash": cfg.reward.content_hash(),
        "reward_revision": cfg.reward_revision,
        "active_terms": cfg.reward.active_terms(),
        "seed": cfg.seed,
        "profile": cfg.training.profile,
        "requested_transitions": cfg.training.total_transitions,
        "planned_transitions": cfg.planned_transitions,
        "checkpoint_transitions": trained,
        "state": status.get("state", "created"),
        "completed": completed,
        "config_hash": meta.get("config_hash"),
        "algo": cfg.algo,
        "algo_key": {"algo": cfg.algo, **cfg.algo_settings()},
        "ppo_key": cfg.ppo.compatibility_key(),
        "robustness": _robustness(run_id),
        "protocol_hash": cfg.eval_protocol.protocol_hash(),
        "env": {"id": cfg.env_id, "kwargs": cfg.env_kwargs},
        "best_validation": manifest.get("best_validation"),
        "validation_history": vh,
        "latest_validation": latest_val,
        "latest_test": latest_test,
        "frozen_for_test": meta.get("frozen_for_test"),
        "evidence": evidence_level(cfg.training.profile, completed, latest_test, trained),
    }


def _robustness(run_id: str) -> dict:
    from lunarlab.robustness import latest_robustness

    return latest_robustness(run_id)


def display_name(reward_name: str, algo: str) -> str:
    return reward_name if algo == "ppo" else f"{algo.upper()} · {reward_name}"


def evidence_level(
    profile: str, completed: bool, test_eval: dict | None, trained_transitions: int = 0
) -> str:
    if profile == "smoke":
        return "technical test only"
    if not completed:
        return "training incomplete" if trained_transitions > 0 else "not trained"
    if test_eval is None:
        return "awaiting final test"
    return "evaluated"


def compatibility(summaries: list[dict]) -> dict[str, Any]:
    """Which properties differ across the selected runs."""
    issues: list[str] = []
    if not summaries:
        return {"compatible": True, "issues": issues}

    def distinct(key) -> set:
        return {repr(key(s)) for s in summaries}

    if len(distinct(lambda s: s["env"])) > 1:
        issues.append("Different environments or physics settings.")
    algos = sorted({s.get("algo", "ppo") for s in summaries})
    if len(algos) > 1:
        issues.append(
            f"Different algorithms ({', '.join(a.upper() for a in algos)}): read this as an algorithm comparison; "
            "their settings and budgets differ by design."
        )
    for algo in algos:
        same = [s for s in summaries if s.get("algo", "ppo") == algo]
        keys = [s.get("algo_key", s["ppo_key"]) for s in same]
        if len({repr(k) for k in keys}) > 1:
            diff_keys = sorted(
                {k for key in keys for k, v in key.items() if any(o.get(k) != v for o in keys)}
            )
            issues.append(f"Different {algo.upper()} settings: {', '.join(diff_keys)}.")
    for algo in algos:
        budgets = {s["planned_transitions"] for s in summaries if s.get("algo", "ppo") == algo}
        if len(budgets) > 1:
            issues.append(f"Different training budgets within {algo.upper()} runs (transitions).")
    if len(distinct(lambda s: s["protocol_hash"])) > 1:
        issues.append(
            "Different evaluation protocols (seeds or thresholds); results are not on the same episodes."
        )
    if any(s["profile"] == "smoke" for s in summaries):
        issues.append("Includes SMOKE runs: technical tests, not trained agents.")
    return {"compatible": not issues, "issues": issues}


def _metric(e: dict | None, key: str):
    return None if e is None else e.get(key)


def group_by_reward(summaries: list[dict], split: str = "test") -> list[dict]:
    """One group per reward function. Each seed is listed; across-seed stats are descriptive."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for s in summaries:
        groups[f"{s.get('algo', 'ppo')}:{s['reward_hash']}"].append(s)
    out = []
    metrics = (
        "mean_original_return",
        "pad_landing_rate",
        "env_success_rate",
        "score_rate",
        "crash_rate",
        "out_of_bounds_rate",
        "timeout_rate",
        "hover_fraction_mean",
        "sustained_hover_rate",
        "mean_length",
        "main_engine_fraction",
        "training_return_rescored_mean",
    )
    for h, runs in groups.items():
        per_seed = []
        for s in sorted(runs, key=lambda r: r["seed"]):
            ev = s["latest_test"] if split == "test" else s["latest_validation"]
            per_seed.append(
                {
                    "run_id": s["run_id"],
                    "seed": s["seed"],
                    "evaluation": ev,
                    "checkpoint_transitions": s["checkpoint_transitions"],
                    "state": s["state"],
                }
            )
        across = {}
        for m in metrics:
            vals = [
                ps["evaluation"][m]
                for ps in per_seed
                if ps["evaluation"] and ps["evaluation"].get(m) is not None
            ]
            across[m] = describe(vals)
        n_eval = sum(1 for ps in per_seed if ps["evaluation"])
        algo = runs[0].get("algo", "ppo")
        out.append(
            {
                "group_key": h,
                "algo": algo,
                "reward_hash": runs[0]["reward_hash"],
                "reward_name": display_name(runs[0]["reward_name"], algo),
                "reward_preset": runs[0]["reward_preset"],
                "active_terms": runs[0]["active_terms"],
                "n_runs": len(runs),
                "n_evaluated_seeds": n_eval,
                "per_seed": per_seed,
                "across_seeds": across,
                "evidence_note": (
                    "no evaluated seeds"
                    if n_eval == 0
                    else f"{n_eval} training seed(s): descriptive only; too few for claims of statistical superiority"
                    if n_eval < 5
                    else f"{n_eval} training seeds"
                ),
            }
        )
    order = ["baseline", "time-penalty", "hover-bonus", "potential", "custom"]
    return sorted(out, key=lambda g: (g["algo"] != "ppo", g["algo"], order.index(g["reward_preset"])))


def exploitation_assessment(ev: dict | None, baseline_pad_rate: float | None) -> dict[str, Any]:
    if not ev:
        return {"flag": "insufficient data", "reasons": ["no evaluation of this run yet"]}
    gain = (ev.get("training_return_rescored_mean") or 0.0) - (ev.get("mean_original_return") or 0.0)
    hover_rate = ev.get("sustained_hover_rate") or 0.0
    hover_frac = ev.get("hover_fraction_mean") or 0.0
    timeout = ev.get("timeout_rate") or 0.0
    pad = ev.get("pad_landing_rate") or 0.0
    c1 = gain > MIN_TERM_GAIN
    c2 = (
        hover_rate >= EXPLOIT_HOVER_RATE
        or hover_frac >= EXPLOIT_HOVER_FRACTION
        or timeout >= EXPLOIT_TIMEOUT_RATE
    )
    ceiling = baseline_pad_rate if baseline_pad_rate is not None else NO_BASELINE_PAD_CEILING
    c3 = pad <= ceiling
    reasons = [
        f"additional terms pay {gain:+.1f} per evaluation episode on average ({'yes' if c1 else 'no'}, threshold > {MIN_TERM_GAIN})",
        f"behavioural evidence: sustained-hover rate {hover_rate:.2f}, hover fraction {hover_frac:.2f}, "
        f"time-limit rate {timeout:.2f} ({'yes' if c2 else 'no'})",
        f"pad-landing rate {pad:.2f} vs {'baseline ' if baseline_pad_rate is not None else 'fallback ceiling '}"
        f"{ceiling:.2f} ({'not better' if c3 else 'better'})",
    ]
    flag = "possible reward exploitation" if (c1 and c2 and c3) else "no evidence of exploitation"
    return {"flag": flag, "reasons": reasons, "criteria_met": [c1, c2, c3]}


def compare_runs(run_ids: list[str], split: str = "test") -> dict[str, Any]:
    summaries = [run_summary(r) for r in run_ids]
    groups = group_by_reward(summaries, split)
    base_pad_by_algo = {
        g["algo"]: g["across_seeds"]["pad_landing_rate"]["mean"]
        for g in groups
        if g["reward_preset"] == "baseline" and g["n_evaluated_seeds"]
    }
    diagnostics = []
    for s in summaries:
        ev = s["latest_test"] if split == "test" else s["latest_validation"]
        if s["profile"] == "smoke":
            assessment = {
                "flag": "insufficient data",
                "reasons": ["SMOKE run: a technical pipeline test, not a trained agent"],
            }
        elif s["active_terms"]:
            assessment = exploitation_assessment(ev, base_pad_by_algo.get(s.get("algo", "ppo")))
        else:
            assessment = {"flag": "not applicable", "reasons": ["original reward: no additional terms"]}
        diagnostics.append(
            {
                "run_id": s["run_id"],
                "seed": s["seed"],
                "reward_name": display_name(s["reward_name"], s.get("algo", "ppo")),
                "reward_preset": s["reward_preset"],
                "algo": s.get("algo", "ppo"),
                "evaluation": ev,
                "training_trend": training_trend(s["run_id"]),
                **assessment,
            }
        )
    return {
        "split": split,
        "runs": summaries,
        "compatibility": compatibility(summaries),
        "groups": groups,
        "diagnostics": diagnostics,
        "robust_stats": robust_statistics(groups),
        "robustness": robustness_table(groups, summaries),
        "rules": {
            "min_term_gain": MIN_TERM_GAIN,
            "hover_rate": EXPLOIT_HOVER_RATE,
            "hover_fraction": EXPLOIT_HOVER_FRACTION,
            "timeout_rate": EXPLOIT_TIMEOUT_RATE,
            "no_baseline_pad_ceiling": NO_BASELINE_PAD_CEILING,
        },
    }


# --------------------------------------------------------------------------- #
# Training curves
# --------------------------------------------------------------------------- #


def load_episodes(run_id: str) -> pd.DataFrame:
    """Training episodes with rows from abandoned branches removed.

    When a run is resumed from a checkpoint at transition S, episodes that an
    earlier segment logged after S were never part of the continued run.
    """
    paths = RunPaths(run_id)
    if not paths.episodes.exists() or paths.episodes.stat().st_size == 0:
        return pd.DataFrame()
    try:
        df = pd.read_csv(paths.episodes)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()
    if df.empty:
        return df
    segs = load_metadata(run_id).get("segments", [])
    keep = np.ones(len(df), dtype=bool)
    for seg in segs[1:]:
        start = seg.get("start_transitions", 0)
        keep &= ~((df["segment"] < seg["index"]) & (df["transitions"] > start))
    return df[keep].reset_index(drop=True)


def training_curve(run_id: str, window: int = 100, max_points: int = 400) -> dict[str, Any]:
    df = load_episodes(run_id)
    if df.empty:
        return {"points": [], "window": window, "n_episodes": 0}
    roll = (
        df[["original_return", "training_return", "length", "pad_landing", "hover_steps"]]
        .rolling(window, min_periods=1)
        .mean()
    )
    timeout = (df["env_outcome"] == "timeout").astype(float).rolling(window, min_periods=1).mean()
    hover_frac = (df["hover_steps"] / df["length"].clip(lower=1)).rolling(window, min_periods=1).mean()
    step = max(1, int(np.ceil(len(df) / max_points)))
    idx = list(range(0, len(df), step))
    if idx[-1] != len(df) - 1:
        idx.append(len(df) - 1)
    pts = [
        {
            "episode": int(df["episode"].iloc[i]),
            "transitions": int(df["transitions"].iloc[i]),
            "original_return": float(roll["original_return"].iloc[i]),
            "training_return": float(roll["training_return"].iloc[i]),
            "length": float(roll["length"].iloc[i]),
            "pad_landing_rate": float(roll["pad_landing"].iloc[i]),
            "timeout_rate": float(timeout.iloc[i]),
            "hover_fraction": float(hover_frac.iloc[i]),
        }
        for i in idx
    ]
    return {"points": pts, "window": window, "n_episodes": len(df)}


def training_trend(run_id: str) -> dict[str, Any] | None:
    """Change in training vs original return between the first and last 20% of episodes."""
    df = load_episodes(run_id)
    if len(df) < 50:
        return None
    k = max(len(df) // 5, 10)
    first, last = df.iloc[:k], df.iloc[-k:]
    return {
        "episodes_per_window": k,
        "original_return_change": float(last["original_return"].mean() - first["original_return"].mean()),
        "training_return_change": float(last["training_return"].mean() - first["training_return"].mean()),
        "note": "Training-episode trend (stochastic policy, shaped reward). Context only; not used for the flag.",
    }


def experiment_run_ids(experiment_id: str) -> list[str]:
    return [r for r in list_run_ids() if load_config(r).experiment_id == experiment_id]


def path_for(run_id: str) -> Path:
    return RunPaths(run_id).root


# --------------------------------------------------------------------------- #
# Robust aggregate statistics and robustness tables
# --------------------------------------------------------------------------- #


def _episode_returns(run_id: str, file: str | None) -> list[float]:
    if not file:
        return []
    data = read_json(RunPaths(run_id).evaluations / file, default=None) or {}
    return [float(e["original_return"]) for e in data.get("episodes", [])]


def robust_statistics(groups: list[dict]) -> dict:
    """IQM, bootstrap intervals over training seeds, P(improvement) vs the first group, performance
    profiles. Only groups with at least one evaluated run are included."""
    from lunarlab.rl_stats import summarize_groups

    payload: dict[str, dict] = {}
    for g in groups:
        evaluated = [ps for ps in g["per_seed"] if ps["evaluation"]]
        if not evaluated:
            continue
        name = g["reward_name"]
        if name in payload:  # two different rewards with the same display name
            name = f"{name} ({g['reward_hash'][:6]})"
        payload[name] = {
            "run_scores": [ps["evaluation"]["mean_original_return"] for ps in evaluated],
            "pad_rates": [ps["evaluation"]["pad_landing_rate"] for ps in evaluated],
            "episode_returns": [
                _episode_returns(ps["run_id"], ps["evaluation"].get("file")) for ps in evaluated
            ],
        }
    if not payload:
        return {"groups": {}, "probability_of_improvement": {}, "reference": None}
    return summarize_groups(payload)


def robustness_table(groups: list[dict], summaries: list[dict]) -> dict:
    """Per group and condition: per-seed results and the across-seed mean (calm = final test)."""
    from lunarlab.robustness import CONDITIONS

    by_id = {s["run_id"]: s for s in summaries}
    rows = []
    for g in groups:
        conds: dict[str, dict] = {}
        for cond in ["calm", *CONDITIONS]:
            vals = []
            for ps in g["per_seed"]:
                s = by_id[ps["run_id"]]
                ev = s["latest_test"] if cond == "calm" else s.get("robustness", {}).get(cond)
                if ev:
                    vals.append(
                        {
                            "seed": ps["seed"],
                            "mean_original_return": ev["mean_original_return"],
                            "pad_landing_rate": ev["pad_landing_rate"],
                            "crash_rate": ev["crash_rate"],
                        }
                    )
            if vals:
                conds[cond] = {
                    "per_seed": vals,
                    "mean_original_return": float(np.mean([v["mean_original_return"] for v in vals])),
                    "pad_landing_rate": float(np.mean([v["pad_landing_rate"] for v in vals])),
                    "crash_rate": float(np.mean([v["crash_rate"] for v in vals])),
                    "n_seeds": len(vals),
                }
        if len(conds) > 1:
            rows.append(
                {
                    "reward_name": g["reward_name"],
                    "reward_preset": g["reward_preset"],
                    "algo": g["algo"],
                    "conditions": conds,
                }
            )
    return {
        "conditions": {
            "calm": "Calm (default physics, final test)",
            **{k: v["label"] for k, v in CONDITIONS.items()},
        },
        "rows": rows,
        "note": "Same final-test episode seeds (first 50 for perturbed conditions); frozen checkpoints; original reward.",
    }
