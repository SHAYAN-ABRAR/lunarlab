"""Reward Stress Test: re-score one saved trajectory under candidate reward configs.

This is **re-scoring a fixed trajectory**. The flight is not re-simulated and no
policy is trained. It shows how each reward design would *score* behaviour that
already happened, and which parts of the flight each term pays for. It is not
a prediction of what PPO would learn under that reward, and it is not causal
evidence that a reward produces any behaviour.

The original reward of each step is taken from the recording. The additional
terms are recomputed with :func:`lunarlab.rewards.terms.compute_terms`, the same
function used during training.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from lunarlab.hover import HoverThresholds, hover_state
from lunarlab.rewards.config import RewardConfig
from lunarlab.rewards.terms import compute_terms

PHASES = ("hover", "airborne", "ground_contact", "final_step")
PHASE_LABELS = {
    "hover": "Hovering (detector: airborne, slow, level, in band)",
    "airborne": "Airborne, not hovering",
    "ground_contact": "One or both legs on the ground",
    "final_step": "The final transition (termination or time limit)",
}


def _phase(obs: np.ndarray, detector: HoverThresholds) -> str:
    if obs[6] > 0.5 or obs[7] > 0.5:
        return "ground_contact"
    return "hover" if hover_state(obs, detector) else "airborne"


def rescore(
    telemetry: dict,
    configs: list[RewardConfig],
    *,
    gamma: float,
    detector: HoverThresholds,
    max_points: int = 400,
) -> dict[str, Any]:
    rows = telemetry["rows"]
    if len(rows) < 2:
        raise ValueError("trajectory has no transitions")
    obs = [np.asarray(r["obs"], dtype=np.float32) for r in rows]
    T = len(rows) - 1
    phases = [_phase(obs[k], detector) for k in range(T + 1)]
    original = np.array([float(rows[k]["original_reward"]) for k in range(1, T + 1)])
    disc = gamma ** np.arange(T)
    stride = max(1, int(np.ceil((T + 1) / max_points)))
    idx = list(range(0, T + 1, stride))
    if idx[-1] != T:
        idx.append(T)

    step_phase = np.array(phases[1:], dtype=object)  # phase of the state each transition leads to
    # The last transition gets its own phase: on true termination potential shaping pays
    # -alpha*Phi(s) there (Phi(terminal) = 0), which cancels the potential collected so far.
    step_phase[-1] = "final_step"
    masks = {p: step_phase == p for p in PHASES}
    phase_steps = {p: int(masks[p].sum()) for p in PHASES}
    results = []
    for cfg in configs:
        learned = None
        if cfg.learned.enabled:
            from lunarlab.preferences.model import load_reward_model

            learned = load_reward_model(str(cfg.learned.model_id))
        term_series: dict[str, np.ndarray] = {}
        for k in range(1, T + 1):
            terms = compute_terms(
                obs[k - 1],
                rows[k]["action"],
                obs[k],
                terminated=bool(rows[k]["terminated"]),
                truncated=bool(rows[k]["truncated"]),
                config=cfg,
                gamma=gamma,
                learned_model=learned,
            )
            for name, v in terms.items():
                term_series.setdefault(name, np.zeros(T))[k - 1] = v
        extra = sum(term_series.values()) if term_series else np.zeros(T)
        training = cfg.original_weight * original + extra
        cum_training = np.concatenate([[0.0], np.cumsum(training)])
        by_phase = {}
        for name, series in {"original": original, **term_series}.items():
            by_phase[name] = {p: float(series[masks[p]].sum()) for p in PHASES}
        explanations = []
        for name, series in term_series.items():
            total = float(series.sum())
            if abs(total) < 1e-9:
                explanations.append(f"{name}: contributes nothing on this trajectory.")
                continue
            shares = by_phase[name]
            dominant = max(PHASES, key=lambda p: abs(shares[p]))
            pct = 100.0 * abs(shares[dominant]) / max(sum(abs(v) for v in shares.values()), 1e-12)
            sign = "rewards" if shares[dominant] > 0 else "penalises"
            explanations.append(
                f"{name}: {total:+.2f} in total; {pct:.0f}% of its magnitude comes from "
                f"'{PHASE_LABELS[dominant].split(' (')[0].lower()}' steps, which it {sign}."
            )
        results.append(
            {
                "name": cfg.name,
                "preset": cfg.preset,
                "reward_hash": cfg.content_hash(),
                "active_terms": cfg.active_terms(),
                "undiscounted": {
                    "original": float(original.sum()),
                    "training": float(training.sum()),
                    "terms": {k: float(v.sum()) for k, v in term_series.items()},
                },
                "discounted": {
                    "original": float((disc * original).sum()),
                    "training": float((disc * training).sum()),
                    "terms": {k: float((disc * v).sum()) for k, v in term_series.items()},
                },
                "by_phase": by_phase,
                "cumulative_training": [float(cum_training[i]) for i in idx],
                "explanations": explanations,
            }
        )
    cum_original = np.concatenate([[0.0], np.cumsum(original)])
    return {
        "kind": "rescoring of a fixed, already-recorded trajectory",
        "disclaimer": (
            "Re-scoring only: the same flight is scored under each reward. This is not retraining, not a "
            "prediction of the policy each reward would produce, and not causal proof of any behaviour."
        ),
        "recording_id": telemetry.get("recording_id"),
        "policy": telemetry.get("policy"),
        "episode_seed": telemetry.get("episode_seed"),
        "gamma": gamma,
        "steps": T,
        "outcome": telemetry.get("episode", {}).get("env_outcome"),
        "phase_steps": phase_steps,
        "phase_labels": PHASE_LABELS,
        "series_index": idx,
        "cumulative_original": [float(cum_original[i]) for i in idx],
        "configs": results,
    }
