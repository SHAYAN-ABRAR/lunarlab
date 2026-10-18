# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Where two platforms' evaluations of the same policy part: per-step traces and their comparison.

A recorded evaluation stores per-episode summaries, not trajectories, so the first step at which a reproduction
departs from the record cannot be read from it. :func:`record_traces` therefore flies chosen seeds of an
artifact and stores, per step, the observation, the network's raw outputs (PPO action logits or DQN Q-values,
float32), the action and the reward. :func:`diagnose` repeats those episodes on another machine against the
stored trace and separates the two possible sources of a difference:

* **policy inference**: the network is evaluated on the *reference* observations; any difference in its
  outputs (bit for bit) or in the chosen action is an inference difference;
* **simulator dynamics**: the environment is stepped open-loop with the *reference* actions; any difference in
  the observations is a dynamics difference (Box2D and the environment code), independent of the policy.

It also reports the closed-loop trajectory: the first step whose observation or action differs, and how far
the episode's return moved. Traces are uncompressed ``.npz`` files of numeric arrays, read with
``allow_pickle=False``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from lunarlab.storage import sha256_file, utc_now

TRACE_FORMAT = "lunarlab.trace"
TRACE_VERSION = 1
ARRAYS = ("observations", "outputs", "actions", "rewards")


def _load_policy(artifact_dir: Path):
    from lunarlab.config import RunConfig
    from lunarlab.env import make_env
    from lunarlab.policies import SB3Policy, load_policy_weights
    from lunarlab.storage import read_yaml

    cfg = RunConfig.model_validate(read_yaml(artifact_dir / "config.yaml"))
    env = make_env()
    try:
        net = load_policy_weights(
            artifact_dir / "checkpoint.zip", cfg.ppo, env.observation_space, env.action_space, algo=cfg.algo,
            dqn_cfg=cfg.dqn,
        )  # fmt: skip
    finally:
        env.close()
    return cfg, SB3Policy(net, deterministic=True, kind=cfg.algo)


def _eval_env(cfg):
    from lunarlab.evaluation import make_eval_env

    return make_eval_env(cfg.eval_protocol, cfg.reward, cfg.gamma)


def policy_outputs(policy, obs: np.ndarray) -> np.ndarray:
    """The raw outputs the greedy action is the arg-max of: PPO action logits or DQN Q-values (float32)."""
    import torch

    net = policy.network
    with torch.no_grad():
        obs_t, _ = net.obs_to_tensor(obs)
        out = net.q_net(obs_t) if policy.kind == "dqn" else net.get_distribution(obs_t).distribution.logits
    return out[0].cpu().numpy().astype(np.float32)


def trace_episode(env, policy, seed: int) -> dict[str, Any]:
    """Fly one greedy episode and keep every step: observations (T+1), outputs, actions and rewards (T)."""
    obs, _ = env.reset(seed=int(seed))
    policy.reset(int(seed))
    observations, outputs, actions, rewards = [np.asarray(obs, np.float32)], [], [], []
    while True:
        outputs.append(policy_outputs(policy, obs))
        action = policy.act(obs)
        actions.append(action)
        obs, reward, terminated, truncated, info = env.step(action)
        observations.append(np.asarray(obs, np.float32))
        rewards.append(float(reward))
        if terminated or truncated:
            break
    episode = info.get("lunarlab_episode") or {}
    return {
        "observations": np.stack(observations),
        "outputs": np.stack(outputs),
        "actions": np.asarray(actions, np.int64),
        "rewards": np.asarray(rewards, np.float64),
        # the evaluation wrapper's accumulated return, exactly as an evaluation records it
        "original_return": float(episode.get("original_return", sum(rewards))),
        "terminated": bool(terminated),
        "truncated": bool(truncated),
    }


def replay_actions(env, seed: int, actions: np.ndarray) -> np.ndarray:
    """Step the environment open-loop with given actions; the observations reached (up to len(actions)+1)."""
    obs, _ = env.reset(seed=int(seed))
    observations = [np.asarray(obs, np.float32)]
    for a in actions:
        obs, _, terminated, truncated, _ = env.step(int(a))
        observations.append(np.asarray(obs, np.float32))
        if terminated or truncated:
            break
    return np.stack(observations)


def _first_difference(a: np.ndarray, b: np.ndarray) -> int | None:
    """First index along axis 0 where the arrays differ bit for bit (or where one of them ends)."""
    n = min(len(a), len(b))
    rows = np.flatnonzero(np.any(a[:n].reshape(n, -1) != b[:n].reshape(n, -1), axis=1))
    if rows.size:
        return int(rows[0])
    return None if len(a) == len(b) else n


