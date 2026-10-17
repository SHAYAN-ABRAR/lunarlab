# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""``python -m lunarlab doctor``: verify the installation with actionable messages."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable

from lunarlab.storage import data_dir, home, project_root, reports_dir, runs_dir

OK, WARN, FAIL = "OK", "WARN", "FAIL"
NODE_MIN = ((20, 19), (22, 12))  # Vite 8 requires Node ^20.19.0 || >=22.12.0


def _check(name: str, fn: Callable[[], tuple[str, str]]) -> dict:
    t0 = time.perf_counter()
    try:
        level, detail = fn()
    except Exception as exc:
        level, detail = FAIL, f"{type(exc).__name__}: {exc}"
    return {"check": name, "level": level, "detail": detail, "seconds": round(time.perf_counter() - t0, 2)}


def check_python() -> tuple[str, str]:
    v = sys.version_info
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    detail = f"{sys.version.split()[0]} at {sys.executable}" + (
        "" if in_venv else " (not a virtual environment)"
    )
    if v >= (3, 14):
        return (
            FAIL,
            detail
            + " — Box2D and pygame have no Windows wheels for 3.14; use Python 3.12 or 3.13 (see README).",
        )
    if v < (3, 10):
        return FAIL, detail + " — Python 3.10+ required."
    return (OK if in_venv else WARN), detail


def check_lock() -> tuple[str, str]:
    import importlib.metadata as md

    lock = project_root() / "requirements.lock"
    if not lock.exists():
        return WARN, "requirements.lock not found"
    mismatches, checked = [], 0
    for line in lock.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)(\s*;\s*(.+))?$", line.strip())
        if not m:
            continue
        name, want, marker = m.group(1), m.group(2), m.group(4)
        if marker:
            try:
                from packaging.markers import Marker

                if not Marker(marker).evaluate():
                    continue
            except Exception:
                continue
        checked += 1
        try:
            have = md.version(name)
        except md.PackageNotFoundError:
            mismatches.append(f"{name} missing (lock {want})")
            continue
        if have.split("+")[0] != want.split("+")[0]:
            mismatches.append(f"{name} {have} (lock {want})")
    if mismatches:
        return WARN, f"{len(mismatches)} of {checked} differ from the lock: " + "; ".join(mismatches[:8])
    return OK, f"{checked} locked packages match"


def check_box2d() -> tuple[str, str]:
    try:
        import Box2D  # noqa: N813
    except ImportError as exc:
        return FAIL, (
            f"cannot import Box2D ({exc}). Install the prebuilt wheel: pip install Box2D==2.3.10 "
            "(wheels exist for CPython 3.10–3.13). Building box2d-py from source needs SWIG and "
            "Microsoft C++ Build Tools; LunarLab does not need that path."
        )
    return OK, f"Box2D {Box2D.__version__}"


def check_env() -> tuple[str, str]:
    from lunarlab.env import TESTED_GYMNASIUM_VERSIONS, check_adapter, environment_record

    rec = environment_record()
    check_adapter()
    detail = (
        f"{rec['env_id']} gymnasium {rec['gymnasium_version']}, max_episode_steps={rec['max_episode_steps']}, "
        f"gravity={rec['gravity']}, wind={rec['enable_wind']}, reset/step + internals adapter OK"
    )
    if rec["gymnasium_version"] not in TESTED_GYMNASIUM_VERSIONS:
        return (
            WARN,
            detail + f" — untested gymnasium version (tested: {', '.join(TESTED_GYMNASIUM_VERSIONS)})",
        )
    return OK, detail


def check_render() -> tuple[str, str]:
    from lunarlab.env import make_env

    env = make_env(render_mode="rgb_array")
    try:
        env.reset(seed=0)
        frame = env.render()
    finally:
        env.close()
    if frame is None or frame.ndim != 3:
        return FAIL, "rgb_array rendering returned no frame (is pygame installed?)"
    return OK, f"rgb_array frame {tuple(frame.shape)}"


def check_video() -> tuple[str, str]:
    from lunarlab.recording import mp4_available

    ok, detail = mp4_available()
    if ok:
        return OK, f"H.264 MP4 encode+decode verified ({detail})"
    return WARN, f"MP4 unavailable ({detail}); recordings fall back to JPEG frame sequences"


def check_dirs() -> tuple[str, str]:
    for d in (data_dir(), runs_dir(), reports_dir()):
        with tempfile.NamedTemporaryFile(dir=d, delete=True) as f:
            f.write(b"ok")
    free = shutil.disk_usage(home()).free / 1e9
    level = OK if free > 5 else WARN
    return level, f"writable: {home()} (free disk {free:.1f} GB)"


def check_sqlite() -> tuple[str, str]:
    from lunarlab.db import Database

    db = Database()
    n = len(db.list_reward_configs())
    return OK, f"{db.path} ({n} reward configurations)"


def check_torch() -> tuple[str, str]:
    import torch

    cuda = torch.cuda.is_available()
    return OK, (
        f"torch {torch.__version__}, CUDA build {torch.version.cuda or 'none'}, CUDA available {cuda}. "
        "CPU is the default device for this small MLP workload."
    )


def check_node() -> tuple[str, str]:
    dist = project_root() / "frontend" / "dist" / "index.html"
    node = shutil.which("node")
    if not node:
        if dist.exists():
            return OK, "Node not found, but the built frontend exists (Node is only needed to rebuild it)"
        return WARN, "Node not found and frontend not built. Install Node 22 LTS (>=22.12) to build the UI."
    out = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
    m = re.match(r"v(\d+)\.(\d+)", out)
    ver = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    ok = (ver[0] == 20 and ver >= NODE_MIN[0]) or ver >= NODE_MIN[1]
    built = "built" if dist.exists() else "not built yet (run scripts/setup.ps1)"
    return (
        OK if ok else FAIL
    ), f"node {out} ({'meets' if ok else 'below'} Vite's ^20.19 || >=22.12); frontend {built}"


CHECKS: list[tuple[str, Callable[[], tuple[str, str]]]] = [
    ("python", check_python),
    ("dependency lock", check_lock),
    ("box2d", check_box2d),
    ("environment", check_env),
    ("rendering", check_render),
    ("video encoding", check_video),
    ("directories", check_dirs),
    ("sqlite", check_sqlite),
    ("torch", check_torch),
    ("node / frontend", check_node),
]


def run_doctor() -> list[dict]:
    return [_check(name, fn) for name, fn in CHECKS]


def print_report(results: list[dict]) -> int:
    colors = {OK: "\033[32m", WARN: "\033[33m", FAIL: "\033[31m"}
    use_color = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
    for r in results:
        tag = f"{colors[r['level']]}{r['level']:<4}\033[0m" if use_color else f"{r['level']:<4}"
        print(f"[{tag}] {r['check']:<16} {r['detail']}")
    fails = sum(r["level"] == FAIL for r in results)
    warns = sum(r["level"] == WARN for r in results)
    print(f"\n{len(results) - fails - warns} ok, {warns} warning(s), {fails} failure(s). Home: {home()}")
    return 1 if fails else 0
