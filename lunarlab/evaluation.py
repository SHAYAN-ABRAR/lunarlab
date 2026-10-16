"""Evaluation with the unmodified environment reward.

Every policy is evaluated in a fresh ``LunarLander-v3`` with the default physics.
The only wrapper added is :class:`LunarLabRewardWrapper` in ``apply=False``
mode: it hands the **original** reward back unchanged and merely records what the
run's training reward *would* have added (useful for reward-hacking diagnostics).
The same fixed episode seeds are used for every compared policy.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from lunarlab.config import EvalProtocol
from lunarlab.env import make_env
from lunarlab.policies import Policy
from lunarlab.rewards.config import TERM_KEYS, RewardConfig, preset
from lunarlab.rewards.wrapper import LunarLabRewardWrapper
from lunarlab.stats import bootstrap_ci_mean, describe, rate
from lunarlab.storage import RunPaths, atomic_write_json, utc_now


class EvaluationAborted(RuntimeError):
    pass


def make_eval_env(
    protocol: EvalProtocol,
    reward: RewardConfig | None,
    gamma: float,
    *,
    render_mode: str | None = None,
    record_steps: bool = False,
    env_overrides: dict | None = None,
) -> LunarLabRewardWrapper:
    return LunarLabRewardWrapper(
        make_env(render_mode=render_mode, overrides=env_overrides),
        reward or preset("baseline"),
        gamma,
        apply=False,  # evaluation reward is ALWAYS the original reward
        detector=protocol.hover_detector,
        pad_criteria=protocol.pad_landing,
        record_steps=record_steps,
    )


def run_episode(env: LunarLabRewardWrapper, policy: Policy, seed: int) -> dict:
    obs, _ = env.reset(seed=int(seed))
    policy.reset(int(seed))
    original_total = 0.0
    while True:
        obs, reward, terminated, truncated, info = env.step(policy.act(obs))
        original_total += float(reward)
        if terminated or truncated:
            ep = dict(info["lunarlab_episode"])
            # Cross-check: what the loop received must be the original return.
            if abs(original_total - ep["original_return"]) > 1e-6:
                raise RuntimeError("evaluation received a modified reward; refusing to report it")
            ep["seed"] = int(seed)
            return ep


def evaluate_policy(
    policy: Policy,
    seeds: list[int],
    *,
    protocol: EvalProtocol,
    reward: RewardConfig | None,
    gamma: float,
    progress: Callable[[int, int], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    env_overrides: dict | None = None,
) -> dict[str, Any]:
    env = make_eval_env(protocol, reward, gamma, env_overrides=env_overrides)
    episodes: list[dict] = []
    t0 = time.perf_counter()
    try:
        for i, s in enumerate(seeds):
            if should_stop and should_stop():
                raise EvaluationAborted("evaluation stopped on request")
            episodes.append(run_episode(env, policy, s))
            if progress:
                progress(i + 1, len(seeds))
    finally:
        env.close()
    return {
        "episodes": episodes,
        "aggregate": aggregate(episodes, protocol),
        "elapsed_s": time.perf_counter() - t0,
    }


def aggregate(episodes: list[dict], protocol: EvalProtocol) -> dict[str, Any]:
    returns = [e["original_return"] for e in episodes]
    outcomes = [e.get("env_outcome", "unknown") for e in episodes]
    lv = protocol.ci_level

    def outcome_rate(name: str) -> dict:
        return rate([o == name for o in outcomes], lv)

    actions = {k: describe([e["actions"][k] for e in episodes]) for k in ("noop", "left", "main", "right")}
    lengths = [e["length"] for e in episodes]
    main_frac = [e["actions"]["main"] / max(e["length"], 1) for e in episodes]
    side_frac = [(e["actions"]["left"] + e["actions"]["right"]) / max(e["length"], 1) for e in episodes]
    return {
        "n_episodes": len(episodes),
        "original_return": {
            **describe(returns),
            "ci": bootstrap_ci_mean(
                returns, level=lv, resamples=protocol.bootstrap_resamples, seed=protocol.bootstrap_seed
            ),
            "ci_method": f"percentile bootstrap of the mean over episodes ({protocol.bootstrap_resamples} resamples, seed {protocol.bootstrap_seed})",
        },
        "score_threshold": protocol.score_threshold,
        "score_at_least_threshold": rate([r >= protocol.score_threshold for r in returns], lv),
        "env_success_at_rest": outcome_rate("at_rest"),
        "pad_landing": rate([bool(e.get("pad_landing")) for e in episodes], lv),
        "landed_off_pad": rate([bool(e.get("landed_off_pad")) for e in episodes], lv),
        "crash": outcome_rate("crash"),
        "out_of_bounds": outcome_rate("out_of_bounds"),
        "timeout": outcome_rate("timeout"),
        "unknown_outcome": outcome_rate("unknown"),
        "body_contact": rate([bool(e.get("body_contact")) for e in episodes], lv),
        "episode_length": describe(lengths),
        "hover_fraction": describe([e["hover_fraction"] for e in episodes]),
        "hover_steps": describe([e["hover_steps"] for e in episodes]),
        "longest_hover_streak": describe([e["longest_hover_streak"] for e in episodes]),
        "sustained_hover": rate(
            [e["longest_hover_streak"] >= protocol.sustained_hover_min_steps for e in episodes], lv
        ),
        "actions": actions,
        "main_engine_fraction": describe(main_frac),
        "side_engine_fraction": describe(side_frac),
        "training_reward_rescored": {
            "note": "What the run's training reward would have paid on these evaluation episodes "
            "(computed after the fact; never fed to the policy or used for selection).",
            "return": describe([e["training_return"] for e in episodes]),
            "terms": {k: describe([e["term_returns"].get(k, 0.0) for e in episodes]) for k in TERM_KEYS},
        },
    }


def summarize_for_index(result: dict) -> dict:
    """The few numbers stored in SQLite / shown in lists."""
    a = result["aggregate"]
    return {
        "n_episodes": a["n_episodes"],
        "mean_original_return": a["original_return"]["mean"],
        "std_original_return": a["original_return"]["std"],
        "median_original_return": a["original_return"]["median"],
        "ci": a["original_return"]["ci"],
        "pad_landing_rate": a["pad_landing"]["rate"],
        "env_success_rate": a["env_success_at_rest"]["rate"],
        "score_rate": a["score_at_least_threshold"]["rate"],
        "crash_rate": a["crash"]["rate"],
        "out_of_bounds_rate": a["out_of_bounds"]["rate"],
        "timeout_rate": a["timeout"]["rate"],
        "hover_fraction_mean": a["hover_fraction"]["mean"],
        "sustained_hover_rate": a["sustained_hover"]["rate"],
        "mean_length": a["episode_length"]["mean"],
        "main_engine_fraction": a["main_engine_fraction"]["mean"],
        "training_return_rescored_mean": a["training_reward_rescored"]["return"]["mean"],
    }


def evaluate_run(
    run_id: str,
    split: str,
    *,
    checkpoint: str = "best",
    progress: Callable[[int, int], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Evaluate a run's checkpoint on the validation or final-test seeds and save the result."""
    from lunarlab.runs import RunError, load_config, load_metadata, load_policy, log_event, update_metadata

    cfg = load_config(run_id)
    paths = RunPaths(run_id)
    protocol = cfg.eval_protocol
    seeds = protocol.seeds_for(split)
    policy, entry = load_policy(run_id, checkpoint, deterministic=protocol.deterministic)

    repeat_index = 0
    if split == "test":
        meta = load_metadata(run_id)
        if meta.get("tuning"):
            raise RunError(
                "this run is a tuning trial: trials are judged on validation only and never evaluated on the "
                "final-test seeds. Create a normal run from the study's best settings and test that one."
            )
        frozen = meta.get("frozen_for_test")
        if frozen is None:
            frozen = {
                "checkpoint": entry["name"],
                "checkpoint_sha256": entry["sha256"],
                "config_hash": meta.get("config_hash"),
                "frozen_at": utc_now(),
            }
            update_metadata(run_id, frozen_for_test=frozen)
            log_event(paths, "info", "run frozen for final test evaluation", **frozen)
        elif frozen["checkpoint_sha256"] != entry["sha256"]:
            raise RunError(
                f"this run was frozen for the final test with checkpoint {frozen['checkpoint']} at "
                f"{frozen['frozen_at']}; evaluating a different checkpoint on the test seeds would be "
                "selection on the test set"
            )
        repeat_index = int(meta.get("test_evaluations", 0))
        update_metadata(run_id, test_evaluations=repeat_index + 1)

    res = evaluate_policy(
        policy,
        seeds,
        protocol=protocol,
        reward=cfg.reward,
        gamma=cfg.gamma,
        progress=progress,
        should_stop=should_stop,
    )
    stamp = utc_now()
    result = {
        "run_id": run_id,
        "split": split,
        "created_at": stamp,
        "checkpoint": entry,
        "policy_label": policy.label,
        "deterministic": protocol.deterministic,
        "seeds": seeds,
        "protocol": protocol.model_dump(mode="json"),
        "protocol_hash": protocol.protocol_hash(),
        "reward_preset": cfg.reward.preset,
        "reward_hash": cfg.reward.content_hash(),
        "repeat_index": repeat_index,
        **res,
    }
    name = f"{split}-{entry['name'].removesuffix('.zip')}-{stamp.replace(':', '').replace('+0000', 'Z')}.json"
    out = paths.evaluations / name
    atomic_write_json(out, result)
    log_event(paths, "info", f"{split} evaluation saved", file=name, **summarize_for_index(result))
    result["file"] = name
    return result


def list_evaluations(run_id: str) -> list[dict]:
    from lunarlab.storage import read_json

    paths = RunPaths(run_id)
    out = []
    if not paths.evaluations.exists():
        return out
    for p in sorted(paths.evaluations.glob("*.json")):
        r = read_json(p)
        if not r or "aggregate" not in r:
            continue
        out.append(
            {
                "file": p.name,
                "split": r["split"],
                "created_at": r["created_at"],
                "checkpoint": r["checkpoint"]["name"],
                "checkpoint_transitions": r["checkpoint"]["transitions"],
                "repeat_index": r.get("repeat_index", 0),
                "protocol_hash": r.get("protocol_hash"),
                **summarize_for_index(r),
            }
        )
    return out
