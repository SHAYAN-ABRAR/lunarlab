"""Fly it yourself: keyboard-controlled episodes, recorded like any policy's.

The browser sends the actions held on the keyboard; the server steps the real environment
(same physics, same reward accounting, same outcome classification as evaluation) and
returns the new telemetry rows. A finished flight is saved as an ordinary recording
(video + telemetry, policy kind ``human``) in ``data/flights``, so it can be replayed and
compared like any other episode.

Optionally an opponent flies the *same* episode seed: Gymnasium's heuristic or a trained
run's frozen (validation-selected) checkpoint. Its whole flight is computed up front,
without rendering, and drawn as a ghost next to the player's lander.

Flight seeds are drawn from 40,000–49,999 (disjoint from training workers, validation,
the final test and preference collection) unless the player picks one.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from lunarlab.config import EvalProtocol, PPOConfig
from lunarlab.recording import EpisodeRecorder
from lunarlab.storage import flights_dir

FLIGHT_SEED_BASE = 40_000
FLIGHT_SEED_RANGE = 10_000
MAX_SESSIONS = 4
IDLE_TIMEOUT_S = 600.0
MAX_ACTIONS_PER_REQUEST = 50
HUMAN_LABEL = "HUMAN — keyboard pilot"


class FlightError(RuntimeError):
    pass


@dataclass
class _Session:
    recorder: EpisodeRecorder
    seed: int
    opponent: str | None
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_seen: float = field(default_factory=time.monotonic)


_SESSIONS: dict[str, _Session] = {}
_REGISTRY = threading.Lock()


def _episode_summary(ep: dict) -> dict[str, Any]:
    return {
        "original_return": float(ep["original_return"]),
        "env_outcome": ep.get("env_outcome"),
        "pad_landing": bool(ep.get("pad_landing")),
        "length": int(ep["length"]),
        "actions": ep.get("actions", {}),
    }


def _opponent_policy(opponent: str):
    """(policy, protocol, gamma, description) for 'heuristic' or a run id."""
    if opponent == "heuristic":
        from lunarlab.env import make_env
        from lunarlab.policies import HeuristicPolicy

        policy = HeuristicPolicy(make_env())  # reads only env.continuous
        return policy, EvalProtocol(), PPOConfig().gamma, {"type": "heuristic"}
    from lunarlab.runs import RunError, load_config, load_policy
    from lunarlab.storage import RunPaths

    try:
        paths = RunPaths(opponent)
    except ValueError as exc:
        raise FlightError("invalid opponent run id") from exc
    if not paths.exists():
        raise FlightError(f"unknown run {opponent}")
    cfg = load_config(opponent)
    try:
        policy, entry = load_policy(opponent, "final-test", deterministic=cfg.eval_protocol.deterministic)
    except (RunError, FileNotFoundError, KeyError) as exc:
        raise FlightError(f"run {opponent} has no usable checkpoint yet") from exc
    info = {
        "type": "run",
        "run_id": opponent,
        "checkpoint": entry["name"],
        "checkpoint_transitions": entry["transitions"],
        "reward_name": cfg.reward.name,
        "algo": cfg.algo,
        "training_seed": cfg.seed,
    }
    return policy, cfg.eval_protocol, cfg.gamma, info


def ghost_flight(opponent: str, seed: int) -> dict[str, Any]:
    """The opponent's whole flight on ``seed`` (positions and actions), without rendering."""
    from lunarlab.evaluation import make_eval_env

    policy, protocol, gamma, info = _opponent_policy(opponent)
    env = make_eval_env(protocol, None, gamma)
    try:
        obs, _ = env.reset(seed=int(seed))
        policy.reset(int(seed))
        rows: list[dict[str, Any]] = [{"obs": [round(float(v), 5) for v in obs], "action": None}]
        while True:
            action = int(policy.act(obs))
            obs, _, terminated, truncated, step_info = env.step(action)
            rows.append({"obs": [round(float(v), 5) for v in obs], "action": action})
            if terminated or truncated:
                episode = step_info["lunarlab_episode"]
                break
    finally:
        env.close()
    return {
        "opponent": opponent,
        "label": policy.label,
        "source": info,
        "rows": rows,
        "episode": _episode_summary(episode),
    }


