# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Exclusive, non-blocking, process-lifetime file locks (Windows and POSIX).

The OS releases the lock automatically if the holding process dies, so a stale
lock file never blocks a later run.
"""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path


class LockBusy(RuntimeError):
    pass


class FileLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh = None

    def acquire(self) -> FileLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+b")  # noqa: SIM115 - held for the process lifetime
        try:
            if sys.platform == "win32":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            fh.close()
            raise LockBusy(f"{self.path} is held by another process") from exc
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()).encode())
        fh.flush()
        self._fh = fh
        return self

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt

                self._fh.seek(0)
                with contextlib.suppress(OSError):
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> FileLock:
        return self.acquire()

    def __exit__(self, *exc) -> None:
        self.release()


@contextlib.contextmanager
def hold(path: Path, *, timeout_s: float = 30.0, poll_s: float = 0.02):
    """Hold ``path``'s lock for a short critical section, waiting up to ``timeout_s`` for it.

    For read-modify-write of small shared files (run metadata, checkpoint manifests) written by
    different processes. Lock order: a process may take this lock while holding a run's worker lock,
    never the other way round, so the two cannot deadlock.
    """
    import time

    deadline = time.monotonic() + timeout_s
    lock = FileLock(path)
    while True:
        try:
            lock.acquire()
            break
        except LockBusy:
            if time.monotonic() >= deadline:
                raise
            time.sleep(poll_s)
    try:
        yield lock
    finally:
        lock.release()
