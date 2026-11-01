# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Follow-up assessment of audit-workflow comparison rows against the historical Windows results.

The frozen runner compares each verdict with one literal expected verdict. A clean control that replays as a
permitted numerical difference on another platform is therefore labelled a false alarm, although every check
passed. This module keeps that literal label (``literal_rule_outcome``) and adds a separate assessment of each
(workflow, case) row:

- ``exact-agreement``: the verdict, exit status, episode count and S1-S10 statuses equal the historical row.
- ``platform-numerical-difference`` (not blocking, and always listed). It applies only when all of these hold:
  - the case is a clean control whose historical replay was exact, run by a workflow that runs S10 (W2, W3);
  - all of S1-S10 pass, and the replay status is the existing nonblocking ``numerical-difference`` (exit 3);
  - the same number of episodes ran;
  - the case and its recorded evaluation name the same recording platform;
  - the runner verified that this machine's operating system or a numerical library differs from that platform.
- ``failure`` (blocking): everything else. This includes crashed, absent or malformed results, a difference on
  the recording platform itself, a changed fault case, and any other change of a label.

Set-level checks:

- all 42 pairs are present, once each;
- W2 and W3 report the same S1-S10 statuses in every case;
- W2 and W3 reject all 12 faults before any episode runs, through the targeted check;
- W1 stays unchecked.

Nothing here re-runs or relaxes a check. Standard library only: the follow-up runner and the package validator
both import this file.

    python assessment.py --platform    # print this interpreter's platform record as JSON
"""

from __future__ import annotations

import json
import sys
from collections import Counter

CHECKS = tuple(f"S{i}" for i in range(1, 11))
CHECK_STATUSES = ("pass", "fail", "warn", "unsupported", "not-run")
EXIT_OF_VERDICT = {
    "accepted": 0,
    "accepted-numerical-difference": 3,
    "rejected-before-execution": 1,
    "rejected-after-execution": 1,
    "unchecked": 4,
}
REPLAY_STATUSES = ("exact", "numerical-difference", "unexpected-difference", "aggregate-disagreement")
WORKFLOWS = ("W1", "W2", "W3")
REPLAYING_WORKFLOWS = ("W2", "W3")
# The operating system and the numerical libraries: the union of W2's and LunarLab's platform comparisons.
PLATFORM_PACKAGES = ("torch", "numpy", "Box2D", "gymnasium", "stable-baselines3")
PLATFORM_KEYS = ("os", *PLATFORM_PACKAGES)


def show(value) -> str:
    """A short, typed rendering of a value for a problem message."""
    if value is None:
        return "null"
    text = repr(value)
    return f"{type(value).__name__} {text[:60]}{'...' if len(text) > 60 else ''}"


def current_platform() -> dict:
    """This interpreter's platform string, Python version and numerical-library versions."""
    import platform
    from importlib.metadata import PackageNotFoundError, version

    packages = {}
    for name in PLATFORM_PACKAGES:
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {"platform": platform.platform(), "python": platform.python_version(), "packages": packages}


def platform_key(info) -> dict:
    """The operating system and numerical-library versions of a platform record; None where not recorded."""
    info = info if isinstance(info, dict) else {}
    plat = info.get("platform")
    packages = info.get("packages") if isinstance(info.get("packages"), dict) else {}
    os_name = plat.split("-", 1)[0] if isinstance(plat, str) and plat else None
    return {"os": os_name, **{p: packages.get(p) for p in PLATFORM_PACKAGES}}


def compare_platform(recorded, current) -> dict:
    """Which components of the recording platform differ on this machine.

    ``verified_different`` needs at least one component that the record states and that differs here. A
    component the record does not state is listed among the differences, but it is not evidence of one.
    """
    rec, cur = platform_key(recorded), platform_key(current)
    differences = {k: [rec[k], cur[k]] for k in PLATFORM_KEYS if rec[k] != cur[k]}
    verified = sorted(k for k, (r, _) in differences.items() if r is not None)
    return {
        "recorded": rec,
        "current": cur,
        "differences": differences,
        "verified_differences": verified,
        "verified_different": bool(verified),
    }


def statuses(row: dict) -> dict:
    return {k: row["checks"][k]["status"] for k in CHECKS}


def replay_status(row: dict) -> str | None:
    """The replay status of a row: its own field (follow-up runner) or the S10 detail's prefix (frozen runner).

    Both W2 and W3 write S10's detail as ``"<status>: <reason>"``.
    """
    status = row.get("replay_status")
    if status is None:
        detail = (row.get("checks") or {}).get("S10", {}).get("detail")
        status = detail.split(":", 1)[0] if isinstance(detail, str) and ":" in detail else None
    return status if status in REPLAY_STATUSES else None


