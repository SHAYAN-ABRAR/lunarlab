# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""The package validator reports every failure it meets, and nothing it cannot verify passes.

In an independent run (29 October 2026), every comparison program crashed on unavailable memory telemetry. The
validator then raised ``AttributeError`` on a row's ``checks=None`` and wrote no ``validation.json``. These
tests reproduce that run's output and the other ways a step can fail: absent, invalid or foreign output, an
exception inside a step, a reused output directory, and a broken historical bundle or checkpoint inventory.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FROZEN = "reports/neurocomputing-2026-10-27/workflow-comparison"
V2 = "reports/neurocomputing-final-validation-2026-11-01/comparison-v2"
RECEIVED = (
    ROOT / "reports/neurocomputing-final-validation-2026-11-01/received/independent-verification-2026-10-29"
)
LINUX = {
    "platform": "Linux-6.18.55-x86_64-with-glibc2.39",
    "python": "3.12.14",
    "packages": {
        "torch": "2.14.1+cpu",
        "numpy": "2.5.4",
        "Box2D": "2.3.10",
        "gymnasium": "1.4.0",
        "stable-baselines3": "2.9.0",
    },
}
WINDOWS = {
    "platform": "Windows-11-10.0.26300-SP0",
    "python": "3.12.13",
    "packages": {**LINUX["packages"], "torch": "2.14.1"},
}


