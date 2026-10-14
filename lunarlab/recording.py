"""Record real episodes: simulator frames + synchronized telemetry.

Frame/step indexing (stored in every telemetry file):

* frame 0 is rendered right after ``reset()``: the initial state, no action yet;
* frame k (k >= 1) is rendered after the k-th ``step()``;
* telemetry row k describes the state shown in frame k, the action applied in
  the step that *produced* it (the engine flames visible in frame k), and the
  reward received for that step. Row 0 has no action and zero reward.

So an episode of T steps has T + 1 frames and T + 1 telemetry rows, and the
video time of frame k is k / fps.

Video: H.264 MP4 (yuv420p, keyframe every 25 frames for fast scrubbing, +faststart) through the ffmpeg binary bundled with
``imageio-ffmpeg``, written frame by frame so memory stays bounded. If that
encoder is unavailable, frames are saved as numbered JPEG files instead, which
the replay UI can play just the same. Every output is verified after writing.
"""

from __future__ import annotations

import contextlib
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from lunarlab.config import EvalProtocol
from lunarlab.env import ACTIONS, OBSERVATION_FIELDS, environment_record, geometry, probe
from lunarlab.evaluation import make_eval_env
from lunarlab.policies import Policy
from lunarlab.rewards.config import RewardConfig
from lunarlab.storage import atomic_write_json, new_id, utc_now

TELEMETRY_SCHEMA = "lunarlab-telemetry-v1"


class RecordingError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# Video sinks
# --------------------------------------------------------------------------- #


class Mp4Sink:
    format = "mp4-h264"

    def __init__(self, path: Path, fps: int) -> None:
        import imageio.v2 as iio

        self.path = path
        self._writer = iio.get_writer(
            str(path),
            fps=fps,
            codec="libx264",
            pixelformat="yuv420p",
            macro_block_size=8,
            ffmpeg_log_level="error",
            ffmpeg_params=["-preset", "veryfast", "-crf", "23", "-g", "25", "-movflags", "+faststart"],
        )
        self.frames = 0

    def add(self, frame: np.ndarray) -> None:
        self._writer.append_data(frame)
        self.frames += 1

    def close(self) -> None:
        self._writer.close()

    def abort(self) -> None:
        with contextlib.suppress(Exception):
            self._writer.close()
        with contextlib.suppress(OSError):
            self.path.unlink()


