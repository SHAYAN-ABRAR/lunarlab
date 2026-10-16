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

Classifier version 2 (``OUTCOME_CLASSIFIER_VERSION``) keeps *where* the lander came to rest apart from
*how well* it landed. ``pad_geography`` is ``within`` (both leg bodies between the flags),
``straddling`` (one leg between them, one beyond), ``outside`` (neither) or ``unknown`` (leg or pad
coordinates missing or not finite: never guessed). ``landing_category`` is exactly one of:

* ``strict_pad_landing``          all five conditions above hold;
* ``on_pad_not_strict``           at rest without body contact, both legs between the flags, but
                                  another condition failed (final angle, or no leg contact seen);
* ``landed_not_within_pad``       at rest without body contact, not wholly within the pad
                                  (``straddling`` or ``outside``);
* ``at_rest_after_body_contact``  the environment's ``at_rest`` after the body touched the ground;
* ``at_rest_geometry_unknown``    at rest without body contact, but the geometry is unknown;
* ``crash`` / ``out_of_bounds`` / ``timeout`` / ``unknown``  the environment outcome.

``strict_failures`` lists every strict condition an episode failed. The definition of
``pad_landing`` itself is unchanged from version 1. ``landed_off_pad`` now means
``landed_not_within_pad``; version 1 set it for *every* clean at-rest episode that was not a strict
pad landing, including tilted landings on the pad. Version-1 records are never relabelled in place:
:func:`reclassify_legacy_episode` derives version-2 categories from the fields they stored, and
derived values are always labelled as derived.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from lunarlab.env import LanderProbe

EnvOutcome = Literal["at_rest", "crash", "out_of_bounds", "timeout", "unknown"]
ENV_OUTCOMES: tuple[str, ...] = ("at_rest", "crash", "out_of_bounds", "timeout", "unknown")

OUTCOME_CLASSIFIER_VERSION = 2
LANDING_CATEGORIES: tuple[str, ...] = (
    "strict_pad_landing",
    "on_pad_not_strict",
    "landed_not_within_pad",
    "at_rest_after_body_contact",
    "at_rest_geometry_unknown",
    "crash",
    "out_of_bounds",
    "timeout",
    "unknown",
)


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
    landing_category: str = "unknown"
    pad_geography: str = "unknown"
    strict_failures: tuple[str, ...] = ()
    on_pad_not_strict: bool = False
    leg_x_world: tuple[float, ...] | None = None
    helipad_x_world: tuple[float, float] | None = None
    outcome_classifier_version: int = field(default=OUTCOME_CLASSIFIER_VERSION)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["strict_failures"] = list(self.strict_failures)
        for k in ("leg_x_world", "helipad_x_world"):  # JSON has no NaN/inf: unknown stays None
            v = d[k]
            d[k] = None if v is None else [x if math.isfinite(x) else None for x in v]
        return d


def pad_geography(leg_xs, pad_x1: float, pad_x2: float) -> str:
    """``within`` / ``straddling`` / ``outside``, or ``unknown`` when any coordinate is unusable."""
    try:
        values = [float(x) for x in leg_xs] + [float(pad_x1), float(pad_x2)]
    except (TypeError, ValueError):
        return "unknown"
    if len(values) != 4 or not all(math.isfinite(v) for v in values) or values[2] == values[3]:
        return "unknown"
    lo, hi = min(values[2:]), max(values[2:])
    inside = [lo <= x <= hi for x in values[:2]]
    return "within" if all(inside) else "straddling" if any(inside) else "outside"


