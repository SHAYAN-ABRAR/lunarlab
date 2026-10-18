# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Controlled experiments behind the cross-platform reproducibility analysis (docs/jmlr/REPRODUCIBILITY.md).

    python tools/reproducibility_experiments.py libm --linux-reports <dir>   # correctly rounded sin/cos
    python tools/reproducibility_experiments.py ulp                          # one-ulp simulator perturbation

Both re-evaluate the supplied artifacts (examples/artifacts) on the recorded final-test seeds in the current
same way as reproduce-artifact (nothing is written outside --out) and write JSON reports to --out
(default reports/jmlr/reproducibility/).

* ``libm``: Gymnasium's LunarLander computes the engine directions with ``math.sin``/``math.cos`` of the C
  library, which differs between operating systems. The experiment replaces both, inside the environment only,
  by correctly rounded values (mpmath, 120 bits) and checks whether the episodes change; with
  ``--linux-reports`` it also checks whether they then reproduce the Linux values recorded by CI
  (``reproduce-<artifact>-linux.json``, which list the first 20 differing episodes).
* ``ulp``: perturbs the simulator once, right after reset, by one float32 unit in the last place of the
  lander's horizontal velocity, and compares every episode and aggregate with the record, exactly as
  ``reproduce-artifact`` compares a reproduction. It shows how a single minimal numerical difference inside the
  simulator propagates.

Inference-side sensitivity needs no tool: run ``reproduce-artifact`` with ``MKL_ENABLE_INSTRUCTIONS=SSE4_2``
and ``MKL_CBWR=COMPATIBLE`` (different BLAS kernels, so different rounding in the network).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ARTIFACTS = ("ppo-baseline-s0", "ppo-hover-bonus-s0", "dqn-baseline-s0")


def _load(name: str):
    from lunarlab.config import RunConfig
    from lunarlab.env import make_env
    from lunarlab.policies import SB3Policy, load_policy_weights
    from lunarlab.storage import read_yaml

    art = ROOT / "examples" / "artifacts" / name
    cfg = RunConfig.model_validate(read_yaml(art / "config.yaml"))
    env = make_env()
    net = load_policy_weights(
        art / "checkpoint.zip",
        cfg.ppo,
        env.observation_space,
        env.action_space,
        algo=cfg.algo,
        dqn_cfg=cfg.dqn,
    )
    env.close()
    recorded = json.loads((art / "evaluation.json").read_text(encoding="utf-8"))
    return cfg, SB3Policy(net, deterministic=True, kind=cfg.algo), recorded


def _evaluate(cfg, policy, seeds):
    from lunarlab.evaluation import evaluate_policy

    return evaluate_policy(policy, seeds, protocol=cfg.eval_protocol, reward=cfg.reward, gamma=cfg.gamma)


class _Trig:
    """Stands in for ``math`` inside lunar_lander: sin/cos native or correctly rounded; counts disagreements."""

    def __init__(self, correct: bool) -> None:
        import mpmath

        mpmath.mp.prec = 120
        self.mp, self.correct, self.calls, self.native_not_correctly_rounded = mpmath, correct, 0, 0

    def _f(self, name: str, x: float) -> float:
        native = getattr(math, name)(x)
        exact = float(getattr(self.mp, name)(self.mp.mpf(x)))
        self.calls += 1
        self.native_not_correctly_rounded += native != exact
        return exact if self.correct else native

    def sin(self, x: float) -> float:
        return self._f("sin", x)

    def cos(self, x: float) -> float:
        return self._f("cos", x)

    def __getattr__(self, name: str):
        return getattr(math, name)


