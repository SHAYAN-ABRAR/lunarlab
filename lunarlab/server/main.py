"""App factory and launcher for the local web application.

Safety model (a local, single-user tool without accounts):

* binds to 127.0.0.1 by default;
* ``TrustedHostMiddleware`` rejects requests whose Host header is not loopback
  (blocks DNS-rebinding attacks);
* state-changing requests must carry ``X-LunarLab: 1`` and, if the browser sends
  an ``Origin``, it must be this app's own origin (or the Vite dev server in dev
  mode). A custom header cannot be sent cross-origin without a CORS preflight,
  which this server never approves for foreign origins;
* request bodies are validated by strict Pydantic schemas; file access goes
  through ``safe_child`` (no arbitrary paths, no traversal).

Shutdown: Ctrl+C in the backend console or ``scripts/stop.ps1`` ends the server.
Before exiting it asks running jobs to stop at a safe boundary (they become
``interrupted`` and can be resumed) and waits for them up to 45 s.
"""

from __future__ import annotations

import contextlib
import os
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from lunarlab import __version__
from lunarlab.db import Database
from lunarlab.jobs import JobManager
from lunarlab.storage import atomic_write_json, data_dir, project_root, utc_now

DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def frontend_dist() -> Path:
    return project_root() / "frontend" / "dist"


def _readiness(app: FastAPI) -> None:
    """Quick capability checks, run once in the background at startup."""
    r = app.state.readiness
    try:
        from lunarlab.env import check_adapter

        check_adapter()
        r["environment"] = {"ok": True, "detail": "LunarLander-v3 reset/step OK"}
    except Exception as exc:
        r["environment"] = {"ok": False, "detail": str(exc)}
    try:
        from lunarlab.recording import mp4_available

        ok, detail = mp4_available()
        r["video"] = {"ok": ok, "detail": detail if ok else f"MP4 unavailable, JPEG fallback: {detail}"}
    except Exception as exc:
        r["video"] = {"ok": False, "detail": str(exc)}
    r["checked"] = True


def create_app(
    *, start_jobs: bool = True, port: int = 8765, dev: bool | None = None, testing: bool = False
) -> FastAPI:
    dev = bool(int(os.environ.get("LUNARLAB_DEV", "0"))) if dev is None else dev

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.db = Database()
        app.state.jobs = JobManager(app.state.db)
        app.state.readiness = {"checked": False, "frontend_built": (frontend_dist() / "index.html").exists()}
        if start_jobs:
            app.state.jobs.start()
            threading.Thread(target=_readiness, args=(app,), daemon=True).start()
            import psutil

            psutil.cpu_percent(interval=None)  # prime the CPU meter
        yield
        if start_jobs:
            result = app.state.jobs.shutdown(grace_s=45)
            if result["still_running"]:
                print(
                    f"[lunarlab] workers still running after the grace period: {result['still_running']}. "
                    "They will be re-adopted on the next start.",
                    file=sys.stderr,
                    flush=True,
                )

    app = FastAPI(
        title="LunarLab",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )

    allowed_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
    if dev:
        allowed_origins |= set(DEV_ORIGINS)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(DEV_ORIGINS),
            allow_methods=["*"],
            allow_headers=["Content-Type", "X-LunarLab"],
        )

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.method in MUTATING:
            origin = request.headers.get("origin")
            if origin is not None and origin not in allowed_origins:
                return JSONResponse({"detail": "cross-origin request refused"}, status_code=403)
            if request.headers.get("x-lunarlab") != "1":
                return JSONResponse({"detail": "missing X-LunarLab header"}, status_code=403)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    hosts = ["127.0.0.1", "localhost", "[::1]"] + (["testserver"] if testing else [])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    from lunarlab.server.api import router

    app.include_router(router)

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        dist = frontend_dist()
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        index = dist / "index.html"
        if not index.exists():
            return JSONResponse(
                {"detail": "Frontend not built. Run scripts/setup.ps1 (or `npm run build` in frontend/)."},
                status_code=503,
            )
        if full_path:
            try:
                from lunarlab.storage import safe_child

                parts = full_path.split("/")
                candidate = dist.resolve()
                for part in parts:
                    candidate = safe_child(candidate, part)
                if candidate.is_file():
                    return FileResponse(candidate)
            except ValueError:
                pass
        return FileResponse(index)

    return app


def serve(host: str = "127.0.0.1", port: int = 8765) -> int:
    import uvicorn

    from lunarlab.locks import FileLock, LockBusy

    if host not in ("127.0.0.1", "localhost", "::1"):
        print(
            f"WARNING: binding to {host} exposes LunarLab beyond this machine. There is no authentication.",
            file=sys.stderr,
        )
    lock = FileLock(data_dir() / "backend.lock")
    try:
        lock.acquire()
    except LockBusy:
        from lunarlab.storage import read_json

        running = read_json(data_dir() / "backend.json", default={}) or {}
        where = running.get("url", "the running instance")
        print(
            f"LunarLab is already running (data/backend.lock is held): {where}. "
            "Use that instance or run scripts/stop.ps1 first.",
            file=sys.stderr,
        )
        return 2
    try:
        import psutil

        me = psutil.Process()
        atomic_write_json(
            data_dir() / "backend.json",
            {
                "pid": os.getpid(),
                "create_time": me.create_time(),
                "host": host,
                "port": port,
                "started_at": utc_now(),
                "url": f"http://127.0.0.1:{port}",
            },
        )
        app = create_app(port=port)
        config = uvicorn.Config(app, host=host, port=port, log_level="warning", access_log=False)
        server = uvicorn.Server(config)
        app.state.uvicorn_server = server
        print(f"LunarLab {__version__} - http://127.0.0.1:{port}  (Ctrl+C to stop)", flush=True)
        server.run()
        return 0
    finally:
        with contextlib.suppress(OSError):
            (data_dir() / "backend.json").unlink()
        lock.release()
