"""Episode outcome classification.

Definitions (documented in docs/EVALUATION.md):

``env_outcome`` — what the *environment* decided at the final step:

* ``at_rest``        terminated because Box2D put the lander to sleep. The env pays
                     +100. This is the environment's own notion of success, and it
                     does **not** check where the lander came to rest.
* ``crash``          terminated because the lander *body* touched the ground
                     (``game_over``) and the lander was still awake. Env pays -100.
* ``out_of_bounds``  terminated because |x| >= 1 without body contact. Env pays -100.
* ``timeout``        truncated by the 1000-step ``TimeLimit``.
* ``unknown``        terminated for no reason we can identify (should not happen;
                     reported rather than guessed).

Note the env's own order: if the body touched the ground *and* the lander fell
asleep on the same step, the env pays +100 (sleep wins). We report ``at_rest``
with ``body_contact=True``; such an episode never counts as a strict pad landing.

``pad_landing`` (strict) requires all of:

1. ``env_outcome == "at_rest"`` (Box2D put the lander to sleep: it is not moving);
2. no body contact at any point (``game_over`` is sticky within an episode);
3. leg ground contact was reported at least once during the episode;
4. both leg bodies horizontally between the helipad flags (x read from the env);
5. final |angle| <= ``max_final_abs_angle_rad``.

Why not "both legs in contact in the final observation"? In gymnasium 1.4.0 the
contact detector keeps one boolean per leg: ``BeginContact`` sets it, ``EndContact``
clears it. When a leg slides across the joint between two terrain edge fixtures,
the new contact begins before the old one ends, so the flag reads 0 although the
leg is still on the ground. Landers asleep on the pad with both flags at 0 are
common (e.g. the heuristic controller on episode seed 20011). A sleeping lander
without body contact must be resting on its legs, so condition 3 only asks that
leg contact was seen at some point. ``both_legs_contact`` (final frame) is still
reported for transparency.

A score of >= 200 is reported separately: score and outcome measure different things.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from lunarlab.env import LanderProbe

EnvOutcome = Literal["at_rest", "crash", "out_of_bounds", "timeout", "unknown"]
ENV_OUTCOMES: tuple[str, ...] = ("at_rest", "crash", "out_of_bounds", "timeout", "unknown")


class PadLandingCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    require_leg_contact_seen: bool = True
    require_legs_within_pad: bool = True
    max_final_abs_angle_rad: float = Field(0.35, gt=0.0, le=3.1416)


@dataclass(frozen=True)
class OutcomeRecord:
    env_outcome: str
    terminated: bool
    truncated: bool
    body_contact: bool
    both_legs_contact: bool
    leg_contact_seen: bool
    legs_within_pad: bool
    pad_landing: bool
    landed_off_pad: bool
    final_abs_angle_rad: float
    pad_x1_obs: float
    pad_x2_obs: float

    def to_dict(self) -> dict:
        return asdict(self)


def classify_env_outcome(terminated: bool, truncated: bool, final_obs: np.ndarray, p: LanderProbe) -> str:
    if terminated:
        if not p.awake:
            return "at_rest"
        if p.body_contact:
            return "crash"
        if abs(float(final_obs[0])) >= 1.0:
            return "out_of_bounds"
        return "unknown"
    if truncated:
        return "timeout"
    return "unknown"


def classify_outcome(
    terminated: bool,
    truncated: bool,
    final_obs: np.ndarray,
    p: LanderProbe,
    criteria: PadLandingCriteria | None = None,
    *,
    leg_contact_seen: bool,
) -> OutcomeRecord:
    c = criteria or PadLandingCriteria()
    env_outcome = classify_env_outcome(terminated, truncated, final_obs, p)
    both_legs = bool(final_obs[6] > 0.5 and final_obs[7] > 0.5)
    lo, hi = min(p.helipad_x1_world, p.helipad_x2_world), max(p.helipad_x1_world, p.helipad_x2_world)
    within = all(lo <= lx <= hi for lx in p.leg_x_world)
    angle_ok = abs(float(final_obs[4])) <= c.max_final_abs_angle_rad
    at_rest_clean = env_outcome == "at_rest" and not p.body_contact
    pad = (
        at_rest_clean
        and (leg_contact_seen or not c.require_leg_contact_seen)
        and (within or not c.require_legs_within_pad)
        and angle_ok
    )
    return OutcomeRecord(
        env_outcome=env_outcome,
        terminated=bool(terminated),
        truncated=bool(truncated),
        body_contact=bool(p.body_contact),
        both_legs_contact=both_legs,
        leg_contact_seen=bool(leg_contact_seen),
        legs_within_pad=within,
        pad_landing=bool(pad),
        landed_off_pad=bool(at_rest_clean and not pad),
        final_abs_angle_rad=abs(float(final_obs[4])),
        pad_x1_obs=p.pad_x1_obs,
        pad_x2_obs=p.pad_x2_obs,
    )