@pytest.fixture(scope="module")
def v():
    spec = importlib.util.spec_from_file_location(
        "validate_review_package", ROOT / "tools/validate_review_package.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def work_tree(tmp_path: Path, runner: str, *, frozen_runner: bool = False) -> Path:
    """A working copy with the real inventory, historical results, fixture records and assessment, and a fake
    runner in place of the real one (so no policy runs)."""
    work = tmp_path / "work"
    for rel in ("protocol/fault_inventory.json", "results/summary.json"):
        (work / FROZEN / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / FROZEN / rel, work / FROZEN / rel)
    for case in (ROOT / FROZEN / "fixtures").iterdir():
        if case.is_dir():
            for name in ("case.json", "evaluation.json"):
                (work / FROZEN / "fixtures" / case.name).mkdir(parents=True, exist_ok=True)
                shutil.copy2(case / name, work / FROZEN / "fixtures" / case.name / name)
    (work / V2).mkdir(parents=True)
    shutil.copy2(ROOT / V2 / "assessment.py", work / V2 / "assessment.py")
    target = work / FROZEN / "run_comparison.py" if frozen_runner else work / V2 / "run_comparison_v2.py"
    target.write_text(runner, encoding="utf-8")
    return work


def fake_runner(summary_code: str) -> str:
    """A runner that writes OUT/summary.json from ``summary_code`` (which sees ``out``, ``run_id`` and ``rows``)."""
    return (
        "import json, sys\n"
        "from pathlib import Path\n"
        "out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)\n"
        "run_id = sys.argv[sys.argv.index('--run-id') + 1] if '--run-id' in sys.argv else None\n"
        f"rows = json.loads(Path({str(ROOT / FROZEN / 'results/summary.json')!r}).read_text(encoding='utf-8'))['rows']\n"
        + summary_code
        + "\n"
    )


def run_comparison(v, tmp_path, runner: str, *, platform=WINDOWS, unmodified=False) -> dict:
    work = work_tree(tmp_path, runner, frozen_runner=unmodified)
    out = tmp_path / "out"
    out.mkdir()
    return v.comparison(sys.executable, work, out, dict(os.environ), platform, unmodified)


def test_the_reviewers_crashed_run_is_42_named_failures_with_their_stderr(v, tmp_path):
    crashed = (RECEIVED / "validation/comparison/summary.json").read_text(encoding="utf-8")
    stderr = {
        w: (RECEIVED / f"validation/comparison/raw/{w}/C0-clean/stderr.txt").read_text(encoding="utf-8")
        for w in ("W1", "W2", "W3")
    }
    runner = (
        "import json, sys\nfrom pathlib import Path\n"
        "out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)\n"
        f"summary = {crashed!r}\nstderr = {stderr!r}\n"
        "(out / 'summary.json').write_text(summary, encoding='utf-8')\n"
        "for row in json.loads(summary)['rows']:\n"
        "    raw = out / 'raw' / row['workflow'] / row['case']; raw.mkdir(parents=True, exist_ok=True)\n"
        "    (raw / 'stderr.txt').write_text(stderr[row['workflow']], encoding='utf-8')\n"
    )
    result = run_comparison(v, tmp_path, runner, platform=LINUX, unmodified=True)
    assert result["ok"] is False and result["exit"] == 0
    assert len(result["blocking"]) == 42 and result["classes"] == {"failure": 42}
    first = result["blocking"][0]
    assert (first["workflow"], first["case"]) == ("W1", "C0-clean")
    assert "checks is null" in first["reasons"][0]
    assert "psutil.NoSuchProcess" in first["stderr_tail"]
    assert first["raw"] == "comparison-unmodified/raw/W1/C0-clean/"


def test_a_clean_follow_up_run_passes(v, tmp_path):
    runner = fake_runner(
        "(out / 'summary.json').write_text(json.dumps({'run_id': run_id, 'inputs': {'verified': True, 'problems': []},"
        " 'rows': rows, 'assessment': {'ok': True}}), encoding='utf-8')"
    )
    result = run_comparison(v, tmp_path, runner)
    assert result["ok"] is True, result["problems"]
    assert result["classes"] == {"exact-agreement": 42} and result["blocking"] == []
    assert all(c["ok"] for c in result["set_checks"].values())


@pytest.mark.parametrize(
    ("scenario", "summary_code", "expected"),
    [
        ("absent", "pass", "summary.json is absent"),
        (
            "invalid JSON",
            "(out / 'summary.json').write_text('{not json', encoding='utf-8')",
            "not valid JSON",
        ),
        ("not an object", "(out / 'summary.json').write_text('[1, 2]', encoding='utf-8')", "not an object"),
        (
            "another run's",
            "(out / 'summary.json').write_text(json.dumps({'run_id': 'an earlier run', 'inputs': {'verified': True},"
            " 'rows': rows, 'assessment': {'ok': True}}), encoding='utf-8')",
            "not this run's output",
        ),
        (
            "unverified inputs",
            "(out / 'summary.json').write_text(json.dumps({'run_id': run_id, 'inputs': {'verified': False, 'problems':"
            " ['missing fixtures/C0-clean/policy.zip']}, 'rows': [], 'assessment': {'ok': False}}), encoding='utf-8')",
            "inputs did not verify",
        ),
        (
            "no rows",
            "(out / 'summary.json').write_text(json.dumps({'run_id': run_id, 'inputs': {'verified': True},"
            " 'assessment': {'ok': False}}), encoding='utf-8')",
            "has no rows",
        ),
        (
            "a self-assessment that disagrees",
            "(out / 'summary.json').write_text(json.dumps({'run_id': run_id, 'inputs': {'verified': True},"
            " 'rows': [{**r, 'checks': None} if r['case'] == 'F03-protocol-mismatch' else r for r in rows],"
            " 'assessment': {'ok': True}}), encoding='utf-8')",
            "differs from this one",
        ),
    ],
)
def test_absent_invalid_or_foreign_output_never_passes(v, tmp_path, scenario, summary_code, expected):
    result = run_comparison(v, tmp_path, fake_runner(summary_code))
    assert result["ok"] is False
    assert any(expected in p for p in result["problems"]), result["problems"]


def test_existing_comparison_output_is_never_read(v, tmp_path):
    work = work_tree(tmp_path, fake_runner("pass"))
    out = tmp_path / "out"
    (out / "comparison").mkdir(parents=True)
    (out / "comparison" / "summary.json").write_text("{}", encoding="utf-8")
    result = v.comparison(sys.executable, work, out, dict(os.environ), WINDOWS, False)
    assert result["ok"] is False and "refusing to read old output" in result["problems"][0]


def test_a_reused_output_directory_is_refused(v, tmp_path, capsys):
    out = tmp_path / "out"
    out.mkdir()
    (out / "validation.json").write_text('{"ok": true}', encoding="utf-8")
    assert v.main([str(tmp_path / "package"), str(out)]) == 2
    assert json.loads((out / "validation.json").read_text(encoding="utf-8")) == {"ok": True}
    assert "not empty" in capsys.readouterr().err


def test_the_report_is_written_when_the_package_is_unusable(v, tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    (package / "SHA256SUMS").write_text("not a digest line\n", encoding="utf-8")
    out = tmp_path / "out"
    assert v.main([str(package), str(out)]) == 1
    report = json.loads((out / "validation.json").read_text(encoding="utf-8"))
    assert report["ok"] is False and report["completed"] is True
    assert {"checksums", "work_copy", "dependencies", "cartpole_records", "figures"} <= set(
        report["failed_steps"]
    )
    assert report["checksums"]["malformed_lines"] == 1
    assert report["dependencies"]["skipped"] == "the working copy could not be prepared"


def test_an_exception_inside_a_step_is_recorded_and_fails(v, tmp_path, monkeypatch):
    def broken(package):
        raise KeyError("rows")

    monkeypatch.setattr(v, "check_checksums", broken)
    out = tmp_path / "out"
    assert v.main([str(tmp_path / "package"), str(out)]) == 1
    report = json.loads((out / "validation.json").read_text(encoding="utf-8"))
    assert report["checksums"]["ok"] is False and report["checksums"]["error"] == "KeyError: 'rows'"
    assert "Traceback" in report["checksums"]["traceback"]


def test_an_exception_outside_any_step_is_recorded_and_fails(v, tmp_path, monkeypatch):
    def broken(*args):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(v, "validate", broken)
    out = tmp_path / "out"
    assert v.main([str(tmp_path / "package"), str(out)]) == 1
    report = json.loads((out / "validation.json").read_text(encoding="utf-8"))
    assert report["ok"] is False and report["completed"] is False
    assert report["unexpected_error"]["error"] == "RuntimeError: unexpected"


# --- the historical bundle and the checkpoint inventory --------------------------------------------------


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bundle_package(
    tmp_path: Path, v, members: dict[str, bytes], listed: dict[str, bytes], committed_extra: dict
):
    """A package holding a bundle ZIP, and a working copy holding its committed digest list."""
    sums = "".join(f"{digest(data)} *{name}\n" for name, data in listed.items()).encode()
    package, work = tmp_path / "package", tmp_path / "work"
    (package / "lunarlander-study").mkdir(parents=True)
    with zipfile.ZipFile(package / v.BUNDLE, "w") as z:
        z.writestr("study-artifacts/SHA256SUMS", sums)
        for name, data in members.items():
            z.writestr(f"study-artifacts/{name}", data)
    record = work / v.BUNDLE_RECORD
    record.parent.mkdir(parents=True)
    record.write_bytes(sums)
    for name, data in committed_extra.items():
        (record.parent / name).write_bytes(data)
    return package, work


def test_an_intact_bundle_verifies_with_its_committed_extras(v, tmp_path):
    files = {"a/artifact.json": b"{}", "a/reward_model/model.npz": b"weights"}
    package, work = bundle_package(
        tmp_path, v, {**files, "DEPENDENCIES.md": b"# deps"}, files, {"DEPENDENCIES.md": b"# deps"}
    )
    result = v.extract_bundle(package, work, tmp_path / "out")
    assert result["ok"] and result["members_checked"] == 2
    assert result["policy_packages"] == 1 and result["packages_with_reward_model"] == 1


@pytest.mark.parametrize("fault", ["altered member", "missing member", "unlisted member", "different list"])
def test_a_damaged_bundle_is_named(v, tmp_path, fault):
    files = {"a/artifact.json": b"{}", "a/evaluation.json": b"[]"}
    members, extra = dict(files), {}
    if fault == "altered member":
        members["a/evaluation.json"] = b"[1]"
    elif fault == "missing member":
        del members["a/evaluation.json"]
    elif fault == "unlisted member":
        members["NOTES.md"] = b"not recorded anywhere"
    package, work = bundle_package(tmp_path, v, members, files, extra)
    if fault == "different list":
        (work / v.BUNDLE_RECORD).write_bytes(b"0" * 64 + b" *a/artifact.json\n")
    result = v.extract_bundle(package, work, tmp_path / "out")
    assert result["ok"] is False and result["problems"]


def test_a_bundle_with_unsafe_member_names_is_not_extracted(v, tmp_path):
    package, work = bundle_package(tmp_path, v, {}, {}, {})
    with zipfile.ZipFile(package / v.BUNDLE, "a") as z:
        z.writestr("../escape.txt", b"x")
    result = v.extract_bundle(package, work, tmp_path / "out")
    assert result["ok"] is False and "unsafe" in result["problems"][0]
    assert not (tmp_path / "escape.txt").exists()


def checkpoint_tree(tmp_path: Path, v) -> tuple[Path, Path, dict[str, bytes]]:
    blobs = {
        "checkpoints/step-1.zip": b"one",
        "checkpoints/step-2.zip": b"two",
        "frozen/sel.zip": b"sel",
        "frozen/fin.zip": b"fin",
    }
    tree, package = tmp_path / "tree", tmp_path / "package"
    run = tree / v.STUDY / "records/main/runs/r1"
    run.mkdir(parents=True)
    record = {
        "checkpoints": [
            {"file": f, "sha256": digest(blobs[f])}
            for f in ("checkpoints/step-1.zip", "checkpoints/step-2.zip")
        ],
        "frozen": {
            "selected": {"file": "frozen/sel.zip", "sha256": digest(b"sel")},
            "final": {"file": "frozen/fin.zip", "sha256": digest(b"fin")},
        },
    }
    (run / "run.json").write_text(json.dumps(record), encoding="utf-8")
    out = package / "cartpole-study-output/main/runs/r1"
    for name in ("frozen/sel.zip", "frozen/fin.zip"):
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_bytes(blobs[name])
    return tree, package, blobs


def write_inventory(package: Path, v, entries: list[dict]) -> None:
    (package / v.INTERMEDIATE).write_text(json.dumps({"not_distributed": entries}), encoding="utf-8")


def test_every_named_checkpoint_is_distributed_or_inventoried(v, tmp_path):
    tree, package, blobs = checkpoint_tree(tmp_path, v)
    write_inventory(
        package,
        v,
        [
            {"path": f"main/runs/r1/{f}", "sha256": digest(blobs[f])}
            for f in ("checkpoints/step-1.zip", "checkpoints/step-2.zip")
        ],
    )
    deps = v.Dependencies()
    v.check_checkpoint_inventory(tree, package, deps)
    assert deps.problems == [] and deps.counts == {"named checkpoint": 4}


@pytest.mark.parametrize(
    "fault", ["absent from the inventory", "wrong digest", "not named", "no inventory", "altered frozen"]
)
def test_an_incomplete_or_wrong_checkpoint_inventory_is_named(v, tmp_path, fault):
    tree, package, blobs = checkpoint_tree(tmp_path, v)
    entries = [
        {"path": f"main/runs/r1/{f}", "sha256": digest(blobs[f])}
        for f in ("checkpoints/step-1.zip", "checkpoints/step-2.zip")
    ]
    if fault == "absent from the inventory":
        entries = entries[:1]
    elif fault == "wrong digest":
        entries[1]["sha256"] = "0" * 64
    elif fault == "not named":
        entries.append({"path": "main/runs/r1/checkpoints/step-9.zip", "sha256": "1" * 64})
    elif fault == "altered frozen":
        (package / "cartpole-study-output/main/runs/r1/frozen/sel.zip").write_bytes(b"other")
    if fault != "no inventory":
        write_inventory(package, v, entries)
    deps = v.Dependencies()
    v.check_checkpoint_inventory(tree, package, deps)
    assert len(deps.problems) == 1, deps.problems
