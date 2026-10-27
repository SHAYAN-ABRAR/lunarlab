# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Build the neutral audit cases of the workflow comparison from one frozen CartPole policy.

    python build_fixtures.py RUN_DIR OUT_DIR

``RUN_DIR`` is a CartPole study run (``run.json``, ``test-selected.json`` and ``frozen/``) of the
``upright-potential`` design. ``OUT_DIR/<case>/`` receives one directory per case of
``protocol/fault_inventory.json``, and ``OUT_DIR/oracle.json`` the independently computed trajectory values.

The trajectory and its per-step shaping values are recorded here with Stable-Baselines3, Gymnasium and
NumPy only; nothing from LunarLab is imported. The recorded test evaluation comes from the study's test record
(written by LunarLab), converted to the neutral format. Each fault case changes one property and recomputes
every digest that would otherwise catch it.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import gymnasium as gym

THETA_MAX = 12 * 2 * math.pi / 360  # Gymnasium's CartPole threshold expression
GAMMA = 0.98
ALPHA = 1.0
TERM = "upright_potential"
CATEGORIES = ["balanced_to_time_limit", "pole_fell", "cart_left_track", "unknown"]
LINUX = "Linux-6.11.0-1018-azure-x86_64-with-glibc2.39"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def phi(obs) -> float:
    return -abs(float(obs[2])) / THETA_MAX


def record_trajectory(policy_path: Path, seed: int) -> dict:
    from stable_baselines3 import PPO

    model = PPO.load(policy_path, device="cpu")
    env = gym.make("CartPole-v1")
    obs, _ = env.reset(seed=seed)
    observations, actions, rewards = [obs.tolist()], [], []
    while True:
        action = int(model.predict(obs, deterministic=True)[0])
        obs, reward, terminated, truncated, _ = env.step(action)
        observations.append(obs.tolist())
        actions.append(action)
        rewards.append(float(reward))
        if terminated or truncated:
            break
    env.close()
    n = len(rewards)
    values = []
    for t in range(n):
        last = t == n - 1
        phi_next = 0.0 if (terminated and last) else phi(observations[t + 1])
        values.append(ALPHA * (GAMMA * phi_next - phi(observations[t])))
    return {
        "format": "neutral-trajectory/1",
        "seed": seed,
        "observations": observations,
        "actions": actions,
        "original_rewards": rewards,
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "term_values": {TERM: values},
    }


def neutral_evaluation(test: dict) -> dict:
    report = test["report"]
    return {
        "format": "neutral-evaluation/1",
        "environment": {"id": "CartPole-v1", "kwargs": {}},
        "gamma": GAMMA,
        "reward_definition": {
            "original_weight": 1.0,
            "terms": [{"name": TERM, "kind": "potential", "alpha": ALPHA}],
        },
        "seeds": list(report["seeds"]),
        "episodes": [
            {
                "seed": e["seed"],
                "length": e["length"],
                "original_return": e["original_return"],
                "training_return": e["training_return"],
                "term_returns": dict(e["term_returns"]),
                "terminated": e["terminated"],
                "truncated": e["truncated"],
                "outcome": e["outcome"],
            }
            for e in report["episodes"]
        ],
        "recorded_with": test["tested_with"],
    }


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8", newline="\n")


def write_case(
    out: Path, case: str, files: dict, policy: Path, recorded_policy_sha: str, validation, test_seeds
) -> Path:
    d = out / case
    d.mkdir(parents=True)
    shutil.copyfile(policy, d / "policy.zip")
    for name, obj in files.items():
        if obj is not None:
            write_json(d / name, obj)
    evaluation = files["evaluation.json"]
    case_doc = {
        "format": "neutral-audit-case/1",
        "case": case,
        "policy": {"file": "policy.zip", "sha256_recorded_at_selection": recorded_policy_sha},
        "environment": {"id": "CartPole-v1", "kwargs": {}, "time_limit": 500},
        "gamma": GAMMA,
        "reward": {
            "original_weight": 1.0,
            "terms": [
                {
                    "name": TERM,
                    "kind": "potential",
                    "potential": "-|theta| / (12*2*pi/360)",
                    "parameters_from": "reward_parameters.json",
                }
            ],
        },
        "outcome_schema": {
            "name": "cartpole",
            "version": "1",
            "categories": CATEGORIES,
            "success": "balanced_to_time_limit",
        },
        "protocol": {"validation_seeds": validation, "test_seeds": test_seeds},
        "files": {name: sha(d / name) for name in files if (d / name).exists()},
        "recorded_platform": evaluation["recorded_with"],
    }
    write_json(d / "case.json", case_doc)
    return d


