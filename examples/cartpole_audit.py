# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Example: auditing reward shaping on a second task (CartPole-v1) with LunarLab's task-independent layer.

Trains PPO twice on CartPole-v1 -- once on the original reward, once on the original reward plus a
potential-based shaping term -- and audits both policies on the same held-out seeds with the ORIGINAL
reward, recording beside it what the shaped reward definition would have paid for the same episodes.

This demonstrates the extension contract (a task adapter with its own outcome definitions). It is not a
research result about CartPole: one training seed, a small budget, the final model (no validation-based
checkpoint selection), and no claim about reward exploitation.

    python examples/cartpole_audit.py                         # 30,000 transitions per policy
    python examples/cartpole_audit.py --transitions 4096      # quick check
    python examples/cartpole_audit.py --out cartpole.json     # also write the full audit records
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from lunarlab.audit import RewardAccountingWrapper, audit_policy, get_adapter, seed_split_problems
from lunarlab.sysinfo import version_info

GAMMA = 0.99
VALIDATION_SEEDS = list(range(10_000, 10_010))  # reserved for checkpoint selection (unused in this example)
TEST_SEEDS = list(range(20_000, 20_050))


def train(adapter, terms: dict, transitions: int, seed: int) -> PPO:
    def make():
        return Monitor(
            RewardAccountingWrapper(adapter.make_env(), terms, gamma=GAMMA, apply=True, adapter=adapter)
        )

    venv = DummyVecEnv([make] * 4)
    # PPO(seed=...) seeds the learner's random generators and also calls venv.seed(seed), which replaces
    # any environment seeds set before it. So the training environments' seed roots are set afterwards:
    # learn() starts with venv.reset(), which uses them once (root + i for environment i). Every later
    # episode is reset without a seed and continues that environment's own random stream.
    model = PPO(
        "MlpPolicy", venv, n_steps=256, batch_size=64, gamma=GAMMA, seed=seed, device="cpu", verbose=0
    )
    venv.seed(1_000_000 + 1000 * seed)  # training episodes never use validation or test seeds
    model.learn(transitions)
    venv.close()
    return model


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--transitions", type=int, default=30_000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", help="write the audit records (JSON) to this file")
    args = ap.parse_args(argv)

    cartpole = get_adapter("cartpole")
    shaping = cartpole.term("upright_potential", gamma=GAMMA)
    problems = seed_split_problems(VALIDATION_SEEDS, TEST_SEEDS)
    if problems:
        raise SystemExit(f"invalid seed split: {problems}")

    audits = {}
    for label, terms in (("original reward", {}), ("original + upright potential", {shaping.name: shaping})):
        model = train(cartpole, terms, args.transitions, args.seed)

        def policy(obs, model=model):
            return int(model.predict(obs, deterministic=True)[0])

        # Scored on the original reward; the shaped definition's return is recorded for the same episodes.
        audits[label] = audit_policy(cartpole, policy, TEST_SEEDS, gamma=GAMMA, terms={shaping.name: shaping})

    print(
        f"CartPole-v1, PPO, {args.transitions:,} transitions per policy, seed {args.seed}, {len(TEST_SEEDS)} test seeds"
    )
    print(
        f"{'trained on':<30} {'original return':>16} {'shaped return':>14} {'time limit':>11} {'pole fell':>10}"
    )
    for label, a in audits.items():
        g, m = a["aggregate"], a["aggregate"]["metrics"]
        print(
            f"{label:<30} {g['mean_original_return']:>16.1f} {g['mean_training_return']:>14.1f} "
            f"{m['time_limit_rate']:>10.0%} {m['pole_fell_rate']:>10.0%}"
        )
    if args.out:
        Path(args.out).write_text(
            json.dumps(
                {"software": version_info(), "transitions": args.transitions, "audits": audits}, indent=2
            ),
            encoding="utf-8",
        )
        print(f"audit records written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
