# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Learned-reward packages must replay without the author's model registry."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
from pathlib import Path

import numpy as np
import pytest

from lunarlab.config import RunConfig
from lunarlab.preferences.model import RewardModel, load_reward_model, model_path
from lunarlab.reproduce import export_artifact, reproduce_artifact
from lunarlab.storage import RunPaths, atomic_write_json, read_yaml, sha256_file, write_yaml

ROOT = Path(__file__).resolve().parent.parent
MODEL_ID = "rm-export-dependency-test"


@pytest.fixture
def learned_run(tmp_path, monkeypatch):
    from lunarlab import freeze, reproduce, runs

    artifact = tmp_path / "recorded"
    shutil.copytree(ROOT / "examples/artifacts/ppo-baseline-s0", artifact)
    cfg = RunConfig.model_validate(read_yaml(artifact / "config.yaml"))
    cfg.reward.learned.enabled = True
    cfg.reward.learned.model_id = MODEL_ID
    model = RewardModel(
        np.zeros(20, dtype=np.float32),
        np.ones(20, dtype=np.float32),
        [(np.zeros((20, 1), dtype=np.float32), np.zeros(1, dtype=np.float32))],
        0.0,
        1.0,
    )
    model.save(model_path(MODEL_ID))
    atomic_write_json(
        model_path(MODEL_ID) / "meta.json", {"sha256": sha256_file(model_path(MODEL_ID) / "model.npz")}
    )
    write_yaml(artifact / "config.yaml", cfg.model_dump(mode="json"))
    recorded = json.loads((artifact / "evaluation.json").read_text())
    recorded["reward_hash"] = cfg.reward.content_hash()
    atomic_write_json(artifact / "evaluation.json", recorded)
    paths = RunPaths(cfg.run_id)
    paths.config.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(artifact / "config.yaml", paths.config)
    monkeypatch.setattr(runs, "load_config", lambda _: cfg)
    monkeypatch.setattr(runs, "load_metadata", lambda _: {"frozen_for_test": True})
    monkeypatch.setattr(
        freeze,
        "resolve_final_checkpoint",
        lambda *a, **k: (artifact / "checkpoint.zip", {"name": "test.zip"}),
    )
    monkeypatch.setattr(reproduce, "_final_test_evaluation", lambda *a: artifact / "evaluation.json")
    load_reward_model.cache_clear()
    yield cfg
    load_reward_model.cache_clear()


def test_export_includes_original_model_and_metadata(learned_run, tmp_path):
    out = tmp_path / "export"
    manifest = export_artifact(learned_run.run_id, out)
    assert manifest["reward_model"] == {"id": MODEL_ID}
    for name in ("model.npz", "meta.json"):
        assert (out / "reward_model" / name).read_bytes() == (model_path(MODEL_ID) / name).read_bytes()
        assert manifest["files"][f"reward_model/{name}"]["sha256"] == sha256_file(out / "reward_model" / name)


@pytest.mark.parametrize("problem", ["missing", "digest"])
def test_export_refuses_missing_or_corrupt_models_before_creating_output(learned_run, tmp_path, problem):
    target = model_path(MODEL_ID) / "meta.json"
    if problem == "missing":
        target.unlink()
    else:
        atomic_write_json(target, {"sha256": "incorrect"})
    with pytest.raises((FileNotFoundError, ValueError), match="reward model"):
        export_artifact(learned_run.run_id, tmp_path / "export")
    assert not (tmp_path / "export").exists()


def test_replay_uses_bundle_in_fresh_home_despite_stale_cached_model(learned_run, tmp_path, monkeypatch):
    out = tmp_path / "export"
    export_artifact(learned_run.run_id, out)
    cached = load_reward_model(MODEL_ID)
    cached.weights[0][1][0] = 999.0
    empty_home = tmp_path / "fresh-home"
    monkeypatch.setenv("LUNARLAB_HOME", str(empty_home))
    report = reproduce_artifact(out, episodes=2, echo=lambda _: None)
    assert report["integrity_ok"] and report["episodes"] == 2
    assert (
        report["comparison"]["max_abs_original_return_difference"]
        == report["comparison"]["max_abs_training_return_difference"]
    )
    assert os.environ["LUNARLAB_HOME"] == str(empty_home)
    assert not empty_home.exists()
    assert load_reward_model.cache_info().currsize == 0


@pytest.mark.parametrize("problem", ["legacy", "missing", "corrupt", "identity"])
def test_incomplete_or_corrupt_bundle_blocks_before_evaluation(learned_run, tmp_path, monkeypatch, problem):
    from lunarlab import evaluation

    out = tmp_path / "export"
    manifest = export_artifact(learned_run.run_id, out)
    if problem == "legacy":
        manifest.pop("reward_model")
        for name in ("reward_model/model.npz", "reward_model/meta.json"):
            manifest["files"].pop(name)
    elif problem == "missing":
        (out / "reward_model/model.npz").unlink()
    elif problem == "corrupt":
        (out / "reward_model/model.npz").write_bytes(b"invalid")
    else:
        manifest["reward_model"]["id"] = "rm-wrong"
    atomic_write_json(out / "artifact.json", manifest)
    monkeypatch.setattr(evaluation, "evaluate_policy", lambda *a, **k: pytest.fail("must not evaluate"))
    report = reproduce_artifact(out, echo=lambda _: None)
    assert report["status"] == "integrity-failure" and report["exit_code"] == 1
    assert report["evaluation_skipped"] and report["episodes"] == 0
    assert not report["integrity_ok"]


def test_cli_and_ci_summary_preserve_the_missing_dependency_failure(learned_run, tmp_path, capsys):
    from lunarlab.cli import main

    out = tmp_path / "export"
    export_artifact(learned_run.run_id, out)
    (out / "reward_model/model.npz").unlink()
    report_path = tmp_path / "reproduce-learned-linux.json"
    assert main(["reproduce-artifact", "--artifact", str(out), "--report", str(report_path)]) == 1
    assert "evaluation was not run" in capsys.readouterr().out
    spec = importlib.util.spec_from_file_location(
        "reproduction_summary", ROOT / "tools/reproduction_summary.py"
    )
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    summary = tool.summarize([report_path], [], {"learned": 1}, "linux")
    assert not summary["ok"]
    assert "integrity-failure" in tool.markdown(summary)