class JpegFramesSink:
    format = "jpeg-frames"

    def __init__(self, directory: Path, fps: int) -> None:
        self.path = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.frames = 0

    def add(self, frame: np.ndarray) -> None:
        from PIL import Image

        Image.fromarray(frame).save(self.path / f"{self.frames:06d}.jpg", quality=82)
        self.frames += 1

    def close(self) -> None:
        pass

    def abort(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


@lru_cache(maxsize=1)
def mp4_available() -> tuple[bool, str]:
    """Probe the H.264 encoder once by writing and decoding a tiny clip."""
    try:
        import imageio.v2 as iio

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "probe.mp4"
            sink = Mp4Sink(p, 10)
            for i in range(4):
                sink.add(np.full((64, 96, 3), 40 * i, dtype=np.uint8))
            sink.close()
            r = iio.get_reader(str(p))
            n = r.count_frames()
            r.close()
            if n != 4:
                return False, f"probe decoded {n} frames instead of 4"
        return True, "libx264 via imageio-ffmpeg"
    except Exception as exc:  # pragma: no cover - depends on platform binaries
        return False, f"{type(exc).__name__}: {exc}"


def verify_video(path: Path, expected_frames: int, fmt: str) -> dict:
    """Check the output exists, is non-empty, decodes, and has the expected frame count."""
    if fmt == "jpeg-frames":
        files = sorted(path.glob("*.jpg"))
        ok = len(files) == expected_frames and all(f.stat().st_size > 0 for f in files[:3])
        if ok:
            from PIL import Image

            with Image.open(files[0]) as im:
                im.verify()
        return {"verified": ok, "frames": len(files), "bytes": sum(f.stat().st_size for f in files)}
    import imageio.v2 as iio

    if not path.exists() or path.stat().st_size == 0:
        return {"verified": False, "frames": 0, "bytes": 0, "error": "missing or empty file"}
    reader = iio.get_reader(str(path))
    try:
        n = reader.count_frames()
        first = reader.get_data(0)
    finally:
        reader.close()
    return {
        "verified": bool(n == expected_frames and first.ndim == 3),
        "frames": int(n),
        "bytes": path.stat().st_size,
        "frame_shape": list(first.shape),
    }


# --------------------------------------------------------------------------- #
# Recording
# --------------------------------------------------------------------------- #


def seed_split(seed: int, protocol: EvalProtocol) -> str:
    if seed in protocol.validation_seeds:
        return "validation"
    if seed in protocol.test_seeds:
        return "test"
    return "other"


def record_episode(
    policy: Policy,
    *,
    episode_seed: int,
    out_dir: Path,
    video_dir: Path,
    reward: RewardConfig | None,
    gamma: float,
    protocol: EvalProtocol,
    source: dict[str, Any],
    prefer: str = "auto",
) -> dict:
    """Fly one episode with ``policy`` and save video + telemetry. Returns the summary."""
    out_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)
    rec_id = new_id(policy.kind, f"seed{episode_seed}")
    fps = int(geometry().fps)
    use_mp4 = prefer == "mp4" or (prefer == "auto" and mp4_available()[0])
    if prefer == "mp4" and not mp4_available()[0]:
        raise RecordingError(f"MP4 encoder unavailable: {mp4_available()[1]}")

    env = make_eval_env(protocol, reward, gamma, render_mode="rgb_array", record_steps=True)
    sink = (
        Mp4Sink(video_dir / f"{rec_id}.mp4", fps)
        if use_mp4
        else JpegFramesSink(video_dir / f"{rec_id}_frames", fps)
    )
    try:
        obs, _ = env.reset(seed=int(episode_seed))
        policy.reset(int(episode_seed))
        p0 = probe(env)
        initial_obs = [float(v) for v in obs]
        sink.add(env.render())
        while True:
            obs, _, terminated, truncated, info = env.step(policy.act(obs))
            sink.add(env.render())
            if terminated or truncated:
                episode = info["lunarlab_episode"]
                break
        sink.close()
    except BaseException:
        sink.abort()
        env.close()
        raise
    steps = env.steps
    env.close()

    n_frames = len(steps) + 1
    check = verify_video(sink.path, n_frames, sink.format)
    if not check["verified"]:
        raise RecordingError(f"video verification failed: {check}")

    zero_terms = {k: 0.0 for k in (steps[0]["terms"] if steps else {})}
    row0 = {
        "t": 0,
        "action": None,
        "obs": initial_obs,
        "original_reward": 0.0,
        "terms": zero_terms,
        "training_reward": 0.0,
        "cum_original": 0.0,
        "cum_training": 0.0,
        "builtin": None,
        "hover": False,
        "terminated": False,
        "truncated": False,
    }
    rows = [row0, *steps]
    telemetry = {
        "schema": TELEMETRY_SCHEMA,
        "recording_id": rec_id,
        "created_at": utc_now(),
        "source": source,
        "policy": {"kind": policy.kind, "label": policy.label},
        "episode_seed": int(episode_seed),
        "seed_split": seed_split(int(episode_seed), protocol),
        "fps": fps,
        "n_frames": n_frames,
        "indexing": "frame k = state after k steps (frame 0 = reset); row k's action/reward produced frame k; time = k/fps",
        "observation_fields": [f.__dict__ for f in OBSERVATION_FIELDS],
        "actions": [a.__dict__ for a in ACTIONS],
        "pad": {"x1_obs": p0.pad_x1_obs, "x2_obs": p0.pad_x2_obs},
        "reward_config": (reward.model_dump(mode="json") if reward else None),
        "reward_applied_during_recording": False,
        "terms_note": "Additional terms are what the training reward would have added on this episode, "
        "computed with the same pure functions as training. The policy acted on observations only.",
        "gamma": gamma,
        "protocol_hash": protocol.protocol_hash(),
        "hover_detector": protocol.hover_detector.model_dump(mode="json"),
        "environment": environment_record(),
        "video": {"format": sink.format, "file": sink.path.name, **check},
        "episode": episode,
        "rows": rows,
    }
    atomic_write_json(out_dir / f"{rec_id}.json", telemetry)
    meta = recording_meta(telemetry)
    atomic_write_json(out_dir / f"{rec_id}.meta.json", meta)
    return meta


