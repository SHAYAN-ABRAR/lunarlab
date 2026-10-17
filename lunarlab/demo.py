# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Static, read-only snapshot of the API for the hosted demo (GitHub Pages).

Every file is produced by calling the real API in-process (FastAPI's TestClient), so the
demo shows exactly what the local app shows for the same data. Lists are filtered to the
exported experiments, runs and recordings, and absolute local paths are scrubbed.

File names: ``demo_name("/api/runs/x/curve")`` maps an API path (with its query string) to a
flat, URL-safe name; the frontend's demo mode applies the same mapping.

Provenance (manifest ``demo.json``, schema 2). A **release** export requires a clean, attributable
source tree (changes inside the output directory itself do not count) and records the full export
revision. ``draft=True`` (``export-demo --draft``) allows uncommitted changes and labels the snapshot
as a draft everywhere it is shown. The manifest also records the dependency-lock digests, the metric,
protocol and schema versions, every exported file's SHA-256, and per run the training-code revisions
and the evaluation files used (with their digests and evaluation-code revisions where recorded).
Snapshots exported earlier keep the provenance they were written with.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

from lunarlab.runs import RunError
from lunarlab.storage import project_root, utc_now

_SAFE = re.compile(r"[A-Za-z0-9.\-]")
DEMO_PAIRS = 40


def demo_name(path: str) -> str:
    """'/api/runs/a-b/events?limit=120' -> 'runs_2fa-b_2fevents_3flimit_3d120'."""
    p = path.removeprefix("/api/")
    return "".join(ch if _SAFE.fullmatch(ch) else f"_{ord(ch):02x}" for ch in p)


def fnv1a(text: str) -> str:
    """32-bit FNV-1a, hex (the frontend computes the same hash)."""
    h = 0x811C9DC5
    for b in text.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def compare_key(run_ids: list[str], split: str) -> str:
    return fnv1a(f"{split}:{','.join(sorted(run_ids))}")


class _Scrubber:
    def __init__(self, needles: list[str]) -> None:
        variants = set()
        for n in needles:
            if n:
                variants |= {n, n.replace("\\", "/"), n.replace("/", "\\")}
        self.needles = sorted(variants, key=len, reverse=True)

    def __call__(self, obj: Any) -> Any:
        if isinstance(obj, str):
            for n in self.needles:
                if n.lower() in obj.lower():
                    obj = re.sub(re.escape(n), "<local>", obj, flags=re.IGNORECASE)
            return obj
        if isinstance(obj, list):
            return [self(v) for v in obj]
        if isinstance(obj, dict):
            return {k: self(v) for k, v in obj.items()}
        return obj


def _round(obj: Any) -> Any:
    """Floats to 6 significant digits: plenty for display, and a smaller snapshot."""
    if isinstance(obj, float):
        return float(f"{obj:.6g}")
    if isinstance(obj, list):
        return [_round(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    return obj


def _git_dirty() -> bool | None:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"], cwd=project_root(), capture_output=True, text=True, timeout=10
        )
        return bool(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return None


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root(),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


class DemoExportError(RunError):
    """A release export was asked for from a source tree that cannot be attributed to a revision."""


def dirty_paths(porcelain: str, exclude: str | None) -> list[str]:
    """Changed paths from ``git status --porcelain``, ignoring those under ``exclude`` (repo-relative)."""
    out = []
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip('"')
        if exclude and (path == exclude.rstrip("/") or path.startswith(exclude.rstrip("/") + "/")):
            continue
        out.append(path)
    return out


def source_state(exclude: Path | None = None) -> dict[str, Any]:
    """Full revision of the exporting source tree and whether it has uncommitted changes."""
    root = project_root()
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10
        )
        st = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "reason": str(exc)[:200]}
    if rev.returncode != 0 or st.returncode != 0:
        return {"available": False, "reason": (rev.stderr or st.stderr).strip()[:200] or "not a git checkout"}
    rel = None
    if exclude is not None:
        try:
            rel = exclude.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel = None  # outside the repository: cannot make it dirty
    changed = dirty_paths(st.stdout, rel)
    return {
        "available": True,
        "revision": rev.stdout.strip(),
        "dirty": bool(changed),
        "changed_paths": len(changed),
    }


def _sha(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _run_sources(run_ids: list[str]) -> dict[str, Any]:
    from lunarlab.runs import load_config, load_metadata
    from lunarlab.storage import RunPaths, read_json, sha256_file

    out: dict[str, Any] = {}
    for rid in run_ids:
        meta = load_metadata(rid)
        cfg = load_config(rid)
        evals = []
        for p in sorted(RunPaths(rid).evaluations.glob("*.json")):
            r = read_json(p, default=None) or {}
            if "aggregate" not in r:
                continue
            evals.append(
                {
                    "file": p.name,
                    "split": r.get("split"),
                    "sha256": sha256_file(p),
                    "outcome_classifier_version": r["aggregate"].get("outcome_classifier_version", 1),
                    "evaluation_code": r.get("code"),  # absent for evaluations made before it was recorded
                }
            )
        out[rid] = {
            "config_hash": meta.get("config_hash"),
            "protocol_hash": cfg.eval_protocol.protocol_hash(),
            "training_code_at_creation": (meta.get("system") or {}).get("git"),
            "training_code_per_segment": [s.get("code") for s in meta.get("segments", [])],
            "frozen_for_test": meta.get("frozen_for_test"),
            "evaluations": evals,
        }
    return out


def export_demo(
    out: Path,
    *,
    experiment_ids: list[str],
    extra_run_ids: list[str] | None = None,
    echo=print,
    draft: bool = False,
) -> dict:
    """Write the snapshot to ``out`` (a directory that becomes ``demo-api/`` on the site).

    Refuses (``DemoExportError``) when the source tree has uncommitted changes outside ``out`` or is not
    a git checkout, unless ``draft`` is set; a draft is labelled as such in its manifest and the UI.
    """
    from fastapi.testclient import TestClient

    source = source_state(exclude=out)
    if not draft and (not source.get("available") or source.get("dirty")):
        detail = (
            f"{source.get('changed_paths')} changed path(s) outside {out}"
            if source.get("available")
            else source.get("reason", "no git revision")
        )
        raise DemoExportError(
            "a release export needs a clean, attributable source tree (" + detail + "). Commit the "
            "changes first, or export a clearly labelled draft with --draft."
        )
    hashes: dict[str, str] = {}

    from lunarlab.compare import experiment_run_ids
    from lunarlab.preferences.data import SegmentSet, _segment_json, dataset_path, list_datasets
    from lunarlab.recording import find_recording, list_recordings
    from lunarlab.server.main import create_app
    from lunarlab.storage import data_dir, list_run_ids
    from lunarlab.sysinfo import cpu_name

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    scrub = _Scrubber(
        [
            str(data_dir().parent.resolve()),
            str(Path.home()),
            str(project_root().resolve()),
            str(Path(sys.prefix).resolve()),
            str(Path(sys.executable).resolve().parent),
        ]
    )
    n_bytes = 0

    def write(name: str, data: Any) -> None:
        nonlocal n_bytes
        text = json.dumps(_round(scrub(data)), separators=(",", ":"), allow_nan=False)
        path = out / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        n_bytes += len(text)
        if name != "demo":
            hashes[f"{name}.json"] = _sha(text.encode("utf-8"))

    exp_runs: dict[str, list[str]] = {e: experiment_run_ids(e) for e in experiment_ids}
    run_ids = sorted({r for ids in exp_runs.values() for r in ids} | set(extra_run_ids or []))
    known = set(list_run_ids())
    missing = [r for r in run_ids if r not in known]
    if missing:
        raise ValueError(f"unknown runs: {missing}")
    keep_runs = set(run_ids)
    recordings = [
        m
        for m in list_recordings()
        if (m.get("run_id") in keep_runs)
        or m.get("run_id") is None
        and m["policy"]["kind"] in ("random", "heuristic")
    ]
    keep_recs = {m["recording_id"] for m in recordings}

    app = create_app(start_jobs=False, testing=True)
    with TestClient(app) as c:

        def get(path: str) -> Any:
            r = c.get(path)
            r.raise_for_status()
            return r.json()

        def save(path: str, data: Any | None = None) -> Any:
            data = get(path) if data is None else data
            write(demo_name(path), data)
            return data

        # The app's start-up checks run in a background thread; record their result explicitly.
        from lunarlab.env import check_adapter
        from lunarlab.recording import mp4_available

        check_adapter()
        video_ok, video_detail = mp4_available()
        readiness = {
            "checked": True,
            "frontend_built": True,
            "environment": {
                "ok": True,
                "detail": "LunarLander-v3 reset/step OK (when the snapshot was taken)",
            },
            "video": {"ok": video_ok, "detail": video_detail},
        }
        save("/api/meta")
        system = get("/api/system")
        system["readiness"] = readiness
        save("/api/system", system)
        save("/api/reward-configs")
        save("/api/jobs?active=true", [])
        save("/api/reports", [])
        runs = [r for r in get("/api/runs") if r["run_id"] in keep_runs]
        save("/api/runs", runs)
        save("/api/experiments", [e for e in get("/api/experiments") if e["experiment_id"] in exp_runs])
        save("/api/recordings", [m for m in get("/api/recordings") if m["recording_id"] in keep_recs])
        ov = get("/api/overview")
        ov["readiness"] = readiness
        ov["runs"] = [r for r in ov["runs"] if r["run_id"] in keep_runs]
        ov["n_runs"] = len(runs)
        ov["recordings"] = len(keep_recs)
        ov["experiments"] = [e for e in ov["experiments"] if e["experiment_id"] in exp_runs]
        ov["active_jobs"] = []
        for slot in ov["by_preset"].values():
            slot["evaluations"] = [e for e in slot["evaluations"] if e["run_id"] in keep_runs]
            slot["runs"] = len(slot["evaluations"])
        save("/api/overview", ov)

        echo(f"Runs: {len(run_ids)}")
        for rid in run_ids:
            base = f"/api/runs/{rid}"
            for path in (
                base,
                f"{base}/curve",
                f"{base}/metrics",
                f"{base}/validation",
                f"{base}/events?limit=120",
            ):
                save(path)

        echo(f"Recordings: {len(keep_recs)}")
        n_video = 0
        for rid in sorted(keep_recs):
            tele = save(f"/api/recordings/{rid}")
            save(f"/api/recordings/{rid}/scene")
            if tele["video"]["format"] == "mp4-h264":
                _, vdir = find_recording(rid)
                src = vdir / tele["video"]["file"]
                dst = out / f"{demo_name(f'/api/recordings/{rid}/video')}.mp4"
                shutil.copyfile(src, dst)
                n_video += src.stat().st_size
                hashes[dst.name] = _sha(dst.read_bytes())

        echo("Comparisons ...")
        selections = [list(ids) for ids in exp_runs.values()]
        real = [r["run_id"] for r in runs if r["profile"] != "smoke"]
        selections.append((real or [r["run_id"] for r in runs])[:16])  # the Compare page's default selection
        for sel in selections:
            for split in ("validation", "test"):
                r = c.post("/api/compare", json={"run_ids": sel, "split": split}, headers={"X-LunarLab": "1"})
                r.raise_for_status()
                write(f"compare/{compare_key(sel, split)}", r.json())

        datasets = save("/api/preferences")
        save("/api/reward-models")
        for d in datasets:
            save(f"/api/preferences/{d['dataset_id']}/active-studies")
        from lunarlab.tuning import REWARD_PARAMS

        for study in save("/api/tuning"):
            save(f"/api/tuning/{study['study_id']}")
        for algo in ("ppo", "dqn"):
            for p in REWARD_PARAMS:
                save(f"/api/tuning/space?algo={algo}&preset={p}")
        pairs: dict[str, int] = {}
        for d in datasets:
            ds = d["dataset_id"]
            seg = SegmentSet.load(dataset_path(ds))
            rng = np.random.default_rng(0)
            for k in range(DEMO_PAIRS):
                i, j = (int(x) for x in rng.choice(len(seg), size=2, replace=False))
                ri, rj = float(seg.returns[i]), float(seg.returns[j])
                write(
                    f"{demo_name(f'/api/preferences/{ds}/pair')}-{k}",
                    {
                        "dataset_id": ds,
                        "i": i,
                        "j": j,
                        "a": _segment_json(seg, i),
                        "b": _segment_json(seg, j),
                        # Revealed only after the visitor answers (computed in the browser, nothing is stored).
                        "demo_reveal": {
                            "returns": {"a": ri, "b": rj},
                            "sources": {
                                "a": seg.sources[int(seg.source[i])],
                                "b": seg.sources[int(seg.source[j])],
                            },
                            "reward_prefers": "a" if ri > rj else "b" if rj > ri else "tie",
                        },
                    },
                )
            pairs[ds] = DEMO_PAIRS
        assert all(
            d["dataset_id"] in pairs
            for d in list_datasets()
            if d["dataset_id"] in {x["dataset_id"] for x in datasets}
        )

    from lunarlab.config import CONFIG_SCHEMA_VERSION
    from lunarlab.continuation import VERSION as CONTINUATION_VERSION
    from lunarlab.freeze import FROZEN_SCHEMA
    from lunarlab.outcomes import OUTCOME_CLASSIFIER_VERSION

    root = project_root()
    sources = _run_sources(run_ids)
    manifest = {
        "schema_version": 2,
        "kind": "draft" if draft else "release",
        "created_at": utc_now(),
        "export_revision": source.get("revision"),
        "export_source_clean": bool(source.get("available") and not source.get("dirty")),
        "export_source_changed_paths": source.get("changed_paths"),
        "commit": (source.get("revision") or "")[:7] or _git_commit(),
        "uncommitted_changes": bool(source.get("dirty")) if source.get("available") else None,
        "dependency_locks": {
            name: _sha((root / name).read_bytes())
            for name in ("requirements.lock", "requirements-ci.lock", "frontend/package-lock.json")
            if (root / name).exists()
        },
        "versions": {
            "outcome_classifier": OUTCOME_CLASSIFIER_VERSION,
            "frozen_for_test_schema": FROZEN_SCHEMA,
            "run_config_schema": CONFIG_SCHEMA_VERSION,
            "dqn_continuation": CONTINUATION_VERSION,
            "eval_protocols": sorted({v["protocol_hash"] for v in sources.values()}),
        },
        "sources": sources,
        "files": dict(sorted(hashes.items())),
        "experiments": list(exp_runs),
        "runs": len(run_ids),
        "recordings": len(keep_recs),
        "preference_pairs": pairs,
        "hardware": cpu_name(),
        "json_bytes": n_bytes,
        "video_bytes": n_video,
    }
    write("demo", manifest)
    echo(f"Wrote {n_bytes / 1e6:.1f} MB JSON + {n_video / 1e6:.1f} MB video to {out}")
    return manifest
