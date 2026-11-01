# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""The follow-up (version 2) comparison: telemetry, crash handling and the platform-aware assessment.

The prespecified comparison's programs read process memory with psutil when they finish. In a sandbox that does
not expose the process to psutil this raised ``NoSuchProcess``, so no program printed its result. The package
validator then crashed on the resulting ``checks=None`` rows. On Linux the clean control replayed as a
permitted numerical difference, and the frozen runner's literal comparison labelled that a false alarm.

These tests pin down three things. The version-2 programs differ from the hashed originals only in telemetry,
which is null with a reason when unavailable and never zero. Crashed or malformed results are recorded and
fail. The assessment separates exact agreement, a verified cross-platform difference of the clean control, and
genuine failures, which stay blocking.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import psutil
import pytest

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "reports/neurocomputing-2026-10-27/workflow-comparison"
V2 = ROOT / "reports/neurocomputing-final-validation-2026-11-01/comparison-v2"
RECEIVED = (
    ROOT / "reports/neurocomputing-final-validation-2026-11-01/received/independent-verification-2026-10-29"
)
PROGRAMS = ("w1_sb3_conventional", "w2_sb3_reference", "w3_lunarlab")
WINDOWS = {
    "platform": "Windows-11-10.0.26300-SP0",
    "python": "3.12.13",
    "packages": {
        "torch": "2.14.1",
        "numpy": "2.5.4",
        "Box2D": "2.3.10",
        "gymnasium": "1.4.0",
        "stable-baselines3": "2.9.0",
    },
}
# The reviewer's Linux sandbox, as its W1 stderr reports it (the CPU wheel's version carries "+cpu").
LINUX = {
    "platform": "Linux-6.18.55-x86_64-with-glibc2.39",
    "python": "3.12.14",
    "packages": {**WINDOWS["packages"], "torch": "2.14.1+cpu"},
}


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = load("comparison_assessment", V2 / "assessment.py")


@pytest.fixture(scope="module")
def runner():
    return load("run_comparison_v2", V2 / "run_comparison_v2.py")


@pytest.fixture(scope="module")
def frozen_classify():
    return load("run_comparison_v1", FROZEN / "run_comparison.py").classify


@pytest.fixture(scope="module")
def inventory():
    return json.loads((FROZEN / "protocol/fault_inventory.json").read_text(encoding="utf-8"))["cases"]


@pytest.fixture(scope="module")
def historical():
    return json.loads((FROZEN / "results/summary.json").read_text(encoding="utf-8"))["rows"]


# --- the version-2 programs -------------------------------------------------------------------------------


def test_the_hashed_originals_are_unchanged():
    recorded = load("derive", V2 / "derive_v2_programs.py").recorded_digests()
    for name in (*(f"workflows/{p}.py" for p in PROGRAMS), "run_comparison.py", "protocol/PROTOCOL.md"):
        assert hashlib.sha256((FROZEN / name).read_bytes()).hexdigest() == recorded[name], name


def test_the_v2_programs_and_their_diff_are_exactly_the_documented_derivation():
    derive = load("derive", V2 / "derive_v2_programs.py")
    programs, diff = derive.derive()
    for name, text in programs.items():
        assert (V2 / "workflows" / name).read_bytes() == text.encode("utf-8"), name
    assert (V2 / "CHANGES.diff").read_bytes() == diff.encode("utf-8")


@pytest.mark.parametrize("program", PROGRAMS)
def test_only_the_telemetry_and_main_differ_from_the_original(program):
    """Every other top-level definition (constants, checks, replay, statistics) is the original's, node for node."""
    original = ast.parse((FROZEN / "workflows" / f"{program}.py").read_text(encoding="utf-8"))
    v2 = ast.parse((V2 / "workflows" / f"{program}_v2.py").read_text(encoding="utf-8"))

    def parts(tree):
        out = {}
        for i, node in enumerate(tree.body[1:]):  # [0] is the docstring
            name = getattr(node, "name", None) or f"#{i}"
            out[name] = ast.dump(node)
        return out

    a, b = parts(original), parts(v2)
    assert a.keys() == b.keys()
    assert [k for k in a if a[k] != b[k]] == ["peak_rss", "main"]


