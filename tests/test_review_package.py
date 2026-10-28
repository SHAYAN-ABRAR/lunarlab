# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""The review-package validator checks scientific dependencies, not only the checksums of present files.

A checksum manifest passed while the CartPole run records were missing from every distribution built from Git
(an unanchored ``runs/`` ignore rule had kept them out). The dependency check must name such a gap.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = "reports/neurocomputing-2026-10-27/cartpole-study"


def _validator():
    spec = importlib.util.spec_from_file_location(
        "validate_review_package", ROOT / "tools" / "validate_review_package.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _study_tree(tmp_path: Path) -> Path:
    tree = tmp_path / "tree"
    shutil.copytree(ROOT / STUDY, tree / STUDY, ignore=shutil.ignore_patterns("checkpoints", "__pycache__"))
    return tree


def test_the_committed_study_records_satisfy_every_recorded_dependency(tmp_path):
    v = _validator()
    deps = v.Dependencies()
    v.check_study_records(_study_tree(tmp_path), deps)
    assert deps.problems == []
    assert deps.counts == {"study index": 72, "analysis input": 45 + 9}  # 18 runs x 4 files; 3 inputs per run


def test_a_missing_or_altered_run_record_is_named(tmp_path):
    v = _validator()
    tree = _study_tree(tmp_path)
    (tree / STUDY / "records/main/runs/original-s52/run.json").unlink()
    altered = tree / STUDY / "records/pilot/runs/failure-bonus-s90/test-final.json"
    altered.write_bytes(altered.read_bytes() + b"\n")
    deps = v.Dependencies()
    v.check_study_records(tree, deps)
    assert f"study index: missing {STUDY}/records/main/runs/original-s52/run.json" in deps.problems
    assert f"analysis input: missing {STUDY}/records/main/runs/original-s52/run.json" in deps.problems
    assert any(
        "failure-bonus-s90/test-final.json does not have its recorded digest" in p for p in deps.problems
    )
