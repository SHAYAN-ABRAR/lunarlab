# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Derived outcome reports never modify the evaluations they read; the planning benchmark measures real throughput."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from lunarlab.outcomes import LANDING_CATEGORIES
from lunarlab.reclassify import reclassification_report, reclassify_file, write_report
from lunarlab.storage import RunPaths, read_json, sha256_file

ROOT = Path(__file__).resolve().parent.parent
V1_EVALUATION = ROOT / "examples" / "artifacts" / "ppo-baseline-s0" / "evaluation.json"


def _install(run_id: str, source: Path) -> Path:
    """Place a copy of an evaluation file where a run's evaluations live (isolated home)."""
    folder = RunPaths(run_id).evaluations
    folder.mkdir(parents=True, exist_ok=True)
    dst = folder / source.name
    shutil.copyfile(source, dst)
    return dst


def test_a_version_1_evaluation_is_reclassified_without_being_modified(tmp_path):
    path = _install("legacy-run", V1_EVALUATION)
    before = sha256_file(path)
    rec = reclassify_file(path)
    assert sha256_file(path) == before == rec["source_sha256"]
    assert rec["source_classifier_version"] == 1 and rec["n_episodes"] == 100
    assert sum(rec["after"][f"{c}_rate"] for c in LANDING_CATEGORIES) == pytest.approx(1.0)
    assert rec["after"]["strict_pad_landing_rate"] == pytest.approx(rec["before"]["pad_landing_rate"])
    assert rec["relabelled_episodes"] == []  # as in the published re-examination

    report = reclassification_report(["legacy-run"])
    assert report["summary"]["evaluation_files"] == 1 and report["summary"]["episodes"] == 100
    files = write_report(report, tmp_path / "out")
    assert [f.name for f in files] == ["outcome_reclassification_v2.json", "outcome_reclassification_v2.md"]
    assert "unchanged" in files[1].read_text(encoding="utf-8")
    assert sha256_file(path) == before


def test_only_version_1_evaluations_are_reclassified(tmp_path):
    record = read_json(V1_EVALUATION)
    record["aggregate"]["outcome_classifier_version"] = 2
    v2 = tmp_path / "v2.json"
    v2.write_text(json.dumps(record), encoding="utf-8")
    assert reclassify_file(v2) is None
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"kind": "not an evaluation"}), encoding="utf-8")
    assert reclassify_file(other) is None
    broken = read_json(V1_EVALUATION)
    del broken["episodes"][0]["legs_within_pad"]  # a field classifier v1 stored and v2 needs
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(broken), encoding="utf-8")
    out = reclassify_file(bad)
    assert out is not None and "error" in out


def test_reclassify_outcomes_command_writes_only_to_its_output_folder(tmp_path):
    from lunarlab.cli import main

    path = _install("legacy-cli", V1_EVALUATION)
    before = sha256_file(path)
    assert main(["reclassify-outcomes", "--run-ids", "legacy-cli", "--out", str(tmp_path / "report")]) == 0
    assert (tmp_path / "report" / "outcome_reclassification_v2.json").exists()
    assert sha256_file(path) == before


@pytest.mark.slow
def test_planning_benchmark_measures_environment_and_ppo_throughput():
    from lunarlab.benchmark import run_benchmark
    from lunarlab.storage import data_dir

    result = run_benchmark(n_envs_list=(1,), vec_kinds=("dummy",), env_seconds=0.2, echo=lambda _m: None)
    (row,) = result["rows"]
    assert row["env_tps"] > 0 and row["ppo_tps"] > 0
    assert read_json(data_dir() / "benchmark.json")["rows"] == result["rows"]
