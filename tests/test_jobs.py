"""Job supervisor: duplicates, recovery, ownership checks, real worker subprocesses."""

from __future__ import annotations

import contextlib
import subprocess
import sys
import time

import psutil
import pytest

from lunarlab.config import EvalProtocol, PPOConfig, TrainingConfig
from lunarlab.db import Database
from lunarlab.jobs import JobConflict, JobManager, job_dir
from lunarlab.rewards import preset
from lunarlab.runs import create_run, read_manifest
from lunarlab.storage import RunPaths, atomic_write_json, read_json


def small_run(total=512):
    return create_run(
        reward=preset("baseline"),
        seed=0,
        ppo=PPOConfig(n_envs=2, n_steps=64, batch_size=32),
        protocol=EvalProtocol(validation_seeds=[10_000]),
        training=TrainingConfig(
            profile="custom", total_transitions=total, checkpoint_every=256, validation_every=256
        ),
    )


def wait_for(fn, timeout=180.0, interval=0.25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        v = fn()
        if v:
            return v
        time.sleep(interval)
    raise TimeoutError("condition not met in time")


def wait_job(jm: JobManager, db: Database, job_id: str, timeout=180.0) -> dict:
    final = ("stopped", "completed", "failed", "interrupted")

    def check():
        jm.tick()
        j = db.get_job(job_id)
        return j if j["state"] in final else None

    return wait_for(check, timeout=timeout)


def test_duplicate_job_for_same_run_is_rejected_and_idempotency_key_dedupes():
    db = Database()
    jm = JobManager(db)
    cfg = small_run()
    j1 = jm.submit("train", run_id=cfg.run_id, idempotency_key="click-1")
    assert jm.submit("train", run_id=cfg.run_id, idempotency_key="click-1")["id"] == j1["id"]
    with pytest.raises(JobConflict):
        jm.submit("train", run_id=cfg.run_id)
    with pytest.raises(JobConflict):
        jm.submit("evaluate", run_id=cfg.run_id, params={"split": "validation"})
    with pytest.raises(ValueError):
        jm.submit("rm -rf", run_id=cfg.run_id)
    with pytest.raises(ValueError):
        jm.submit("evaluate", run_id="../escape")


def test_queued_job_cancel_and_queue_paused_after_restart():
    db = Database()
    jm = JobManager(db)
    cfg = small_run()
    j = jm.submit("train", run_id=cfg.run_id)
    jm2 = JobManager(db)  # simulated backend restart
    jm2.reconcile()
    assert jm2.queue_paused
    jm2.tick()
    assert db.get_job(j["id"])["state"] == "queued"  # nothing starts while paused
    assert jm2.request_stop(j["id"])["state"] == "stopped"


def _fake_running_job(
    db: Database, pid: int, create_time: float | None, job_id: str = "job-20260101-000000-x-ab12"
):
    import json

    with db.transaction() as c:
        c.execute(
            "INSERT INTO jobs (id,kind,lane,run_id,params_json,state,created_at,pid,pid_create_time) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                job_id,
                "record_demo",
                "analysis",
                None,
                json.dumps({}),
                "running",
                "2026-01-01T00:00:00+00:00",
                pid,
                create_time,
            ),
        )
    return job_id


def test_reconcile_marks_dead_worker_interrupted_or_uses_final_status():
    db = Database()
    dead = _fake_running_job(db, pid=999_999, create_time=1.0, job_id="job-20260101-000000-dead-0001")
    done = _fake_running_job(db, pid=999_998, create_time=1.0, job_id="job-20260101-000000-done-0002")
    atomic_write_json(
        job_dir(done) / "status.json", {"final_state": "completed", "updated_at": "2026-01-01T00:01:00+00:00"}
    )
    res = JobManager(db).reconcile()
    assert set(res["closed"]) == {dead, done}
    assert db.get_job(dead)["state"] == "interrupted"
    assert db.get_job(done)["state"] == "completed"


def test_live_worker_is_adopted_and_pid_reuse_is_never_killed():
    db = Database()
    job_id = "job-20260101-000000-live-0003"
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)", "worker", "--job-id", job_id]
    )
    try:
        created = psutil.Process(proc.pid).create_time()
        _fake_running_job(db, proc.pid, created, job_id)
        jm = JobManager(db)
        assert job_id in jm.reconcile()["adopted"]
        assert jm.verify_owned(db.get_job(job_id)) is not None
        # Same PID but a different creation time => not ours. Force-terminate must not kill it.
        db.update_job(job_id, pid_create_time=created - 1000)
        jm.force_terminate(job_id)
        assert proc.poll() is None, "an unverified process was terminated"
        assert db.get_job(job_id)["state"] in ("failed", "interrupted")
    finally:
        proc.kill()
        proc.wait(timeout=10)


