# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Prespecified analysis of the CartPole reward-design audit (see protocol/PROTOCOL.md).

    python reports/neurocomputing-2026-10-27/cartpole-study/analyze.py STUDY_DIR OUT_DIR

Reads ``STUDY_DIR/runs/*/run.json``, ``test-selected.json`` and ``test-final.json``. Writes ``results.json``
(every number below, with the SHA-256 of every input) and ``RESULTS.md``.

The unit is the trained policy, five per design. A policy's statistics are over its 100 test episodes, and
every statistic conditions on the fixed test seeds. Intervals are 95% percentile bootstraps with 10,000
resamples and seed 0, resampling policies, or seed-paired differences for the paired effects. The trimmed
mean is the integer-boundary 25% trimmed mean: sort, drop int(0.25 n) values from each end and average the
rest (the middle three of five). It is not a fractional-weight interquartile mean.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

RESAMPLES = 10_000
LEVEL = 0.95
SEED = 0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trimmed_mean(values) -> float:
    a = np.sort(np.asarray(values, dtype=float))
    k = int(0.25 * a.size)
    return float(a[k : a.size - k].mean())


def boot_mean(values) -> list[float]:
    a = np.asarray(values, dtype=float)
    rng = np.random.default_rng(SEED)
    stats = a[rng.integers(0, a.size, (RESAMPLES, a.size))].mean(axis=1)
    lo, hi = np.quantile(stats, [(1 - LEVEL) / 2, 1 - (1 - LEVEL) / 2])
    return [float(lo), float(hi)]


def boot_unpaired(x, y) -> list[float]:
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    rng = np.random.default_rng(SEED)
    d = x[rng.integers(0, x.size, (RESAMPLES, x.size))].mean(axis=1) - y[rng.integers(0, y.size, (RESAMPLES, y.size))].mean(axis=1)
    lo, hi = np.quantile(d, [(1 - LEVEL) / 2, 1 - (1 - LEVEL) / 2])
    return [float(lo), float(hi)]


def policy_row(run: dict, test: dict, success: str) -> dict:
    eps = test["report"]["episodes"]
    n = len(eps)
    terms = sorted({k for e in eps for k in e["term_returns"]})
    return {
        "run": f"{run['design']}-s{run['training_seed']}",
        "design": run["design"],
        "training_seed": run["training_seed"],
        "checkpoint_step": test["checkpoint_step"],
        "checkpoint_sha256": test["checkpoint_sha256"],
        "episodes": n,
        "mean_original_return": float(np.mean([e["original_return"] for e in eps])),
        "horizon_completion_rate": sum(e["outcome"] == success for e in eps) / n,
        "outcomes": {o: sum(e["outcome"] == o for e in eps) for o in sorted({e["outcome"] for e in eps})},
        "mean_training_return_own_design": float(np.mean([e["training_return"] for e in eps])),
        "mean_term_returns": {t: float(np.mean([e["term_returns"][t] for e in eps])) for t in terms},
        "mean_length": float(np.mean([e["length"] for e in eps])),
        "terminated": sum(e["terminated"] for e in eps),
        "truncated": sum(e["truncated"] for e in eps),
    }


def summarise(rows: list[dict], key: str) -> dict:
    values = [r[key] for r in sorted(rows, key=lambda r: r["training_seed"])]
    return {
        "values_by_seed": {r["training_seed"]: r[key] for r in sorted(rows, key=lambda r: r["training_seed"])},
        "mean": float(np.mean(values)),
        "mean_ci95": boot_mean(values),
        "integer_trimmed_mean_25": trimmed_mean(values),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def effects(rows: dict[str, list[dict]], key: str, reference: str) -> dict:
    out = {}
    ref = {r["training_seed"]: r[key] for r in rows[reference]}
    for design, rs in rows.items():
        if design == reference:
            continue
        mine = {r["training_seed"]: r[key] for r in rs}
        seeds = sorted(set(ref) & set(mine))
        diffs = [mine[s] - ref[s] for s in seeds]
        out[f"{design} - {reference}"] = {
            "paired_by_seed": {
                "differences_by_seed": dict(zip(seeds, diffs, strict=True)),
                "mean": float(np.mean(diffs)),
                "ci95": boot_mean(diffs),
            },
            "difference_of_means": float(np.mean(list(mine.values())) - np.mean(list(ref.values()))),
            "unpaired_ci95": boot_unpaired(list(mine.values()), list(ref.values())),
        }
    return out


def main() -> int:
    study, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    protocol = json.loads((study / "runs" / next(iter(sorted(p.name for p in (study / "runs").iterdir()))) / "protocol.json").read_text(encoding="utf-8"))
    success = protocol["success_outcome"]
    inputs = {}
    tables = {"selected": {}, "final": {}}
    selection = []
    for run_dir in sorted((study / "runs").iterdir()):
        run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        inputs[f"runs/{run_dir.name}/run.json"] = sha256(run_dir / "run.json")
        selection.append(
            {
                "run": run_dir.name,
                "selected_step": run["selection"]["step"],
                "validation_by_step": {c["step"]: c["validation"]["mean_original_return"] for c in run["checkpoints"]},
                "transitions": run["transitions"]["actual"],
                "effective_first_reset_seeds": run["seeding"]["effective_first_reset_seeds"],
            }
        )
        for which in ("selected", "final"):
            path = run_dir / f"test-{which}.json"
            inputs[f"runs/{run_dir.name}/{path.name}"] = sha256(path)
            test = json.loads(path.read_text(encoding="utf-8"))
            tables[which].setdefault(run["design"], []).append(policy_row(run, test, success))
    results = {"protocol_study_id": protocol["study_id"], "success_outcome": success, "inputs_sha256": inputs, "selection": selection}
    for which, rows in tables.items():
        results[which] = {
            "policies": {d: sorted(rs, key=lambda r: r["training_seed"]) for d, rs in rows.items()},
            "by_design": {
                d: {
                    "mean_original_return": summarise(rs, "mean_original_return"),
                    "horizon_completion_rate": summarise(rs, "horizon_completion_rate"),
                    "mean_training_return_own_design": summarise(rs, "mean_training_return_own_design"),
                }
                for d, rs in rows.items()
            },
            "effects_vs_original": {
                "mean_original_return": effects(rows, "mean_original_return", "original"),
                "horizon_completion_rate": effects(rows, "horizon_completion_rate", "original"),
            },
        }
    results["conventions"] = {
        "unit": "trained policy (five per design); 100 test episodes per policy; statistics condition on the fixed test seeds",
        "intervals": f"{LEVEL:.0%} percentile bootstrap, {RESAMPLES} resamples, seed {SEED}; policies resampled (paired: per-seed differences resampled)",
        "trimmed_mean": "integer-boundary 25% trimmed mean: drop int(0.25 n) from each end (middle three of five); not a fractional-weight IQM",
        "training_return": "each design's own training reward on the same test episodes; a different scale from original return, never compared with it",
    }
    (out / "results.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8", newline="\n")

    lines = ["# CartPole reward-design audit: results", "", f"Study `{protocol['study_id']}`. Generated by `analyze.py` from the run and test records; inputs and their SHA-256 are in `results.json`.", ""]
    for which, title in (("selected", "Primary: validation-selected checkpoints"), ("final", "Secondary (prespecified): final checkpoints")):
        lines += [f"## {title}", "", "| Design | Policies (seeds 50-54): mean original return | Mean [95% CI] | Trimmed mean | Horizon completion by policy | Mean completion [95% CI] | Own training return (separate scale) |", "|---|---|---|---|---|---|---|"]
        for d, s in results[which]["by_design"].items():
            o, c, t = s["mean_original_return"], s["horizon_completion_rate"], s["mean_training_return_own_design"]
            lines.append(
                f"| {d} | {', '.join(f'{v:.2f}' for v in o['values_by_seed'].values())} | {o['mean']:.2f} [{o['mean_ci95'][0]:.2f}, {o['mean_ci95'][1]:.2f}] | {o['integer_trimmed_mean_25']:.2f} | "
                f"{', '.join(f'{v:.0%}' for v in c['values_by_seed'].values())} | {c['mean']:.0%} [{c['mean_ci95'][0]:.0%}, {c['mean_ci95'][1]:.0%}] | {t['mean']:.1f} |"
            )
        lines += ["", "| Effect vs original | Paired mean difference [95% CI] | Difference of means [unpaired 95% CI] |", "|---|---|---|"]
        for key, label, scale, unit in (
            ("mean_original_return", "original return", 1.0, ""),
            ("horizon_completion_rate", "completion rate", 100.0, " pp"),
        ):
            for name, e in results[which]["effects_vs_original"][key].items():
                p = e["paired_by_seed"]
                m, (a, b) = p["mean"] * scale, (x * scale for x in p["ci95"])
                u, (c, d) = e["difference_of_means"] * scale, (x * scale for x in e["unpaired_ci95"])
                lines.append(f"| {name}, {label} | {m:.2f}{unit} [{a:.2f}, {b:.2f}] | {u:.2f}{unit} [{c:.2f}, {d:.2f}] |")
        lines.append("")
    lines += ["## Selection", "", "| Run | Selected step | Validation mean original return by checkpoint step |", "|---|---|---|"]
    for s in selection:
        lines.append(f"| {s['run']} | {s['selected_step']:,} | " + ", ".join(f"{k:,}: {v:.1f}" for k, v in s["validation_by_step"].items()) + " |")
    (out / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out / 'results.json'} and RESULTS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
