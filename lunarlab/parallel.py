"""Run independent training/evaluation runs in parallel, one process per run.

Each run is a separate ``python -m lunarlab ...`` process with ``OMP_NUM_THREADS=1``
and one torch thread, so ``workers`` processes use about ``workers`` CPU cores.
Runs never share state: each owns its directory and its OS file lock.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Callable

from lunarlab.storage import RunPaths, project_root


def _command(action: str, run_id: str, extra_args: list[str] | None = None) -> list[str]:
    base = [sys.executable, "-m", "lunarlab"]
    if action == "robustness":
        return [*base, "robustness-run", "--run-id", run_id, *(extra_args or [])]
    if action == "train":
        return [*base, "train-run", "--run-id", run_id]
    if action == "resume":
        return [*base, "resume", "--run-id", run_id]
    if action == "test":
        return [*base, "evaluate", "--run-id", run_id, "--split", "test"]
    raise ValueError(f"unknown action {action!r}")


def run_parallel(
    jobs: list[tuple[str, str]],
    *,
    workers: int,
    echo: Callable[[str], None] = print,
    poll_s: float = 2.0,
    extra_args: list[str] | None = None,
) -> dict[str, int]:
    """Run ``(action, run_id)`` jobs with at most ``workers`` processes at a time.

    Returns the exit code of each run. Output of each process is appended to the run's
    ``worker.log``.
    """
    workers = max(1, int(workers))
    pending = list(jobs)
    running: dict[str, tuple[subprocess.Popen, object, str]] = {}
    codes: dict[str, int] = {}
    env = os.environ.copy()
    env.update(
        {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    )
    t0 = time.monotonic()
    while pending or running:
        while pending and len(running) < workers:
            action, rid = pending.pop(0)
            log = open(RunPaths(rid).worker_log, "ab")  # noqa: SIM115 - closed when the process ends
            proc = subprocess.Popen(
                _command(action, rid, extra_args),
                cwd=str(project_root()),
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            running[rid] = (proc, log, action)
            echo(f"  started {action:<6} {rid}  (pid {proc.pid}, {len(running)}/{workers} slots)")
            sys.stdout.flush()
        for rid, (proc, log, action) in list(running.items()):
            code = proc.poll()
            if code is None:
                continue
            log.close()
            codes[rid] = code
            del running[rid]
            mins = (time.monotonic() - t0) / 60
            echo(
                f"  {'done' if code == 0 else f'exit {code}':<7} {action:<6} {rid}  ({mins:.1f} min elapsed)"
            )
            sys.stdout.flush()
        time.sleep(poll_s)
    return codes
