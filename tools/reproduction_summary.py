# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Summarise artifact reproductions for CI: a JSON summary, a Markdown table, and a gate on blocking statuses.

    python tools/reproduction_summary.py --platform linux --exit-codes codes.txt \
        --reports reproduce-*-linux.json --divergence divergence-*-linux.json \
        --json reproduction-summary-linux.json --markdown "$GITHUB_STEP_SUMMARY"

``codes.txt`` has one ``<artifact> <exit code>`` line per ``reproduce-artifact`` call. The command fails (exit 1)
when an artifact has a blocking status (integrity failure, a difference on the recording platform, a
significant aggregate difference), when a report is missing, or when a command's exit code does not match the
status in its report. Non-blocking cross-platform numerical differences are listed with the reason they are
tolerated. Nothing is hidden: every status, exit code and difference is printed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TOLERATED = (
    "exact cross-platform identity is not a supported guarantee (docs/jmlr/REPRODUCIBILITY.md); integrity "
    "holds and no aggregate differs significantly from the record"
)


def _artifact_name(report_path: Path) -> str:
    stem = report_path.stem  # reproduce-<artifact>-<platform>
    return stem.removeprefix("reproduce-").rsplit("-", 1)[0]


def summarize(reports: list[Path], divergence: list[Path], exit_codes: dict[str, int], platform: str) -> dict:
    from lunarlab.reproduce import STATUSES

    rows, problems = [], []
    seen = set()
    for path in sorted(reports):
        name = _artifact_name(path)
        seen.add(name)
        r = json.loads(path.read_text(encoding="utf-8"))
        status = r.get("status")
        if status not in STATUSES:
            problems.append(f"{name}: report has no known status (schema {r.get('schema')})")
            continue
        code = exit_codes.get(name)
        expected = STATUSES[status]["exit_code"]
        if code is not None and code != expected:
            problems.append(f"{name}: exit code {code} does not match status {status} (expected {expected})")
        if r.get("evaluation_skipped"):
            problems.append(f"{name}: {status}: {r['status_reason']}")
            continue
        s = r["comparison"]["summary"]
        rows.append(
            {
                "artifact": name,
                "status": status,
                "blocking": STATUSES[status]["blocking"],
                "exit_code": code,
                "integrity_ok": r["integrity_ok"],
                "same_platform": r["platform"]["same_platform"],
                "platform_differences": r["platform"]["differences"],
                "episodes": r["episodes"],
                "bit_identical": r["comparison"]["exact"],
                "outcome_agreement": s["agreement"]["all_outcome_fields"],
                "length_agreement": s["agreement"]["length"],
                "median_abs_return_difference": s["return_difference"]["median_abs"],
                "max_abs_return_difference": s["return_difference"]["max_abs"],
                "mean_return": [r["recorded_mean_original_return"], r["reproduced_mean_original_return"]],
                "pad_landing": [r["recorded_pad_landing_rate"], r["reproduced_pad_landing_rate"]],
                "aggregates_consistent": r["aggregates"]["consistent"],
                "reason": r["status_reason"],
                "tolerated_because": TOLERATED if status == "numerical-difference" else None,
            }
        )
        if STATUSES[status]["blocking"]:
            problems.append(f"{name}: {status}: {r['status_reason']}")
    for name, code in exit_codes.items():
        if name not in seen:
            problems.append(f"{name}: exit code {code} but no report (the command failed before writing one)")
    diag = []
    for path in sorted(divergence):
        d = json.loads(path.read_text(encoding="utf-8"))
        for e in d["episodes"]:
            diag.append(
                {
                    "artifact": d["artifact"],
                    "seed": e["seed"],
                    "source": e["source"],
                    "first_output_difference_step": e["inference"]["first_output_difference_step"],
                    "action_flips_on_reference_observations": e["inference"]["action_flips"],
                    "first_open_loop_observation_difference_step": e["dynamics"][
                        "first_observation_difference_step"
                    ],
                    "first_open_loop_difference_max_abs": e["dynamics"]["first_difference_max_abs"],
                    "closed_loop_first_observation_difference_step": e["closed_loop"][
                        "first_observation_difference_step"
                    ],
                    "closed_loop_abs_return_difference": e["closed_loop"]["abs_return_difference"],
                }
            )
        if "unexplained" in d["sources"]:
            problems.append(f"{d['artifact']}: closed loop differs although inference and dynamics do not")
    return {
        "platform": platform,
        "artifacts": rows,
        "divergence": diag,
        "problems": problems,
        "ok": not problems,
    }


