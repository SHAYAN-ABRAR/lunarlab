"""Evaluation with the unmodified environment reward.

Every policy is evaluated in a fresh ``LunarLander-v3`` with the default physics.
The only wrapper added is :class:`LunarLabRewardWrapper` in ``apply=False``
mode: it hands the **original** reward back unchanged and merely records what the
run's training reward *would* have added (useful for reward-hacking diagnostics).
The same fixed episode seeds are used for every compared policy.

Every result records the environment that actually ran (``environment``: id, keyword arguments,
robustness overrides and the effective physics read back from the instantiated env); an evaluation
under the protocol's own environment refuses to report if that differs from what the protocol
declares. Final tests run under the run's worker lock, on the frozen artifact (``lunarlab.freeze``),
with every attempt recorded.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from lunarlab.config import EvalProtocol
from lunarlab.env import instantiated_environment, make_env
from lunarlab.outcomes import LANDING_CATEGORIES, OUTCOME_CLASSIFIER_VERSION, derived_v2_rates
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
    environment = instantiated_environment(env, env_overrides)
    environment["matches_protocol"] = (
        not environment["overrides"]
        and environment["env_id"] == protocol.env_id
        and environment["kwargs"] == protocol.env_kwargs
    )
    if not env_overrides and not environment["matches_protocol"]:
        env.close()
        raise RuntimeError(
            f"the instantiated environment {environment['env_id']} {environment['kwargs']} does not match the "
            f"protocol's declaration {protocol.env_id} {protocol.env_kwargs}; refusing to report"
        )
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
        "environment": environment,
    }


def aggregate(episodes: list[dict], protocol: EvalProtocol) -> dict[str, Any]:
    """Rates and summaries over episodes. The outcome classifier version is detected from the episodes:
    version 2 adds landing categories; ``landed_off_pad`` means ``landed_not_within_pad`` there."""
    version = (
        OUTCOME_CLASSIFIER_VERSION
        if episodes
        and all(e.get("outcome_classifier_version") == OUTCOME_CLASSIFIER_VERSION for e in episodes)
        else 1
    )
    returns = [e["original_return"] for e in episodes]
    outcomes = [e.get("env_outcome", "unknown") for e in episodes]
    lv = protocol.ci_level

    def outcome_rate(name: str) -> dict:
        return rate([o == name for o in outcomes], lv)

    actions = {k: describe([e["actions"][k] for e in episodes]) for k in ("noop", "left", "main", "right")}
    lengths = [e["length"] for e in episodes]
    main_frac = [e["actions"]["main"] / max(e["length"], 1) for e in episodes]
    side_frac = [(e["actions"]["left"] + e["actions"]["right"]) / max(e["length"], 1) for e in episodes]
    categories = (
        {c: rate([e.get("landing_category") == c for e in episodes], lv) for c in LANDING_CATEGORIES}
        if version >= 2
        else None
    )
    return {
        "n_episodes": len(episodes),
        "outcome_classifier_version": version,
        **({"landing_categories": categories} if categories else {}),
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


def summarize_for_index(result: dict, *, episodes: list[dict] | None = None) -> dict:
    """The few numbers stored in SQLite / shown in lists.

    Results written by outcome classifier version 1 report ``outcome_classifier_version: 1`` and no
    version-2 category rates of their own; ``derived_v2`` then holds rates derived from their stored
    episode fields, labelled as derived (the stored file is never changed)."""
    a = result["aggregate"]
    version = int(a.get("outcome_classifier_version", 1))
    cats = a.get("landing_categories") or {}

    def cat(name: str):
        return (cats.get(name) or {}).get("rate") if version >= 2 else None

    derived = None
    if version < 2:
        eps = episodes if episodes is not None else result.get("episodes")
        criteria = ((result.get("protocol") or {}).get("pad_landing")) or {}
        derived = derived_v2_rates(
            eps or [], max_final_abs_angle_rad=float(criteria.get("max_final_abs_angle_rad", 0.35))
        )
    return {
        "outcome_classifier_version": version,
        "on_pad_not_strict_rate": cat("on_pad_not_strict"),
        "landed_not_within_pad_rate": cat("landed_not_within_pad"),
        "at_rest_after_body_contact_rate": cat("at_rest_after_body_contact"),
        "at_rest_geometry_unknown_rate": cat("at_rest_geometry_unknown"),
        **({"derived_v2": derived} if derived else {}),
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
    """Evaluate a run's checkpoint on the validation or final-test seeds and save the result.

    The final test (``split="test"``) runs under the run's worker lock: it freezes the selected
    checkpoint into an immutable artifact on first use, always evaluates that artifact, and records
    the attempt (``started`` -> ``completed`` / ``interrupted`` / ``failed``)."""
    from lunarlab.runs import RunError, load_config, load_policy

    cfg = load_config(run_id)
    protocol = cfg.eval_protocol
    try:
        protocol.require_valid()
    except ValueError as exc:
        raise RunError(f"{exc}. This run can be inspected, but not evaluated.") from exc
    seeds = protocol.seeds_for(split)
    if split == "test":
        return _evaluate_final_test(run_id, cfg, checkpoint, progress=progress, should_stop=should_stop)
    policy, entry = load_policy(run_id, checkpoint, deterministic=protocol.deterministic)
    res = evaluate_policy(
        policy,
        seeds,
        protocol=protocol,
        reward=cfg.reward,
        gamma=cfg.gamma,
        progress=progress,
        should_stop=should_stop,
    )
    return _save_result(run_id, cfg, split, entry, policy.label, seeds, res, repeat_index=0)


def _evaluate_final_test(run_id: str, cfg, checkpoint: str, *, progress, should_stop) -> dict[str, Any]:
    from lunarlab.freeze import (
        completed_test_count,
        finish_attempt,
        freeze_for_test,
        start_attempt,
    )
    from lunarlab.lineage import record_test_exposure
    from lunarlab.locks import FileLock, LockBusy
    from lunarlab.runs import RunError, load_metadata, load_policy

    paths = RunPaths(run_id)
    if load_metadata(run_id).get("tuning"):
        raise RunError(
            "this run is a tuning trial: trials are judged on validation only and never evaluated on the "
            "final-test seeds. Create a normal run from the study's best settings and test that one."
        )
    lock = FileLock(paths.lock)
    try:
        lock.acquire()
    except LockBusy as exc:
        raise RunError(
            "the run is busy: it is training, or another final-test evaluation of it is in progress. "
            "Run the final test once that has finished."
        ) from exc
    try:
        meta = load_metadata(run_id)  # re-read under the lock
        frozen = meta.get("frozen_for_test")
        if frozen is None:
            frozen = freeze_for_test(run_id, checkpoint)
        elif checkpoint not in ("best", "frozen", frozen["checkpoint"]):
            raise RunError(
                f"this run was frozen for the final test with checkpoint {frozen['checkpoint']} at "
                f"{frozen['frozen_at']}; evaluating a different checkpoint on the test seeds would be "
                "selection on the test set"
            )
        policy, entry = load_policy(run_id, "frozen", deterministic=cfg.eval_protocol.deterministic)
        repeat_index = completed_test_count(load_metadata(run_id), run_id)
        attempt = start_attempt(run_id, entry["sha256"])
        seeds = cfg.eval_protocol.seeds_for("test")
        try:
            res = evaluate_policy(
                policy,
                seeds,
                protocol=cfg.eval_protocol,
                reward=cfg.reward,
                gamma=cfg.gamma,
                progress=progress,
                should_stop=should_stop,
            )
        except EvaluationAborted:
            finish_attempt(run_id, attempt, "interrupted")
            raise
        except BaseException as exc:
            finish_attempt(run_id, attempt, "failed", error=f"{type(exc).__name__}: {exc}"[:300])
            raise
        result = _save_result(
            run_id, cfg, "test", entry, policy.label, seeds, res, repeat_index=repeat_index, attempt=attempt
        )
        finish_attempt(run_id, attempt, "completed", file=result["file"])
        record_test_exposure(cfg.eval_protocol, run_id, result["file"])
        return result
    finally:
        lock.release()


def _save_result(
    run_id: str,
    cfg,
    split: str,
    entry: dict,
    policy_label: str,
    seeds: list[int],
    res: dict,
    *,
    repeat_index: int,
    attempt: int | None = None,
) -> dict[str, Any]:
    from lunarlab.runs import log_event
    from lunarlab.sysinfo import git_state

    paths = RunPaths(run_id)
    protocol = cfg.eval_protocol
    stamp = utc_now()
    result = {
        "run_id": run_id,
        "split": split,
        "created_at": stamp,
        "checkpoint": entry,
        "policy_label": policy_label,
        "deterministic": protocol.deterministic,
        "seeds": seeds,
        "protocol": protocol.model_dump(mode="json"),
        "protocol_hash": protocol.protocol_hash(),
        "reward_preset": cfg.reward.preset,
        "reward_hash": cfg.reward.content_hash(),
        "repeat_index": repeat_index,
        **({"attempt": attempt} if attempt is not None else {}),
        "outcome_classifier_version": OUTCOME_CLASSIFIER_VERSION,
        "code": git_state(),
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
                "checkpoint_sha256": r["checkpoint"].get("sha256"),
                **summarize_for_index(r),
            }
        )
    return out
