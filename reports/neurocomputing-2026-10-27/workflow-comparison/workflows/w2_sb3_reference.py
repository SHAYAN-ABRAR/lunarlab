# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""W2: an independent reference implementation of the audit specification on Stable-Baselines3.

    python w2_sb3_reference.py CASE_DIR

It implements checks S1-S10 of ``protocol/specification.json`` in explicit custom code, using
Stable-Baselines3, Gymnasium, NumPy, psutil and the Python standard library. It imports nothing from
LunarLab. Checks S1-S9 run before the policy is executed; any failure rejects the case and no episode is
played. Prints one JSON object on stdout. Exit status: 0 accepted, 3 permitted numerical difference,
1 rejected.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path

import gymnasium as gym
import numpy as np
import psutil
import torch
from stable_baselines3 import PPO

THETA_MAX = 12 * 2 * math.pi / 360  # Gymnasium's pole-angle threshold expression
X_MAX = 2.4
SCHEMA = {
    "name": "cartpole",
    "version": "1",
    "categories": ["balanced_to_time_limit", "pole_fell", "cart_left_track", "unknown"],
}
SUCCESS = "balanced_to_time_limit"
FIELDS = ("length", "original_return", "training_return", "outcome", "terminated", "truncated")
NUMERICAL = ("torch", "numpy", "gymnasium", "stable-baselines3")
PERMUTATIONS = 10_000
ALPHA_FWER = 0.05


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def finite_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def seed_problems(seeds, label: str) -> list[str]:
    if not isinstance(seeds, list) or not seeds:
        return [f"{label} must be a non-empty list"]
    bad = [repr(s) for s in seeds if type(s) is not int or s < 0]  # type() excludes bool and float
    out = [f"{label} entries are not nonnegative integers: {bad[:5]}"] if bad else []
    if not bad and len(set(seeds)) != len(seeds):
        out.append(f"{label} contain duplicates")
    return out


def phi(obs) -> float:
    return -abs(float(obs[2])) / THETA_MAX


def shaping(obs, next_obs, terminated: bool, alpha: float, gamma: float) -> float:
    phi_next = 0.0 if terminated else phi(next_obs)
    return alpha * (gamma * phi_next - phi(obs))


