# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Parallel runs and the job supervisor with real worker processes: the slot limit, failure isolation, forced
termination, a crashed worker, recovery by resuming, and a graceful supervisor shutdown."""

from __future__ import annotations

import re
import time

import psutil
import pytest

from lunarlab.config import EvalProtocol, PPOConfig, TrainingConfig
from lunarlab.db import Database
from lunarlab.jobs import JobManager, tail
from lunarlab.parallel import _command, run_parallel
from lunarlab.rewards import preset
from lunarlab.runs import create_run, read_manifest
from lunarlab.storage import RunPaths, read_json


def _run(total: int, checkpoint_every: int = 256):
    return create_run(
        reward=preset("baseline"),
        seed=0,
        ppo=PPOConfig(n_envs=2, n_steps=64, batch_size=32),
        protocol=EvalProtocol(validation_seeds=[10_000], test_seeds=[20_000]),
        training=TrainingConfig(
            profile="custom", total_transitions=total, checkpoint_every=checkpoint_every, validation_every=256
        ),
    )


def _wait(fn, timeout: float = 180.0, interval: float = 0.25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        v = fn()
        if v:
            return v
        time.sleep(interval)
    raise TimeoutError("condition not met in time")


def _running(jm: JobManager, run_id: str, transitions: int = 600):
    def check():
        jm.tick()
        st = read_json(RunPaths(run_id).status, default={}) or {}
        return st.get("state") == "running" and st.get("transitions", 0) >= transitions

    return _wait(check)


def _final(jm: JobManager, db: Database, job_id: str) -> dict:
    def check():
        jm.tick()
        j = db.get_job(job_id)
        return j if j["state"] in ("stopped", "completed", "failed", "interrupted") else None

    return _wait(check)


def test_unknown_parallel_actions_are_refused():
    assert _command("test", "r1")[-5:] == ["evaluate", "--run-id", "r1", "--split", "test"]
    assert _command("resume", "r1")[-3:] == ["resume", "--run-id", "r1"]
    assert _command("train", "r1")[-3:] == ["train-run", "--run-id", "r1"]
    assert _command("robustness", "r1", ["--episodes", "5"])[-4:] == ["--run-id", "r1", "--episodes", "5"]
    with pytest.raises(ValueError, match="unknown action"):
        _command("rm -rf", "r1")


@pytest.mark.slow
def test_parallel_runs_respect_the_slot_limit_and_a_failure_does_not_stop_the_others():
    good = [_run(512) for _ in range(3)]
    untrained = _run(512)  # a final test of a run without checkpoints fails
    lines: list[str] = []
    jobs = [("train", c.run_id) for c in good] + [("test", untrained.run_id)]
    codes = run_parallel(jobs, workers=2, echo=lines.append, poll_s=0.2)
    assert all(codes[c.run_id] == 0 for c in good), codes
    assert codes[untrained.run_id] != 0
    slots = [int(m.group(1)) for line in lines if (m := re.search(r", (\d+)/2 slots\)", line))]
    assert len(slots) == 4 and max(slots) <= 2
    for c in good:
        paths = RunPaths(c.run_id)
        assert read_json(paths.status)["state"] == "completed"
        assert paths.worker_log.stat().st_size > 0
        assert read_json(paths.metadata)["segments"][0]["parallel_slots"] == 2


@pytest.mark.slow
def test_force_termination_crash_recovery_and_graceful_supervisor_shutdown():
    db = Database()
    jm = JobManager(db, poll_interval=0.2)

    # forced termination: no stop checkpoint, the run is left interrupted and resumable from its last checkpoint
    a = _run(200_000)
    job = jm.submit("train", run_id=a.run_id)
    _running(jm, a.run_id)
    worker = psutil.Process(db.get_job(job["id"])["pid"])
    done = jm.force_terminate(job["id"])
    assert done["state"] == "stopped" and "force-terminated" in done["error"]
    assert not worker.is_running() or worker.status() == psutil.STATUS_ZOMBIE
    assert read_json(RunPaths(a.run_id).status)["state"] == "interrupted"

    # a crashed worker (killed from outside) is recorded as failed with the reason, and the run resumes
    b = _run(200_000)
    job = jm.submit("train", run_id=b.run_id)
    _running(jm, b.run_id, transitions=1_200)
    psutil.Process(db.get_job(job["id"])["pid"]).kill()
    crashed = _final(jm, db, job["id"])
    assert crashed["state"] == "failed" and "unexpectedly" in crashed["error"]
    assert read_json(RunPaths(b.run_id).status)["state"] == "interrupted"  # not left claiming "running"
    assert any(e["kind"] == "periodic" for e in read_manifest(RunPaths(b.run_id))["checkpoints"])
    resumed = jm.submit("resume", run_id=b.run_id)

    def resumed_segment():
        jm.tick()
        st = read_json(RunPaths(b.run_id).status, default={}) or {}
        return st.get("segment") == 1 and st.get("state") == "running"

    _wait(resumed_segment)

    # a graceful supervisor shutdown asks the running job to stop at a safe boundary: interrupted, resumable
    result = jm.shutdown(grace_s=90)
    assert result["stopped_jobs"] == [resumed["id"]] and result["still_running"] == []
    assert db.get_job(resumed["id"])["state"] == "interrupted"
    assert any(e["kind"] == "stop" for e in read_manifest(RunPaths(b.run_id))["checkpoints"])


def test_tail_reads_the_end_of_a_log_and_tolerates_a_missing_file(tmp_path):
    log = tmp_path / "worker.log"
    log.write_text("\n".join(f"line {i}" for i in range(100)), encoding="utf-8")
    assert tail(log, n=3).splitlines() == ["line 97", "line 98", "line 99"]
    assert tail(tmp_path / "missing.log") == ""