@pytest.fixture(scope="module", params=PROGRAMS)
def v2_program(request):
    return load(f"{request.param}_v2", V2 / "workflows" / f"{request.param}_v2.py")


class _Info:
    def __init__(self, **fields):
        self.__dict__.update(fields)


def _process(raises=None, **fields):
    class Process:
        def __init__(self, pid=None):
            if raises is not None:
                raise raises

        def memory_info(self):
            return _Info(**fields)

    return Process


@pytest.mark.parametrize(
    ("error", "name"),
    [
        (psutil.NoSuchProcess(547, msg="process PID not found"), "NoSuchProcess"),
        (psutil.AccessDenied(547), "AccessDenied"),
    ],
)
def test_unavailable_memory_is_null_with_its_reason_never_zero(v2_program, monkeypatch, error, name):
    monkeypatch.setattr(v2_program.psutil, "Process", _process(raises=error))
    value, status = v2_program.peak_rss()
    assert value is None
    assert status.startswith(f"unavailable: {name}")


def test_available_memory_is_the_value_the_original_reports(v2_program, monkeypatch):
    monkeypatch.setattr(v2_program.psutil, "Process", _process(peak_wset=123_456_789, rss=1_000))
    assert v2_program.peak_rss() == (123_456_789, "measured: peak_wset")
    monkeypatch.setattr(v2_program.psutil, "Process", _process(rss=98_765_432))
    assert v2_program.peak_rss() == (98_765_432, "measured: rss")


def test_a_memory_record_without_either_field_is_unavailable_not_zero(v2_program, monkeypatch):
    monkeypatch.setattr(v2_program.psutil, "Process", _process())
    assert v2_program.peak_rss() == (None, "unavailable: psutil reported neither peak_wset nor rss")


def test_unrelated_errors_are_not_swallowed(v2_program, monkeypatch):
    monkeypatch.setattr(
        v2_program.psutil, "Process", _process(raises=RuntimeError("not a telemetry problem"))
    )
    with pytest.raises(RuntimeError, match="not a telemetry problem"):
        v2_program.peak_rss()


def test_the_real_telemetry_works_here(v2_program):
    try:
        psutil.Process().memory_info()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pytest.skip("this sandbox does not expose the process to psutil")
    value, status = v2_program.peak_rss()
    assert isinstance(value, int) and value > 0 and status.startswith("measured: ")


# --- the runner: inputs, crashes and malformed output ------------------------------------------------------


FAKES = {
    "crashes": "raise SystemExit('psutil.NoSuchProcess: process PID not found (pid=547)')",
    "prints-nothing": "pass",
    "invalid-json": "print('{not json')",
    "a-list": "print('[1, 2]')",
    "checks-null": (
        "import json; print(json.dumps({'workflow': 'W2', 'case': 'C0-clean', 'checks': None, "
        "'verdict': 'accepted', 'episodes_executed': 100}))"
    ),
    "wrong-case": (
        "import json; print(json.dumps({'workflow': 'W2', 'case': 'C1-numerical-difference', 'checks': {}, "
        "'verdict': 'accepted', 'episodes_executed': 100}))"
    ),
    "string-exit-status": (
        "import json, sys; c = {f'S{i}': {'status': 'pass', 'detail': ''} for i in range(1, 11)}; "
        "print(json.dumps({'workflow': 'W2', 'case': 'C0-clean', 'checks': c, 'verdict': 'accepted', "
        "'episodes_executed': '100', 'peak_rss_bytes_self': 0, 'peak_rss_status': 'measured: rss'}))"
    ),
}


