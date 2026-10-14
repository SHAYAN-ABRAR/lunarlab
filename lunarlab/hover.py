"""The hover predicate shared by the hover-bonus reward and the hover detector.

There is **one** predicate implementation and **two independent parameter sets**:

* ``HoverBonusConfig.eligibility`` (part of a reward configuration) decides when
  the flawed hover-bonus preset pays its bonus.
* ``EvalProtocol.hover_detector`` (part of the evaluation protocol) measures
  hovering for *every* agent, whatever reward it was trained on. Editing a
  reward configuration never changes the detector.

Thresholds are in the environment's observation units (see ``lunarlab.env``).
They are design choices, not validated optimal values.
"""

from __future__ import annotations

import math

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator


class HoverThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_height: float = Field(0.25, ge=-0.5, le=2.5, description="Lower bound on observation y (normalized).")
    max_height: float = Field(1.0, ge=-0.5, le=2.5, description="Upper bound on observation y (normalized).")
    max_abs_angle_rad: float = Field(0.2, gt=0.0, le=math.pi, description="Maximum |angle| in radians.")
    max_abs_vx: float = Field(0.1, gt=0.0, le=5.0, description="Maximum |vx| (scaled units).")
    max_abs_vy: float = Field(0.1, gt=0.0, le=5.0, description="Maximum |vy| (scaled units).")
    max_abs_angular_velocity: float | None = Field(
        0.2, gt=0.0, le=5.0, description="Maximum |angular velocity| (scaled units); null disables the check."
    )

    @model_validator(mode="after")
    def _band(self) -> HoverThresholds:
        if self.min_height >= self.max_height:
            raise ValueError("min_height must be strictly less than max_height")
        return self


def hover_state(obs: np.ndarray, t: HoverThresholds) -> bool:
    """True when ``obs`` is an airborne, slow, level state inside the height band.

    Boundaries are inclusive: a value exactly at a threshold counts as inside.
    """
    x, y, vx, vy, angle, ang_vel, left, right = (float(v) for v in obs[:8])
    if left > 0.5 or right > 0.5:  # airborne: neither leg in contact
        return False
    if not (t.min_height <= y <= t.max_height):
        return False
    if abs(angle) > t.max_abs_angle_rad:
        return False
    if abs(vx) > t.max_abs_vx or abs(vy) > t.max_abs_vy:
        return False
    return not (t.max_abs_angular_velocity is not None and abs(ang_vel) > t.max_abs_angular_velocity)


# Default eligibility for the *reward* (deliberately narrow: a slow, level state
# well above the pad).
DEFAULT_BONUS_ELIGIBILITY = HoverThresholds()

# Default *detector* for evaluation. Slightly broader band so it also notices
# slow, level loitering lower down. Angular velocity is not checked.
DEFAULT_DETECTOR = HoverThresholds(
    min_height=0.1,
    max_height=1.6,
    max_abs_angle_rad=0.35,
    max_abs_vx=0.1,
    max_abs_vy=0.1,
    max_abs_angular_velocity=None,
)
