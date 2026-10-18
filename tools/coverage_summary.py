# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Write reports/jmlr/coverage/SUMMARY.md from a coverage.py JSON report.

    python -m pytest --cov --cov-report=json:reports/jmlr/coverage/coverage.json \
        --cov-report=html:reports/jmlr/coverage/html
    python tools/coverage_summary.py

Reports statement and branch coverage in total and per module (scientific core first), compared with the
baseline measured before the JMLR-readiness work (reports/jmlr/coverage/baseline/coverage.json).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "jmlr" / "coverage"
CRITICAL = [
    "lunarlab/rewards/terms.py",
    "lunarlab/rewards/accounting.py",
    "lunarlab/rewards/wrapper.py",
    "lunarlab/rewards/config.py",
    "lunarlab/audit/core.py",
    "lunarlab/audit/adapters.py",
    "lunarlab/audit/evaluate.py",
    "lunarlab/training.py",
    "lunarlab/continuation.py",
    "lunarlab/freeze.py",
    "lunarlab/outcomes.py",
    "lunarlab/hover.py",
    "lunarlab/config.py",
    "lunarlab/evaluation.py",
    "lunarlab/stats.py",
    "lunarlab/rl_stats.py",
    "lunarlab/results.py",
    "lunarlab/reproduce.py",
    "lunarlab/divergence.py",
    "lunarlab/runs.py",
    "lunarlab/storage.py",
    "lunarlab/lineage.py",
    "lunarlab/demo.py",
    "lunarlab/sysinfo.py",
]


def _pct(s: dict) -> float:
    covered = s["covered_lines"] + s.get("covered_branches", 0)
    total = s["num_statements"] + s.get("num_branches", 0)
    return 100.0 * covered / total if total else 100.0


def _files(report: dict) -> dict[str, dict]:
    return {k.replace("\\", "/"): v["summary"] for k, v in report["files"].items()}


def main() -> int:
    now = json.loads((OUT / "coverage.json").read_text(encoding="utf-8"))
    base_path = OUT / "baseline" / "coverage.json"
    base = json.loads(base_path.read_text(encoding="utf-8")) if base_path.exists() else None
    t = now["totals"]
    lines = [
        "# Code coverage",
        "",
        "Measured with coverage.py (statement and branch coverage, worker subprocesses included) over the whole "
        "`lunarlab` package; nothing is omitted except `if TYPE_CHECKING:` blocks and `__main__` guards. "
        "Reproduce with the commands in `tools/coverage_summary.py`. The HTML report is regenerated locally "
        "(`reports/jmlr/coverage/html/`, not stored in git).",
        "",
        "| | Statements | Missed | Branches | Partial | Coverage (statements + branches) |",
        "|---|---:|---:|---:|---:|---:|",
        f"| **Now** | {t['num_statements']:,} | {t['missing_lines']:,} | {t['num_branches']:,} | "
        f"{t['num_partial_branches']:,} | **{t['percent_covered']:.1f} %** |",
    ]
    if base:
        b = base["totals"]
        lines.append(
            f"| Before this work (`baseline/`) | {b['num_statements']:,} | {b['missing_lines']:,} | "
            f"{b['num_branches']:,} | {b['num_partial_branches']:,} | {b['percent_covered']:.1f} % |"
        )
    files = _files(now)
    base_files = _files(base) if base else {}
    lines += ["", "## Scientific core", "", "| Module | Now | Before |", "|---|---:|---:|"]
    for f in CRITICAL:
        if f in files:
            before = f"{_pct(base_files[f]):.1f} %" if f in base_files else "new"
            lines.append(f"| `{f}` | {_pct(files[f]):.1f} % | {before} |")
    rest = sorted(set(files) - set(CRITICAL))
    lines += ["", "## All other modules", "", "| Module | Now | Before |", "|---|---:|---:|"]
    for f in rest:
        before = f"{_pct(base_files[f]):.1f} %" if f in base_files else "new"
        lines.append(f"| `{f}` | {_pct(files[f]):.1f} % | {before} |")
    low = sorted(f for f in files if _pct(files[f]) < 70)
    reasons = {
        "lunarlab/cli.py": "command handlers; the tutorial, documentation and CLI tests run the common commands end to "
        "end, while orchestration commands (tuning, RLHF studies, showcase recording, demo export) are tested through "
        "the functions they call",
        "lunarlab/server/api.py": "HTTP endpoints of the web interface; the 15 browser flows exercise them, but in a "
        "separate server process that this measurement does not include",
        "lunarlab/server/main.py": "server start-up, static file serving and shutdown (same note as the API)",
        "lunarlab/jobs.py": "the job supervisor's process management and crash recovery across operating-system processes",
        "lunarlab/parallel.py": "running several experiment runs in parallel worker processes",
        "lunarlab/results.py": "the learned-reward figure and rare table branches; the basic, algorithm-comparison, "
        "ablation and robustness paths are tested",
        "lunarlab/sysinfo.py": "platform-specific branches (for example Linux CPU detection) that do not run on Windows",
    }
    lines += ["", "## What remains below 70 %, and why", ""]
    for f in low:
        lines.append(f"- `{f}` ({_pct(files[f]):.1f} %): {reasons.get(f, 'see the HTML report')}.")
    lines += [
        "",
        "Coverage measures which lines ran, not whether their results are right; the scientific core is additionally "
        "checked by exact-value, property-based and end-to-end tests.",
        "",
    ]
    (OUT / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"total {t['percent_covered']:.1f} % -> {OUT.relative_to(ROOT) / 'SUMMARY.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