@pytest.fixture(scope="module")
def clean_case(inventory):
    return next(c for c in inventory if c["id"] == "C0-clean")


@pytest.mark.parametrize("fake", sorted(FAKES))
def test_a_crashed_or_malformed_result_is_recorded_and_never_passes(
    runner, frozen_classify, clean_case, tmp_path, fake
):
    program = tmp_path / f"{fake}.py"
    program.write_text(FAKES[fake] + "\n", encoding="utf-8")
    raw = tmp_path / "out" / "raw" / "W2" / "C0-clean"
    run = runner.run_pair(program, tmp_path, raw, dict(os.environ))
    assert (
        (raw / "stdout.txt").is_file()
        and (raw / "stderr.txt").is_file()
        and (raw / "exit_code.txt").is_file()
    )
    row = runner.make_row(clean_case, "W2", run, frozen_classify)
    assert row["outcome"] in ("crashed", "malformed")
    assert row["result_problems"] and row["note"]
    assessed = A.assess_row(row, None, clean_case, None)
    assert assessed["blocking"] and assessed["class"] == "failure"
    if fake == "crashes":
        assert "NoSuchProcess" in (raw / "stderr.txt").read_text(encoding="utf-8")
        assert "NoSuchProcess" in row["stderr_tail"]
    if fake == "string-exit-status":
        joined = " ".join(row["result_problems"])
        assert "episodes_executed is str" in joined and "peak_rss_bytes_self is int 0" in joined


def test_a_hung_program_times_out_and_is_recorded(runner, frozen_classify, clean_case, tmp_path):
    program = tmp_path / "hangs.py"
    program.write_text("import time\nprint('started', flush=True)\ntime.sleep(60)\n", encoding="utf-8")
    raw = tmp_path / "raw"
    run = runner.run_pair(program, tmp_path, raw, dict(os.environ), timeout=2)
    assert run["exit_code"] is None and run["failure"].startswith("timed out")
    assert (raw / "exit_code.txt").read_text(encoding="utf-8").startswith("none: timed out")
    assert runner.make_row(clean_case, "W3", run, frozen_classify)["outcome"] == "crashed"


def test_the_runner_refuses_a_directory_with_earlier_output(runner, tmp_path, capsys):
    out = tmp_path / "out"
    (out / "raw").mkdir(parents=True)
    (out / "summary.json").write_text("{}", encoding="utf-8")
    assert runner.main([str(FROZEN / "fixtures"), str(out)]) == 2
    assert (out / "summary.json").read_text(encoding="utf-8") == "{}"
    assert "not empty" in capsys.readouterr().err


def test_altered_inputs_stop_the_run_before_any_program_starts(runner, tmp_path):
    fixtures = tmp_path / "fixtures"
    shutil.copytree(FROZEN / "fixtures", fixtures, ignore=shutil.ignore_patterns("policy.zip"))
    evaluation = fixtures / "C0-clean" / "evaluation.json"
    evaluation.write_bytes(evaluation.read_bytes() + b"\n")
    out = tmp_path / "out"
    assert runner.main([str(fixtures), str(out), "--run-id", "test"]) == 2
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["run_id"] == "test" and summary["inputs"]["verified"] is False and summary["rows"] == []
    assert (
        "fixtures/C0-clean/evaluation.json does not have its recorded digest" in summary["inputs"]["problems"]
    )
    assert not (out / "raw").exists()


def test_the_committed_inputs_verify_apart_from_policies_absent_from_this_checkout(runner):
    problems = runner.verify_inputs(FROZEN / "fixtures")
    absent = [p for p in problems if p.startswith("missing fixtures/") and p.endswith("/policy.zip")]
    for p in absent:  # Git does not hold the fixture policies; they are in the packages
        assert not (FROZEN / p.removeprefix("missing ")).exists()
    assert [p for p in problems if p not in absent] == []


# --- the assessment -----------------------------------------------------------------------------------------