def markdown(summary: dict) -> str:
    def f(x, fmt=".3g"):
        return "-" if x is None else format(x, fmt)

    lines = [
        f"## Artifact reproduction on {summary['platform']}",
        "",
        "| Artifact | Status | Exit | Integrity | Exact summary fields | Outcomes agree | Median / max abs original-return diff | "
        "Mean return (recorded -> here) | Pad landing | Aggregates |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in summary["artifacts"]:
        lines.append(
            f"| {r['artifact']} | **{r['status']}**{' (blocking)' if r['blocking'] else ''} | {r['exit_code']} | "
            f"{'ok' if r['integrity_ok'] else 'FAILED'} | {r['bit_identical']}/{r['episodes']} | "
            f"{r['outcome_agreement']:.0%} | {f(r['median_abs_return_difference'])} / {f(r['max_abs_return_difference'])} | "
            f"{r['mean_return'][0]:.2f} -> {r['mean_return'][1]:.2f} | {r['pad_landing'][0]:.0%} -> {r['pad_landing'][1]:.0%} | "
            f"{'no significant difference' if r['aggregates_consistent'] else 'SIGNIFICANT DIFFERENCE'} |"
        )
    tolerated = [r for r in summary["artifacts"] if r["tolerated_because"]]
    lines += [
        "",
        "Exact matches concern five selected episode-summary fields, not complete trajectories. "
        "Non-significant differences do not establish equivalence; no equivalence margins were specified.",
    ]
    if tolerated:
        lines += ["", f"Tolerated (not failed): {', '.join(r['artifact'] for r in tolerated)}: {TOLERATED}."]
    if summary["divergence"]:
        lines += [
            "",
            "### Where the trajectories part (against the recorded Windows traces)",
            "",
            "| Artifact | Seed | Source | First output difference | Action flips | First open-loop obs. difference "
            "(size) | Closed loop parts at | abs return diff |",
            "|---|---:|---|---:|---:|---:|---:|---:|",
        ]
        for d in summary["divergence"]:
            lines.append(
                f"| {d['artifact']} | {d['seed']} | {d['source']} | {f(d['first_output_difference_step'], 'd')} | "
                f"{d['action_flips_on_reference_observations']} | {f(d['first_open_loop_observation_difference_step'], 'd')} "
                f"({f(d['first_open_loop_difference_max_abs'])}) | {f(d['closed_loop_first_observation_difference_step'], 'd')} | "
                f"{f(d['closed_loop_abs_return_difference'])} |"
            )
    lines += ["", "**Problems:** " + ("; ".join(summary["problems"]) if summary["problems"] else "none")]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--platform", required=True)
    ap.add_argument("--reports", nargs="+", default=[])
    ap.add_argument("--divergence", nargs="*", default=[])
    ap.add_argument("--exit-codes", help="file of '<artifact> <exit code>' lines")
    ap.add_argument("--json", help="write the summary here")
    ap.add_argument("--markdown", help="append the Markdown table here (e.g. $GITHUB_STEP_SUMMARY)")
    args = ap.parse_args(argv)
    codes = {}
    if args.exit_codes:
        for line in Path(args.exit_codes).read_text(encoding="utf-8").splitlines():
            if line.strip():
                name, code = line.split()
                codes[name] = int(code)
    summary = summarize(
        [Path(p) for p in args.reports], [Path(p) for p in args.divergence], codes, args.platform
    )
    text = markdown(summary)
    print(text)
    if args.json:
        Path(args.json).write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
    if args.markdown:
        with open(args.markdown, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