def classify(final_obs, terminated: bool, truncated: bool) -> str:
    x, theta = float(final_obs[0]), float(final_obs[2])
    if truncated and not terminated:
        return "balanced_to_time_limit"
    if terminated and abs(theta) > THETA_MAX:
        return "pole_fell"
    if terminated and abs(x) > X_MAX:
        return "cart_left_track"
    return "unknown"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def integrity(case_dir: Path, case: dict) -> tuple[dict, dict]:
    """Checks S1-S9. Returns (checks, loaded data)."""
    checks: dict[str, dict] = {}

    def put(key: str, ok: bool | None, detail: str = "") -> None:
        checks[key] = {"status": "not-run" if ok is None else ("pass" if ok else "fail"), "detail": detail}

    policy = case_dir / case["policy"]["file"]
    if not policy.is_file():
        put("S1", False, "policy file missing")
    else:
        actual = sha256(policy)
        put("S1", actual == case["policy"]["sha256_recorded_at_selection"], f"policy {actual[:16]}...")
    missing, changed = [], []
    for name, digest in case["files"].items():
        p = case_dir / name
        if not p.is_file():
            missing.append(name)
        elif sha256(p) != digest:
            changed.append(name)
    put(
        "S2",
        not missing and not changed,
        f"missing {missing}, changed {changed}" if missing or changed else "",
    )
    data: dict = {}
    for name in ("evaluation.json", "trajectory.json", "reward_parameters.json"):
        if (case_dir / name).is_file():
            data[name] = load_json(case_dir / name)
    evaluation = data.get("evaluation.json")
    test_seeds = case["protocol"]["test_seeds"]
    validation = case["protocol"]["validation_seeds"]
    if evaluation is None:
        put("S3", None, "no recorded evaluation")
    else:
        same = (
            evaluation.get("environment")
            == {"id": case["environment"]["id"], "kwargs": case["environment"]["kwargs"]}
            and evaluation.get("gamma") == case["gamma"]
            and evaluation.get("seeds") == test_seeds
            and [e.get("seed") for e in evaluation.get("episodes", [])] == test_seeds
        )
        put("S3", same, "" if same else "recorded environment, gamma or test seeds differ from the case")
    seed_out = seed_problems(validation, "validation seeds") + seed_problems(test_seeds, "test seeds")
    if not seed_out and set(validation) & set(test_seeds):
        seed_out.append(f"validation and test seeds overlap: {sorted(set(validation) & set(test_seeds))[:5]}")
    put("S4", not seed_out, "; ".join(seed_out))
    params = data.get("reward_parameters.json")
    weight = case["reward"]["original_weight"]
    gamma = case["gamma"]
    alpha = None
    if params is None:
        put("S5", None, "reward parameters unavailable")
    else:
        alpha = params.get("upright_potential", {}).get("alpha")
        ok = finite_number(weight) and finite_number(gamma) and 0 < gamma <= 1 and finite_number(alpha)
        put("S5", ok, "" if ok else f"weight {weight!r}, gamma {gamma!r}, alpha {alpha!r}")
    names = sorted(t["name"] for t in case["reward"]["terms"])
    if evaluation is None:
        put("S6", None)
        put("S7", None)
    else:
        bad = []
        for i, e in enumerate(evaluation["episodes"]):
            terms = e.get("term_returns")
            values = [e.get("original_return"), e.get("training_return")]
            if (
                not isinstance(terms, dict)
                or sorted(terms) != names
                or not all(finite_number(v) for v in values + list(terms.values()))
            ):
                bad.append(i)
        put("S6", not bad, f"episodes {bad[:5]}" if bad else "")
        if bad:
            put("S7", None, "channels incomplete")
        else:
            broken = [
                i
                for i, e in enumerate(evaluation["episodes"])
                if abs(
                    e["training_return"] - (weight * e["original_return"] + sum(e["term_returns"].values()))
                )
                > 1e-9 * max(1.0, abs(e["training_return"]))
            ]
            put("S7", not broken, f"episodes {broken[:5]}" if broken else "")
    trajectory = data.get("trajectory.json")
    if trajectory is None or not finite_number(alpha) or not finite_number(gamma):
        put("S8", None, "trajectory or finite parameters unavailable")
    else:
        obs = trajectory["observations"]
        n = len(trajectory["original_rewards"])
        recorded = trajectory["term_values"]["upright_potential"]
        worst = max(
            abs(
                recorded[t]
                - shaping(obs[t], obs[t + 1], trajectory["terminated"] and t == n - 1, alpha, gamma)
            )
            for t in range(n)
        )
        put("S8", worst <= 1e-9, f"largest difference {worst:.3g}")
    schema = case["outcome_schema"]
    schema_ok = {k: schema.get(k) for k in SCHEMA} == SCHEMA
    labels_ok = evaluation is not None and {e.get("outcome") for e in evaluation["episodes"]} <= set(
        SCHEMA["categories"]
    )
    put(
        "S9",
        schema_ok and labels_ok,
        "" if schema_ok and labels_ok else "outcome schema or recorded labels differ",
    )
    data["alpha"] = alpha
    return checks, data


def replay(case_dir: Path, case: dict, alpha: float) -> list[dict]:
    model = PPO.load(case_dir / case["policy"]["file"], device="cpu")
    weight, gamma = case["reward"]["original_weight"], case["gamma"]
    env = gym.make(case["environment"]["id"], **case["environment"]["kwargs"])
    episodes = []
    for seed in case["protocol"]["test_seeds"]:
        obs, _ = env.reset(seed=seed)
        original = training = term = 0.0
        length = 0
        while True:
            action = int(model.predict(obs, deterministic=True)[0])
            next_obs, reward, terminated, truncated, _ = env.step(action)
            f = shaping(obs, next_obs, bool(terminated), alpha, gamma)
            original += float(reward)
            term += f
            training += weight * float(reward) + f
            length += 1
            obs = next_obs
            if terminated or truncated:
                break
        episodes.append(
            {
                "seed": seed,
                "length": length,
                "original_return": original,
                "training_return": training,
                "outcome": classify(obs, bool(terminated), bool(truncated)),
                "terminated": bool(terminated),
                "truncated": bool(truncated),
            }
        )
    env.close()
    return episodes


