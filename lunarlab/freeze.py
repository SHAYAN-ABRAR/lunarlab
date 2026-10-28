# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Final-test freezing: one immutable tested artifact per run, shared by every final-test consumer.

Freezing happens at the first final-test evaluation, under the run's worker lock (the same lock
training holds, so a run can never be frozen while it trains, and two final tests never overlap):

1. the selected checkpoint is resolved and its digest verified against the manifest;
2. its bytes are copied to ``checkpoints/frozen/<sha256>.zip`` (content-addressed, written to a
   temporary name, verified, made read-only) and recorded in ``metadata.json -> frozen_for_test``
   (schema 2) with the configuration, reward and protocol identities.

Afterwards the run never trains again under its run ID (``training._train_locked`` refuses), and the
final test, robustness evaluations, showcase recordings and ghost flights all load the frozen bytes
through :func:`resolve_final_checkpoint`, never a mutable name such as ``best_validation.zip``.

Freezing is not testing: ``metadata.json -> test_attempts`` records each attempt as ``started``,
``completed``, ``interrupted`` or ``failed``. Only a completed attempt (or, for runs tested before
attempts were recorded, a stored test evaluation of the frozen bytes) counts as a completed final
test; an interrupted or failed one is retried on the same frozen checkpoint.

Legacy records (schema 1: checkpoint name and digest only) still resolve while the named file still
has the recorded bytes. :func:`migrate_legacy_freeze` creates the immutable copy explicitly and logs
it; when the bytes are gone, nothing is substituted and the historical results stay historical.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import stat
from pathlib import Path
from typing import Any

from lunarlab.runs import (
    RunError,
    load_config,
    load_metadata,
    log_event,
    mutate_metadata,
    read_manifest,
    resolve_checkpoint,
)
from lunarlab.storage import RunPaths, read_json, sha256_file, utc_now

FROZEN_SCHEMA = 2


def _artifact_rel(sha: str) -> str:
    return f"checkpoints/frozen/{sha}.zip"


def _write_immutable_copy(src: Path, paths: RunPaths, sha: str) -> Path:
    """Copy ``src`` to the content-addressed frozen location; verify; make it read-only."""
    paths.frozen.mkdir(parents=True, exist_ok=True)
    return immutable_copy(src, paths.root / _artifact_rel(sha), sha)


def immutable_copy(src: Path, dst: Path, sha: str) -> Path:
    """Copy ``src`` (whose SHA-256 must be ``sha``) to ``dst``, verify the copy and make it read-only.

    An existing ``dst`` is kept only if it already holds those bytes; otherwise nothing is overwritten. The
    copy is written to a temporary name and renamed after its digest is checked, so a partly written file
    never appears under ``dst``. Used for the main pipeline's frozen final-test checkpoints and for the
    generic audit study (:mod:`lunarlab.audit.study`).
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if sha256_file(dst) != sha:
            raise RunError(f"{dst.name} exists with different bytes; refusing to overwrite a frozen artifact")
        return dst
    tmp = dst.with_name(f".{dst.name}.{os.getpid()}.tmp")
    try:
        with open(src, "rb") as fi, open(tmp, "wb") as fo:
            shutil.copyfileobj(fi, fo)
            fo.flush()
            os.fsync(fo.fileno())
        if sha256_file(tmp) != sha:
            raise RunError("the checkpoint changed while it was being frozen")
        os.replace(tmp, dst)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()
    with contextlib.suppress(OSError):
        os.chmod(dst, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    return dst


def freeze_for_test(run_id: str, checkpoint: str = "best") -> dict:
    """Freeze ``checkpoint`` for the final test. The caller must hold the run's worker lock."""
    cfg = load_config(run_id)
    paths = RunPaths(run_id)
    src, entry = resolve_checkpoint(run_id, checkpoint)  # digest verified against the manifest
    artifact = _write_immutable_copy(src, paths, entry["sha256"])
    frozen = {
        "schema": FROZEN_SCHEMA,
        "checkpoint": entry["name"],
        "checkpoint_kind": entry.get("kind"),
        "checkpoint_sha256": entry["sha256"],
        "checkpoint_transitions": entry.get("transitions"),
        "artifact": artifact.relative_to(paths.root).as_posix(),
        "config_hash": cfg.config_hash(),
        "reward_hash": cfg.reward.content_hash(),
        "protocol_id": cfg.eval_protocol.protocol_id,
        "protocol_hash": cfg.eval_protocol.protocol_hash(),
        "source_entry": entry,
        "frozen_at": utc_now(),
    }

    def put(meta: dict) -> None:
        if meta.get("frozen_for_test"):
            raise RunError("this run was frozen concurrently by another process")
        meta["frozen_for_test"] = frozen

    mutate_metadata(run_id, put)
    log_event(
        paths,
        "info",
        "run frozen for final test evaluation",
        checkpoint=entry["name"],
        sha256=entry["sha256"],
    )
    return frozen


