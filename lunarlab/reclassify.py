# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Derived outcome-classifier-v2 reports for evaluations written by classifier version 1.

Historical evaluation files are never modified. This module reads them, records their SHA-256,
derives version-2 landing categories from the per-episode fields they stored
(:func:`lunarlab.outcomes.reclassify_legacy_episode`) and reports before/after differences. Output
goes only to a directory chosen by the caller (``python -m lunarlab reclassify-outcomes --out``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lunarlab.outcomes import LANDING_CATEGORIES, OUTCOME_CLASSIFIER_VERSION, reclassify_legacy_episode
from lunarlab.storage import RunPaths, atomic_write_text, read_json, sha256_file, utc_now


def reclassify_file(path: Path) -> dict[str, Any] | None:
    """Before/after for one evaluation file, or None if it is not a version-1 evaluation."""
    r = read_json(path, default=None) or {}
    episodes = r.get("episodes")
    if not episodes or "aggregate" not in r:
        return None
    if r["aggregate"].get("outcome_classifier_version", 1) >= OUTCOME_CLASSIFIER_VERSION:
        return None
    criteria = ((r.get("protocol") or {}).get("pad_landing")) or {}
    max_angle = float(criteria.get("max_final_abs_angle_rad", 0.35))
    try:
        derived = [reclassify_legacy_episode(e, max_final_abs_angle_rad=max_angle) for e in episodes]
    except ValueError as exc:
        return {"source_file": path.name, "error": str(exc)}
    n = len(derived)
    counts = {c: sum(d["landing_category"] == c for d in derived) for c in LANDING_CATEGORIES}
    relabelled = [
        {
            "seed": e.get("seed"),
            "v1_landed_off_pad": True,
            "v2_category": d["landing_category"],
            "failures": d["strict_failures"],
        }
        for e, d in zip(episodes, derived, strict=True)
        if d["v1_landed_off_pad"] and d["landing_category"] != "landed_not_within_pad"
    ]
    return {
        "source_file": path.name,
        "source_sha256": sha256_file(path),
        "split": r.get("split"),
        "checkpoint": (r.get("checkpoint") or {}).get("name"),
        "n_episodes": n,
        "source_classifier_version": 1,
        "derived_classifier_version": OUTCOME_CLASSIFIER_VERSION,
        "before": {
            "pad_landing_rate": sum(bool(e.get("pad_landing")) for e in episodes) / n,
            "landed_off_pad_rate_v1": sum(d["v1_landed_off_pad"] for d in derived) / n,
        },
        "after": {f"{c}_rate": counts[c] / n for c in LANDING_CATEGORIES},
        "relabelled_episodes": relabelled,
        "note": "leg positions were not stored by version 1: 'landed_not_within_pad' covers both straddling and outside",
    }


def reclassification_report(run_ids: list[str]) -> dict[str, Any]:
    files = []
    for rid in run_ids:
        for p in sorted(RunPaths(rid).evaluations.glob("*.json")):
            rec = reclassify_file(p)
            if rec is not None:
                files.append({"run_id": rid, **rec})
    usable = [f for f in files if "error" not in f]
    total = sum(f["n_episodes"] for f in usable)
    return {
        "generated_at": utc_now(),
        "derived_classifier_version": OUTCOME_CLASSIFIER_VERSION,
        "files": files,
        "summary": {
            "evaluation_files": len(usable),
            "episodes": total,
            "pad_landings": round(sum(f["before"]["pad_landing_rate"] * f["n_episodes"] for f in usable)),
            "v1_landed_off_pad": round(
                sum(f["before"]["landed_off_pad_rate_v1"] * f["n_episodes"] for f in usable)
            ),
            "v2_landed_not_within_pad": round(
                sum(f["after"]["landed_not_within_pad_rate"] * f["n_episodes"] for f in usable)
            ),
            "v2_on_pad_not_strict": round(
                sum(f["after"]["on_pad_not_strict_rate"] * f["n_episodes"] for f in usable)
            ),
            "relabelled_episodes": sum(len(f["relabelled_episodes"]) for f in usable),
            "files_with_errors": len(files) - len(usable),
        },
    }


def write_report(report: dict[str, Any], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    js = out_dir / "outcome_reclassification_v2.json"
    atomic_write_text(js, json.dumps(report, indent=1))
    s = report["summary"]
    lines = [
        f"_Generated {report['generated_at']} by `python -m lunarlab reclassify-outcomes` (derived; the "
        "evaluation files themselves are unchanged, their SHA-256 digests are in the JSON)._",
        "",
        f"Evaluation files: {s['evaluation_files']} · episodes: {s['episodes']:,} · strict pad landings: "
        f"{s['pad_landings']:,} (unchanged by definition).",
        "",
        "| Classification | Episodes |",
        "|---|---:|",
        f"| v1 `landed_off_pad` (any clean at-rest landing that was not a strict pad landing) | {s['v1_landed_off_pad']:,} |",
        f"| v2 landed not within the pad | {s['v2_landed_not_within_pad']:,} |",
        f"| v2 on the pad, not strict (tilted, or no leg contact seen) | {s['v2_on_pad_not_strict']:,} |",
        f"| v1 'off pad' episodes that were on the pad | {s['relabelled_episodes']:,} |",
    ]
    md = out_dir / "outcome_reclassification_v2.md"
    atomic_write_text(md, "\n".join(lines) + "\n")
    return [js, md]
