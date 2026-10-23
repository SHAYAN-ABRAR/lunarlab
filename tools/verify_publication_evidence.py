# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Recompute publication summaries without training or modifying historical evidence.

Run: python tools/verify_publication_evidence.py --out /path/to/new-report.json
Uses only the standard library. This verifies summaries, not absent raw evaluations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    d = json.loads((ROOT / "docs/results/results.json").read_text(encoding="utf-8"))
    groups = []
    for g in d["groups"]:
        es = [x["evaluation"] for x in g["per_seed"]]
        scores = sorted(e["mean_original_return"] for e in es)
        k = len(scores) // 4
        iqm = statistics.mean(scores[k : len(scores) - k])
        published = d["robust_stats"]["groups"][g["reward_name"]]
        assert math.isclose(iqm, published["iqm"], abs_tol=1e-10)
        landings = sum(round(e["pad_landing_rate"] * e["n_episodes"]) for e in es)
        timeouts = sum(round(e["timeout_rate"] * e["n_episodes"]) for e in es)
        groups.append(
            dict(
                name=g["reward_name"],
                algorithm=g["algo"],
                policies=len(es),
                episodes=sum(e["n_episodes"] for e in es),
                iqm=iqm,
                recorded_iqm_ci=published["iqm_ci"],
                mean_original_return=statistics.mean(scores),
                strict_landings=landings,
                timeouts=timeouts,
                training_budgets=sorted({x["checkpoint_transitions"] for x in g["per_seed"]}),
                run_ids=[x["run_id"] for x in g["per_seed"]],
            )
        )
    artifacts = []
    for a in sorted((ROOT / "examples/artifacts").glob("*/artifact.json")):
        m = json.loads(a.read_text(encoding="utf-8"))
        checks = []
        for name, spec in m["files"].items():
            expected = spec["sha256"] if isinstance(spec, dict) else spec
            actual = sha(a.parent / name)
            checks.append(dict(file=name, match=actual == expected, sha256=actual))
        assert all(c["match"] for c in checks)
        artifacts.append(dict(name=a.parent.name, files=checks))
    baseline = json.loads(
        (ROOT / "reports/jmlr/artifacts/integrity_baseline.json").read_text(encoding="utf-8")
    )
    present = []
    absent = []
    different = []
    line_endings = []
    for name, (size, digest) in baseline.items():
        f = ROOT / name
        if not f.is_file():
            absent.append(name)
        elif f.stat().st_size == size and sha(f) == digest:
            present.append(name)
        elif hashlib.sha256(f.read_bytes().replace(b"\n", b"\r\n")).hexdigest() == digest:
            line_endings.append(name)
        else:
            different.append(name)
    bdir = ROOT / "reports/jmlr/benchmarks/standard-2026-10-18T132206+0000"
    rows = [json.loads(s) for s in (bdir / "raw.jsonl").read_text(encoding="utf-8").splitlines() if s]
    benchmark = {}
    base = statistics.mean(x["loop_s"] for x in rows if x["config"] == "sb3")
    basewall = statistics.mean(x["wall_s"] for x in rows if x["config"] == "sb3")
    for name in ["sb3", "accounting", "lunarlab"]:
        rr = [x for x in rows if x["config"] == name]
        speed = [x["transitions"] / x["loop_s"] for x in rr]
        benchmark[name] = dict(
            n=len(rr),
            transitions_per_s_mean=statistics.mean(speed),
            transitions_per_s_sd=statistics.stdev(speed),
            loop_time_ratio=statistics.mean(x["loop_s"] for x in rr) / base,
            wall_time_ratio=statistics.mean(x["wall_s"] for x in rr) / basewall,
            process_peak_bytes_mean=statistics.mean(x["peak_memory_bytes"] for x in rr),
        )
    out = dict(
        schema=1,
        source_revision="67440c664f658ccd589f7198ee2182d5820ca7c1",
        scope="Summary recomputation and available-file integrity; not independent recovery of all raw episodes",
        groups=groups,
        policies=sum(g["policies"] for g in groups),
        episodes=sum(g["episodes"] for g in groups),
        artifacts=artifacts,
        historical_integrity=dict(
            manifest_entries=len(baseline),
            present_matching=len(present),
            absent=len(absent),
            line_ending_only=line_endings,
            different=different,
        ),
        benchmark=benchmark,
        benchmark_caveat="Historical C memory sampled after optional recording; not a training-only comparison",
        input_sha256={
            "docs/results/results.json": sha(ROOT / "docs/results/results.json"),
            str((bdir / "raw.jsonl").relative_to(ROOT)): sha(bdir / "raw.jsonl"),
        },
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        f"Verified {out['policies']} policy summaries, {out['episodes']} reported episodes, {len(artifacts)} supplied artifacts"
    )
    print("Historical manifest:", out["historical_integrity"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
