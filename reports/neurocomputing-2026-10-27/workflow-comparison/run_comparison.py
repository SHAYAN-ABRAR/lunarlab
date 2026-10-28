# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Run every (case, workflow) pair of the audit-workflow comparison and classify each result.

    python run_comparison.py FIXTURES_DIR OUT_DIR

Each pair runs in a fresh process with one thread (``OMP_NUM_THREADS``, ``MKL_NUM_THREADS``; the programs
also set one PyTorch thread). Raw stdout, stderr and exit status go to ``OUT_DIR/raw/<workflow>/<case>/``.
The classification against ``protocol/fault_inventory.json`` (see ``protocol/PROTOCOL.md``) goes to
``OUT_DIR/summary.json`` and ``OUT_DIR/MATRIX.md``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKFLOWS = {
    "W1": HERE / "workflows" / "w1_sb3_conventional.py",
    "W2": HERE / "workflows" / "w2_sb3_reference.py",
    "W3": HERE / "workflows" / "w3_lunarlab.py",
}
CODES = {0: "accepted", 3: "accepted-numerical-difference", 1: "rejected", 4: "unchecked"}


def child_env() -> dict:
    env = dict(os.environ)
    env.update(OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONIOENCODING="utf-8")
    return env


def run(workflow: str, case_dir: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(WORKFLOWS[workflow]), str(case_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env(),
        timeout=1800,
        check=False,
    )
    wall = time.perf_counter() - t0
    (out_dir / "stdout.txt").write_text(proc.stdout, encoding="utf-8", newline="\n")
    (out_dir / "stderr.txt").write_text(proc.stderr, encoding="utf-8", newline="\n")
    (out_dir / "exit_code.txt").write_text(f"{proc.returncode}\n", encoding="utf-8", newline="\n")
    lines = [line for line in proc.stdout.splitlines() if line.strip().startswith("{")]
    try:
        result = json.loads(lines[-1]) if lines else None
    except ValueError:
        result = None
    return {"exit_code": proc.returncode, "wall_seconds": wall, "result": result}


def classify(case: dict, run_: dict) -> dict:
    """The outcome of one (workflow, case) pair under the prespecified rules."""
    result, code = run_["result"], run_["exit_code"]
    if result is None or code not in CODES:
        return {
            "outcome": "crashed",
            "note": f"exit status {code}, no JSON result" if result is None else f"exit {code}",
        }
    checks = result["checks"]
    verdict = result["verdict"]
    executed = result.get("episodes_executed", 0)
    if case["kind"] == "control":
        if verdict == case["expected_verdict"]:
            return {"outcome": "correct", "note": verdict}
        if verdict == "unchecked":
            return {
                "outcome": "unsupported",
                "note": "results produced without the specification's checks; no false alarm",
            }
        failed = [k for k, c in checks.items() if c["status"] in ("fail", "warn")]
        return {"outcome": "false alarm", "note": f"{verdict}; failed {failed}"}
    targets = case["targets"]
    statuses = {t: checks.get(t, {}).get("status") for t in targets}
    if verdict.startswith("rejected"):
        if all(s == "fail" for s in statuses.values()):
            late = verdict == "rejected-after-execution" or executed > 0
            return {"outcome": "late" if late else "rejected", "note": f"{verdict}; targeted {statuses}"}
        return {"outcome": "rejected (other check)", "note": f"{verdict}; targeted {statuses}"}
    if any(s == "warn" for s in statuses.values()):
        return {"outcome": "warned", "note": f"{verdict}; targeted {statuses}"}
    if all(s == "unsupported" for s in statuses.values()):
        return {"outcome": "unsupported", "note": f"{verdict}; {executed} episodes executed"}
    return {"outcome": "missed", "note": f"{verdict}; targeted {statuses}; {executed} episodes executed"}


def main() -> int:
    fixtures, out = Path(sys.argv[1]), Path(sys.argv[2])
    inventory = json.loads((HERE / "protocol" / "fault_inventory.json").read_text(encoding="utf-8"))
    rows = []
    for case in inventory["cases"]:
        for workflow in WORKFLOWS:
            r = run(workflow, fixtures / case["id"], out / "raw" / workflow / case["id"])
            c = classify(case, r)
            rows.append(
                {
                    "case": case["id"],
                    "kind": case["kind"],
                    "targets": case["targets"],
                    "expected_verdict": case["expected_verdict"],
                    "workflow": workflow,
                    "exit_code": r["exit_code"],
                    "verdict": (r["result"] or {}).get("verdict"),
                    "episodes_executed": (r["result"] or {}).get("episodes_executed"),
                    "wall_seconds": r["wall_seconds"],
                    "checks": (r["result"] or {}).get("checks"),
                    **c,
                }
            )
            print(
                f"{case['id']:32s} {workflow}: {c['outcome']:24s} exit {r['exit_code']} ({r['wall_seconds']:.1f} s)",
                flush=True,
            )
    summary = {"inventory_cases": len(inventory["cases"]), "rows": rows}
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
    lines = [
        "# Audit-workflow comparison: outcome matrix",
        "",
        f"{len(inventory['cases'])} prespecified cases (2 controls, 12 faults), each run once by each workflow. "
        "Outcome definitions are in `protocol/PROTOCOL.md`. Raw output for each pair is under `raw/<workflow>/<case>/`.",
        "",
        "| Case | Targeted check | W1 conventional SB3 | W2 SB3 reference | W3 LunarLab |",
        "|---|---|---|---|---|",
    ]
    for case in inventory["cases"]:
        cells = []
        for workflow in WORKFLOWS:
            row = next(r for r in rows if r["case"] == case["id"] and r["workflow"] == workflow)
            ran = row["episodes_executed"]
            cells.append(
                f"{row['outcome']} (exit {row['exit_code']}, {ran if ran is not None else '?'} episodes)"
            )
        lines.append(f"| {case['id']} | {', '.join(case['targets']) or 'none'} | " + " | ".join(cells) + " |")
    (out / "MATRIX.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
