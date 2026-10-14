"""Environment construction and a small read-only adapter for LunarLander internals.

Everything in LunarLab that needs to look *inside* the Gymnasium LunarLander
implementation (pad geometry, whether the lander body touched the ground,
whether Box2D put the lander to sleep) goes through :func:`probe`. That keeps the
dependency on private attributes in one tested place. The adapter only reads; it
never mutates the simulator.

Verified against gymnasium 1.4.0 (``gymnasium/envs/box2d/lunar_lander.py``).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import gymnasium as gym
import numpy as np

ENV_ID = "LunarLander-v3"
# Default physics for every primary experiment: gravity -10, wind disabled.
# Only the action space is chosen explicitly. Do not add keys here casually:
# every reward experiment must run on identical dynamics.
ENV_KWARGS: dict[str, Any] = {"continuous": False}
TESTED_GYMNASIUM_VERSIONS = ("1.4.0",)


class AdapterError(RuntimeError):
    """Raised when the installed LunarLander no longer exposes what we read."""


def _ll_module():
    from gymnasium.envs.box2d import lunar_lander

    return lunar_lander


def make_env(render_mode: str | None = None) -> gym.Env:
    """Create the standard environment.

    ``render_mode=None`` for training/evaluation, ``"rgb_array"`` for recording.
    The returned env includes the registered ``TimeLimit`` wrapper.
    """
    if render_mode not in (None, "rgb_array"):
        raise ValueError("render_mode must be None or 'rgb_array'")
    return gym.make(ENV_ID, render_mode=render_mode, **ENV_KWARGS)


# --------------------------------------------------------------------------- #
# Observation and action metadata
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ObservationField:
    index: int
    key: str
    label: str
    units: str
    description: str


OBSERVATION_FIELDS: tuple[ObservationField, ...] = (
    ObservationField(
        0,
        "x",
        "Horizontal position",
        "normalized",
        "(x - W/2) / (W/2) with W = 20 world units. 0 is the pad centre; |x| >= 1 ends the episode (out of bounds).",
    ),
    ObservationField(
        1,
        "y",
        "Vertical position",
        "normalized",
        "(y - (pad_y + LEG_DOWN/SCALE)) / (H/2) with H = 13.33 world units. 0 is roughly leg-on-pad height; ~1.4 at spawn.",
    ),
    ObservationField(
        2,
        "vx",
        "Horizontal velocity",
        "scaled",
        "vx_world * (W/2) / FPS (= 0.2 * world units per second). Not an SI quantity.",
    ),
    ObservationField(
        3,
        "vy",
        "Vertical velocity",
        "scaled",
        "vy_world * (H/2) / FPS (~0.133 * world units per second). Negative is falling. Not an SI quantity.",
    ),
    ObservationField(
        4,
        "angle",
        "Angle",
        "rad",
        "Body angle in radians (unnormalized). 0 is upright; shown in degrees as a secondary presentation.",
    ),
    ObservationField(
        5,
        "angular_velocity",
        "Angular velocity",
        "scaled",
        "20 * omega / FPS (= 0.4 * rad/s).",
    ),
    ObservationField(
        6, "left_contact", "Left leg contact", "boolean", "1.0 while the left leg touches the ground."
    ),
    ObservationField(
        7, "right_contact", "Right leg contact", "boolean", "1.0 while the right leg touches the ground."
    ),
)
OBS_KEYS = tuple(f.key for f in OBSERVATION_FIELDS)


@dataclass(frozen=True)
class ActionInfo:
    index: int
    key: str
    label: str


ACTIONS: tuple[ActionInfo, ...] = (
    ActionInfo(0, "noop", "Do nothing"),
    ActionInfo(1, "left", "Fire left orientation engine"),
    ActionInfo(2, "main", "Fire main engine"),
    ActionInfo(3, "right", "Fire right orientation engine"),
)
ACTION_KEYS = tuple(a.key for a in ACTIONS)

# Built-in engine costs (gymnasium 1.4.0, discrete mode: m_power = s_power = 1.0).
BUILTIN_MAIN_ENGINE_COST = 0.30
BUILTIN_SIDE_ENGINE_COST = 0.03
BUILTIN_TERMINAL_CRASH = -100.0
BUILTIN_TERMINAL_REST = 100.0


# --------------------------------------------------------------------------- #
# Read-only internals adapter
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Geometry:
    """Constants of the installed implementation, read from the module."""

    viewport_w: float
    viewport_h: float
    scale: float
    fps: float
    leg_down: float

    @property
    def world_w(self) -> float:
        return self.viewport_w / self.scale

    @property
    def world_h(self) -> float:
        return self.viewport_h / self.scale

    def world_x_to_obs(self, x_world: float) -> float:
        half = self.world_w / 2
        return (x_world - half) / half


def geometry() -> Geometry:
    m = _ll_module()
    try:
        return Geometry(
            viewport_w=float(m.VIEWPORT_W),
            viewport_h=float(m.VIEWPORT_H),
            scale=float(m.SCALE),
            fps=float(m.FPS),
            leg_down=float(m.LEG_DOWN),
        )
    except AttributeError as exc:  # pragma: no cover - only on incompatible gymnasium
        raise AdapterError(f"LunarLander module constants changed: {exc}") from exc


@dataclass(frozen=True)
class LanderProbe:
    """Snapshot of internal flags after a step (read-only)."""

    body_contact: bool  # env.game_over: the lander *body* touched the ground (sticky within an episode)
    awake: bool  # Box2D sleep state; the env terminates with +100 when the lander falls asleep
    helipad_x1_world: float
    helipad_x2_world: float
    helipad_y_world: float
    pad_x1_obs: float
    pad_x2_obs: float
    leg_x_world: tuple[float, float]
    leg_contact: tuple[bool, bool]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def probe(env: gym.Env) -> LanderProbe:
    """Read outcome-relevant internals from any wrapped LunarLander env."""
    u = env.unwrapped
    try:
        geo = geometry()
        x1, x2, y = float(u.helipad_x1), float(u.helipad_x2), float(u.helipad_y)
        legs = u.legs
        return LanderProbe(
            body_contact=bool(u.game_over),
            awake=bool(u.lander.awake),
            helipad_x1_world=x1,
            helipad_x2_world=x2,
            helipad_y_world=y,
            pad_x1_obs=geo.world_x_to_obs(x1),
            pad_x2_obs=geo.world_x_to_obs(x2),
            leg_x_world=(float(legs[0].position[0]), float(legs[1].position[0])),
            leg_contact=(bool(legs[0].ground_contact), bool(legs[1].ground_contact)),
        )
    except AttributeError as exc:
        raise AdapterError(
            "The installed LunarLander no longer exposes an attribute LunarLab reads "
            f"({exc}). Tested gymnasium versions: {', '.join(TESTED_GYMNASIUM_VERSIONS)}."
        ) from exc


def check_adapter() -> dict[str, Any]:
    """Exercise the adapter on a real reset/step. Used by tests and ``doctor``."""
    env = make_env()
    try:
        env.reset(seed=0)
        env.step(0)
        p = probe(env)
        builtin = getattr(env.unwrapped, "prev_shaping", None)
        if builtin is None:
            raise AdapterError(
                "env.unwrapped.prev_shaping missing; built-in reward decomposition unavailable"
            )
        return {"ok": True, "probe": p.to_dict(), "gymnasium": gym.__version__}
    finally:
        env.close()


def environment_record() -> dict[str, Any]:
    """Everything we store about the environment with each run."""
    env = make_env()
    try:
        spec = env.spec
        u = env.unwrapped
        geo = geometry()
        return {
            "env_id": ENV_ID,
            "env_kwargs": dict(ENV_KWARGS),
            "gymnasium_version": gym.__version__,
            "max_episode_steps": int(spec.max_episode_steps) if spec and spec.max_episode_steps else None,
            "reward_threshold": float(spec.reward_threshold) if spec and spec.reward_threshold else None,
            "gravity": float(u.gravity),
            "enable_wind": bool(u.enable_wind),
            "wind_power": float(u.wind_power),
            "turbulence_power": float(u.turbulence_power),
            "fps": geo.fps,
            "observation_space": str(env.observation_space),
            "action_space": str(env.action_space),
            "wrapper_stack": str(env),
        }
    finally:
        env.close()


def builtin_shaping(obs: np.ndarray) -> float:
    """The environment's internal shaping potential, recomputed from an observation.

    Mirrors the installed implementation::

        -100*sqrt(x^2+y^2) - 100*sqrt(vx^2+vy^2) - 100*|angle| + 10*left + 10*right

    The environment evaluates this on float64 values *before* casting the
    observation to float32, so a reconstruction from the float32 observation
    differs by a tiny rounding residual, which LunarLab reports explicitly.
    """
    x, y, vx, vy, ang, _w, lc, rc = (float(v) for v in obs[:8])
    return -100.0 * math.hypot(x, y) - 100.0 * math.hypot(vx, vy) - 100.0 * abs(ang) + 10.0 * lc + 10.0 * rc


def decompose_builtin_reward(
    prev_obs: np.ndarray, next_obs: np.ndarray, action: int, reward: float, terminated: bool
) -> dict[str, float]:
    """Explain one original reward in terms of its built-in pieces.

    On non-terminal steps the original reward is::

        [shaping(s') - shaping(s)] - 0.30*[main fired] - 0.03*[side fired]

    On a terminal step the environment *replaces* the whole reward with -100
    (crash / out of bounds) or +100 (lander at rest), so no other component is
    reported for that step. ``residual`` is reward minus the sum of the reported
    components and should be tiny (float32 rounding) on ordinary steps.
    """
    if terminated:
        return {
            "distance": 0.0,
            "speed": 0.0,
            "tilt": 0.0,
            "leg_contact": 0.0,
            "main_engine": 0.0,
            "side_engine": 0.0,
            "terminal": float(reward),
            "residual": 0.0,
        }
    p, n = prev_obs, next_obs
    distance = -100.0 * (math.hypot(n[0], n[1]) - math.hypot(p[0], p[1]))
    speed = -100.0 * (math.hypot(n[2], n[3]) - math.hypot(p[2], p[3]))
    tilt = -100.0 * (abs(float(n[4])) - abs(float(p[4])))
    legs = 10.0 * ((float(n[6]) + float(n[7])) - (float(p[6]) + float(p[7])))
    main = -BUILTIN_MAIN_ENGINE_COST if action == 2 else 0.0
    side = -BUILTIN_SIDE_ENGINE_COST if action in (1, 3) else 0.0
    parts = {
        "distance": float(distance),
        "speed": float(speed),
        "tilt": float(tilt),
        "leg_contact": float(legs),
        "main_engine": main,
        "side_engine": side,
        "terminal": 0.0,
    }
    parts["residual"] = float(reward) - sum(parts.values())
    return parts
