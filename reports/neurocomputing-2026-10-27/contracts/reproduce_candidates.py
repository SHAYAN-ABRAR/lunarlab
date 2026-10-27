# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Minimal reproductions of the contract candidates named in the 27 October 2026 handoff.

    python reports/neurocomputing-2026-10-27/contracts/reproduce_candidates.py OUT.json

Every case records what the code under test actually does with one input: the value returned or the
exception raised, how many environments were created and how many episodes ran before that happened. The
classification compares that observation with the intended contract (nonnegative integer seeds, rejected
before any environment exists; finite rewards; a reward identity that distinguishes behaviour). Nothing is
trained: the CartPole seeding case constructs PPO and resets its environment exactly as ``learn`` does.
"""

from __future__ import annotations

import json
import math
import sys
import traceback
from pathlib import Path

import gymnasium as gym
import numpy as np

from lunarlab.audit import (
    RewardAccountingWrapper,
    RewardTerm,
    TaskAdapter,
    audit_policy,
    get_adapter,
    seed_split_problems,
    terms_hash,
)
from lunarlab.sysinfo import version_info

CREATED = {"envs": 0}
RESETS: list = []


class ResetRecorder(gym.Wrapper):
    """Records the seed every reset receives."""

    def reset(self, *, seed=None, options=None):
        RESETS.append(seed)
        return self.env.reset(seed=seed, options=options)


def counting_cartpole() -> TaskAdapter:
    base = get_adapter("cartpole")

    def factory(**kw):
        CREATED["envs"] += 1
        return ResetRecorder(gym.make("CartPole-v1", **kw))

    return TaskAdapter(**{**base.__dict__, "name": "cartpole-counting", "factory": factory})


def lean(o):
    return int(o[2] + 0.5 * o[3] > 0)


def observe(fn):
    CREATED["envs"] = 0
    RESETS.clear()
    try:
        value = fn()
        out = {"raised": None, "returned": value}
    except Exception as exc:  # recorded, not hidden
        out = {
            "raised": f"{type(exc).__name__}: {exc}",
            "traceback_tail": traceback.format_exc().splitlines()[-3:],
        }
    out["environments_created"] = CREATED["envs"]
    out["reset_seeds"] = [s if s is None or isinstance(s, int) else repr(s) for s in RESETS]
    return out


def audit_summary(report):
    return {
        "n_episodes": report["aggregate"]["n_episodes"],
        "seeds_recorded": report["seeds"],
        "mean_original_return": report["aggregate"]["mean_original_return"],
        "metrics": report["aggregate"]["metrics"],
        "reward_hash": report["reward"]["hash"],
    }


def seed_cases():
    adapter = counting_cartpole()
    inputs = {
        "booleans": [True, False],
        "fractional_floats": [1.5, 2.7],
        "integral_floats": [3.0, 4.0],
        "numeric_strings": ["7", "8"],
        "negative_after_valid": [5, -1],
        "empty": [],
        "numpy_int64": [np.int64(5), np.int64(6)],
        "collapse_after_coercion": [1, 1.5],
        "string_and_int_collapse": ["9", 9],
    }
    out = {}
    for label, seeds in inputs.items():
        obs = observe(lambda seeds=seeds: audit_summary(audit_policy(adapter, lean, seeds, gamma=0.99)))
        obs["input"] = [repr(s) for s in seeds]
        out[label] = obs
    return out


def split_cases():
    inputs = {
        "empty_lists": ([], []),
        "negative": ([-1, 2], [3]),
        "duplicates": ([1, 1], [3]),
        "overlap": ([1, 2], [2, 3]),
        "numeric_strings": (["1"], [2]),
        "integral_float": ([1.0], [2]),
        "numpy_integers": ([np.int64(1)], [np.int32(2)]),
        "numpy_bool": ([np.bool_(True)], [2]),
        "numpy_int_overlap": ([np.int64(5)], [5]),
        "unhashable_entry": ([[1]], [2]),
    }
    out = {}
    for label, (val, test) in inputs.items():
        obs = observe(lambda v=val, t=test: seed_split_problems(v, t))
        obs["input"] = {"validation": [repr(s) for s in val], "test": [repr(s) for s in test]}
        out[label] = obs
    return out


def cartpole_seeding_case():
    from stable_baselines3 import PPO
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.vec_env import DummyVecEnv

    RESETS.clear()
    cp = get_adapter("cartpole")

    def make():
        return Monitor(
            ResetRecorder(RewardAccountingWrapper(cp.make_env(), {}, gamma=0.99, apply=True, adapter=cp))
        )

    venv = DummyVecEnv([make] * 4)
    venv.seed(1_000_000)  # what examples/cartpole_audit.py does for seed 0, before constructing PPO
    model = PPO("MlpPolicy", venv, n_steps=256, batch_size=64, gamma=0.99, seed=0, device="cpu", verbose=0)
    first = model.env.reset()  # learn() begins with exactly this reset (OnPolicyAlgorithm._setup_learn)
    initial = list(RESETS)
    rng = np.random.default_rng(0)
    for _ in range(600):  # step without learning until several episodes have auto-reset
        model.env.step(rng.integers(0, 2, size=4))
    later = RESETS[len(initial) :]
    venv.close()
    return {
        "intended_initial_seed_roots": [1_000_000 + i for i in range(4)],
        "effective_initial_reset_seeds": initial,
        "later_auto_reset_seeds_sample": later[:8],
        "later_auto_resets": len(later),
        "later_resets_all_unseeded": all(s is None for s in later),
        "first_observation_shape": list(np.asarray(first).shape),
    }


class Custom:
    """Two terms with identical declared descriptions and different behaviour."""

    a = RewardTerm("bonus", lambda t: 1.0, {"type": "custom", "id": "bonus"})
    b = RewardTerm("bonus", lambda t: 1000.0, {"type": "custom", "id": "bonus"})


def provenance_cases():
    cp = get_adapter("cartpole")
    ha, hb = terms_hash({"bonus": Custom.a}, 1.0), terms_hash({"bonus": Custom.b}, 1.0)
    reports = {}
    for label, term in (("pays_1", Custom.a), ("pays_1000", Custom.b)):
        r = audit_policy(cp, lean, [100, 101], gamma=0.99, terms={"bonus": term})
        reports[label] = {
            "reward_hash": r["reward"]["hash"],
            "mean_training_return": r["aggregate"]["mean_training_return"],
            "recorded_terms": r["reward"]["terms"],
        }
    return {
        "terms_hash_pays_1": ha,
        "terms_hash_pays_1000": hb,
        "hashes_equal": ha == hb,
        "hash_length_hex": len(ha),
        "audits": reports,
    }


def nonfinite_cases():
    cp = get_adapter("cartpole")
    nan_term = RewardTerm("nan_term", lambda t: math.nan, {"type": "custom", "id": "nan"})
    inf_term = RewardTerm("inf_term", lambda t: math.inf, {"type": "custom", "id": "inf"})
    out = {}
    for label, kwargs in (
        ("nan_term", {"terms": {"nan_term": nan_term}}),
        ("inf_term", {"terms": {"inf_term": inf_term}}),
        ("nan_original_weight", {"original_weight": math.nan}),
        ("inf_original_weight", {"original_weight": math.inf}),
    ):
        obs = observe(lambda kw=kwargs: audit_policy(cp, lean, [100], gamma=0.99, **kw))
        if obs.get("returned") is not None:
            r = obs.pop("returned")
            ep = r["episodes"][0]
            obs["returned_report"] = {
                "n_episodes": r["aggregate"]["n_episodes"],
                "training_return": repr(ep["training_return"]),
                "mean_training_return": repr(r["aggregate"]["mean_training_return"]),
            }
            try:
                json.dumps(r, allow_nan=False)
                obs["strict_json_serialisable"] = True
            except ValueError as exc:
                obs["strict_json_serialisable"] = f"no: {exc}"
        out[label] = obs
    bad_describe = RewardTerm("bad", lambda t: 0.0, {"type": "custom", "scale": math.nan})
    out["nan_in_term_description"] = observe(lambda: terms_hash({"bad": bad_describe}, 1.0))
    obj_describe = RewardTerm("obj", lambda t: 0.0, {"type": "custom", "f": object()})
    out["non_json_term_description"] = observe(lambda: terms_hash({"obj": obj_describe}, 1.0))
    for v in out.values():
        v.pop("reset_seeds", None)
    return out


def main() -> int:
    out = {
        "software": version_info(),
        "seeds_audit_policy": seed_cases(),
        "seed_split_problems": split_cases(),
        "cartpole_example_seeding": cartpole_seeding_case(),
        "reward_definition_identity": provenance_cases(),
        "nonfinite_values": nonfinite_cases(),
    }
    Path(sys.argv[1]).write_text(json.dumps(out, indent=2, default=repr), encoding="utf-8")
    print(f"wrote {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