def recording_meta(t: dict) -> dict:
    ep = t["episode"]
    return {
        "recording_id": t["recording_id"],
        "created_at": t["created_at"],
        "source": t["source"],
        "policy": t["policy"],
        "episode_seed": t["episode_seed"],
        "seed_split": t["seed_split"],
        "n_frames": t["n_frames"],
        "fps": t["fps"],
        "video": t["video"],
        "original_return": ep["original_return"],
        "training_return": ep["training_return"],
        "env_outcome": ep.get("env_outcome"),
        "pad_landing": ep.get("pad_landing"),
        "length": ep["length"],
        "hover_fraction": ep["hover_fraction"],
        "reward_preset": (t.get("reward_config") or {}).get("preset"),
        "protocol_hash": t.get("protocol_hash"),
    }


# --------------------------------------------------------------------------- #
# High-level entry points and the recording library
# --------------------------------------------------------------------------- #


def record_demo(kind: str = "random", *, episode_seed: int = 20_000, action_seed: int = 0) -> dict:
    """Record a RANDOM or HEURISTIC demonstration (no training involved)."""
    from lunarlab.config import EvalProtocol, PPOConfig
    from lunarlab.env import make_env
    from lunarlab.policies import HeuristicPolicy, RandomPolicy
    from lunarlab.storage import demos_dir

    protocol = EvalProtocol()
    if kind == "random":
        policy: Policy = RandomPolicy(action_seed=action_seed)
        source = {"type": "demo", "kind": "random", "action_seed": action_seed}
    elif kind == "heuristic":
        # The heuristic only reads env.continuous; any LunarLander instance works.
        holder = make_env()
        policy = HeuristicPolicy(holder)
        source = {"type": "demo", "kind": "heuristic"}
    else:
        raise ValueError("kind must be 'random' or 'heuristic'")
    d = demos_dir()
    return record_episode(
        policy,
        episode_seed=episode_seed,
        out_dir=d,
        video_dir=d,
        reward=None,
        gamma=PPOConfig().gamma,
        protocol=protocol,
        source=source,
    )


def record_run(run_id: str, *, episode_seed: int, checkpoint: str = "best") -> dict:
    """Record one episode of a trained run's checkpoint (evaluation conditions)."""
    from lunarlab.runs import load_config, load_policy, log_event
    from lunarlab.storage import RunPaths

    cfg = load_config(run_id)
    paths = RunPaths(run_id)
    policy, entry = load_policy(run_id, checkpoint, deterministic=cfg.eval_protocol.deterministic)
    source = {
        "type": "run",
        "run_id": run_id,
        "checkpoint": entry["name"],
        "checkpoint_transitions": entry["transitions"],
        "reward_preset": cfg.reward.preset,
        "reward_name": cfg.reward.name,
        "training_seed": cfg.seed,
        "profile": cfg.training.profile,
        "deterministic": cfg.eval_protocol.deterministic,
    }
    meta = record_episode(
        policy,
        episode_seed=episode_seed,
        out_dir=paths.trajectories,
        video_dir=paths.videos,
        reward=cfg.reward,
        gamma=cfg.ppo.gamma,
        protocol=cfg.eval_protocol,
        source=source,
    )
    log_event(paths, "info", "episode recorded", recording_id=meta["recording_id"], episode_seed=episode_seed)
    return meta


def _recording_dirs() -> list[tuple[Path, Path, str | None]]:
    """(telemetry dir, video dir, run_id) for every place recordings live."""
    from lunarlab.storage import demos_dir, list_run_ids, runs_dir

    out: list[tuple[Path, Path, str | None]] = [(demos_dir(), demos_dir(), None)]
    for rid in list_run_ids():
        root = runs_dir() / rid
        out.append((root / "trajectories", root / "videos", rid))
    return out


def list_recordings() -> list[dict]:
    from lunarlab.storage import read_json

    out = []
    for tdir, _vdir, rid in _recording_dirs():
        if not tdir.exists():
            continue
        for p in tdir.glob("*.meta.json"):
            m = read_json(p)
            if m:
                m["run_id"] = rid
                out.append(m)
    out.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return out


def find_recording(recording_id: str) -> tuple[Path, Path]:
    """Locate (telemetry json, video dir) for a recording id, safely."""
    from lunarlab.storage import safe_child

    for tdir, vdir, _rid in _recording_dirs():
        try:
            cand = safe_child(tdir, f"{recording_id}.json")
        except ValueError as exc:
            raise KeyError(recording_id) from exc
        if cand.exists():
            return cand, vdir
    raise KeyError(recording_id)