def platforms(current: dict, *, consistent: bool = True, recorded: dict | None = None) -> dict:
    out = {}
    for case_dir in sorted(d for d in (FROZEN / "fixtures").iterdir() if d.is_dir()):
        case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        out[case_dir.name] = {
            "consistent": consistent,
            "comparison": A.compare_platform(recorded or case["recorded_platform"], current),
        }
    return out


def as_numerical_difference(rows: list[dict], pairs=(("W2", "C0-clean"), ("W3", "C0-clean"))) -> list[dict]:
    """The historical rows, with the clean control's replay turned into a permitted numerical difference."""
    rows = copy.deepcopy(rows)
    for row in rows:
        if (row["workflow"], row["case"]) in pairs:
            row.update(verdict="accepted-numerical-difference", exit_code=3, outcome="false alarm")
            row["checks"]["S10"] = {
                "status": "pass",
                "detail": "numerical-difference: 2 of 100 episodes differ",
            }
    return rows


def classes(result: dict) -> dict:
    return {
        f"{r['workflow']}/{r['case']}": r["class"] for r in result["rows"] if r["class"] != "exact-agreement"
    }


def test_the_historical_results_agree_with_themselves_exactly(historical, inventory):
    result = A.assess(historical, historical, inventory, platforms(WINDOWS))
    assert result["ok"] and result["classes"] == {"exact-agreement": 42} and result["pairs_present"] == 42
    assert all(c["ok"] for c in result["set_checks"].values())


def test_the_clean_control_may_differ_numerically_on_a_verified_other_platform(historical, inventory):
    result = A.assess(as_numerical_difference(historical), historical, inventory, platforms(LINUX))
    assert result["ok"]
    assert classes(result) == {
        "W2/C0-clean": "platform-numerical-difference",
        "W3/C0-clean": "platform-numerical-difference",
    }
    shown = {d["pair"]: d["reasons"][0] for d in result["platform_differences"]}
    assert "os (Windows recorded, Linux here)" in shown["W3/C0-clean"]
    row = next(r for r in result["rows"] if (r["workflow"], r["case"]) == ("W3", "C0-clean"))
    assert row["literal_rule_outcome"] == "false alarm" and row["verdict"] == "accepted-numerical-difference"
    assert not row["blocking"]


def test_a_difference_on_the_recording_platform_stays_a_failure(historical, inventory):
    result = A.assess(as_numerical_difference(historical), historical, inventory, platforms(WINDOWS))
    assert not result["ok"]
    assert result["blocking"] == ["W2/C0-clean", "W3/C0-clean"]
    reasons = next(r for r in result["rows"] if r["case"] == "C0-clean" and r["workflow"] == "W2")["reasons"]
    assert any("on the recording platform a replay difference is unexpected" in r for r in reasons)


def test_an_unknown_or_inconsistent_recording_platform_is_not_evidence_of_a_difference(historical, inventory):
    rows = as_numerical_difference(historical)
    unknown = A.assess(rows, historical, inventory, platforms(LINUX, recorded={"platform": None}))
    assert unknown["blocking"] == ["W2/C0-clean", "W3/C0-clean"]
    inconsistent = A.assess(rows, historical, inventory, platforms(LINUX, consistent=False))
    assert inconsistent["blocking"] == ["W2/C0-clean", "W3/C0-clean"]


