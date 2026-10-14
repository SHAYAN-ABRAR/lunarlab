"""Training lifecycle with real PPO updates (small budgets): checkpoints, stop, resume, reload."""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from lunarlab.config import (
    EvalProtocol,
    PPOConfig,
    RunConfig,
    TrainingConfig,
    actual_budget,
    resume_compatibility,
)
from lunarlab.env import make_env
from lunarlab.rewards import preset
from lunarlab.runs import RunError, create_run, load_metadata, read_manifest, resolve_checkpoint
from lunarlab.storage import RunPaths, atomic_write_json, read_json, read_jsonl
from lunarlab.training import EXIT_BUSY, EXIT_COMPLETED, EXIT_STOPPED, request_stop, train

pytestmark = pytest.mark.slow

SMALL_PPO = PPOConfig(n_envs=2, n_steps=64, batch_size=32)  # 128 transitions per rollout
SMALL_PROTOCOL = EvalProtocol(validation_seeds=[10_000, 10_001])


def small_run(name="potential", total=512, seed=0):
    return create_run(
        reward=preset(name),
        seed=seed,
        ppo=SMALL_PPO,
        protocol=SMALL_PROTOCOL,
        training=TrainingConfig(
            profile="custom", total_transitions=total, checkpoint_every=256, validation_every=256
        ),
    )


def test_budget_rounds_up_to_whole_rollouts():
    assert actual_budget(8192, 4096) == 8192
    assert actual_budget(1_000_000, 4096) == 1_003_520
    assert actual_budget(300, 128) == 384


def test_ppo_config_validation():
    with pytest.raises(ValueError):
        PPOConfig(n_envs=4, n_steps=100, batch_size=64)  # 400 not divisible by 64
    with pytest.raises(ValueError):
        PPOConfig(n_envs=1, n_steps=32, batch_size=64)  # batch larger than buffer
    with pytest.raises(ValueError):
        PPOConfig(net_arch_pi=[2048])
    with pytest.raises(ValueError):
        RunConfig(run_id="x", created_at="t", reward=preset("baseline"), env_kwargs={"continuous": True})


def test_complete_run_records_everything():
    cfg = small_run()
    assert train(cfg.run_id, quiet=True) == EXIT_COMPLETED
    paths = RunPaths(cfg.run_id)
    status = read_json(paths.status)
    assert status["state"] == "completed" and status["transitions"] == 512
    manifest = read_manifest(paths)
    kinds = {c["kind"] for c in manifest["checkpoints"]}
    assert {"periodic", "final", "best_validation"} <= kinds
    vh = read_jsonl(paths.validation_history)
    assert [v["transitions"] for v in vh] == [0, 256, 512]
    best = manifest["best_validation"]
    assert best["validation_mean_original_return"] == max(v["mean_original_return"] for v in vh)
    metrics = read_jsonl(paths.metrics)
    assert len(metrics) == 512 // 128
    assert {
        "approx_kl",
        "clip_fraction",
        "entropy_loss",
        "value_loss",
        "explained_variance",
        "learning_rate",
    } <= set(metrics[-1])
    import pandas as pd

    df = pd.read_csv(paths.episodes)
    assert {"original_return", "training_return", "term_potential_shaping"} <= set(df.columns)
    assert np.allclose(
        df["training_return"],
        df["original_return"]
        + df["term_potential_shaping"]
        + df["term_time_penalty"]
        + df["term_hover_bonus"],
        atol=1e-3,
    )
    meta = load_metadata(cfg.run_id)
    assert meta["segments"][0]["worker_seeds"] == cfg.worker_seeds(0)
    assert meta["system"]["packages"]["stable-baselines3"]
    with pytest.raises(RunError):
        train(cfg.run_id, resume=True, quiet=True)  # completed runs cannot be resumed


def test_weights_only_reload_reproduces_actions():
    from stable_baselines3 import PPO

    from lunarlab.runs import load_policy

    cfg = small_run(total=256)
    assert train(cfg.run_id, quiet=True) == EXIT_COMPLETED
    path, _ = resolve_checkpoint(cfg.run_id, "final")
    policy, entry = load_policy(cfg.run_id, "final")
    reference = PPO.load(str(path), device="cpu")  # trusted here: we just wrote this file in the test
    env = make_env()
    obs, _ = env.reset(seed=3)
    for _ in range(50):
        a_ref, _ = reference.predict(obs, deterministic=True)
        assert policy.act(obs) == int(a_ref)
        obs, *_ = env.step(policy.act(obs))
    env.close()


