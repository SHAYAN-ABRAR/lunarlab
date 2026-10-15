"""Local storage: data root, run directories, atomic writes and path safety.

Layout (under the LunarLab home, default = project root)::

    data/lunarlab.sqlite          lightweight metadata index
    data/demos/<demo_id>/         random / heuristic demonstrations
    runs/<run_id>/
        config.yaml               exact RunConfig (immutable after creation)
        metadata.json             versions, hardware, git, lineage, segments
        status.json               worker heartbeat (atomic writes)
        events.jsonl              human-readable event log (bounded)
        episodes.csv              one row per *training* episode
        metrics.jsonl             PPO diagnostics, one row per update
        control/                  stop requests from the supervisor
        evaluations/              validation history + evaluation results
        checkpoints/              *.zip + manifest.json (sha256 per file)
        trajectories/ videos/ figures/ reports/
"""

from __future__ import annotations

import contextlib
import csv
import datetime as _dt
import hashlib
import json
import os
import re
import secrets
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,95}$")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,127}$")
MAX_EVENTS_BYTES = 2_000_000  # events.jsonl is rotated once beyond this size


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def home() -> Path:
    """LunarLab home. Override with the LUNARLAB_HOME environment variable."""
    env = os.environ.get("LUNARLAB_HOME")
    return Path(env).resolve() if env else project_root()


def data_dir() -> Path:
    p = home() / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def runs_dir() -> Path:
    p = home() / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def demos_dir() -> Path:
    p = data_dir() / "demos"
    p.mkdir(parents=True, exist_ok=True)
    return p


def flights_dir() -> Path:
    """Keyboard flights (``lunarlab.play``): recordings with policy kind ``human``."""
    p = data_dir() / "flights"
    p.mkdir(parents=True, exist_ok=True)
    return p


def reports_dir() -> Path:
    p = home() / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def new_id(*parts: str, prefix: str = "") -> str:
    """Immutable, sortable id: ``[prefix-]YYYYMMDD-HHMMSS-<parts>-<4 hex>``."""
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    clean = [re.sub(r"[^A-Za-z0-9]+", "-", p).strip("-").lower()[:24] for p in parts if p]
    head = [prefix] if prefix else []
    return "-".join([*head, stamp, *clean, secrets.token_hex(2)])


def validate_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not RUN_ID_RE.match(run_id):
        raise ValueError(f"invalid id: {run_id!r}")
    return run_id


def safe_child(base: Path, *parts: str) -> Path:
    """Join ``parts`` under ``base`` and refuse anything that escapes it.

    Each part must be a plain name (no separators, no '..', no drive letters).
    """
    base_r = base.resolve()
    for p in parts:
        if not isinstance(p, str) or not SAFE_NAME_RE.match(p) or p in (".", ".."):
            raise ValueError(f"unsafe path component: {p!r}")
    target = base_r.joinpath(*parts).resolve()
    if target != base_r and base_r not in target.parents:
        raise ValueError("path escapes its base directory")
    return target


# --------------------------------------------------------------------------- #
# Atomic file writes
# --------------------------------------------------------------------------- #


def replace_file(src: str | Path, dst: Path, timeout_s: float = 15.0) -> None:
    """``os.replace`` that tolerates brief sharing violations on Windows.

    Windows refuses to replace a file that another process has open. Readers in
    LunarLab open-read-close quickly, but antivirus real-time scanners commonly
    open freshly written files (such as new checkpoints) for a moment too.
    """
    deadline = time.monotonic() + timeout_s
    delay = 0.02
    while True:
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 1.6, 0.5)


def _replace_with_retry(src: str, dst: Path) -> None:
    replace_file(src, dst, timeout_s=30.0)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        _replace_with_retry(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, obj: Any) -> None:
    atomic_write_text(path, json.dumps(obj, indent=2, sort_keys=False, default=_json_default))


def _json_default(o: Any):
    try:
        import numpy as np

        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:  # pragma: no cover
        pass
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"not JSON serializable: {type(o).__name__}")


def read_json(path: Path, default: Any = None) -> Any:
    for attempt in range(5):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return default
        except (json.JSONDecodeError, PermissionError):
            if attempt == 4:
                return default
            time.sleep(0.02)
    return default


def write_yaml(path: Path, obj: Any) -> None:
    atomic_write_text(path, yaml.safe_dump(obj, sort_keys=False, allow_unicode=True))


def read_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def append_jsonl(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.name == "events.jsonl" and path.exists() and path.stat().st_size > MAX_EVENTS_BYTES:
        rotated = path.with_suffix(".1.jsonl")
        with contextlib.suppress(OSError):
            os.replace(path, rotated)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, default=_json_default) + "\n")


def read_jsonl(path: Path, limit: int | None = None) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a partially written last line during a crash
    return rows[-limit:] if limit else rows


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Run directories
# --------------------------------------------------------------------------- #


class RunPaths:
    def __init__(self, run_id: str, root: Path | None = None) -> None:
        self.run_id = validate_run_id(run_id)
        self.root = (root or runs_dir()) / run_id

    @property
    def config(self) -> Path:
        return self.root / "config.yaml"

    @property
    def metadata(self) -> Path:
        return self.root / "metadata.json"

    @property
    def status(self) -> Path:
        return self.root / "status.json"

    @property
    def events(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def episodes(self) -> Path:
        return self.root / "episodes.csv"

    @property
    def metrics(self) -> Path:
        return self.root / "metrics.jsonl"

    @property
    def control(self) -> Path:
        return self.root / "control"

    @property
    def stop_request(self) -> Path:
        return self.control / "stop_requested.json"

    @property
    def lock(self) -> Path:
        return self.root / ".worker.lock"

    @property
    def evaluations(self) -> Path:
        return self.root / "evaluations"

    @property
    def validation_history(self) -> Path:
        return self.evaluations / "validation_history.jsonl"

    @property
    def checkpoints(self) -> Path:
        return self.root / "checkpoints"

    @property
    def checkpoint_manifest(self) -> Path:
        return self.checkpoints / "manifest.json"

    @property
    def trajectories(self) -> Path:
        return self.root / "trajectories"

    @property
    def videos(self) -> Path:
        return self.root / "videos"

    @property
    def figures(self) -> Path:
        return self.root / "figures"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def worker_log(self) -> Path:
        return self.root / "worker.log"

    def exists(self) -> bool:
        return self.config.exists()

    def create_dirs(self) -> None:
        for d in (
            self.root,
            self.control,
            self.evaluations,
            self.checkpoints,
            self.trajectories,
            self.videos,
            self.figures,
            self.reports,
        ):
            d.mkdir(parents=True, exist_ok=True)


def list_run_ids() -> list[str]:
    out = []
    for p in sorted(runs_dir().iterdir()) if runs_dir().exists() else []:
        if p.is_dir() and RUN_ID_RE.match(p.name) and (p / "config.yaml").exists():
            out.append(p.name)
    return out


class CsvAppender:
    """Append rows to a CSV with a fixed header, buffering between flushes."""

    def __init__(self, path: Path, fieldnames: Iterable[str]) -> None:
        self.path = path
        self.fieldnames = list(fieldnames)
        self._buffer: list[dict] = []
        if not path.exists() or path.stat().st_size == 0:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=self.fieldnames).writeheader()

    def add(self, row: dict) -> None:
        self._buffer.append(row)

    def flush(self) -> None:
        if not self._buffer:
            return
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=self.fieldnames, extrasaction="ignore")
            w.writerows(self._buffer)
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)