def _legacy_path(run_id: str, frozen: dict) -> Path:
    """A schema-1 record: the named file, only if it still has the recorded bytes."""
    paths = RunPaths(run_id)
    p = paths.checkpoints / frozen["checkpoint"]
    if not p.exists() or sha256_file(p) != frozen["checkpoint_sha256"]:
        raise RunError(
            f"the checkpoint tested at freeze time ({frozen['checkpoint']}, SHA-256 "
            f"{frozen['checkpoint_sha256'][:12]}…) is no longer available: the file is missing or now holds "
            "different bytes. The historical final-test results remain evidence of what was measured then, "
            "but they cannot be re-run from this run directory, and no other checkpoint is used in its place."
        )
    return p


def resolve_frozen_checkpoint(run_id: str) -> tuple[Path, dict]:
    """The frozen artifact of a run, verified against its digest (RunError if absent or altered)."""
    frozen = load_metadata(run_id).get("frozen_for_test")
    if not frozen:
        raise RunError("this run has not been frozen for the final test")
    paths = RunPaths(run_id)
    if frozen.get("artifact"):
        p = paths.root / frozen["artifact"]
        if not p.exists():
            raise RunError(f"the frozen artifact {frozen['artifact']} is missing")
        if sha256_file(p) != frozen["checkpoint_sha256"]:
            raise RunError(f"the frozen artifact {frozen['artifact']} does not match its recorded SHA-256")
        return p, {**frozen, "legacy": False}
    return _legacy_path(run_id, frozen), {**frozen, "legacy": True}


def frozen_artifact_for(run_id: str, sha256: str) -> Path | None:
    """The run's frozen artifact if it holds exactly these bytes (used by warm restarts)."""
    frozen = load_metadata(run_id).get("frozen_for_test") or {}
    if frozen.get("checkpoint_sha256") != sha256:
        return None
    with contextlib.suppress(RunError):
        return resolve_frozen_checkpoint(run_id)[0]
    return None


def entry_for_frozen(info: dict) -> dict:
    """A manifest-like entry describing the frozen checkpoint (for results and labels)."""
    src = dict(info.get("source_entry") or {})
    return {
        **src,
        "name": info["checkpoint"],
        "sha256": info["checkpoint_sha256"],
        "transitions": info.get("checkpoint_transitions", src.get("transitions")),
        "frozen": True,
        "frozen_artifact": info.get("artifact"),
        "frozen_legacy": info.get("legacy", False),
    }


def resolve_final_checkpoint(run_id: str, *, require_frozen: bool = False) -> tuple[Path, dict]:
    """What final-test consumers evaluate: the frozen bytes if the run is frozen, otherwise (unless
    ``require_frozen``) the validation-selected checkpoint, labelled as not yet frozen."""
    meta = load_metadata(run_id)
    if meta.get("frozen_for_test"):
        path, info = resolve_frozen_checkpoint(run_id)
        if info.get("source_entry") is None:  # legacy: describe it from the manifest when possible
            match = next(
                (
                    c
                    for c in read_manifest(RunPaths(run_id))["checkpoints"]
                    if c["sha256"] == info["checkpoint_sha256"]
                ),
                None,
            )
            info = {**info, "source_entry": match}
        return path, entry_for_frozen(info)
    if require_frozen:
        raise RunError("this run has not been frozen for the final test yet")
    path, entry = resolve_checkpoint(run_id, "best")
    return path, {**entry, "frozen": False}


# --------------------------------------------------------------------------- #
# Attempts and completion
# --------------------------------------------------------------------------- #


def start_attempt(run_id: str, sha256: str) -> int:
    """Record a final-test attempt of the frozen checkpoint as started; returns its index."""
    index: list[int] = []

    def add(meta: dict) -> None:
        attempts = meta.setdefault("test_attempts", [])
        index.append(len(attempts))
        attempts.append(
            {
                "attempt": len(attempts),
                "checkpoint_sha256": sha256,
                "state": "started",
                "started_at": utc_now(),
            }
        )

    mutate_metadata(run_id, add)
    return index[0]


