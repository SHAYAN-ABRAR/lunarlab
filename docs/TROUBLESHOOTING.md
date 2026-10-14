# Troubleshooting

Start with `.venv\Scripts\python.exe -m lunarlab doctor`. It checks Python, the dependency lock, Box2D,
environment reset/step, rendering, video encoding, writable folders, SQLite, torch and Node.

## Installing

**"No matching distribution" / build errors for Box2D, box2d-py or SWIG**
LunarLab installs the prebuilt `Box2D==2.3.10` wheel, available for CPython 3.10–3.13 on Windows. Errors
usually mean the virtual environment uses Python 3.14. Delete `.venv` and rerun `scripts\setup.ps1`; it
picks 3.12 or 3.13 (via uv, the `py` launcher, or `python`). Do not install `box2d-py` (gymnasium's
`[box2d]` extra): it is source-only and needs SWIG plus Microsoft C++ Build Tools. Retrying the same failed
install will not help.

**pygame fails to install** — same cause: pygame 2.6.1 has Windows wheels up to Python 3.13.

**`setup.ps1` cannot be run / "running scripts is disabled"** — use
`powershell -ExecutionPolicy Bypass -File scripts\setup.ps1`. This bypass applies only to that one
process. LunarLab never changes your execution policy.

**Node.js too old** — Vite 8 requires Node `^20.19.0` or `>=22.12.0`. Install Node 22 LTS. The CLI works
without Node; only the web UI build needs it.

**Linux: torch download is huge** — PyPI's Linux torch includes CUDA. Install the CPU wheel first:
`uv pip install --python .venv/bin/python torch --index-url https://download.pytorch.org/whl/cpu`.

## Running

**"LunarLab is already running (data/backend.lock is held)"** — another backend for this project is
running. Open the printed URL or stop it with `scripts\stop.ps1`. The lock is released automatically if a
process dies.

**Port 8765 in use by another program** — `scripts\start.ps1 -Port 8780`.

**A job stays in "stopping…"** — the worker finishes the current step and, during validation, the current
validation episode before writing the stop checkpoint. That is usually seconds. If it never ends, use
**Force terminate** on the job (no stop checkpoint; resume from the latest periodic checkpoint).
`python -m lunarlab processes` lists this project's server and worker processes;
`scripts\stop.ps1 -Force` terminates them after verifying they belong to this project.

**"Queue paused" after a restart** — jobs that were queued when the backend stopped do not start on their
own. Click *Resume queue* in the sidebar, or cancel them.

**Training "interrupted"** — the backend shut down or the worker died. Open the run and choose
*Resume from latest checkpoint*.

**Heartbeat warning** — if the laptop slept, training was suspended and continues on wake. If the worker
process is gone, the supervisor marks the job interrupted within a few seconds.

**`PermissionError` / "Access is denied" when replacing a file** — on Windows, antivirus real-time scanning
briefly opens freshly written files. LunarLab retries replacements for up to 15 s. If it persists, exclude
the project folder from real-time scanning, or check that no other program holds the file open.

## Video

**Replays show JPEG frames instead of MP4** — the bundled ffmpeg (imageio-ffmpeg) could not encode H.264
when the recording was made. `doctor` shows the reason. The frame player still works with synchronized
telemetry.

## GPU

CPU is the default and usually the fastest choice for this 64×64 MLP. To try a GPU you need a CUDA build of
torch (for an RTX 50-series card, CUDA 12.8 or newer) installed into `.venv`, then `--device cuda` on
`train`. Measure it against CPU with the benchmark before relying on it.