def _expire_idle() -> None:
    now = time.monotonic()
    with _REGISTRY:
        stale = [k for k, s in _SESSIONS.items() if now - s.last_seen > IDLE_TIMEOUT_S]
        sessions = [_SESSIONS.pop(k) for k in stale]
    for s in sessions:
        s.recorder.abort()


def start_flight(seed: int | None = None, opponent: str | None = None) -> dict[str, Any]:
    _expire_idle()
    if seed is None:
        seed = FLIGHT_SEED_BASE + secrets.randbelow(FLIGHT_SEED_RANGE)
    ghost = ghost_flight(opponent, seed) if opponent else None
    rec = EpisodeRecorder(
        policy_kind="human",
        policy_label=HUMAN_LABEL,
        episode_seed=seed,
        out_dir=flights_dir(),
        video_dir=flights_dir(),
        reward=None,
        gamma=PPOConfig().gamma,
        protocol=EvalProtocol(),
        source={"type": "flight", "input": "keyboard", "opponent": ghost["source"] if ghost else None},
    )
    evicted: list[_Session] = []
    with _REGISTRY:
        while len(_SESSIONS) >= MAX_SESSIONS:
            oldest = min(_SESSIONS, key=lambda k: _SESSIONS[k].last_seen)
            evicted.append(_SESSIONS.pop(oldest))
        _SESSIONS[rec.recording_id] = _Session(recorder=rec, seed=seed, opponent=opponent)
    for s in evicted:
        s.recorder.abort()
    return {
        "session_id": rec.recording_id,
        "seed": seed,
        "seed_split": "flight"
        if FLIGHT_SEED_BASE <= seed < FLIGHT_SEED_BASE + FLIGHT_SEED_RANGE
        else "other",
        "fps": rec.fps,
        "scene": {**rec.scene, "source": "this flight's environment"},
        "pad": {"x1_obs": rec.pad.pad_x1_obs, "x2_obs": rec.pad.pad_x2_obs},
        "row": rec.row0(),
        "max_actions_per_request": MAX_ACTIONS_PER_REQUEST,
        "ghost": ghost,
    }


def step_flight(session_id: str, actions: list[int]) -> dict[str, Any]:
    """Apply the actions in order (stopping at the end of the episode); returns the new rows.
    When the episode ends, the recording is saved and the session closes."""
    if not 1 <= len(actions) <= MAX_ACTIONS_PER_REQUEST:
        raise FlightError(f"send 1–{MAX_ACTIONS_PER_REQUEST} actions per request")
    if any(a not in (0, 1, 2, 3) for a in actions):
        raise FlightError("actions must be 0, 1, 2 or 3")
    with _REGISTRY:
        s = _SESSIONS.get(session_id)
    if s is None:
        raise KeyError(session_id)
    with s.lock:
        s.last_seen = time.monotonic()
        rec = s.recorder
        rows = []
        for a in actions:
            if rec.done:
                break
            rows.append(rec.step(a))
        out: dict[str, Any] = {"rows": rows, "done": rec.done}
        if rec.done:
            with _REGISTRY:
                _SESSIONS.pop(session_id, None)
            out["recording"] = rec.finish()
            out["episode"] = _episode_summary(rec.episode or {})
    return out


def abandon_flight(session_id: str) -> bool:
    with _REGISTRY:
        s = _SESSIONS.pop(session_id, None)
    if s is None:
        return False
    with s.lock:
        s.recorder.abort()
    return True


def active_flights() -> int:
    with _REGISTRY:
        return len(_SESSIONS)