def main() -> int:
    run_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    test = json.loads((run_dir / "test-selected.json").read_text(encoding="utf-8"))
    protocol = json.loads((run_dir / "protocol.json").read_text(encoding="utf-8"))
    selected = run_dir / run["frozen"]["selected"]["file"]
    final = run_dir / run["frozen"]["final"]["file"]
    assert sha(selected) == run["frozen"]["selected"]["sha256"] != run["frozen"]["final"]["sha256"]
    validation, test_seeds = list(protocol["validation_seeds"]), list(protocol["test_seeds"])
    evaluation = neutral_evaluation(test)
    trajectory = record_trajectory(selected, test_seeds[0])
    params = {TERM: {"alpha": ALPHA}}
    clean = {"evaluation.json": evaluation, "trajectory.json": trajectory, "reward_parameters.json": params}
    rec_sha = run["frozen"]["selected"]["sha256"]
    oracle = {
        "trajectory_seed": test_seeds[0],
        "length": len(trajectory["original_rewards"]),
        "terminated": trajectory["terminated"],
        "truncated": trajectory["truncated"],
        "last_value_correct": trajectory["term_values"][TERM][-1],
        "last_value_if_wrongly_absorbing": ALPHA * (GAMMA * 0.0 - phi(trajectory["observations"][-2])),
        "discounted_sum_correct": sum(GAMMA**t * v for t, v in enumerate(trajectory["term_values"][TERM])),
        "policy_sha256": rec_sha,
        "swapped_policy_sha256": run["frozen"]["final"]["sha256"],
    }
    write_json(out / "oracle.json", oracle)

    def variant(**changes):
        files = copy.deepcopy(clean)
        files.update(changes)
        return files

    write_case(out, "C0-clean", clean, selected, rec_sha, validation, test_seeds)

    c1 = copy.deepcopy(evaluation)
    c1["recorded_with"]["platform"] = LINUX
    n = len(evaluation["episodes"])
    for index, length in ((min(41, n - 3), 497), (min(77, n - 2), 499)):
        e = c1["episodes"][index]
        e.update(
            length=length,
            original_return=float(length),
            terminated=True,
            truncated=False,
            outcome="pole_fell",
        )
        e["training_return"] = float(length) + e["term_returns"][TERM]
    write_case(
        out,
        "C1-numerical-difference",
        variant(**{"evaluation.json": c1}),
        selected,
        rec_sha,
        validation,
        test_seeds,
    )

    write_case(out, "F01-checkpoint-swapped", clean, final, rec_sha, validation, test_seeds)
    corrupted = rec_sha[:-1] + ("0" if rec_sha[-1] != "0" else "1")
    write_case(out, "F02-recorded-digest-corrupted", clean, selected, corrupted, validation, test_seeds)
    write_case(
        out, "F03-protocol-mismatch", clean, selected, rec_sha, validation, [s + 100 for s in test_seeds]
    )
    d = write_case(out, "F04-dependency-missing", clean, selected, rec_sha, validation, test_seeds)
    (d / "reward_parameters.json").unlink()
    d = write_case(out, "F05-dependency-changed", clean, selected, rec_sha, validation, test_seeds)
    write_json(d / "reward_parameters.json", {TERM: {"alpha": 2.0}})  # digest in case.json left stale
    coerced = [float(s) if s == test_seeds[5] else s for s in test_seeds]
    write_case(out, "F06-coercible-seed", clean, selected, rec_sha, validation, coerced)
    write_case(
        out, "F07-overlapping-seeds", clean, selected, rec_sha, [test_seeds[0], *validation[1:]], test_seeds
    )
    write_case(
        out,
        "F08-nonfinite-parameter",
        variant(**{"reward_parameters.json": {TERM: {"alpha": float("nan")}}}),
        selected,
        rec_sha,
        validation,
        test_seeds,
    )
    f09 = copy.deepcopy(evaluation)
    for e in f09["episodes"]:
        e.pop("original_return")
    write_case(
        out,
        "F09-original-channel-absent",
        variant(**{"evaluation.json": f09}),
        selected,
        rec_sha,
        validation,
        test_seeds,
    )
    f10 = copy.deepcopy(evaluation)
    for index in (3, min(57, len(evaluation["episodes"]) - 1)):
        f10["episodes"][index]["training_return"] += 0.5
    write_case(
        out,
        "F10-inconsistent-totals",
        variant(**{"evaluation.json": f10}),
        selected,
        rec_sha,
        validation,
        test_seeds,
    )
    f11 = copy.deepcopy(trajectory)
    assert f11["truncated"] and not f11["terminated"], "the fixture trajectory must end at the time limit"
    f11["term_values"][TERM][-1] = oracle["last_value_if_wrongly_absorbing"]
    write_case(
        out,
        "F11-potential-at-truncation",
        variant(**{"trajectory.json": f11}),
        selected,
        rec_sha,
        validation,
        test_seeds,
    )
    f12 = copy.deepcopy(evaluation)
    for e in f12["episodes"]:
        e["outcome"] = "success" if e["outcome"] == "balanced_to_time_limit" else e["outcome"]
    write_case(
        out,
        "F12-outcome-schema-mismatch",
        variant(**{"evaluation.json": f12}),
        selected,
        rec_sha,
        validation,
        test_seeds,
    )
    print(f"wrote {len(list(out.glob('*/case.json')))} cases to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