def row_problems(row) -> list[str]:
    """Why a row cannot be assessed: absent, wrongly typed or mutually inconsistent fields. Empty if none."""
    if not isinstance(row, dict):
        return [f"the row is {show(row)}, not an object"]
    problems = []
    for key in ("workflow", "case"):
        if not isinstance(row.get(key), str):
            problems.append(f"{key} is {show(row.get(key))}, not a name")
    code, verdict = row.get("exit_code"), row.get("verdict")
    if type(code) is not int:
        problems.append(f"exit_code is {show(code)}, not an integer")
    if verdict not in EXIT_OF_VERDICT:
        problems.append(f"verdict is {show(verdict)}, not a protocol verdict")
    elif type(code) is int and EXIT_OF_VERDICT[verdict] != code:
        problems.append(f"exit status {code} does not belong to verdict {verdict!r}")
    episodes = row.get("episodes_executed")
    if type(episodes) is not int or episodes < 0:
        problems.append(f"episodes_executed is {show(episodes)}, not a count")
    checks = row.get("checks")
    if not isinstance(checks, dict):
        problems.append(f"checks is {show(checks)}, not an object mapping S1-S10")
    else:
        if sorted(checks) != sorted(CHECKS):
            problems.append(f"checks has the keys {sorted(map(str, checks))}, not S1-S10")
        for key in CHECKS:
            entry = checks.get(key)
            if key in checks and (not isinstance(entry, dict) or entry.get("status") not in CHECK_STATUSES):
                status = entry.get("status") if isinstance(entry, dict) else entry
                problems.append(f"{key} status is {show(status)}, not one of {', '.join(CHECK_STATUSES)}")
    telemetry = row.get("telemetry")
    if telemetry is not None and not isinstance(telemetry, dict):
        problems.append(f"telemetry is {show(telemetry)}, not an object")
    elif telemetry is not None:  # follow-up rows only; the frozen runner does not copy it
        value, status = telemetry.get("peak_rss_bytes_self"), telemetry.get("peak_rss_status")
        if value is not None and (type(value) is not int or value <= 0):
            problems.append(f"peak_rss_bytes_self is {show(value)}: a measurement must be a positive integer")
        if not isinstance(status, str):
            problems.append(f"peak_rss_status is {show(status)}, not a status")
        elif (value is None) != status.startswith("unavailable"):
            problems.append(f"peak_rss_status {status!r} does not match the value {show(value)}")
    return problems


def failure(*reasons: str) -> dict:
    return {"class": "failure", "blocking": True, "reasons": list(reasons)}


def assess_row(row, historical, case: dict, case_platform: dict | None) -> dict:
    """The follow-up class of one row: exact agreement, verified platform-dependent difference, or failure."""
    problems = row_problems(row)
    if problems:
        return failure("the result cannot be assessed: " + "; ".join(problems))
    if historical is None or row_problems(historical):
        return failure("there is no well-formed historical row to compare with")
    if all(row[k] == historical[k] for k in ("verdict", "exit_code", "episodes_executed")) and statuses(
        row
    ) == statuses(historical):
        return {"class": "exact-agreement", "blocking": False, "reasons": []}
    reasons = []
    if case.get("kind") != "control":
        reasons.append("a fault case's result changed; the faults are rejected before any episode runs")
    if historical["verdict"] != "accepted" or case.get("expected_verdict") != "accepted":
        reasons.append("only a control whose historical replay was exact may become a permitted difference")
    if row["workflow"] not in REPLAYING_WORKFLOWS:
        reasons.append(f"{row['workflow']} does not run the replay check S10")
    if row["verdict"] != "accepted-numerical-difference":
        reasons.append(f"the verdict is {row['verdict']!r} (exit {row['exit_code']})")
    if replay_status(row) != "numerical-difference":
        reasons.append(f"the replay status is {show(replay_status(row))}, not 'numerical-difference'")
    failing = [k for k in CHECKS if row["checks"][k]["status"] != "pass"]
    if failing:
        reasons.append(f"checks that do not pass: {', '.join(failing)}")
    if row["episodes_executed"] != historical["episodes_executed"]:
        reasons.append(f"{row['episodes_executed']} episodes ran, not {historical['episodes_executed']}")
    case_platform = case_platform or {}
    comparison = case_platform.get("comparison") or {}
    if not case_platform.get("consistent"):
        reasons.append("the case and its recorded evaluation do not name the same recording platform")
    if not comparison.get("verified_different"):
        reasons.append(
            "the runner did not verify that this machine's operating system or numerical libraries differ "
            "from the recording platform; on the recording platform a replay difference is unexpected"
        )
    if reasons:
        return failure(*reasons)
    detail = row["checks"]["S10"].get("detail", "")
    return {
        "class": "platform-numerical-difference",
        "blocking": False,
        "reasons": [
            "this machine differs from the recording platform in "
            + ", ".join(f"{k} ({a} recorded, {b} here)" for k, (a, b) in comparison["differences"].items())
            + f"; S10: {detail}"
        ],
    }


