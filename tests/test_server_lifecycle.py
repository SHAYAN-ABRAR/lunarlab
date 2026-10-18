# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""The real backend process (``python -m lunarlab serve``): start-up, request guards, a single instance per
home, the UI and its path checks, a training job started over HTTP, graceful shutdown that interrupts the job at
a safe boundary, and recovery after a restart."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import psutil
import pytest

from lunarlab.config import EvalProtocol, PPOConfig, TrainingConfig
from lunarlab.db import Database
from lunarlab.rewards import preset
from lunarlab.runs import create_run, read_manifest
from lunarlab.storage import RunPaths, data_dir, read_json

ROOT = Path(__file__).resolve().parent.parent
H = {"X-LunarLab": "1"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(port: int, log: Path) -> subprocess.Popen:
    env = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy", "PYTHONUNBUFFERED": "1"}
    with open(log, "ab") as fh:
        return subprocess.Popen(
            [sys.executable, "-m", "lunarlab", "serve", "--port", str(port)],
            cwd=ROOT,
            env=env,
            stdout=fh,
            stderr=subprocess.STDOUT,
        )


def _wait(fn, timeout: float = 120.0, interval: float = 0.25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            v = fn()
        except httpx.HTTPError:
            v = None
        if v:
            return v
        time.sleep(interval)
    raise TimeoutError("condition not met in time")


@pytest.mark.slow
def test_backend_lifecycle_guards_single_instance_graceful_shutdown_and_recovery(tmp_path):
    port, log = _free_port(), tmp_path / "server.log"
    base = f"http://127.0.0.1:{port}"
    cfg = create_run(
        reward=preset("baseline"),
        seed=0,
        ppo=PPOConfig(n_envs=2, n_steps=64, batch_size=32),
        protocol=EvalProtocol(validation_seeds=[10_000]),
        training=TrainingConfig(
            profile="custom", total_transitions=200_000, checkpoint_every=512, validation_every=100_000
        ),
    )
    paths = RunPaths(cfg.run_id)
    proc = _start(port, log)
    try:
        with httpx.Client(base_url=base, timeout=10) as c:
            health = _wait(lambda: c.get("/api/health").json())
            assert health["status"] == "ok" and Path(health["home"]) == data_dir().parent
            info = read_json(data_dir() / "backend.json")
            # the recorded PID is the interpreter serving; on Windows a venv launcher may sit in between
            launched = {proc.pid} | {ch.pid for ch in psutil.Process(proc.pid).children(recursive=True)}
            assert info["pid"] in launched and info["port"] == port
            # the background readiness check runs once at start-up
            readiness = _wait(lambda: (r := c.get("/api/system").json()["readiness"])["checked"] and r)
            assert readiness["environment"]["ok"], readiness

            # a second backend for the same home is refused while the first holds the lock
            second = subprocess.run(
                [sys.executable, "-m", "lunarlab", "serve", "--port", str(_free_port())],
                cwd=ROOT, env=os.environ.copy(), capture_output=True, text=True, timeout=120,
            )  # fmt: skip
            assert second.returncode == 2 and "already running" in second.stderr

            # request guards: header, origin, host
            assert c.post("/api/shutdown").status_code == 403
            assert c.post("/api/shutdown", headers={**H, "Origin": "http://evil.example"}).status_code == 403
            assert c.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
            assert c.get("/api/does-not-exist").status_code == 404
            r = c.get("/")
            if (ROOT / "frontend" / "dist" / "index.html").exists():
                assert r.status_code == 200 and "<html" in r.text.lower()
                assert r.headers["x-content-type-options"] == "nosniff"
                # an encoded path outside the build folder falls back to the app, never to the file
                leak = c.get("/..%2F..%2Fpyproject.toml")
                assert leak.status_code in (200, 404) and "[project]" not in leak.text
            else:
                assert r.status_code == 503 and "Frontend not built" in r.json()["detail"]

            # a training job started over HTTP runs in a supervised worker process
            job = c.post(f"/api/runs/{cfg.run_id}/train", headers=H, json={}).json()
            assert job["kind"] == "train" and job["run_id"] == cfg.run_id
            _wait(
                lambda: (read_json(paths.status, default={}) or {}).get("transitions", 0) >= 600, timeout=180
            )
            assert c.get(f"/api/jobs/{job['id']}").json()["state"] in ("starting", "running")
            # graceful shutdown asks the job to stop at a safe boundary before the server exits
            assert c.post("/api/shutdown", headers=H).json()["status"] == "shutting down"
        assert proc.wait(timeout=120) == 0, log.read_text(errors="replace")
        assert not (data_dir() / "backend.json").exists()
        state = Database().get_job(job["id"])["state"]
        assert state in ("interrupted", "stopped"), state
        assert any(e["kind"] == "stop" for e in read_manifest(paths)["checkpoints"])
        assert (read_json(paths.status) or {})["state"] in ("interrupted", "stopped")

        # after a restart the job is not adopted as running; the run can be resumed
        proc = _start(port, log)
        with httpx.Client(base_url=base, timeout=10) as c:
            _wait(lambda: c.get("/api/health").json())
            listed = {j["id"]: j for j in c.get("/api/jobs").json()}
            assert listed[job["id"]]["state"] in ("interrupted", "stopped")
            assert c.post(f"/api/runs/{cfg.run_id}/stop", headers=H).status_code == 409  # nothing running
            assert c.post("/api/shutdown", headers=H).status_code == 200
        assert proc.wait(timeout=120) == 0, log.read_text(errors="replace")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)