@pytest.mark.parametrize(
    "change",
    [
        "a check fails",
        "aggregate disagreement",
        "real rejection after execution",
        "fewer episodes",
        "W1 claims a replay",
    ],
)
def test_genuine_control_failures_stay_blocking_on_another_platform(historical, inventory, change):
    rows = as_numerical_difference(historical)
    target = ("W1", "C0-clean") if change == "W1 claims a replay" else ("W3", "C0-clean")
    row = next(r for r in rows if (r["workflow"], r["case"]) == target)
    if change == "a check fails":
        row["checks"]["S9"] = {"status": "fail", "detail": "outcome schema or recorded labels differ"}
    elif change == "aggregate disagreement":
        row.update(verdict="rejected-after-execution", exit_code=1)
        row["checks"]["S10"] = {
            "status": "fail",
            "detail": "aggregate-disagreement: significant paired differences",
        }
    elif change == "real rejection after execution":
        row.update(verdict="rejected-after-execution", exit_code=1)
        row["checks"]["S10"] = {"status": "fail", "detail": "unexpected-difference: 2 of 100 episodes differ"}
    elif change == "fewer episodes":
        row["episodes_executed"] = 99
    else:
        row.update(verdict="accepted-numerical-difference", exit_code=3)
    result = A.assess(rows, historical, inventory, platforms(LINUX))
    assert not result["ok"] and f"{target[0]}/{target[1]}" in result["blocking"]


@pytest.mark.parametrize(
    ("case", "change"),
    [
        ("F01-checkpoint-swapped", "accepted"),
        ("F06-coercible-seed", "late"),
        ("F10-inconsistent-totals", "numerical difference"),
    ],
)
def test_a_changed_fault_result_is_blocking_on_any_platform(historical, inventory, case, change):
    rows = copy.deepcopy(historical)
    row = next(r for r in rows if (r["workflow"], r["case"]) == ("W2", case))
    passing = {f"S{i}": {"status": "pass", "detail": ""} for i in range(1, 11)}
    if change == "accepted":
        row.update(verdict="accepted", exit_code=0, episodes_executed=100, checks=passing)
    elif change == "late":
        row.update(verdict="rejected-after-execution", episodes_executed=100)
    else:
        row.update(
            verdict="accepted-numerical-difference", exit_code=3, episodes_executed=100, checks=passing
        )
    result = A.assess(rows, historical, inventory, platforms(LINUX))
    assert not result["ok"] and f"W2/{case}" in result["blocking"]
    assert result["set_checks"]["faults_rejected_before_execution"]["not_rejected_before_execution"] == [
        f"W2/{case}"
    ]
    assert not result["set_checks"]["w2_w3_status_agreement"]["ok"] or change == "late"


def test_the_clean_control_designed_difference_on_its_own_recording_platform_fails(historical, inventory):
    """C1 records a Linux platform; replayed there with the same libraries, its difference is unexpected."""
    rows = copy.deepcopy(historical)
    for row in rows:
        if row["case"] == "C1-numerical-difference" and row["workflow"] in ("W2", "W3"):
            row.update(verdict="rejected-after-execution", exit_code=1, outcome="false alarm")
            row["checks"]["S10"] = {
                "status": "fail",
                "detail": "unexpected-difference: 2 of 100 episodes differ",
            }
    c1_linux = json.loads((FROZEN / "fixtures/C1-numerical-difference/case.json").read_text(encoding="utf-8"))
    result = A.assess(rows, historical, inventory, platforms(c1_linux["recorded_platform"]))
    assert result["blocking"] == ["W2/C1-numerical-difference", "W3/C1-numerical-difference"]


@pytest.mark.parametrize(
    "malformed",
    [
        {"checks": None, "verdict": None, "exit_code": 1, "episodes_executed": None},
        {"checks": []},
        {"exit_code": "0"},
        {"episodes_executed": True},
        {"verdict": "accepted-ish"},
        {"exit_code": 3},
        {"checks": {"S1": {"status": "pass"}}},
        {"checks": {f"S{i}": {"status": 1} for i in range(1, 11)}},
        {"telemetry": {"peak_rss_bytes_self": 0, "peak_rss_status": "measured: rss"}},
        {"telemetry": {"peak_rss_bytes_self": None, "peak_rss_status": "measured: rss"}},
        {"telemetry": "unavailable"},
    ],
)
def test_wrongly_typed_or_inconsistent_fields_are_failures_not_crashes(historical, inventory, malformed):
    rows = copy.deepcopy(historical)
    rows[1].update(malformed)  # W2/C0-clean
    result = A.assess(rows, historical, inventory, platforms(WINDOWS))
    assert not result["ok"] and result["blocking"][0] == "W2/C0-clean"
    assert result["rows"][1]["reasons"][0].startswith("the result cannot be assessed")


