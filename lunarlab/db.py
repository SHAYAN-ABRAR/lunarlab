# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""SQLite metadata: jobs, reward-configuration revisions, settings.

Large artifacts (checkpoints, telemetry, videos, episode logs) stay in files.
Physics-rate data is never written here. WAL mode lets the backend, the CLI and
workers read concurrently.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from lunarlab.rewards.config import RewardConfig, all_presets
from lunarlab.storage import data_dir, new_id, utc_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS reward_configs (
    id TEXT PRIMARY KEY,
    family TEXT NOT NULL,
    revision INTEGER NOT NULL,
    parent_id TEXT,
    name TEXT NOT NULL,
    preset TEXT NOT NULL,
    builtin INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(family, revision)
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    lane TEXT NOT NULL,
    run_id TEXT,
    params_json TEXT NOT NULL,
    state TEXT NOT NULL,
    idempotency_key TEXT UNIQUE,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    heartbeat_at TEXT,
    pid INTEGER,
    pid_create_time REAL,
    exit_code INTEGER,
    error TEXT,
    progress_json TEXT,
    result_json TEXT,
    log_path TEXT
);
CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS jobs_run ON jobs(run_id);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

ACTIVE_STATES = ("queued", "starting", "running", "stop_requested")
FINAL_STATES = ("stopped", "completed", "failed", "interrupted")
JOB_STATES = ACTIVE_STATES + FINAL_STATES


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (data_dir() / "lunarlab.sqlite")
        self._lock = threading.RLock()
        with self.connect() as c:
            c.executescript(SCHEMA)
        self.seed_builtin_presets()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        with self._lock, self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                yield c
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise

    # ------------------------------------------------------------------ #
    # Reward configurations (immutable revisions)
    # ------------------------------------------------------------------ #
    def seed_builtin_presets(self) -> None:
        with self.transaction() as c:
            for cfg in all_presets():
                family = f"preset-{cfg.preset}"
                row = c.execute(
                    "SELECT id FROM reward_configs WHERE family=? AND revision=1", (family,)
                ).fetchone()
                if row is None:
                    c.execute(
                        "INSERT INTO reward_configs (id,family,revision,parent_id,name,preset,builtin,content_hash,config_json,created_at)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (
                            family + "-r1",
                            family,
                            1,
                            None,
                            cfg.name,
                            cfg.preset,
                            1,
                            cfg.content_hash(),
                            cfg.model_dump_json(),
                            utc_now(),
                        ),
                    )

    def _reward_row(self, r: sqlite3.Row) -> dict[str, Any]:
        cfg = json.loads(r["config_json"])
        return {
            "id": r["id"],
            "family": r["family"],
            "revision": r["revision"],
            "parent_id": r["parent_id"],
            "name": r["name"],
            "preset": r["preset"],
            "builtin": bool(r["builtin"]),
            "content_hash": r["content_hash"],
            "created_at": r["created_at"],
            "config": cfg,
        }

    def list_reward_configs(self) -> list[dict[str, Any]]:
        with self.connect() as c:
            rows = c.execute(
                "SELECT * FROM reward_configs ORDER BY builtin DESC, family, revision"
            ).fetchall()
        return [self._reward_row(r) for r in rows]

    def get_reward_config(self, config_id: str) -> dict[str, Any]:
        with self.connect() as c:
            r = c.execute("SELECT * FROM reward_configs WHERE id=?", (config_id,)).fetchone()
        if r is None:
            raise KeyError(config_id)
        return self._reward_row(r)

    def create_reward_config(self, cfg: RewardConfig, *, parent_id: str | None = None) -> dict[str, Any]:
        """Create a new family (no parent) or a new revision of the parent's family.

        Existing revisions are never modified, so a run that references one keeps
        exactly the reward it was trained with.
        """
        with self.transaction() as c:
            if parent_id:
                parent = c.execute("SELECT * FROM reward_configs WHERE id=?", (parent_id,)).fetchone()
                if parent is None:
                    raise KeyError(parent_id)
                if parent["builtin"]:
                    family = new_id(cfg.name, prefix="rc")
                    revision = 1
                else:
                    family = parent["family"]
                    revision = (
                        c.execute(
                            "SELECT MAX(revision) FROM reward_configs WHERE family=?", (family,)
                        ).fetchone()[0]
                        + 1
                    )
            else:
                family = new_id(cfg.name, prefix="rc")
                revision = 1
            cid = f"{family}-r{revision}"
            c.execute(
                "INSERT INTO reward_configs (id,family,revision,parent_id,name,preset,builtin,content_hash,config_json,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    cid,
                    family,
                    revision,
                    parent_id,
                    cfg.name,
                    cfg.preset,
                    0,
                    cfg.content_hash(),
                    cfg.model_dump_json(),
                    utc_now(),
                ),
            )
        return self.get_reward_config(cid)

    # ------------------------------------------------------------------ #
    # Jobs
    # ------------------------------------------------------------------ #
    @staticmethod
    def job_row(r: sqlite3.Row | None) -> dict[str, Any] | None:
        if r is None:
            return None
        d = dict(r)
        for k in ("params_json", "progress_json", "result_json"):
            d[k.removesuffix("_json")] = json.loads(d.pop(k)) if d.get(k) else None
        return d

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as c:
            return self.job_row(c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def job_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        with self.connect() as c:
            return self.job_row(c.execute("SELECT * FROM jobs WHERE idempotency_key=?", (key,)).fetchone())

    def list_jobs(self, *, states: tuple[str, ...] | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as c:
            if states:
                q = f"SELECT * FROM jobs WHERE state IN ({','.join('?' * len(states))}) ORDER BY created_at DESC LIMIT ?"
                rows = c.execute(q, (*states, limit)).fetchall()
            else:
                rows = c.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self.job_row(r) for r in rows]

    def update_job(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        for k in ("params", "progress", "result"):
            if k in fields:
                fields[f"{k}_json"] = json.dumps(fields.pop(k), default=str)
        cols = ", ".join(f"{k}=?" for k in fields)
        with self.transaction() as c:
            c.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), job_id))

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.connect() as c:
            r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(r["value"]) if r else default

    def set_setting(self, key: str, value: Any) -> None:
        with self.transaction() as c:
            c.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)),
            )