def _category(env_outcome: str, body_contact: bool, pad: bool, geography: str) -> str:
    if env_outcome != "at_rest":
        return env_outcome if env_outcome in ENV_OUTCOMES else "unknown"
    if body_contact:
        return "at_rest_after_body_contact"
    if pad:
        return "strict_pad_landing"
    if geography == "unknown":
        return "at_rest_geometry_unknown"
    if geography == "within":
        return "on_pad_not_strict"
    return "landed_not_within_pad"


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
    geography = pad_geography(p.leg_x_world, p.helipad_x1_world, p.helipad_x2_world)
    within = geography == "within"  # unknown geometry is never "within" (as in version 1)
    angle_ok = abs(float(final_obs[4])) <= c.max_final_abs_angle_rad
    at_rest_clean = env_outcome == "at_rest" and not p.body_contact
    pad = (
        at_rest_clean
        and (leg_contact_seen or not c.require_leg_contact_seen)
        and (within or not c.require_legs_within_pad)
        and angle_ok
    )
    failures: list[str] = []
    if env_outcome != "at_rest":
        failures.append("not_at_rest")
    if p.body_contact:
        failures.append("body_contact")
    if c.require_leg_contact_seen and not leg_contact_seen:
        failures.append("no_leg_contact_seen")
    if c.require_legs_within_pad and geography == "unknown":
        failures.append("geometry_unknown")
    elif c.require_legs_within_pad and not within:
        failures.append("legs_not_within_pad")
    if not angle_ok:
        failures.append("final_angle_too_large")
    category = _category(env_outcome, bool(p.body_contact), bool(pad), geography)
    return OutcomeRecord(
        env_outcome=env_outcome,
        terminated=bool(terminated),
        truncated=bool(truncated),
        body_contact=bool(p.body_contact),
        both_legs_contact=both_legs,
        leg_contact_seen=bool(leg_contact_seen),
        legs_within_pad=within,
        pad_landing=bool(pad),
        landed_off_pad=category == "landed_not_within_pad",
        final_abs_angle_rad=abs(float(final_obs[4])),
        pad_x1_obs=p.pad_x1_obs,
        pad_x2_obs=p.pad_x2_obs,
        landing_category=category,
        pad_geography=geography,
        strict_failures=tuple(failures) if not pad else (),
        on_pad_not_strict=category == "on_pad_not_strict",
        leg_x_world=tuple(float(x) for x in p.leg_x_world),
        helipad_x_world=(float(p.helipad_x1_world), float(p.helipad_x2_world)),
    )


LEGACY_FIELDS = (
    "env_outcome",
    "body_contact",
    "leg_contact_seen",
    "legs_within_pad",
    "final_abs_angle_rad",
    "pad_landing",
)


def reclassify_legacy_episode(ep: dict, *, max_final_abs_angle_rad: float) -> dict:
    """Version-2 category of a version-1 episode record, derived only from what it stored.

    Version 1 stored whether both legs were between the flags, not the leg positions, so a landing
    that was not within the pad is ``not_within`` (straddling and outside cannot be told apart).
    """
    missing = [k for k in LEGACY_FIELDS if k not in ep]
    if missing:
        raise ValueError(f"cannot reclassify: stored episode record is missing {missing}")
    env_outcome = str(ep["env_outcome"])
    body = bool(ep["body_contact"])
    geography = "within" if ep["legs_within_pad"] else "not_within"
    pad = bool(ep["pad_landing"])  # the strict definition did not change
    category = _category(env_outcome, body, pad, geography)
    failures = []
    if env_outcome == "at_rest" and not pad:
        if body:
            failures.append("body_contact")
        if not ep["leg_contact_seen"]:
            failures.append("no_leg_contact_seen")
        if not ep["legs_within_pad"]:
            failures.append("legs_not_within_pad")
        if not float(ep["final_abs_angle_rad"]) <= max_final_abs_angle_rad:
            failures.append("final_angle_too_large")
    return {
        "landing_category": category,
        "pad_geography": geography,
        "strict_failures": failures,
        "landed_off_pad": category == "landed_not_within_pad",
        "on_pad_not_strict": category == "on_pad_not_strict",
        "derived_from_classifier_version": 1,
        "v1_landed_off_pad": bool(ep.get("landed_off_pad")),
    }


def derived_v2_rates(episodes: list[dict], *, max_final_abs_angle_rad: float) -> dict | None:
    """Version-2 category rates derived from version-1 episode records (None if they lack the fields)."""
    if not episodes:
        return None
    try:
        derived = [
            reclassify_legacy_episode(e, max_final_abs_angle_rad=max_final_abs_angle_rad) for e in episodes
        ]
    except ValueError:
        return None
    n = len(derived)
    rates = {f"{c}_rate": sum(d["landing_category"] == c for d in derived) / n for c in LANDING_CATEGORIES}
    return {
        **rates,
        "n_episodes": n,
        "v1_landed_off_pad_rate": sum(d["v1_landed_off_pad"] for d in derived) / n,
        "derived_from_classifier_version": 1,
        "note": "derived from the episode fields stored by classifier version 1 (leg positions were not stored)",
    }
