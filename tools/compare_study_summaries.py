# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Check the published study summary against a regeneration and against the raw final-test episodes.

    python tools/compare_study_summaries.py --artifacts <study-artifact bundle> \
        [--regenerated <folder written by `lunarlab results`>] --out comparison.json

Read-only. ``--artifacts`` is a folder written by ``tools/export_study_artifacts.py`` (its ``inventory.json``
locates each policy's exported ``evaluation.json``). For every policy in ``docs/results/results.json`` this
recomputes, with NumPy and without LunarLab code, the episode count, mean original return, strict pad-landing
rate and time-limit rate from the recorded episodes, and each group's interquartile mean of the per-policy
means. With ``--regenerated`` it also compares a fresh ``python -m lunarlab results`` output with the published
file key by key, ignoring generation metadata, and classifies every difference. Bootstrap intervals are not
recomputed. Exit 0 when every recomputed value matches and no published value changed.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
IGNORED = {"generated_at", "created_at", "provenance", "source_revision", "git", "code", "generated_with"}


def differences(a, b, path: str = "", out: list | None = None) -> list[dict]:
    """Every difference between two JSON values, ignoring generation metadata keys."""
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in IGNORED:
                continue
            if k not in a or k not in b:
                out.append(
                    {
                        "path": f"{path}/{k}",
                        "published": a.get(k, "<absent>"),
                        "regenerated": b.get(k, "<absent>"),
                    }
                )
            else:
                differences(a[k], b[k], f"{path}/{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append({"path": path, "published": f"list of {len(a)}", "regenerated": f"list of {len(b)}"})
        for i, (x, y) in enumerate(zip(a, b, strict=False)):
            differences(x, y, f"{path}[{i}]", out)
    elif isinstance(a, float) and isinstance(b, float):
        if not (a == b or (math.isnan(a) and math.isnan(b))):
            out.append({"path": path, "published": a, "regenerated": b, "abs_difference": abs(a - b)})
    elif a != b:
        out.append({"path": path, "published": a, "regenerated": b})
    return out


def iqm(values: list[float]) -> float:
    v = np.sort(np.asarray(values, dtype=float))
    k = len(v) // 4
    return float(v[k : len(v) - k].mean())


def recompute(published: dict, artifacts: Path) -> dict:
    inventory = json.loads((artifacts / "inventory.json").read_text(encoding="utf-8"))
    folder = {r["run_id"]: artifacts / r["folder"] for r in inventory["runs"]}
    groups = []
    for g in published["groups"]:
        policies = []
        for s in g["per_seed"]:
            ev = json.loads((folder[s["run_id"]] / "evaluation.json").read_text(encoding="utf-8"))
            eps = ev["episodes"]
            raw = {
                "run_id": s["run_id"],
                "n_episodes": len(eps),
                "mean_original_return": float(np.mean([e["original_return"] for e in eps])),
                "pad_landing_rate": sum(bool(e["pad_landing"]) for e in eps) / len(eps),
                "timeout_rate": sum(e["env_outcome"] == "timeout" for e in eps) / len(eps),
            }
            pub = s["evaluation"]
            raw["matches_published"] = {
                "n_episodes": raw["n_episodes"] == pub["n_episodes"],
                "mean_original_return": math.isclose(
                    raw["mean_original_return"], pub["mean_original_return"], rel_tol=0, abs_tol=1e-9
                ),
                "pad_landing_rate": raw["pad_landing_rate"] == pub["pad_landing_rate"],
                "timeout_rate": raw["timeout_rate"] == pub["timeout_rate"],
            }
            policies.append(raw)
        published_iqm = published["robust_stats"]["groups"].get(g["reward_name"], {}).get("iqm")
        group_iqm = iqm([p["mean_original_return"] for p in policies])
        groups.append(
            {
                "group": g["reward_name"],
                "policies": len(policies),
                "episodes": sum(p["n_episodes"] for p in policies),
                "iqm_from_raw_episodes": group_iqm,
                "published_iqm": published_iqm,
                "iqm_matches": published_iqm is not None
                and math.isclose(group_iqm, published_iqm, rel_tol=0, abs_tol=1e-9),
                "all_policies_match": all(all(p["matches_published"].values()) for p in policies),
                "per_policy": policies,
            }
        )
    return {
        "scope": "per-policy means and rates and group IQMs recomputed with NumPy from the exported final-test "
        "episodes; bootstrap intervals are not recomputed",
        "policies": sum(g["policies"] for g in groups),
        "episodes": sum(g["episodes"] for g in groups),
        "all_match": all(g["all_policies_match"] and g["iqm_matches"] for g in groups),
        "groups": groups,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--published", type=Path, default=ROOT / "docs" / "results" / "results.json")
    ap.add_argument(
        "--artifacts", type=Path, required=True, help="folder written by export_study_artifacts.py"
    )
    ap.add_argument("--regenerated", type=Path, help="folder written by `python -m lunarlab results`")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    published = json.loads(args.published.read_text(encoding="utf-8"))
    report: dict = {"kind": "lunarlab.study-summary-comparison", "published": args.published.name}
    ok = True
    if args.regenerated:
        regenerated = json.loads((args.regenerated / "results.json").read_text(encoding="utf-8"))
        diff = differences(published, regenerated)
        kinds = {
            "published_value_changed": [
                d for d in diff if "<absent>" not in (d["published"], d["regenerated"])
            ],
            "published_field_missing": [d for d in diff if d["regenerated"] == "<absent>"],
            "field_added_by_current_code": [d for d in diff if d["published"] == "<absent>"],
        }
        report["regeneration"] = {
            "ignored_keys": sorted(IGNORED),
            "counts": {k: len(v) for k, v in kinds.items()},
            "differences": kinds,
        }
        ok = not kinds["published_value_changed"] and not kinds["published_field_missing"]
        print(f"regeneration: {report['regeneration']['counts']}")
    report["raw_episode_recomputation"] = rr = recompute(published, args.artifacts)
    ok = ok and rr["all_match"]
    print(f"raw episodes: {rr['policies']} policies, {rr['episodes']} episodes, all match: {rr['all_match']}")
    for g in rr["groups"]:
        print(
            f"  {g['group']:<34} IQM {g['iqm_from_raw_episodes']:10.4f}  published {g['published_iqm']:10.4f}"
        )
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