def sign_flip_p(d: np.ndarray) -> float:
    if not np.any(d):
        return 1.0
    rng = np.random.default_rng(0)
    observed = abs(d.mean())
    signs = rng.choice((-1.0, 1.0), size=(PERMUTATIONS, d.size))
    count = int(np.sum(np.abs((signs * d).mean(axis=1)) >= observed - 1e-12))
    return (count + 1) / (PERMUTATIONS + 1)


def mcnemar_p(gained: int, lost: int) -> float:
    n = gained + lost
    if n == 0:
        return 1.0
    k = min(gained, lost)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2**n)


def holm(p: dict[str, float]) -> dict[str, bool]:
    order = sorted(p, key=p.get)
    rejected = {k: False for k in p}
    for i, key in enumerate(order):
        if p[key] <= ALPHA_FWER / (len(p) - i):
            rejected[key] = True
        else:
            break
    return rejected


def same_platform(recorded: dict) -> bool:
    rec_os = str(recorded.get("platform", "")).split("-", 1)[0]
    if rec_os != platform.platform().split("-", 1)[0]:
        return False
    from importlib.metadata import version

    packages = recorded.get("packages") or {}
    return all(packages.get(p) == version(p) for p in NUMERICAL)


def peak_rss() -> int:
    info = psutil.Process().memory_info()
    return int(getattr(info, "peak_wset", 0) or getattr(info, "rss", 0))


def main() -> int:
    t0 = time.perf_counter()
    torch.set_num_threads(1)
    case_dir = Path(sys.argv[1])
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    checks, data = integrity(case_dir, case)
    result = {"workflow": "W2", "case": case.get("case"), "checks": checks, "episodes_executed": 0}
    if any(c["status"] != "pass" for c in checks.values()):
        checks["S10"] = {"status": "not-run", "detail": "an integrity check failed"}
        result.update(verdict="rejected-before-execution", execution_started_before_failure=False)
        code = 1
    else:
        recorded = data["evaluation.json"]["episodes"]
        reproduced = replay(case_dir, case, data["alpha"])
        result["episodes_executed"] = len(reproduced)
        by_seed = {e["seed"]: e for e in recorded}
        differing = [e["seed"] for e in reproduced if any(by_seed[e["seed"]][f] != e[f] for f in FIELDS)]
        d = np.array([e["original_return"] - by_seed[e["seed"]]["original_return"] for e in reproduced])
        gained = sum(e["outcome"] == SUCCESS and by_seed[e["seed"]]["outcome"] != SUCCESS for e in reproduced)
        lost = sum(e["outcome"] != SUCCESS and by_seed[e["seed"]]["outcome"] == SUCCESS for e in reproduced)
        rejected = holm({"mean_original_return": sign_flip_p(d), "success_rate": mcnemar_p(gained, lost)})
        if not differing:
            status, verdict, code = "exact", "accepted", 0
        elif same_platform(data["evaluation.json"]["recorded_with"]):
            status, verdict, code = "unexpected-difference", "rejected-after-execution", 1
        elif any(rejected.values()):
            status, verdict, code = "aggregate-disagreement", "rejected-after-execution", 1
        else:
            status, verdict, code = "numerical-difference", "accepted-numerical-difference", 3
        checks["S10"] = {
            "status": "pass" if code in (0, 3) else "fail",
            "detail": f"{status}: {len(differing)} of {len(reproduced)} episodes differ",
        }
        result.update(
            verdict=verdict,
            replay_status=status,
            execution_started_before_failure=code == 1,
            mean_original_return=float(np.mean([e["original_return"] for e in reproduced])),
            completion_rate=sum(e["outcome"] == SUCCESS for e in reproduced) / len(reproduced),
        )
    result.update(seconds=time.perf_counter() - t0, peak_rss_bytes_self=peak_rss())
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    sys.exit(main())