def test_missing_duplicated_and_foreign_rows_fail(historical, inventory):
    rows = copy.deepcopy(historical)
    missing = A.assess(rows[1:], historical, inventory, platforms(WINDOWS))
    assert missing["pairs_present"] == 41 and missing["blocking"] == ["W1/C0-clean"]
    dup = A.assess([*rows, rows[0]], historical, inventory, platforms(WINDOWS))
    assert "W1/C0-clean appears more than once" in dup["problems"] and not dup["ok"]
    foreign = A.assess([*rows, {**rows[0], "case": "C9"}], historical, inventory, platforms(WINDOWS))
    assert any("outside the inventory" in p for p in foreign["problems"]) and not foreign["ok"]
    assert not A.assess({"rows": rows}, historical, inventory, platforms(WINDOWS))["ok"]
    assert not A.assess(rows, None, inventory, platforms(WINDOWS))["ok"]


def test_a_w2_w3_status_disagreement_fails_the_set(historical, inventory):
    rows = copy.deepcopy(historical)
    rows[2]["checks"]["S8"] = {"status": "not-run", "detail": ""}  # W3/C0-clean
    result = A.assess(rows, historical, inventory, platforms(WINDOWS))
    assert result["set_checks"]["w2_w3_status_agreement"]["disagreeing_or_missing"] == ["C0-clean"]
    assert not result["ok"]


# --- the reviewer's actual outputs (received 1 November 2026) ----------------------------------------------


def test_the_reviewers_unmodified_run_is_42_named_failures_not_a_crash(historical, inventory):
    crashed = json.loads((RECEIVED / "validation/comparison/summary.json").read_text(encoding="utf-8"))[
        "rows"
    ]
    result = A.assess(crashed, historical, inventory, platforms(LINUX))
    assert not result["ok"] and len(result["blocking"]) == 42 and result["classes"] == {"failure": 42}
    assert all("checks is null" in r["reasons"][0] for r in result["rows"])


def test_the_reviewers_diagnostic_linux_run_is_classified_and_kept_visible(historical, inventory):
    """Telemetry made optional in a reviewer's copy: all 42 completed and the two C0 rows changed label."""
    diagnostic = json.loads(
        (RECEIVED / "comparison-diagnostic/results/summary.json").read_text(encoding="utf-8")
    )
    result = A.assess(diagnostic["rows"], historical, inventory, platforms(LINUX))
    assert result["ok"] and result["pairs_present"] == 42
    assert classes(result) == {
        "W2/C0-clean": "platform-numerical-difference",
        "W3/C0-clean": "platform-numerical-difference",
    }
    literal = {(r["workflow"], r["case"]): r["literal_rule_outcome"] for r in result["rows"]}
    assert (
        literal[("W2", "C0-clean")] == literal[("W3", "C0-clean")] == "false alarm"
    )  # the raw label is kept
    assert result["set_checks"]["faults_rejected_before_execution"]["ok"]
    assert result["set_checks"]["w2_w3_status_agreement"]["ok"] and result["set_checks"]["w1_unchecked"]["ok"]
    same_platform = A.assess(diagnostic["rows"], historical, inventory, platforms(WINDOWS))
    assert same_platform["blocking"] == ["W2/C0-clean", "W3/C0-clean"]


def test_the_platform_record_reads_this_interpreter():
    record = A.current_platform()
    assert record["platform"] and record["python"] == ".".join(map(str, sys.version_info[:3]))
    assert record["packages"]["stable-baselines3"]