def record_traces(artifact_dir: Path, seeds: list[int], out: Path) -> dict[str, Any]:
    """Trace ``seeds`` of an artifact on this machine; write ``out`` (``.npz``) and ``out`` with ``.json``."""
    from lunarlab.sysinfo import hardware, version_info

    artifact_dir, out = Path(artifact_dir), Path(out)
    cfg, policy = _load_policy(artifact_dir)
    recorded = {
        int(e["seed"]): e
        for e in json.loads((artifact_dir / "evaluation.json").read_text(encoding="utf-8"))["episodes"]
    }
    env = _eval_env(cfg)
    arrays: dict[str, np.ndarray] = {}
    episodes = []
    try:
        for s in seeds:
            t = trace_episode(env, policy, s)
            for k in ARRAYS:
                arrays[f"s{s}_{k}"] = t[k]
            rec = recorded.get(int(s))
            episodes.append(
                {
                    "seed": int(s),
                    "steps": len(t["actions"]),
                    "original_return": t["original_return"],
                    "matches_recorded_return": rec is not None
                    and rec["original_return"] == t["original_return"],
                }
            )
    finally:
        env.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        np.savez(f, **arrays)
    meta = {
        "format": TRACE_FORMAT,
        "version": TRACE_VERSION,
        "artifact": json.loads((artifact_dir / "artifact.json").read_text(encoding="utf-8"))["source_run_id"],
        "algo": cfg.algo,
        "created_at": utc_now(),
        "software": version_info(),
        "hardware": hardware(),
        "seeds": [int(s) for s in seeds],
        "episodes": episodes,
        "arrays": {"file": out.name, "sha256": sha256_file(out)},
    }
    out.with_suffix(".json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8", newline="\n")
    return meta


def load_traces(path: Path) -> tuple[dict, dict[int, dict[str, np.ndarray]]]:
    """Read a trace pair (``.npz`` + ``.json``); the arrays must match the digest in the JSON."""
    path = Path(path)
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if meta.get("format") != TRACE_FORMAT or meta.get("version") != TRACE_VERSION:
        raise ValueError(f"{path.name}: not a {TRACE_FORMAT} v{TRACE_VERSION} file")
    if sha256_file(path) != meta["arrays"]["sha256"]:
        raise ValueError(
            f"{path.name} does not match the digest recorded in {path.with_suffix('.json').name}"
        )
    with np.load(path, allow_pickle=False) as z:
        traces = {int(s): {k: z[f"s{s}_{k}"] for k in ARRAYS} for s in meta["seeds"]}
    return meta, traces


def compare_trace(
    reference: dict[str, np.ndarray], env, policy, seed: int, *, reference_return: float | None = None
) -> dict[str, Any]:
    """Compare one reference episode with this machine: inference, open-loop dynamics and closed loop."""
    ref_obs, ref_out, ref_act = reference["observations"], reference["outputs"], reference["actions"]
    # 1. Policy inference on the reference observations.
    outs = np.stack([policy_outputs(policy, o) for o in ref_obs[: len(ref_act)]])
    acts = np.asarray([policy.act(o) for o in ref_obs[: len(ref_act)]], np.int64)
    inference_first = _first_difference(outs, ref_out)
    # 2. Simulator dynamics with the reference actions.
    replayed = replay_actions(env, seed, ref_act)
    dynamics_first = _first_difference(replayed, ref_obs)
    n_dyn = min(len(replayed), len(ref_obs))
    # 3. Closed loop on this machine.
    closed = trace_episode(env, policy, seed)
    obs_first = _first_difference(closed["observations"], ref_obs)
    act_first = _first_difference(closed["actions"], ref_act)
    ref_return = float(reference["rewards"].sum()) if reference_return is None else float(reference_return)
    if inference_first is None and dynamics_first is None:
        source = "none" if obs_first is None and act_first is None else "unexplained"
    elif inference_first is None:
        source = "simulator dynamics"
    elif dynamics_first is None:
        source = "policy inference"
    else:
        source = "both"
    return {
        "seed": int(seed),
        "source": source,
        "inference": {
            "first_output_difference_step": inference_first,
            "max_abs_output_difference": float(np.abs(outs - ref_out).max()) if len(outs) else 0.0,
            "action_flips": int((acts != ref_act).sum()),
        },
        "dynamics": {
            "first_observation_difference_step": dynamics_first,
            "first_difference_max_abs": (
                float(np.abs(replayed[dynamics_first] - ref_obs[dynamics_first]).max())
                if dynamics_first is not None and dynamics_first < n_dyn
                else None
            ),
            "max_abs_difference": float(np.abs(replayed[:n_dyn] - ref_obs[:n_dyn]).max()),
            "steps_compared": int(n_dyn),
        },
        "closed_loop": {
            "first_observation_difference_step": obs_first,
            "first_action_difference_step": act_first,
            "reference_steps": len(ref_act),
            "steps": len(closed["actions"]),
            "reference_return": ref_return,
            "return": closed["original_return"],
            "abs_return_difference": abs(closed["original_return"] - ref_return),
        },
    }


def diagnose(artifact_dir: Path, reference: Path) -> dict[str, Any]:
    """Compare every traced episode of ``reference`` with this machine (see the module docstring)."""
    from lunarlab.reproduce import compare_platforms
    from lunarlab.sysinfo import hardware, version_info

    artifact_dir = Path(artifact_dir)
    meta, traces = load_traces(reference)
    cfg, policy = _load_policy(artifact_dir)
    env = _eval_env(cfg)
    returns = {int(e["seed"]): e["original_return"] for e in meta["episodes"]}
    try:
        episodes = [
            compare_trace(traces[s], env, policy, s, reference_return=returns.get(int(s)))
            for s in meta["seeds"]
        ]
    finally:
        env.close()
    sources = sorted({e["source"] for e in episodes})
    return {
        "kind": "lunarlab.divergence",
        "schema": 1,
        "artifact": meta["artifact"],
        "created_at": utc_now(),
        "reference": {
            "file": Path(reference).name,
            "software": meta["software"],
            "created_at": meta["created_at"],
        },
        "software": version_info(),
        "hardware": hardware(),
        "platform": compare_platforms(meta["software"], version_info()),
        "sources": sources,
        "identical": sources == ["none"],
        "episodes": episodes,
    }
