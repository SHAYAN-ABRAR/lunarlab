"""Find (and optionally terminate) LunarLab processes that belong to *this* project.

A process qualifies only if its command line runs ``-m lunarlab serve`` or
``-m lunarlab worker`` **and** its working directory is this project's root (the
launch scripts and the job supervisor always start processes there). A matching
name or a remembered PID alone is never enough.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

import psutil

from lunarlab.storage import project_root


def _norm(p: str | Path) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


def _role(cmdline: list[str]) -> str | None:
    for i in range(len(cmdline) - 2):
        if cmdline[i] == "-m" and cmdline[i + 1] == "lunarlab" and cmdline[i + 2] in ("serve", "worker"):
            return cmdline[i + 2]
    return None


def find_lunarlab_processes() -> list[dict]:
    root = _norm(project_root())
    me = os.getpid()
    out = []
    for p in psutil.process_iter(["pid", "cmdline", "create_time"]):
        try:
            if p.pid == me:
                continue
            cmd = p.info["cmdline"] or []
            role = _role(cmd)
            if role is None or _norm(p.cwd()) != root:
                continue
            out.append(
                {"pid": p.pid, "role": role, "create_time": p.info["create_time"], "cmdline": " ".join(cmd)}
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return out


def terminate(procs: list[dict], timeout: float = 10.0) -> list[tuple[int, str]]:
    """Terminate verified processes (re-verified by PID + creation time immediately before)."""
    results = []
    for info in procs:
        try:
            p = psutil.Process(info["pid"])
            if abs(p.create_time() - info["create_time"]) > 0.5:
                results.append((info["pid"], "skipped: PID now belongs to a different process"))
                continue
            for child in p.children(recursive=True):
                with contextlib.suppress(psutil.Error):
                    child.kill()
            p.kill()
            p.wait(timeout=timeout)
            results.append((info["pid"], "terminated"))
        except psutil.NoSuchProcess:
            results.append((info["pid"], "already exited"))
        except psutil.Error as exc:
            results.append((info["pid"], f"failed: {exc}"))
    return results
