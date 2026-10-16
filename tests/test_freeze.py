"""Final-test freezing: an immutable tested artifact, no further training, safe concurrency and retries."""

from __future__ import annotations

import threading
import time

import pytest

from lunarlab.config import EvalProtocol, PPOConfig, TrainingConfig
from lunarlab.locks import FileLock
from lunarlab.rewards import preset
from lunarlab.runs import RunError, create_run, load_metadata, read_manifest, register_checkpoint
from lunarlab.storage import RunPaths, sha256_file

pytestmark = pytest.mark.slow

TINY_PPO = PPOConfig(n_envs=2, n_steps=64, batch_size=32)  # 128 transitions per rollout
TINY_PROTOCOL = EvalProtocol(validation_seeds=[10_000], test_seeds=[20_000, 20_001])


def tiny_run(total=512):
    return create_run(
        reward=preset("baseline"),
        seed=0,
        ppo=TINY_PPO,
        protocol=TINY_PROTOCOL,
        training=TrainingConfig(
            profile="custom", total_transitions=total, checkpoint_every=256, validation_every=256
        ),
    )


def stopped_run():
    """A run stopped at 256 transitions (a resumable stop checkpoint and a validation-selected one)."""
    from lunarlab.training import EXIT_STOPPED, train

    cfg = tiny_run()
    assert train(cfg.run_id, quiet=True, on_validation=lambda n, _m: n >= 256) == EXIT_STOPPED
    return cfg


def completed_run():
    from lunarlab.training import EXIT_COMPLETED, train

    cfg = tiny_run()
    assert train(cfg.run_id, quiet=True) == EXIT_COMPLETED
    return cfg


def test_a_frozen_run_refuses_more_training_in_core_cli_api_and_worker(capsys):
    from fastapi.testclient import TestClient

    from lunarlab.cli import main
    from lunarlab.db import Database
    from lunarlab.evaluation import evaluate_run
    from lunarlab.jobs import JobManager, run_worker
    from lunarlab.server.main import create_app
    from lunarlab.training import train

    cfg = stopped_run()
    evaluate_run(cfg.run_id, "test")  # freezes the validation-selected checkpoint
    before = read_manifest(RunPaths(cfg.run_id))
    with pytest.raises(RunError, match="frozen"):
        train(cfg.run_id, resume=True, quiet=True)
    assert main(["resume", "--run-id", cfg.run_id]) != 0
    assert "frozen" in capsys.readouterr().err
    with TestClient(create_app(start_jobs=False, testing=True)) as c:
        r = c.post(
            f"/api/runs/{cfg.run_id}/resume", json={"checkpoint": "latest"}, headers={"X-LunarLab": "1"}
        )
        assert r.status_code == 409 and "frozen" in r.json()["detail"]
    # A job accepted before the freeze is refused again inside the worker, under the run lock.
    job = JobManager(Database()).submit("resume", run_id=cfg.run_id, params={"checkpoint": "latest"})
    assert run_worker(job["id"]) != 0
    assert read_manifest(RunPaths(cfg.run_id)) == before  # nothing was written


def test_tested_bytes_stay_available_when_an_alias_changes():
    from lunarlab.evaluation import evaluate_run
    from lunarlab.recording import record_run
    from lunarlab.robustness import evaluate_robustness

    cfg = completed_run()
    paths = RunPaths(cfg.run_id)
    first = evaluate_run(cfg.run_id, "test")
    frozen = load_metadata(cfg.run_id)["frozen_for_test"]
    artifact = paths.root / frozen["artifact"]
    assert artifact.exists() and sha256_file(artifact) == frozen["checkpoint_sha256"]
    assert first["checkpoint"]["sha256"] == frozen["checkpoint_sha256"]

    # Simulate the mutable alias being replaced afterwards (the bug this protects against).
    alias = paths.checkpoints / "best_validation.zip"
    alias.write_bytes((paths.checkpoints / "final.zip").read_bytes() + b"\0")
    register_checkpoint(paths, alias, kind="best_validation", transitions=999, updates=1, segment=0)
    again = evaluate_run(cfg.run_id, "test")
    assert again["checkpoint"]["sha256"] == frozen["checkpoint_sha256"] and again["repeat_index"] == 1
    rob = evaluate_robustness(cfg.run_id, "wind-5", episodes=1)
    assert rob["checkpoint"]["sha256"] == frozen["checkpoint_sha256"]
    rec = record_run(cfg.run_id, episode_seed=20_000, checkpoint="frozen")
    assert rec["source"]["checkpoint_sha256"] == frozen["checkpoint_sha256"]
    assert sha256_file(artifact) == frozen["checkpoint_sha256"]  # tested bytes unchanged


