"""Local job supervisor: owned worker subprocesses, a small queue, stop and recovery.

* Every job runs in its own process: ``python -m lunarlab worker --job-id <id>``,
  launched from an argument list (never ``shell=True``). Training never runs in
  the web server process.
* Two lanes, one slot each by default: ``train`` (train/resume) and
  ``analysis`` (evaluate/record/demo/report/benchmark). Video and evaluation jobs therefore
  never pile up behind, or multiply alongside, a training job.
* Duplicate prevention: one active job per run (checked in a transaction), an
  idempotency key per user action, a per-run OS file lock held by the worker,
  and a single-instance lock for the backend itself.
* Stop is cooperative (a control file the worker polls); force-termination is
  available only after verifying the process is ours: same PID, same process
  creation time, and a command line containing this job id. A stale PID in the
  database is never enough to kill anything.
* Workers survive a browser closing. On backend shutdown, running jobs are asked
  to stop at a safe boundary (state ``interrupted``, resumable). After a backend
  crash/restart, live workers are re-adopted and dead ones are reconciled from
  their status files. Queued jobs left from a previous session wait until the
  queue is resumed explicitly.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import psutil

from lunarlab.db import ACTIVE_STATES, Database
from lunarlab.storage import (
    RunPaths,
    atomic_write_json,
    data_dir,
    new_id,
    project_root,
    read_json,
    utc_now,
    validate_run_id,
)
from lunarlab.training import (
    EXIT_BUSY,
    EXIT_COMPLETED,
    EXIT_INTERRUPTED,
    EXIT_STOPPED,
    request_stop,
)

KIND_LANES = {
    "train": "train",
    "resume": "train",
    "evaluate": "analysis",
    "record": "analysis",
    "record_demo": "analysis",
    "report": "analysis",
    "benchmark": "analysis",
}
LANE_LIMITS = {"train": 1, "analysis": 1}
EXIT_STATE = {EXIT_COMPLETED: "completed", EXIT_STOPPED: "stopped", EXIT_INTERRUPTED: "interrupted"}
STALE_HEARTBEAT_S = 60


class JobConflict(RuntimeError):
    pass


class JobNotFound(KeyError):
    pass


def job_dir(job_id: str) -> Path:
    validate_run_id(job_id)
    p = data_dir() / "jobs" / job_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def job_stop_file(job_id: str) -> Path:
    return job_dir(job_id) / "stop_requested.json"


def tail(path: Path, n: int = 25) -> str:
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 8000))
            lines = f.read().decode("utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except OSError:
        return ""


class JobManager:
    def __init__(self, db: Database, *, poll_interval: float = 1.0, python: str | None = None) -> None:
        self.db = db
        self.poll_interval = poll_interval
        self.python = python or sys.executable
        self._procs: dict[str, subprocess.Popen] = {}
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._halt = threading.Event()
        self._wake = threading.Event()
        self._last_progress_write: dict[str, float] = {}

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        self.reconcile()
        self._thread = threading.Thread(target=self._loop, name="lunarlab-jobs", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._halt.is_set():
            try:
                self.tick()
            except Exception as exc:  # keep supervising even if one tick fails
                print(f"[lunarlab.jobs] tick error: {exc!r}", file=sys.stderr, flush=True)
            self._wake.wait(self.poll_interval)
            self._wake.clear()

    def shutdown(self, grace_s: float = 45.0) -> dict[str, Any]:
        """Ask running jobs to stop at a safe boundary, wait, then stop supervising."""
        self._halt.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)
        active = self.db.list_jobs(states=("starting", "running", "stop_requested"))
        for job in active:
            with contextlib.suppress(Exception):
                self.request_stop(job["id"], reason="shutdown")
        deadline = time.monotonic() + grace_s
        while time.monotonic() < deadline:
            self.tick(start_new=False)
            if not self.db.list_jobs(states=("starting", "running", "stop_requested")):
                break
            time.sleep(0.5)
        left = self.db.list_jobs(states=("starting", "running", "stop_requested"))
        return {
            "stopped_jobs": [j["id"] for j in active],
            "still_running": [{"id": j["id"], "pid": j["pid"]} for j in left],
        }

    @property
    def queue_paused(self) -> bool:
        return bool(self.db.get_setting("queue_paused", False))

    def set_queue_paused(self, paused: bool) -> None:
        self.db.set_setting("queue_paused", bool(paused))
        self._wake.set()

    # ------------------------------------------------------------------ #
    # Submission and control
    # ------------------------------------------------------------------ #
    def submit(
        self,
        kind: str,
        *,
        run_id: str | None = None,
        params: dict | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if kind not in KIND_LANES:
            raise ValueError(f"unknown job kind: {kind}")
        if run_id:
            validate_run_id(run_id)
        lane = KIND_LANES[kind]
        job_id = new_id(kind, prefix="job")
        with self.db.transaction() as c:
            if idempotency_key:
                row = c.execute("SELECT * FROM jobs WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if row is not None:
                    return self.db.job_row(row)
            if run_id:
                q = f"SELECT id, kind, state FROM jobs WHERE run_id=? AND state IN ({','.join('?' * len(ACTIVE_STATES))})"
                active = c.execute(q, (run_id, *ACTIVE_STATES)).fetchone()
                if active is not None:
                    raise JobConflict(
                        f"run {run_id} already has an active job ({active['kind']} {active['id']}, {active['state']})"
                    )
                if kind in ("train", "resume"):
                    st = read_json(RunPaths(run_id).status, default={}) or {}
                    if st.get("state") == "running" and _fresh(st.get("updated_at")):
                        raise JobConflict(
                            f"run {run_id} is being trained by another process (pid {st.get('pid')})"
                        )
            import json

            c.execute(
                "INSERT INTO jobs (id,kind,lane,run_id,params_json,state,idempotency_key,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (job_id, kind, lane, run_id, json.dumps(params or {}), "queued", idempotency_key, utc_now()),
            )
        self._wake.set()
        return self.db.get_job(job_id)

    def request_stop(self, job_id: str, *, reason: str = "user") -> dict[str, Any]:
        with self._lock:
            job = self.db.get_job(job_id)
            if job is None:
                raise JobNotFound(job_id)
            if job["state"] == "queued":
                self.db.update_job(
                    job_id, state="stopped", finished_at=utc_now(), error="cancelled before it started"
                )
                return self.db.get_job(job_id)
            if job["state"] not in ("starting", "running", "stop_requested"):
                return job
            atomic_write_json(job_stop_file(job_id), {"requested_at": utc_now(), "reason": reason})
            if job["kind"] in ("train", "resume") and job["run_id"]:
                request_stop(RunPaths(job["run_id"]), reason=reason, source="supervisor", job_id=job["id"])
            self.db.update_job(job_id, state="stop_requested")
            self._wake.set()
            return self.db.get_job(job_id)

    def force_terminate(self, job_id: str) -> dict[str, Any]:
        """Terminate a worker that did not stop cooperatively (ownership verified first)."""
        with self._lock:
            job = self.db.get_job(job_id)
            if job is None:
                raise JobNotFound(job_id)
            if job["state"] not in ("starting", "running", "stop_requested"):
                raise JobConflict(f"job is {job['state']}; nothing to terminate")
            proc = self.verify_owned(job)
            if proc is None:
                self._finalize(job, None, note="process no longer exists")
                return self.db.get_job(job_id)
            for child in proc.children(recursive=True):
                with contextlib.suppress(psutil.Error):
                    child.kill()
            with contextlib.suppress(psutil.Error):
                proc.kill()
            with contextlib.suppress(psutil.Error):
                proc.wait(timeout=10)
            popen = self._procs.pop(job_id, None)
            if popen is not None:
                with contextlib.suppress(Exception):
                    popen.wait(timeout=5)
            self.db.update_job(
                job_id,
                state="stopped",
                finished_at=utc_now(),
                error="force-terminated: no stop checkpoint was written; resume from the latest checkpoint",
            )
            if job["kind"] in ("train", "resume") and job["run_id"]:
                paths = RunPaths(job["run_id"])
                st = read_json(paths.status, default={}) or {}
                st.update(
                    {
                        "state": "interrupted",
                        "phase": "ended",
                        "updated_at": utc_now(),
                        "error": "worker force-terminated",
                    }
                )
                atomic_write_json(paths.status, st)
            return self.db.get_job(job_id)

    # ------------------------------------------------------------------ #
    # Supervision
    # ------------------------------------------------------------------ #
    def verify_owned(self, job: dict[str, Any]) -> psutil.Process | None:
        pid, created = job.get("pid"), job.get("pid_create_time")
        if not pid or created is None:
            return None
        try:
            p = psutil.Process(int(pid))
            if abs(p.create_time() - float(created)) > 1.0:
                return None  # PID reused by an unrelated process
            cmd = p.cmdline()
            if job["id"] in cmd and "worker" in cmd:
                return p
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
        return None

    def tick(self, *, start_new: bool = True) -> None:
        with self._lock:
            for job in self.db.list_jobs(states=("starting", "running", "stop_requested")):
                self._monitor(job)
            if start_new and not self.queue_paused:
                self._start_queued()

    def _monitor(self, job: dict[str, Any]) -> None:
        popen = self._procs.get(job["id"])
        if popen is not None:
            rc = popen.poll()
            alive = rc is None
        else:
            rc = None
            alive = self.verify_owned(job) is not None
        if not alive:
            self._procs.pop(job["id"], None)
            self._finalize(job, rc)
            return
        progress = self._progress(job)
        now = time.monotonic()
        if now - self._last_progress_write.get(job["id"], 0) >= 2.0:
            self._last_progress_write[job["id"]] = now
            fields: dict[str, Any] = {
                "progress": progress,
                "heartbeat_at": progress.get("updated_at") or utc_now(),
            }
            if job["state"] == "starting" and progress.get("state") in ("running", "completed"):
                fields["state"] = "running"
            self.db.update_job(job["id"], **fields)

    def _progress(self, job: dict[str, Any]) -> dict[str, Any]:
        if job["kind"] in ("train", "resume") and job["run_id"]:
            st = read_json(RunPaths(job["run_id"]).status, default={}) or {}
            if st.get("job_id") == job["id"]:
                return st
        return read_json(job_dir(job["id"]) / "status.json", default={}) or {}

    def _finalize(self, job: dict[str, Any], rc: int | None, note: str | None = None) -> None:
        jd = job_dir(job["id"])
        jstatus = read_json(jd / "status.json", default={}) or {}
        result = read_json(jd / "result.json", default=None)
        state = EXIT_STATE.get(rc) if rc is not None else None
        if state is None:
            state = jstatus.get("final_state")
        error = None
        if state is None and rc is None and job["state"] == "stop_requested":
            state = "interrupted"  # an adopted worker that went away after a stop request
        if state is None or state == "failed":
            state = "failed"
            if rc == EXIT_BUSY:
                error = "another worker already holds this run's lock"
            else:
                error = jstatus.get("error") or note or f"worker exited unexpectedly (code {rc})"
                log_tail = tail(Path(job["log_path"])) if job.get("log_path") else ""
                if log_tail:
                    error = f"{error}\n--- worker log (tail) ---\n{log_tail}"
        if state == "stopped":
            stop_req = read_json(job_stop_file(job["id"]), default={}) or {}
            if stop_req.get("reason") == "shutdown":
                state = "interrupted"
        self.db.update_job(
            job["id"],
            state=state,
            exit_code=rc,
            finished_at=utc_now(),
            error=error,
            result=result,
            progress=self._progress(job),
        )

    def _start_queued(self) -> None:
        active = self.db.list_jobs(states=("starting", "running", "stop_requested"))
        counts = {lane: sum(1 for j in active if j["lane"] == lane) for lane in LANE_LIMITS}
        queued = sorted(self.db.list_jobs(states=("queued",), limit=500), key=lambda j: j["created_at"])
        for job in queued:
            if counts[job["lane"]] >= LANE_LIMITS[job["lane"]]:
                continue
            self._launch(job)
            counts[job["lane"]] += 1

    def _launch(self, job: dict[str, Any]) -> None:
        jd = job_dir(job["id"])
        log_path = jd / "worker.log"
        cmd = [self.python, "-m", "lunarlab", "worker", "--job-id", job["id"]]
        env = os.environ.copy()
        env.update(
            {
                "LUNARLAB_HOME": str(Path(os.environ.get("LUNARLAB_HOME") or project_root()).resolve()),
                "PYTHONUNBUFFERED": "1",
                "PYTHONIOENCODING": "utf-8",
                "OMP_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
            }
        )
        kwargs: dict[str, Any] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        else:
            kwargs["start_new_session"] = True
        log = open(log_path, "ab")  # noqa: SIM115 - owned by the child for its lifetime
        try:
            popen = subprocess.Popen(
                cmd,
                cwd=str(project_root()),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                **kwargs,
            )
        except OSError as exc:
            log.close()
            self.db.update_job(
                job["id"], state="failed", finished_at=utc_now(), error=f"could not start worker: {exc}"
            )
            return
        finally:
            with contextlib.suppress(Exception):
                log.close()
        try:
            created = psutil.Process(popen.pid).create_time()
        except psutil.Error:
            created = None
        self._procs[job["id"]] = popen
        self.db.update_job(
            job["id"],
            state="starting",
            started_at=utc_now(),
            pid=popen.pid,
            pid_create_time=created,
            log_path=str(log_path),
        )

    def reconcile(self) -> dict[str, list[str]]:
        """Bring job rows in line with reality after a backend (re)start."""
        adopted, closed = [], []
        with self._lock:
            for job in self.db.list_jobs(states=("starting", "running", "stop_requested")):
                if self.verify_owned(job) is not None:
                    adopted.append(job["id"])
                    continue
                jd = job_dir(job["id"])
                jstatus = read_json(jd / "status.json", default={}) or {}
                final = jstatus.get("final_state")
                if final:
                    self.db.update_job(
                        job["id"],
                        state=final,
                        finished_at=jstatus.get("updated_at") or utc_now(),
                        result=read_json(jd / "result.json", default=None),
                        progress=self._progress(job),
                        error=jstatus.get("error"),
                    )
                else:
                    self.db.update_job(
                        job["id"],
                        state="interrupted",
                        finished_at=utc_now(),
                        error="worker was no longer running when the backend restarted; resume from the latest checkpoint",
                    )
                    if job["kind"] in ("train", "resume") and job["run_id"]:
                        paths = RunPaths(job["run_id"])
                        st = read_json(paths.status, default={}) or {}
                        if st.get("state") == "running":
                            st.update({"state": "interrupted", "phase": "ended", "updated_at": utc_now()})
                            atomic_write_json(paths.status, st)
                closed.append(job["id"])
            if self.db.list_jobs(states=("queued",)):
                self.set_queue_paused(True)
        return {"adopted": adopted, "closed": closed}


def _fresh(ts: str | None) -> bool:
    if not ts:
        return False
    import datetime as dt

    try:
        t = dt.datetime.fromisoformat(ts)
    except ValueError:
        return False
    return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() < STALE_HEARTBEAT_S


# --------------------------------------------------------------------------- #
# Worker side
# --------------------------------------------------------------------------- #


def run_worker(job_id: str) -> int:
    """Entry point of ``python -m lunarlab worker --job-id <id>``. Writes files only."""
    from lunarlab.evaluation import EvaluationAborted, evaluate_run, summarize_for_index
    from lunarlab.recording import record_demo, record_run
    from lunarlab.training import EXIT_FAILED, train

    db = Database()
    job = db.get_job(job_id)
    if job is None:
        print(f"unknown job {job_id}", file=sys.stderr)
        return EXIT_FAILED
    jd = job_dir(job_id)
    params = job.get("params") or {}
    started = utc_now()

    def status(**kw: Any) -> None:
        atomic_write_json(
            jd / "status.json",
            {
                "job_id": job_id,
                "kind": job["kind"],
                "pid": os.getpid(),
                "started_at": started,
                "updated_at": utc_now(),
                **kw,
            },
        )

    def should_stop() -> bool:
        return job_stop_file(job_id).exists()

    status(state="running")
    print(f"[lunarlab] worker {job_id}: {job['kind']} run={job['run_id']} params={params}", flush=True)
    code, result, error = EXIT_FAILED, None, None
    try:
        kind = job["kind"]
        if kind == "train":
            code = train(job["run_id"], job_id=job_id)
        elif kind == "resume":
            code = train(
                job["run_id"], resume=True, checkpoint=params.get("checkpoint", "latest"), job_id=job_id
            )
        elif kind == "evaluate":
            res = evaluate_run(
                job["run_id"],
                params["split"],
                checkpoint=params.get("checkpoint", "best"),
                progress=lambda i, n: status(
                    state="running", episodes_done=i, episodes_total=n, progress=i / n
                ),
                should_stop=should_stop,
            )
            result = {"file": res["file"], "split": res["split"], "summary": summarize_for_index(res)}
            code = EXIT_COMPLETED
        elif kind == "record":
            result = record_run(
                job["run_id"],
                episode_seed=int(params["episode_seed"]),
                checkpoint=params.get("checkpoint", "best"),
            )
            code = EXIT_COMPLETED
        elif kind == "record_demo":
            result = record_demo(
                params.get("policy", "random"),
                episode_seed=int(params.get("episode_seed", 20_000)),
                action_seed=int(params.get("action_seed", 0)),
            )
            code = EXIT_COMPLETED
        elif kind == "benchmark":
            from lunarlab.benchmark import run_benchmark

            status(state="running", note="measuring throughput")
            result = run_benchmark(
                n_envs_list=tuple(params.get("n_envs", [1, 2, 4, 8])), ppo=bool(params.get("ppo", True))
            )
            code = EXIT_COMPLETED
        elif kind == "report":
            from lunarlab.report import build_report

            result = build_report(
                params["run_ids"],
                title=params.get("title", "LunarLab report"),
                report_id=params["report_id"],
                split=params.get("split", "test"),
            )
            code = EXIT_COMPLETED
        else:
            raise ValueError(f"unknown job kind {kind}")
    except EvaluationAborted:
        code = EXIT_STOPPED
    except Exception as exc:
        import traceback

        error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    final = EXIT_STATE.get(code, "failed")
    if final == "stopped":
        req = read_json(job_stop_file(job_id), default={}) or {}
        if req.get("reason") == "shutdown":
            final = "interrupted"
    if result is not None:
        atomic_write_json(jd / "result.json", result)
    status(state=final, final_state=final, error=error, exit_code=code)
    print(f"[lunarlab] worker {job_id}: {final}", flush=True)
    return code
