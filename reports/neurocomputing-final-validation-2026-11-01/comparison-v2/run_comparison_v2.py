# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Follow-up runner (version 2) of the audit-workflow comparison.

    python run_comparison_v2.py FIXTURES_DIR OUT_DIR [--run-id ID]

The prespecified comparison in ``reports/neurocomputing-2026-10-27/workflow-comparison/`` is fixed by its
``protocol/HASHES.sha256`` and is unchanged: protocol, fixtures, programs, ``run_comparison.py`` and the Windows
results of 27 October. This runner differs from ``run_comparison.py`` in four ways. None of them changes a
check, a threshold, a fixture or a fault expectation.

1. **Programs:** it runs ``workflows/*_v2.py``, the hashed programs with one change to the optional memory
   telemetry (``CHANGES.diff``, produced by ``derive_v2_programs.py``).
2. **Inputs first:** nothing runs unless the protocol, fixtures, programs and frozen runner match
   ``protocol/HASHES.sha256``, the version-2 files match ``HASHES-v2.sha256``, and the historical results match
   the digest pinned below.
3. **Results kept whole:** a program that crashes, times out or prints malformed output is recorded with its
   exit status, its stdout and stderr and the reason, and the run continues. ``OUT_DIR`` must be new or empty,
   so earlier output cannot be read as this run's. ``summary.json`` carries the run identifier.
4. **Assessment:** each pair keeps its raw verdict, and the frozen runner's literal rule is applied unchanged
   (``literal_rule_outcome``). Each pair is also assessed against the historical Windows row with
   ``assessment.py``, as exact agreement, a verified platform-dependent numerical difference of a clean
   control, or a failure.

Writes ``raw/<workflow>/<case>/`` (stdout, stderr, exit status), ``summary.json`` and ``MATRIX.md``. Exit status:
0 if every pair and every set-level check passes the assessment; 1 otherwise; 2 if the inputs did not verify
(then nothing ran) or ``OUT_DIR`` is not empty.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parents[1] / "neurocomputing-2026-10-27" / "workflow-comparison"
WORKFLOWS = {
    "W1": HERE / "workflows" / "w1_sb3_conventional_v2.py",
    "W2": HERE / "workflows" / "w2_sb3_reference_v2.py",
    "W3": HERE / "workflows" / "w3_lunarlab_v2.py",
}
# The frozen hash list and the historical Windows results this runner compares with (committed bytes).
FROZEN_HASHES_SHA256 = "9a953c5c42ff2ded1e5accbafb0074f3a20ae6064d7c6c3d545f065be47b7f9c"
HISTORICAL_SUMMARY_SHA256 = "20d56895589b244d6d02bb31670a83f4b4e5fea42ec767389d6c24b27a27056d"
TIMEOUT = 1800
STDERR_TAIL = 1500
DIGEST_LINE = re.compile(r"^([0-9a-f]{64}) [ *](.+)$")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


assessment = load_module("comparison_assessment", HERE / "assessment.py")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_list(path: Path) -> list[tuple[str, str]]:
    """``(digest, name)`` rows of a ``sha256sum``-style list; other lines (such as a header) are skipped."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = DIGEST_LINE.match(line.strip())
        if m:
            rows.append((m.group(1), m.group(2).strip()))
    return rows


def digest_problem(path: Path, digest: str, shown: str) -> list[str]:
    if not path.is_file():
        return [f"missing {shown}"]
    return [] if sha256(path) == digest else [f"{shown} does not have its recorded digest"]


def verify_inputs(fixtures: Path) -> list[str]:
    """Every hashed input of the comparison and every version-2 file, against its recorded digest."""
    frozen_list = FROZEN / "protocol" / "HASHES.sha256"
    problems = digest_problem(frozen_list, FROZEN_HASHES_SHA256, "protocol/HASHES.sha256")
    problems += digest_problem(
        FROZEN / "results" / "summary.json", HISTORICAL_SUMMARY_SHA256, "the historical results/summary.json"
    )
    if not problems:
        for digest, name in hash_list(frozen_list):
            path = fixtures / name.split("/", 1)[1] if name.startswith("fixtures/") else FROZEN / name
            problems += digest_problem(path, digest, name)
    v2_list = HERE / "HASHES-v2.sha256"
    rows = hash_list(v2_list) if v2_list.is_file() else []
    if not rows:
        problems.append("HASHES-v2.sha256 is missing or lists nothing")
    for digest, name in rows:
        problems += digest_problem(HERE / name, digest, f"comparison-v2/{name}")
    return problems


def text_of(stream) -> str:
    if stream is None:
        return ""
    return stream.decode("utf-8", "replace") if isinstance(stream, bytes) else stream


def run_pair(program: Path, case_dir: Path, out_dir: Path, env: dict, timeout: float = TIMEOUT) -> dict:
    """Run one program on one case in a fresh process; keep stdout, stderr and the exit status."""
    out_dir.mkdir(parents=True, exist_ok=False)
    t0 = time.perf_counter()
    failure = None
    try:
        proc = subprocess.run(
            [sys.executable, str(program), str(case_dir)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
            check=False,
        )
        code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        code, stdout, stderr = None, text_of(exc.stdout), text_of(exc.stderr)
        failure = f"timed out after {timeout:g} s"
    except OSError as exc:
        code, stdout, stderr = None, "", ""
        failure = f"could not be started: {exc}"
    wall = time.perf_counter() - t0
    (out_dir / "stdout.txt").write_text(stdout, encoding="utf-8", newline="\n")
    (out_dir / "stderr.txt").write_text(stderr, encoding="utf-8", newline="\n")
    (out_dir / "exit_code.txt").write_text(
        f"{code}\n" if failure is None else f"none: {failure}\n", encoding="utf-8", newline="\n"
    )
    result, parse_problem = parse_result(stdout)
    return {
        "exit_code": code,
        "wall_seconds": wall,
        "result": result,
        "failure": failure or parse_problem,
        "stderr_tail": stderr[-STDERR_TAIL:],
    }


def parse_result(stdout: str) -> tuple[dict | None, str | None]:
    """The program's result: the last stdout line that starts with ``{``, read as the frozen runner reads it."""
    lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    if not lines:
        return None, "no JSON result on stdout"
    try:
        result = json.loads(lines[-1])
    except ValueError as exc:
        return None, f"the last JSON line does not parse: {exc}"
    if not isinstance(result, dict):
        return None, f"the result is {assessment.show(result)}, not an object"
    return result, None


def make_row(case: dict, workflow: str, run: dict, literal_classify) -> dict:
    """One comparison row: the raw result, its problems, the frozen literal rule's outcome and the raw paths."""
    result = run["result"] or {}
    row = {
        "case": case["id"],
        "kind": case["kind"],
        "targets": case["targets"],
        "expected_verdict": case["expected_verdict"],
        "workflow": workflow,
        "exit_code": run["exit_code"],
        "verdict": result.get("verdict"),
        "replay_status": result.get("replay_status"),
        "episodes_executed": result.get("episodes_executed"),
        "execution_started_before_failure": result.get("execution_started_before_failure"),
        "wall_seconds": run["wall_seconds"],
        "checks": result.get("checks"),
        "raw": f"raw/{workflow}/{case['id']}/",
    }
    if run["result"] is not None:
        row["telemetry"] = {
            "peak_rss_bytes_self": result.get("peak_rss_bytes_self"),
            "peak_rss_status": result.get("peak_rss_status"),
        }
    problems = [run["failure"]] if run["failure"] else []
    if run["result"] is not None:
        if (result.get("workflow"), result.get("case")) != (workflow, case["id"]):
            problems.append(f"the result names {result.get('workflow')}/{result.get('case')}")
        problems += assessment.row_problems(row)
    row["result_problems"] = problems
    if problems:
        row.update(outcome="crashed" if run["result"] is None else "malformed", note="; ".join(problems))
        row["stderr_tail"] = run["stderr_tail"]
    else:
        literal = literal_classify(case, {"exit_code": run["exit_code"], "result": result})
        row.update(outcome=literal["outcome"], note=literal["note"])
    return row


def case_platform(case_dir: Path, current: dict) -> dict:
    """The case's recording platform (``case.json``), its agreement with the recorded evaluation, and this one."""

    def read(name: str):
        try:
            return json.loads((case_dir / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    case, evaluation = read("case.json") or {}, read("evaluation.json") or {}
    recorded = case.get("recorded_platform")
    consistent = recorded is not None and assessment.platform_key(recorded) == assessment.platform_key(
        evaluation.get("recorded_with")
    )
    return {"consistent": consistent, "comparison": assessment.compare_platform(recorded, current)}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")


def matrix(summary: dict, cases: list[dict]) -> str:
    a = summary["assessment"]
    plat = summary["platform"]
    lines = [
        "# Audit-workflow comparison, follow-up run (version 2): outcome matrix",
        "",
        f"Run `{summary['run_id']}`, {summary['started_utc']} to {summary.get('finished_utc')}, on "
        f"{plat['platform']}, Python {plat['python']}, "
        + ", ".join(f"{k} {v}" for k, v in plat["packages"].items())
        + ".",
        "",
        "Inputs: "
        + (
            "verified against `protocol/HASHES.sha256` and `HASHES-v2.sha256`."
            if summary["inputs"]["verified"]
            else "**did not verify; nothing ran**: " + "; ".join(summary["inputs"]["problems"])
        ),
        "",
    ]
    if not summary["rows"]:
        return "\n".join(lines) + "\n"
    rows = {(r["workflow"], r["case"]): r for r in a["rows"]}
    raw = {(r["workflow"], r["case"]): r for r in summary["rows"]}
    lines += [
        "Each cell: raw verdict (exit status, episodes) · the frozen runner's literal-rule outcome · the follow-up "
        "assessment. Outcome definitions: `protocol/PROTOCOL.md`; assessment rules: `assessment.py`.",
        "",
        "| Case | Targeted check | W1 conventional SB3 | W2 SB3 reference | W3 LunarLab |",
        "|---|---|---|---|---|",
    ]
    for case in cases:
        cells = []
        for w in assessment.WORKFLOWS:
            r, s = rows[(w, case["id"])], raw.get((w, case["id"]), {})
            ran = s.get("episodes_executed")
            cells.append(
                f"{r['verdict'] or 'no result'} (exit {r['exit_code']}, {ran if ran is not None else '?'} episodes)"
                f" · {r['literal_rule_outcome']} · **{r['class']}**"
            )
        lines.append(f"| {case['id']} | {', '.join(case['targets']) or 'none'} | " + " | ".join(cells) + " |")
    sc = a["set_checks"]
    lines += [
        "",
        f"**Assessment: {'passed' if a['ok'] else 'FAILED'}.** {a['pairs_present']} of {a['pairs_expected']} pairs "
        "present; classes: " + ", ".join(f"{k} {v}" for k, v in sorted(a["classes"].items())) + ".",
        "",
        f"- W2 and W3 report the same S1-S10 statuses: {'yes' if sc['w2_w3_status_agreement']['ok'] else 'NO'}"
        f" ({sc['w2_w3_status_agreement']['cases']} cases; disagreeing or missing: "
        f"{sc['w2_w3_status_agreement']['disagreeing_or_missing'] or 'none'}).",
        f"- W2 and W3 reject all {sc['faults_rejected_before_execution']['faults']} faults before execution: "
        f"{'yes' if sc['faults_rejected_before_execution']['ok'] else 'NO'} (not so: "
        f"{sc['faults_rejected_before_execution']['not_rejected_before_execution'] or 'none'}).",
        f"- W1 is unchecked in every case: {'yes' if sc['w1_unchecked']['ok'] else 'NO'} "
        f"(otherwise: {sc['w1_unchecked']['not_unchecked'] or 'none'}).",
    ]
    if a["platform_differences"]:
        lines += ["", "**Platform-dependent numerical differences (not blocking):**", ""]
        lines += [f"- {d['pair']}: {'; '.join(d['reasons'])}" for d in a["platform_differences"]]
    failures = [r for r in a["rows"] if r["blocking"]]
    if failures or a["problems"]:
        lines += ["", "**Failures (blocking):**", ""]
        lines += [f"- {r['workflow']}/{r['case']}: {'; '.join(r['reasons'])}" for r in failures]
        lines += [f"- {p}" for p in a["problems"]]
    tele = [r.get("telemetry") or {} for r in summary["rows"]]
    measured = sum(1 for t in tele if isinstance(t.get("peak_rss_bytes_self"), int))
    unavailable = sorted({t["peak_rss_status"] for t in tele if t.get("peak_rss_bytes_self") is None and t})
    lines += [
        "",
        f"Memory telemetry (optional): measured in {measured} of {len(summary['rows'])} results"
        + (f"; unavailable: {'; '.join(unavailable)}" if unavailable else "")
        + ".",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("fixtures", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--run-id", help="identifier to record in summary.json (default: a new random one)")
    a = ap.parse_args(argv)
    out = a.out
    if out.exists() and any(out.iterdir()):
        print(
            f"refusing to write into {out}: it is not empty, and earlier output must not be read as this run's",
            file=sys.stderr,
        )
        return 2
    out.mkdir(parents=True, exist_ok=True)
    summary: dict = {
        "runner": "comparison-v2/run_comparison_v2.py",
        "version": 2,
        "run_id": a.run_id or uuid.uuid4().hex,
        "started_utc": now(),
        "platform": assessment.current_platform(),
    }
    problems = verify_inputs(a.fixtures)
    summary["inputs"] = {"verified": not problems, "problems": problems}
    if problems:  # nothing unverified is read or run
        summary.update(
            rows=[], assessment={"ok": False, "problems": ["the inputs did not verify; nothing ran"]}
        )
        summary["finished_utc"] = now()
        write_json(out / "summary.json", summary)
        (out / "MATRIX.md").write_text(matrix(summary, []), encoding="utf-8", newline="\n")
        print("inputs did not verify; nothing ran:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 2
    inventory = json.loads((FROZEN / "protocol" / "fault_inventory.json").read_text(encoding="utf-8"))
    frozen = load_module("run_comparison_v1", FROZEN / "run_comparison.py")  # verified above; used unchanged
    historical = json.loads((FROZEN / "results" / "summary.json").read_text(encoding="utf-8"))["rows"]
    env = frozen.child_env()
    rows, platforms = [], {}
    for case in inventory["cases"]:
        case_dir = a.fixtures / case["id"]
        platforms[case["id"]] = case_platform(case_dir, summary["platform"])
        for workflow, program in WORKFLOWS.items():
            run = run_pair(program, case_dir, out / "raw" / workflow / case["id"], env)
            row = make_row(case, workflow, run, frozen.classify)
            rows.append(row)
            print(
                f"{case['id']:32s} {workflow}: {row['outcome']:24s} exit {run['exit_code']} "
                f"({run['wall_seconds']:.1f} s)",
                flush=True,
            )
    summary["rows"] = rows
    summary["case_platforms"] = platforms
    summary["assessment"] = assessment.assess(rows, historical, inventory["cases"], platforms)
    summary["finished_utc"] = now()
    write_json(out / "summary.json", summary)
    (out / "MATRIX.md").write_text(matrix(summary, inventory["cases"]), encoding="utf-8", newline="\n")
    verdict = summary["assessment"]
    print(f"assessment: {'passed' if verdict['ok'] else 'FAILED'}; classes {verdict['classes']}", flush=True)
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