@pytest.mark.slow
def test_worker_subprocess_records_demo():
    db = Database()
    jm = JobManager(db, poll_interval=0.2)
    job = jm.submit("record_demo", params={"policy": "random", "episode_seed": 20_001})

    j = wait_job(jm, db, job["id"])
    assert j["state"] == "completed", j.get("error")
    assert j["result"]["video"]["verified"] is True
    assert j["result"]["episode_seed"] == 20_001


@pytest.mark.slow
def test_supervised_training_graceful_stop_then_resume():
    db = Database()
    jm = JobManager(db, poll_interval=0.2)
    cfg = small_run(total=50_000)
    paths = RunPaths(cfg.run_id)
    job = jm.submit("train", run_id=cfg.run_id)

    def running_with_progress():
        jm.tick()
        st = read_json(paths.status, default={}) or {}
        return st.get("state") == "running" and st.get("transitions", 0) >= 600

    wait_for(running_with_progress, timeout=180)
    jm.request_stop(job["id"])

    j = wait_job(jm, db, job["id"])
    assert j["state"] == "stopped", j.get("error")
    assert j["exit_code"] == 3
    assert any(c["kind"] == "stop" for c in read_manifest(paths)["checkpoints"])
    assert read_json(paths.status)["state"] == "stopped"

    resume = jm.submit("resume", run_id=cfg.run_id)

    def resumed():
        jm.tick()
        st = read_json(paths.status, default={}) or {}
        return st.get("segment") == 1 and st.get("state") == "running"

    wait_for(resumed, timeout=120)
    jm.request_stop(resume["id"])
    j2 = wait_job(jm, db, resume["id"])
    assert j2["state"] == "stopped", j2.get("error")
    segs = read_json(paths.metadata)["segments"]
    assert segs[1]["kind"] == "resume" and segs[1]["start_transitions"] > 0


def test_process_discovery_requires_this_project_and_rechecks_identity(tmp_path):
    """Only processes whose working directory is this project qualify; PID reuse is detected.

    On Windows the venv's python.exe can be a launcher whose child is the real interpreter, so the
    test compares whole process trees rather than the launcher PID alone.
    """
    from lunarlab.procs import find_lunarlab_processes, terminate
    from lunarlab.storage import project_root

    args = [sys.executable, "-c", "import time; time.sleep(120)", "-m", "lunarlab", "worker", "--job-id", "x"]
    ours = subprocess.Popen(args, cwd=str(project_root()))
    foreign = subprocess.Popen(args, cwd=str(tmp_path))  # same command line, different project

    def tree(proc):
        try:
            root = psutil.Process(proc.pid)
            return {proc.pid} | {c.pid for c in root.children(recursive=True)}
        except psutil.NoSuchProcess:
            return {proc.pid}

    try:
        found = wait_for(lambda: [p for p in find_lunarlab_processes() if p["pid"] in tree(ours)], timeout=20)
        assert not [p for p in find_lunarlab_processes() if p["pid"] in tree(foreign)]
        stale = [dict(found[0], create_time=found[0]["create_time"] - 1000)]
        assert terminate(stale)[0][1].startswith("skipped")  # PID reuse protection
        assert ours.poll() is None
        assert all(outcome == "terminated" for _, outcome in terminate(found))
        ours.wait(timeout=15)
        assert foreign.poll() is None  # the other project's process was never touched
    finally:
        for p in (ours, foreign):
            for pid in tree(p):
                with contextlib.suppress(psutil.Error):
                    psutil.Process(pid).kill()
            p.wait(timeout=15)


def test_evidence_labels():
    from lunarlab.compare import evidence_level

    assert evidence_level("smoke", True, {"x": 1}, 8192) == "technical test only"
    assert evidence_level("standard", False, None, 0) == "not trained"
    assert evidence_level("standard", False, None, 409600) == "training incomplete"
    assert evidence_level("standard", True, None, 1003520) == "awaiting final test"
    assert evidence_level("standard", True, {"x": 1}, 1003520) == "evaluated"
