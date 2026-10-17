# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Provenance: release vs draft demo exports, recorded revisions, and file digests."""

from __future__ import annotations

import hashlib
import json

import pytest

from lunarlab.rewards import preset


def test_dirty_paths_ignores_the_export_directory_only():
    from lunarlab.demo import dirty_paths

    porcelain = " M lunarlab/compare.py\n?? demo/api/runs.json\n M demo/api/demo.json\nR  a.py -> b.py\n"
    assert dirty_paths(porcelain, "demo/api") == ["lunarlab/compare.py", "b.py"]
    assert dirty_paths(porcelain, None) == [
        "lunarlab/compare.py",
        "demo/api/runs.json",
        "demo/api/demo.json",
        "b.py",
    ]
    assert dirty_paths("?? demo/apiary.txt\n", "demo/api") == ["demo/apiary.txt"]  # a prefix is not a folder


@pytest.mark.slow
def test_release_exports_need_a_clean_source_and_record_full_provenance(tmp_path, monkeypatch):
    import lunarlab.demo as demo
    from lunarlab.evaluation import evaluate_run
    from lunarlab.experiments import create_experiment
    from lunarlab.training import EXIT_COMPLETED, train

    exp = create_experiment(name="prov", rewards=[preset("baseline")], seeds=[0], profile="smoke")
    (rid,) = exp["run_ids"]
    assert train(rid) == EXIT_COMPLETED
    evaluate_run(rid, "validation")
    from lunarlab.recording import record_run

    record_run(rid, episode_seed=20_000, checkpoint="final")  # a video is exported (and hashed) too

    dirty = {"available": True, "revision": "a" * 40, "dirty": True, "changed_paths": 3}
    monkeypatch.setattr(demo, "source_state", lambda exclude=None: dirty)
    with pytest.raises(demo.DemoExportError, match="--draft"):
        demo.export_demo(tmp_path / "rel", experiment_ids=[exp["experiment_id"]], echo=lambda *_: None)
    draft = demo.export_demo(
        tmp_path / "draft", experiment_ids=[exp["experiment_id"]], echo=lambda *_: None, draft=True
    )
    assert (
        draft["kind"] == "draft" and draft["uncommitted_changes"] is True and not draft["export_source_clean"]
    )

    clean = {"available": True, "revision": "b" * 40, "dirty": False, "changed_paths": 0}
    monkeypatch.setattr(demo, "source_state", lambda exclude=None: clean)
    out = tmp_path / "release"
    m = demo.export_demo(out, experiment_ids=[exp["experiment_id"]], echo=lambda *_: None)
    assert m["kind"] == "release" and m["export_revision"] == "b" * 40 and m["export_source_clean"]
    assert m["versions"]["outcome_classifier"] == 2 and "requirements.lock" in m["dependency_locks"]
    # Every exported file is listed with its digest, and the digests are right.
    assert m["files"] and all(
        hashlib.sha256((out / name).read_bytes()).hexdigest() == sha
        for name, sha in list(m["files"].items())[:25]
    )
    assert any(name.endswith(".mp4") for name in m["files"])
    src = m["sources"][rid]
    assert src["config_hash"] and src["training_code_per_segment"][0] is not None
    ev = src["evaluations"][0]
    assert ev["evaluation_code"] is not None and ev["outcome_classifier_version"] == 2
    assert json.loads((out / "demo.json").read_text())["kind"] == "release"


@pytest.mark.slow
def test_training_and_evaluation_record_their_code_revision():
    from lunarlab.evaluation import evaluate_run
    from lunarlab.experiments import create_experiment
    from lunarlab.runs import load_metadata
    from lunarlab.training import EXIT_COMPLETED, train

    exp = create_experiment(name="rev", rewards=[preset("baseline")], seeds=[0], profile="smoke")
    (rid,) = exp["run_ids"]
    assert train(rid) == EXIT_COMPLETED
    seg = load_metadata(rid)["segments"][0]
    assert "available" in seg["code"]  # a revision when run from a git checkout, a reason otherwise
    res = evaluate_run(rid, "validation")
    assert "available" in res["code"] and res["environment"]["matches_protocol"] is True