def assess(rows, historical_rows, cases: list[dict], case_platforms: dict) -> dict:
    """Assess every pair of the comparison and the set-level properties."""
    problems: list[str] = []
    if not isinstance(rows, list):
        problems.append(f"rows is {show(rows)}, not a list")
        rows = []
    index: dict[tuple[str, str], dict] = {}
    for i, row in enumerate(rows):
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("workflow"), str)
            or not isinstance(row.get("case"), str)
        ):
            problems.append(f"row {i} does not name its workflow and case")
            continue
        key = (row["workflow"], row["case"])
        if key in index:
            problems.append(f"{key[0]}/{key[1]} appears more than once")
            continue
        index[key] = row
    if not isinstance(historical_rows, list):
        problems.append(f"the historical rows are {show(historical_rows)}, not a list")
        historical_rows = []
    historical = {(r.get("workflow"), r.get("case")): r for r in historical_rows if isinstance(r, dict)}
    expected = [(w, c["id"]) for c in cases for w in WORKFLOWS]
    extra = sorted(f"{w}/{c}" for w, c in set(index) - set(expected))
    if extra:
        problems.append(f"rows for pairs outside the inventory: {', '.join(extra)}")
    by_id = {c["id"]: c for c in cases}
    assessed = []
    for workflow, case_id in expected:
        row, past = index.get((workflow, case_id)), historical.get((workflow, case_id))
        if row is None:
            result = failure("no row: the pair did not run, or its result was lost")
        else:
            result = assess_row(row, past, by_id[case_id], case_platforms.get(case_id))
        assessed.append(
            {
                "workflow": workflow,
                "case": case_id,
                "verdict": row.get("verdict") if row else None,
                "exit_code": row.get("exit_code") if row else None,
                "literal_rule_outcome": row.get("outcome") if row else None,
                "historical_verdict": past.get("verdict") if past else None,
                "historical_outcome": past.get("outcome") if past else None,
                **result,
            }
        )
    usable = {k: r for k, r in index.items() if not row_problems(r)}
    set_checks = set_level(usable, cases)
    blocking = [f"{a['workflow']}/{a['case']}" for a in assessed if a["blocking"]]
    ok = not problems and not blocking and all(c["ok"] for c in set_checks.values())
    return {
        "ok": ok,
        "pairs_expected": len(expected),
        "pairs_present": sum(1 for k in expected if k in index),
        "classes": dict(Counter(a["class"] for a in assessed)),
        "blocking": blocking,
        "platform_differences": [
            {"pair": f"{a['workflow']}/{a['case']}", "reasons": a["reasons"]}
            for a in assessed
            if a["class"] == "platform-numerical-difference"
        ],
        "set_checks": set_checks,
        "problems": problems,
        "rows": assessed,
    }


def set_level(rows: dict, cases: list[dict]) -> dict:
    """The comparison's set-level properties, over well-formed rows only (an absent row fails them)."""
    w2_w3, faults, w1 = [], [], []
    for case in cases:
        c = case["id"]
        w2, w3 = rows.get(("W2", c)), rows.get(("W3", c))
        if w2 is None or w3 is None or statuses(w2) != statuses(w3):
            w2_w3.append(c)
        if case["kind"] == "fault":
            for workflow, row in (("W2", w2), ("W3", w3)):
                if (
                    row is None
                    or row["verdict"] != "rejected-before-execution"
                    or row["episodes_executed"] != 0
                    or any(row["checks"][t]["status"] != "fail" for t in case["targets"])
                ):
                    faults.append(f"{workflow}/{c}")
        row = rows.get(("W1", c))
        if (
            row is None
            or row["verdict"] != "unchecked"
            or row["exit_code"] != 4
            or set(statuses(row).values()) != {"unsupported"}
        ):
            w1.append(c)
    n_faults = sum(case["kind"] == "fault" for case in cases)
    return {
        "w2_w3_status_agreement": {
            "ok": not w2_w3,
            "cases": len(cases),
            "disagreeing_or_missing": w2_w3,
        },
        "faults_rejected_before_execution": {
            "ok": not faults,
            "faults": n_faults,
            "not_rejected_before_execution": faults,
        },
        "w1_unchecked": {"ok": not w1, "cases": len(cases), "not_unchecked": w1},
    }


if __name__ == "__main__":
    if sys.argv[1:] != ["--platform"]:
        raise SystemExit("usage: python assessment.py --platform")
    print(json.dumps(current_platform()))
