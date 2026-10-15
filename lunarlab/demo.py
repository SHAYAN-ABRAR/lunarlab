"""Static, read-only snapshot of the API for the hosted demo (GitHub Pages).

Every file is produced by calling the real API in-process (FastAPI's TestClient), so the
demo shows exactly what the local app shows for the same data. Lists are filtered to the
exported experiments, runs and recordings, and absolute local paths are scrubbed.

File names: ``demo_name("/api/runs/x/curve")`` maps an API path (with its query string) to a
flat, URL-safe name; the frontend's demo mode applies the same mapping.
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


def export_demo(
    out: Path, *, experiment_ids: list[str], extra_run_ids: list[str] | None = None, echo=print
) -> dict:
    """Write the snapshot to ``out`` (a directory that becomes ``demo-api/`` on the site)."""
    from fastapi.testclient import TestClient

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

    manifest = {
        "created_at": utc_now(),
        "commit": _git_commit(),
        "uncommitted_changes": _git_dirty(),
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