def finish_attempt(run_id: str, attempt: int, state: str, **info: Any) -> None:
    """Mark a final-test attempt completed, interrupted or failed, and update the completed-test count."""

    def done(meta: dict) -> None:
        a = meta["test_attempts"][attempt]
        a.update(state=state, ended_at=utc_now(), **info)
        meta["test_evaluations"] = completed_test_count(meta, run_id)

    mutate_metadata(run_id, done)


def _legacy_completed(run_id: str, sha256: str) -> list[str]:
    """Test evaluation files of these bytes written before attempts were recorded."""
    out = []
    for p in sorted(RunPaths(run_id).evaluations.glob("test-*.json")):
        r = read_json(p, default=None) or {}
        if (r.get("checkpoint") or {}).get("sha256") == sha256 and "aggregate" in r and "attempt" not in r:
            out.append(p.name)
    return out


def completed_test_count(meta: dict, run_id: str) -> int:
    """Completed final tests of the frozen checkpoint, including test files written before attempts were recorded."""
    frozen = meta.get("frozen_for_test") or {}
    sha = frozen.get("checkpoint_sha256")
    if not sha:
        return 0
    recorded = [
        a
        for a in meta.get("test_attempts", [])
        if a.get("state") == "completed" and a.get("checkpoint_sha256") == sha
    ]
    return len(recorded) + len(_legacy_completed(run_id, sha))


def test_status(run_id: str) -> dict:
    """Frozen identity, every attempt, and whether a completed final test exists."""
    meta = load_metadata(run_id)
    frozen = meta.get("frozen_for_test")
    attempts = list(meta.get("test_attempts", []))
    sha = (frozen or {}).get("checkpoint_sha256")
    legacy = _legacy_completed(run_id, sha) if sha else []
    completed = completed_test_count(meta, run_id) > 0
    last = attempts[-1]["state"] if attempts else ("completed" if legacy else None)
    return {
        "frozen": bool(frozen),
        "frozen_for_test": frozen,
        "immutable_artifact": bool((frozen or {}).get("artifact")),
        "attempts": attempts,
        "legacy_completed_files": legacy,
        "completed": completed,
        "completed_count": completed_test_count(meta, run_id),
        "last_state": last,
        "needs_retry": bool(frozen) and not completed,
    }


def pending_final_tests(run_ids: list[str]) -> list[str]:
    """Runs that finished training but have no completed final test (frozen-only counts as pending)."""
    out = []
    for rid in run_ids:
        entries = read_manifest(RunPaths(rid)).get("checkpoints", [])
        if not any(c["kind"] == "final" for c in entries):
            continue
        if load_metadata(rid).get("tuning"):
            continue
        if not test_status(rid)["completed"]:
            out.append(rid)
    return out


# --------------------------------------------------------------------------- #
# Explicit migration of legacy freeze records
# --------------------------------------------------------------------------- #


def migrate_legacy_freeze(run_id: str) -> dict:
    """Create the immutable copy for a schema-1 freeze record, only if the tested bytes are intact.

    Never substitutes another checkpoint; reports instead. Logged in the run's event log.
    """
    from lunarlab.locks import FileLock, LockBusy

    meta = load_metadata(run_id)
    frozen = meta.get("frozen_for_test")
    if not frozen:
        return {"run_id": run_id, "migrated": False, "reason": "not frozen"}
    if frozen.get("artifact"):
        return {"run_id": run_id, "migrated": False, "reason": "already has an immutable artifact"}
    paths = RunPaths(run_id)
    try:
        lock = FileLock(paths.lock).acquire()
    except LockBusy:
        return {"run_id": run_id, "migrated": False, "reason": "the run is busy (training or being tested)"}
    try:
        try:
            src = _legacy_path(run_id, frozen)
        except RunError as exc:
            log_event(
                paths, "warning", "legacy freeze not migrated: tested bytes unavailable", detail=str(exc)
            )
            return {"run_id": run_id, "migrated": False, "reason": str(exc)}
        artifact = _write_immutable_copy(src, paths, frozen["checkpoint_sha256"])
        rel = artifact.relative_to(paths.root).as_posix()

        def upgrade(m: dict) -> None:
            f = m["frozen_for_test"]
            f.update(schema=FROZEN_SCHEMA, artifact=rel, migrated_from_schema=1, migrated_at=utc_now())

        mutate_metadata(run_id, upgrade)
        log_event(paths, "info", "legacy freeze migrated to an immutable artifact", artifact=rel)
        return {"run_id": run_id, "migrated": True, "artifact": rel}
    finally:
        lock.release()