def test_stop_at_safe_boundary_then_resume_preserves_counters():
    cfg = small_run(total=1024, name="hover-bonus")
    paths = RunPaths(cfg.run_id)

    def stopper():
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            st = read_json(paths.status, default={}) or {}
            if st.get("transitions", 0) >= 300:
                request_stop(paths, reason="user", source="test")
                return
            time.sleep(0.05)

    t = threading.Thread(target=stopper)
    t.start()
    code = train(cfg.run_id, quiet=True)
    t.join()
    assert code == EXIT_STOPPED
    status = read_json(paths.status)
    assert status["state"] == "stopped"
    stop_ckpt = [c for c in read_manifest(paths)["checkpoints"] if c["kind"] == "stop"]
    assert len(stop_ckpt) == 1
    stopped_at = stop_ckpt[0]["transitions"]
    assert stopped_at % SMALL_PPO.rollout_size == 0 and 256 <= stopped_at < 1024

    assert train(cfg.run_id, resume=True, quiet=True) == EXIT_COMPLETED
    meta = load_metadata(cfg.run_id)
    segs = meta["segments"]
    assert [s["kind"] for s in segs] == ["initial", "resume"]
    assert segs[1]["start_transitions"] == stopped_at
    assert segs[1]["parent_checkpoint"] == stop_ckpt[0]["name"]
    assert segs[1]["worker_seeds"] != segs[0]["worker_seeds"]
    assert read_json(paths.status)["transitions"] == 1024
    from lunarlab.compare import load_episodes

    df = load_episodes(cfg.run_id)
    assert set(df["segment"]) == {0, 1}
    assert not ((df["segment"] == 0) & (df["transitions"] > stopped_at)).any()  # abandoned rows dropped


def test_incompatible_or_corrupt_resume_is_rejected():
    cfg = small_run(total=512)
    paths = RunPaths(cfg.run_id)
    request_stop(paths)  # stale request is cleared at start, so training still runs
    assert train(cfg.run_id, quiet=True) == EXIT_COMPLETED
    # Pretend the run never finished, then tamper with the checkpoint provenance.
    manifest = read_manifest(paths)
    manifest["checkpoints"] = [c for c in manifest["checkpoints"] if c["kind"] != "final"]
    for c in manifest["checkpoints"]:
        c["config_hash"] = "0000000000000000"
    atomic_write_json(paths.checkpoint_manifest, manifest)
    with pytest.raises(RunError, match="different configuration"):
        train(cfg.run_id, resume=True, quiet=True)
    # Corrupt checkpoint bytes: SHA-256 check refuses to load it.
    entry = max(
        (c for c in manifest["checkpoints"] if c["kind"] == "periodic"), key=lambda c: c["transitions"]
    )
    f = paths.checkpoints / entry["name"]
    f.write_bytes(f.read_bytes()[:-10] + b"0123456789")
    with pytest.raises(RunError, match="SHA-256"):
        resolve_checkpoint(cfg.run_id, entry["name"])
    # Changed reward function is a new experiment, not a continuation.
    other = cfg.model_copy(update={"reward": preset("hover-bonus")})
    assert any("reward function differs" in p for p in resume_compatibility(cfg, other))
    assert resume_compatibility(cfg, cfg) == []


def test_second_worker_on_same_run_is_refused():
    from lunarlab.locks import FileLock

    cfg = small_run(total=256)
    with FileLock(RunPaths(cfg.run_id).lock):
        assert train(cfg.run_id, quiet=True) == EXIT_BUSY


def test_stop_requested_while_job_starting_is_honoured_not_discarded():
    """Regression: Stop clicked while a resume job was still starting must not be cleared as stale."""
    cfg = small_run(total=256)
    paths = RunPaths(cfg.run_id)
    request_stop(paths, reason="user", source="test", job_id="job-20260101-000000-a-0001")
    assert train(cfg.run_id, job_id="job-20260101-000000-a-0001", quiet=True) == EXIT_STOPPED
    assert read_manifest(paths)["checkpoints"] == []  # nothing was trained
    assert load_metadata(cfg.run_id)["segments"] == []
    assert read_json(paths.status)["state"] == "stopped"
    # A request addressed to a different (earlier) job is stale: it is cleared and training proceeds.
    request_stop(paths, reason="user", source="test", job_id="job-20260101-000000-old-0002")
    assert train(cfg.run_id, job_id="job-20260101-000000-b-0003", quiet=True) == EXIT_COMPLETED
