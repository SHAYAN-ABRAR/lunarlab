# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Execution cost of the three workflows on the clean control, under the prespecified design.

    python measure_cost.py CASE_DIR OUT_DIR [--blocks 5]

There are 5 blocks, each a permutation of (W1, W2, W3) drawn with ``numpy.random.default_rng(20261027)``.
Every run is a fresh process with one thread, timed from process start to exit. Memory is measured two
ways: the child's own peak working set, which the program reports at exit, and the process-tree resident
set sampled every 10 ms, which includes any subprocess such as ``git``. Sampling can miss short peaks.
Writes ``cost.json`` and ``COST.md``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_comparison import WORKFLOWS, child_env  # noqa: E402


def tree_rss(proc: psutil.Process) -> int:
    total = 0
    try:
        procs = [proc, *proc.children(recursive=True)]
    except psutil.Error:
        return 0
    for p in procs:
        with contextlib.suppress(psutil.Error):
            total += p.memory_info().rss
    return total


def one(workflow: str, case_dir: Path) -> dict:
    t0 = time.perf_counter()
    proc = subprocess.Popen(
        [sys.executable, str(WORKFLOWS[workflow]), str(case_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=child_env(),
    )
    ps = psutil.Process(proc.pid)
    peak_tree = 0
    while proc.poll() is None:
        peak_tree = max(peak_tree, tree_rss(ps))
        time.sleep(0.01)
    wall = time.perf_counter() - t0
    out = proc.stdout.read().decode("utf-8", "replace") if proc.stdout else ""
    lines = [line for line in out.splitlines() if line.strip().startswith("{")]
    result = json.loads(lines[-1]) if lines else {}
    return {
        "workflow": workflow,
        "exit_code": proc.returncode,
        "wall_seconds": wall,
        "peak_tree_rss_sampled_bytes": peak_tree,
        "peak_self_bytes_reported": result.get("peak_rss_bytes_self"),
        "episodes_executed": result.get("episodes_executed"),
        "verdict": result.get("verdict"),
    }


def boot_median(values, seed: int = 0) -> list[float]:
    a = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    stats = np.median(a[rng.integers(0, a.size, (10_000, a.size))], axis=1)
    return [float(np.quantile(stats, 0.025)), float(np.quantile(stats, 0.975))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--blocks", type=int, default=5)
    args = ap.parse_args()
    case_dir, out = Path(args.case_dir), Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261027)
    order = [list(rng.permutation(list(WORKFLOWS))) for _ in range(args.blocks)]
    runs = []
    for b, block in enumerate(order):
        for w in block:
            r = one(str(w), case_dir)
            r["block"] = b
            runs.append(r)
            print(
                f"block {b} {w}: {r['wall_seconds']:.2f} s, self peak {r['peak_self_bytes_reported']}, exit {r['exit_code']}",
                flush=True,
            )
    summary = {}
    for w in WORKFLOWS:
        rs = [r for r in runs if r["workflow"] == w]
        wall = [r["wall_seconds"] for r in rs]
        selfm = [r["peak_self_bytes_reported"] / 1e6 for r in rs if r["peak_self_bytes_reported"]]
        tree = [r["peak_tree_rss_sampled_bytes"] / 1e6 for r in rs]
        summary[w] = {
            "n": len(rs),
            "wall_seconds": {
                "median": float(np.median(wall)),
                "min": min(wall),
                "max": max(wall),
                "median_ci95": boot_median(wall),
                "all": wall,
            },
            "peak_self_MB": {
                "median": float(np.median(selfm)),
                "min": min(selfm),
                "max": max(selfm),
                "all": selfm,
            },
            "peak_tree_MB_sampled": {
                "median": float(np.median(tree)),
                "min": min(tree),
                "max": max(tree),
                "all": tree,
            },
            "episodes_executed": sorted({r["episodes_executed"] for r in rs}),
        }
    import stable_baselines3
    import torch

    record = {
        "design": "5 blocks, each a permutation of (W1, W2, W3) from numpy.random.default_rng(20261027); fresh process per run; OMP/MKL 1 thread, PyTorch 1 thread",
        "order": [[str(w) for w in b] for b in order],
        "runs": runs,
        "summary": summary,
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count_logical": psutil.cpu_count(),
            "memory_total_bytes": psutil.virtual_memory().total,
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "stable_baselines3": stable_baselines3.__version__,
        },
        "megabyte": "1 MB = 10^6 bytes",
    }
    (out / "cost.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8", newline="\n")
    lines = [
        "# Execution cost on the clean control (C0)",
        "",
        "Each workflow evaluated the same 100 test episodes once per run; the workflows differ in the checks they perform. "
        f"{args.blocks} runs per workflow in randomized blocks; fresh process each; one thread. Wall time includes interpreter start-up and imports. "
        "MB = 10^6 bytes.",
        "",
        "| Workflow | Wall time median [95% CI of median] (min-max), s | Self peak working set median (min-max), MB | Sampled process-tree peak median, MB |",
        "|---|---|---|---|",
    ]
    for w, s in summary.items():
        ws, ms, ts = s["wall_seconds"], s["peak_self_MB"], s["peak_tree_MB_sampled"]
        lines.append(
            f"| {w} | {ws['median']:.2f} [{ws['median_ci95'][0]:.2f}, {ws['median_ci95'][1]:.2f}] ({ws['min']:.2f}-{ws['max']:.2f}) | "
            f"{ms['median']:.0f} ({ms['min']:.0f}-{ms['max']:.0f}) | {ts['median']:.0f} |"
        )
    (out / "COST.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