def libm(args) -> dict:
    import gymnasium.envs.box2d.lunar_lander as ll

    out = {}
    for name in ARTIFACTS:
        cfg, policy, recorded = _load(name)
        rec = {int(e["seed"]): e["original_return"] for e in recorded["episodes"]}
        linux = {}
        if args.linux_reports:
            report = json.loads(
                (Path(args.linux_reports) / f"reproduce-{name}-linux.json").read_text(encoding="utf-8")
            )
            for m in report["comparison"]["mismatches"]:
                f = m.get("fields", {})
                linux[int(m["seed"])] = (
                    f["original_return"][1] if "original_return" in f else rec[int(m["seed"])]
                )
        seeds = sorted(linux) if linux else list(recorded["seeds"])[: args.episodes]
        result = {}
        for mode in ("native", "correctly_rounded"):
            trig = _Trig(correct=mode == "correctly_rounded")
            ll.math = trig
            try:
                eps = {
                    int(e["seed"]): e["original_return"] for e in _evaluate(cfg, policy, seeds)["episodes"]
                }
            finally:
                ll.math = math
            result[mode] = {
                "equal_to_recorded": sum(eps[s] == rec[s] for s in seeds),
                "equal_to_linux": sum(eps[s] == linux[s] for s in seeds) if linux else None,
                "trig_calls": trig.calls,
                "native_trig_not_correctly_rounded": trig.native_not_correctly_rounded,
            }
        out[name] = {"seeds": seeds, **result}
        print(name, json.dumps(result))
    return {
        "experiment": "correctly rounded sin/cos inside LunarLander (all other code unchanged)",
        "linux_reference": "GitHub Actions run 39069730331 (first 20 differing episodes per artifact)"
        if args.linux_reports
        else None,
        "results": out,
    }


def ulp(args) -> dict:
    import gymnasium.envs.box2d.lunar_lander as ll
    import numpy as np

    from lunarlab.reproduce import compare_aggregates, compare_episodes

    original_reset = ll.LunarLander.reset

    def perturbed_reset(self, *, seed=None, options=None):
        result = original_reset(self, seed=seed, options=options)
        v = self.lander.linearVelocity
        self.lander.linearVelocity = (float(np.nextafter(np.float32(v.x), np.float32(np.inf))), v.y)
        return result

    out = {}
    for name in ARTIFACTS:
        cfg, policy, recorded = _load(name)
        seeds = list(recorded["seeds"])[: args.episodes]
        ll.LunarLander.reset = perturbed_reset
        try:
            res = _evaluate(cfg, policy, seeds)
        finally:
            ll.LunarLander.reset = original_reset
        cmp = compare_episodes(recorded["episodes"], res["episodes"])
        agg = compare_aggregates(recorded["episodes"], res["episodes"], cfg.eval_protocol)
        out[name] = {
            "episodes": len(seeds),
            "bit_identical": cmp["exact"],
            "summary": cmp["summary"],
            "aggregates": {
                k: {kk: m[kk] for kk in ("recorded", "reproduced", "p_value", "significant")}
                for k, m in agg["metrics"].items()
            },  # fmt: skip
            "paired_return_difference": agg["paired_return_difference"],
            "consistent": agg["consistent"],
        }
        s = cmp["summary"]
        print(
            f"{name}: {cmp['exact']}/{len(seeds)} bit-identical; |dR| median {s['return_difference']['median_abs']:.3g}, "
            f"max {s['return_difference']['max_abs']:.3g}; outcomes agree {s['agreement']['all_outcome_fields']:.0%}; "
            f"no significant aggregate difference: {agg['consistent']}"
        )
    return {
        "experiment": "one float32 ulp added to the lander's horizontal velocity right after reset",
        "results": out,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("libm")
    a.add_argument("--linux-reports", help="folder with CI's reproduce-<artifact>-linux.json reports")
    a.add_argument("--episodes", type=int, default=20)
    b = sub.add_parser("ulp")
    b.add_argument("--episodes", type=int)
    for p in (a, b):
        p.add_argument("--out", default=str(ROOT / "reports" / "jmlr" / "reproducibility"))
    args = ap.parse_args()

    from lunarlab.storage import utc_now
    from lunarlab.sysinfo import hardware, version_info

    report = {"created_at": utc_now(), "software": version_info(), "hardware": hardware()}
    report.update(libm(args) if args.cmd == "libm" else ulp(args))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{args.cmd}-{'windows' if sys.platform == 'win32' else sys.platform}.json"
    path.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
