# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""The reviewer-facing reproducibility commands: smoke pipeline, artifact export and re-evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from lunarlab.config import EvalProtocol, PPOConfig, RunConfig, TrainingConfig
from lunarlab.reproduce import (
    compare_episodes,
    episodes_digest,
    export_artifact,
    reproduce_artifact,
    run_smoke,
    weights_digest,
)
from lunarlab.rewards.config import preset
from lunarlab.storage import sha256_file

ROOT = Path(__file__).resolve().parent.parent
SUPPLIED = sorted((ROOT / "examples" / "artifacts").glob("*/artifact.json"))


def _ep(seed, ret, *, length=100, outcome="at_rest", pad=True):
    return {
        "seed": seed,
        "length": length,
        "original_return": ret,
        "training_return": ret,
        "env_outcome": outcome,
        "pad_landing": pad,
    }


def test_compare_episodes_exact_tolerance_and_mismatches():
    rec = [_ep(1, 10.0), _ep(2, 20.0), _ep(3, 30.0)]
    assert compare_episodes(rec, [_ep(1, 10.0), _ep(2, 20.0)])["exact"] == 2
    near = compare_episodes(rec, [_ep(1, 10.0 + 1e-9)], tolerance=1e-6)
    assert (near["exact"], near["within_tolerance"], near["n_mismatches"]) == (0, 1, 0)
    assert near["max_abs_return_difference"] == pytest.approx(1e-9)
    strict = compare_episodes(rec, [_ep(1, 10.0 + 1e-9)])
    assert strict["n_mismatches"] == 1 and "original_return" in strict["mismatches"][0]["fields"]
    outcome = compare_episodes(rec, [_ep(2, 20.0, outcome="timeout", pad=False)], tolerance=1.0)
    assert outcome["n_mismatches"] == 1
    assert set(outcome["mismatches"][0]["fields"]) == {"env_outcome", "pad_landing"}
    missing = compare_episodes(rec, [_ep(9, 1.0)])
    assert episodes_digest(rec) == episodes_digest(list(reversed(rec)))  # seed order, not list order
    assert episodes_digest(rec) != episodes_digest([_ep(1, 10.0 + 1e-12), *rec[1:]])
    assert missing["n_mismatches"] == 1 and "not in the recorded" in missing["mismatches"][0]["reason"]


@pytest.mark.slow
def test_smoke_pipeline_verifies_every_link_and_is_deterministic(tmp_path):
    report = run_smoke(
        tmp_path / "work", transitions=1024, training_determinism=True, keep=True, echo=lambda _m: None
    )
    failed = [c for c in report["checks"] if not c["ok"]]
    assert report["ok"], failed
    assert report["repeated_evaluation"]["exact"] == report["repeated_evaluation"]["compared"] == 4
    det = report["training_determinism"]
    assert det["same_config_hash"] and det["identical_final_weights"] and det["identical_training_episodes"]
    assert report["software"]["lunarlab"] and report["checkpoints"]
    # Content digests compare trainings across processes; file digests differ (zip entries carry save times).
    runs = tmp_path / "work" / "home" / "runs"
    a, b = (
        weights_digest(runs / r / "checkpoints" / "final.zip")
        for r in (report["run_id"], det["second_run_id"])
    )
    assert a == b == report["final_weights_sha256"]
    assert len(report["final_test_episodes_sha256"]) == 64
    assert (tmp_path / "work" / "export" / "final_test_summary.json").exists()


@pytest.mark.slow
def test_smoke_pipeline_removes_its_temporary_home(tmp_path):
    report = run_smoke(tmp_path / "work", transitions=512, echo=lambda _m: None)
    assert report["ok"] and report["workdir"] is None
    assert not (tmp_path / "work").exists()  # including the read-only frozen checkpoint


def _tested_run():
    from lunarlab.evaluation import evaluate_run
    from lunarlab.runs import create_run
    from lunarlab.training import EXIT_COMPLETED, train

    cfg = create_run(
        reward=preset("potential"),
        seed=3,
        ppo=PPOConfig(n_envs=2, n_steps=128, batch_size=64),
        protocol=EvalProtocol(validation_seeds=[10_000], test_seeds=[20_000, 20_001, 20_002]),
        training=TrainingConfig(
            profile="custom", total_transitions=512, checkpoint_every=256, validation_every=256
        ),
    )
    assert train(cfg.run_id, quiet=True) == EXIT_COMPLETED
    evaluate_run(cfg.run_id, "test")
    return cfg


@pytest.mark.slow
def test_export_then_reproduce_artifact_matches_exactly_and_detects_tampering(tmp_path):
    cfg = _tested_run()
    out = tmp_path / "artifact"
    manifest = export_artifact(cfg.run_id, out)
    assert manifest["config_hash"] == cfg.config_hash()
    assert manifest["documented_metric"]["n_episodes"] == 3
    report = reproduce_artifact(out, echo=lambda _m: None)
    assert report["ok"], [c for c in report["checks"] if not c["ok"]]
    assert report["comparison"]["exact"] == 3
    assert report["recorded_mean_original_return"] == report["reproduced_mean_original_return"]

    # A changed recorded value is a reproduction mismatch...
    rec = json.loads((out / "evaluation.json").read_text(encoding="utf-8"))
    rec["episodes"][0]["original_return"] += 1.0
    (out / "evaluation.json").write_text(json.dumps(rec), encoding="utf-8")
    tampered = reproduce_artifact(out, echo=lambda _m: None)
    assert not tampered["ok"]
    failed = {c["check"] for c in tampered["checks"] if not c["ok"]}
    assert "evaluation.json matches its recorded SHA-256" in failed
    assert any(name.startswith("every re-evaluated episode matches") for name in failed)


@pytest.mark.slow
def test_export_refuses_a_run_without_a_final_test(tmp_path):
    from lunarlab.runs import create_run

    cfg = create_run(
        reward=preset("baseline"),
        seed=0,
        training=TrainingConfig(
            profile="custom", total_transitions=512, checkpoint_every=256, validation_every=256
        ),
    )
    with pytest.raises(ValueError, match="no final test"):
        export_artifact(cfg.run_id, tmp_path / "x")
    assert not (tmp_path / "x").exists()


def test_supplied_artifacts_exist():
    assert {p.parent.name for p in SUPPLIED} >= {"ppo-baseline-s0", "ppo-hover-bonus-s0", "dqn-baseline-s0"}


@pytest.mark.parametrize("manifest_path", SUPPLIED, ids=[p.parent.name for p in SUPPLIED])
def test_supplied_artifact_is_internally_consistent(manifest_path):
    """Digests, configuration identity and the documented metric, without re-running anything."""
    folder = manifest_path.parent
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, info in m["files"].items():
        assert sha256_file(folder / name) == info["sha256"], name
    cfg = RunConfig.model_validate(yaml.safe_load((folder / "config.yaml").read_text(encoding="utf-8")))
    assert cfg.config_hash() == m["config_hash"]
    rec = json.loads((folder / "evaluation.json").read_text(encoding="utf-8"))
    assert rec["checkpoint"]["sha256"] == m["files"]["checkpoint.zip"]["sha256"]
    assert rec["split"] == "test" and rec["seeds"] == cfg.eval_protocol.test_seeds
    mean = sum(e["original_return"] for e in rec["episodes"]) / len(rec["episodes"])
    assert mean == pytest.approx(m["documented_metric"]["mean_original_return"], abs=1e-9)
    assert m["documented_metric"]["n_episodes"] == len(rec["episodes"]) == 100