def test_freeze_cannot_race_with_a_training_process():
    from lunarlab.evaluation import evaluate_run

    cfg = completed_run()
    lock = FileLock(RunPaths(cfg.run_id).lock).acquire()  # what a training worker holds
    try:
        with pytest.raises(RunError, match="busy|in progress"):
            evaluate_run(cfg.run_id, "test")
    finally:
        lock.release()
    assert load_metadata(cfg.run_id)["frozen_for_test"] is None


def test_two_simultaneous_final_tests_cannot_produce_inconsistent_metadata(monkeypatch):
    import lunarlab.evaluation as ev

    cfg = completed_run()
    real = ev.run_episode

    def slow_episode(*a, **k):
        time.sleep(0.4)
        return real(*a, **k)

    monkeypatch.setattr(ev, "run_episode", slow_episode)
    outcomes: list[str] = []

    def attempt():
        try:
            ev.evaluate_run(cfg.run_id, "test")
            outcomes.append("completed")
        except RunError as exc:
            outcomes.append(f"refused: {exc}")

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(o.split(":")[0] for o in outcomes) == ["completed", "refused"]
    meta = load_metadata(cfg.run_id)
    assert [a["state"] for a in meta["test_attempts"]] == ["completed"]


def test_an_interrupted_final_test_is_not_counted_and_is_retried_on_the_same_checkpoint():
    from lunarlab.evaluation import EvaluationAborted, evaluate_run
    from lunarlab.freeze import pending_final_tests, test_status

    cfg = completed_run()
    with pytest.raises(EvaluationAborted):
        evaluate_run(cfg.run_id, "test", should_stop=lambda: True)
    status = test_status(cfg.run_id)
    assert status["frozen"] and not status["completed"] and status["attempts"][-1]["state"] == "interrupted"
    assert pending_final_tests([cfg.run_id]) == [cfg.run_id]  # freeze alone is not a completed test
    sha = load_metadata(cfg.run_id)["frozen_for_test"]["checkpoint_sha256"]
    res = evaluate_run(cfg.run_id, "test")
    assert res["checkpoint"]["sha256"] == sha and res["repeat_index"] == 0
    assert test_status(cfg.run_id)["completed"] and pending_final_tests([cfg.run_id]) == []


def test_missing_or_tampered_frozen_artifact_is_rejected():
    from lunarlab.evaluation import evaluate_run
    from lunarlab.freeze import resolve_frozen_checkpoint

    cfg = completed_run()
    evaluate_run(cfg.run_id, "test")
    path, _ = resolve_frozen_checkpoint(cfg.run_id)
    path.chmod(0o644)
    path.write_bytes(path.read_bytes()[:-1] + b"!")
    with pytest.raises(RunError, match="does not match"):
        resolve_frozen_checkpoint(cfg.run_id)
    path.unlink()
    with pytest.raises(RunError, match="missing"):
        evaluate_run(cfg.run_id, "test")


def test_legacy_freeze_records_resolve_only_while_the_tested_bytes_are_intact():
    from lunarlab.freeze import migrate_legacy_freeze, resolve_frozen_checkpoint
    from lunarlab.runs import update_metadata

    cfg = completed_run()
    paths = RunPaths(cfg.run_id)
    best = read_manifest(paths)["best_validation"]
    legacy = {
        "checkpoint": best["name"],
        "checkpoint_sha256": best["sha256"],
        "config_hash": cfg.config_hash(),
        "frozen_at": "2026-10-15T00:00:00+00:00",
    }
    update_metadata(cfg.run_id, frozen_for_test=legacy, test_evaluations=1)
    path, info = resolve_frozen_checkpoint(cfg.run_id)
    assert info["legacy"] and sha256_file(path) == best["sha256"]
    report = migrate_legacy_freeze(cfg.run_id)
    assert (
        report["migrated"]
        and (paths.root / load_metadata(cfg.run_id)["frozen_for_test"]["artifact"]).exists()
    )

    other = completed_run()
    update_metadata(other.run_id, frozen_for_test={**legacy, "checkpoint_sha256": "0" * 64})
    with pytest.raises(RunError, match="no longer available"):
        resolve_frozen_checkpoint(other.run_id)
    report = migrate_legacy_freeze(other.run_id)
    assert not report["migrated"] and "no longer" in report["reason"]
    assert load_metadata(other.run_id)["frozen_for_test"]["checkpoint_sha256"] == "0" * 64  # untouched


def test_child_runs_of_a_tested_run_carry_their_test_exposure():
    from lunarlab.evaluation import evaluate_run
    from lunarlab.lineage import create_warm_restart

    cfg = completed_run()
    evaluate_run(cfg.run_id, "test")
    child = create_warm_restart(cfg.run_id, checkpoint="final", confirm=True)
    lineage = load_metadata(child.run_id)["lineage"]
    assert lineage["post_test"] is True and lineage["parent_frozen_sha256"]
    from lunarlab.compare import run_summary

    assert run_summary(child.run_id)["evidence_role"] == "exploratory"
    assert run_summary(cfg.run_id)["evidence_role"] == "confirmatory"
