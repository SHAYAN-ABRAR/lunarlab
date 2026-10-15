"""Robustness: how do trained policies cope with conditions they never trained on?

Every run trains in calm default physics. Here its frozen, validation-selected
checkpoint flies the *same* final-test episode seeds (identical terrain and
initial push) under changed physics: wind and turbulence (Gymnasium's own wind
model) or stronger gravity. The original reward is used, as everywhere.

These are separate, clearly named evaluations ("robustness:<condition>"). They
never replace or modify the calm final-test result, and nothing is tuned on them.
"""

from __future__ import annotations

from typing import Any

from lunarlab.storage import RunPaths, atomic_write_json, utc_now

CONDITIONS: dict[str, dict[str, Any]] = {
    "wind-5": {
        "label": "Light wind (5, turbulence 0.5)",
        "env": {"enable_wind": True, "wind_power": 5.0, "turbulence_power": 0.5},
    },
    "wind-10": {
        "label": "Moderate wind (10, turbulence 1.0)",
        "env": {"enable_wind": True, "wind_power": 10.0, "turbulence_power": 1.0},
    },
    "wind-15": {
        "label": "Strong wind (15, turbulence 1.5)",
        "env": {"enable_wind": True, "wind_power": 15.0, "turbulence_power": 1.5},
    },
    "gravity-11.5": {"label": "Heavy gravity (-11.5 instead of -10)", "env": {"gravity": -11.5}},
}
DEFAULT_EPISODES = 50


def evaluate_robustness(run_id: str, condition: str, *, episodes: int = DEFAULT_EPISODES) -> dict[str, Any]:
    from lunarlab.evaluation import evaluate_policy, summarize_for_index
    from lunarlab.runs import load_config, load_metadata, load_policy, log_event

    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}; choose from {', '.join(CONDITIONS)}")
    cfg = load_config(run_id)
    frozen = load_metadata(run_id).get("frozen_for_test")
    checkpoint = frozen["checkpoint"] if frozen else "best"
    policy, entry = load_policy(run_id, checkpoint, deterministic=cfg.eval_protocol.deterministic)
    seeds = list(cfg.eval_protocol.test_seeds)[:episodes]
    env_overrides = CONDITIONS[condition]["env"]
    res = evaluate_policy(
        policy,
        seeds,
        protocol=cfg.eval_protocol,
        reward=cfg.reward,
        gamma=cfg.gamma,
        env_overrides=env_overrides,
    )
    stamp = utc_now()
    result = {
        "run_id": run_id,
        "split": f"robustness:{condition}",
        "condition": condition,
        "condition_label": CONDITIONS[condition]["label"],
        "env_overrides": env_overrides,
        "created_at": stamp,
        "checkpoint": entry,
        "policy_label": policy.label,
        "deterministic": cfg.eval_protocol.deterministic,
        "seeds": seeds,
        "protocol_hash": cfg.eval_protocol.protocol_hash(),
        "reward_preset": cfg.reward.preset,
        "reward_hash": cfg.reward.content_hash(),
        **res,
    }
    name = f"robustness-{condition}-{entry['name'].removesuffix('.zip')}-{stamp.replace(':', '').replace('+0000', 'Z')}.json"
    atomic_write_json(RunPaths(run_id).evaluations / name, result)
    log_event(
        RunPaths(run_id),
        "info",
        f"robustness evaluation ({condition}) saved",
        file=name,
        **summarize_for_index(result),
    )
    result["file"] = name
    return result


def latest_robustness(run_id: str) -> dict[str, dict]:
    """Most recent summary per condition for one run."""
    from lunarlab.evaluation import list_evaluations

    out: dict[str, dict] = {}
    for e in list_evaluations(run_id):
        if str(e["split"]).startswith("robustness:"):
            out[e["split"].split(":", 1)[1]] = e
    return out
