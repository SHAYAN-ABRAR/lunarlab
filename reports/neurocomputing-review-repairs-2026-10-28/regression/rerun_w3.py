# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Rerun the comparison's W3 (LunarLab) program on the 14 fixtures with the repaired code, and compare.

    python reports/neurocomputing-review-repairs-2026-10-28/regression/rerun_w3.py OUT_DIR

W3 uses ``check_recorded_episodes`` and the accounting wrapper, both changed by the repairs. The repaired
code must leave the recorded W3 results of 27 October unchanged on every designed case. Compared for each
case:

- the S1-S10 status vector;
- the verdict;
- the exit status;
- the number of episodes executed.

The detail strings are allowed to change. Nothing is trained: the fixtures' policies are only evaluated, on
the two control cases.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPARISON = ROOT / "reports/neurocomputing-2026-10-27/workflow-comparison"
sys.path.insert(0, str(COMPARISON))

from run_comparison import run  # noqa: E402  (the comparison's own runner)


def last_json(path: Path) -> dict:
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip().startswith("{")]
    return json.loads(lines[-1])


def main(out: Path) -> int:
    rows, differences = [], []
    for case_dir in sorted(p for p in (COMPARISON / "fixtures").iterdir() if p.is_dir()):
        case = case_dir.name
        recorded_dir = COMPARISON / "results/raw/W3" / case
        recorded = last_json(recorded_dir / "stdout.txt")
        recorded_exit = int((recorded_dir / "exit_code.txt").read_text(encoding="utf-8").strip())
        info = run("W3", case_dir, out / "raw" / "W3" / case)
        now = last_json(out / "raw" / "W3" / case / "stdout.txt")
        statuses = lambda r: {k: v["status"] for k, v in r["checks"].items()}  # noqa: E731
        same = {
            "status_vector": statuses(now) == statuses(recorded),
            "verdict": now["verdict"] == recorded["verdict"],
            "exit_code": info["exit_code"] == recorded_exit,
            "episodes_executed": now.get("episodes_executed") == recorded.get("episodes_executed"),
        }
        rows.append({"case": case, "recorded_exit": recorded_exit, "now_exit": info["exit_code"], **same})
        if not all(same.values()):
            differences.append(case)
    report = {
        "cases": len(rows),
        "identical": len(rows) - len(differences),
        "differences": differences,
        "rows": rows,
    }
    (out / "comparison.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}))
    return 0 if not differences else 1


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
