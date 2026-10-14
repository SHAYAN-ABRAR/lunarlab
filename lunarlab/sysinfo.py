"""Versions, hardware and source-control state recorded with every run."""

from __future__ import annotations

import importlib.metadata as md
import os
import platform
import subprocess
import sys
from functools import lru_cache

import psutil

from lunarlab.storage import project_root

TRACKED_PACKAGES = (
    "gymnasium",
    "Box2D",
    "pygame",
    "stable-baselines3",
    "torch",
    "numpy",
    "pandas",
    "matplotlib",
    "imageio",
    "imageio-ffmpeg",
    "fastapi",
    "uvicorn",
    "pydantic",
    "psutil",
    "PyYAML",
)


def package_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in TRACKED_PACKAGES:
        try:
            out[name] = md.version(name)
        except md.PackageNotFoundError:
            out[name] = None
    return out


@lru_cache(maxsize=1)
def cpu_name() -> str:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            ) as k:
                return str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    elif sys.platform.startswith("linux"):
        try:
            with open("/proc/cpuinfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or "unknown"


def hardware() -> dict:
    vm = psutil.virtual_memory()
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": cpu_name(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "ram_gb": round(vm.total / 1e9, 1),
    }


def torch_info() -> dict:
    try:
        import torch

        return {
            "torch": torch.__version__,
            "cuda_build": torch.version.cuda,
            "cuda_available": bool(torch.cuda.is_available()),
            "num_threads": torch.get_num_threads(),
        }
    except Exception as exc:  # pragma: no cover
        return {"error": str(exc)}


def git_state() -> dict:
    root = project_root()
    if not (root / ".git").exists():
        return {"available": False, "reason": "not a git repository"}
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=5, check=False
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, timeout=5, check=False
        )
        if rev.returncode != 0:
            return {"available": False, "reason": rev.stderr.strip()[:200] or "no commits"}
        return {"available": True, "revision": rev.stdout.strip(), "dirty": bool(status.stdout.strip())}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "reason": str(exc)[:200]}


def snapshot() -> dict:
    return {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "packages": package_versions(),
        "hardware": hardware(),
        "torch": torch_info(),
        "git": git_state(),
        "pid": os.getpid(),
    }
