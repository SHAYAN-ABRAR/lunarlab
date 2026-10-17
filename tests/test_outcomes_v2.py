# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Outcome classifier v2: where the lander came to rest is kept apart from how well it landed."""

from __future__ import annotations

import math

import numpy as np
import pytest

from lunarlab.env import LanderProbe
from lunarlab.outcomes import (
    OUTCOME_CLASSIFIER_VERSION,
    PadLandingCriteria,
    classify_outcome,
    reclassify_legacy_episode,
)

PAD = (8.0, 12.0)


def probe(*, body=False, awake=False, legs=(9.5, 10.5), pad=PAD):
    return LanderProbe(
        body_contact=body,
        awake=awake,
        helipad_x1_world=pad[0],
        helipad_x2_world=pad[1],
        helipad_y_world=3.33,
        pad_x1_obs=-0.2,
        pad_x2_obs=0.2,
        leg_x_world=legs,
        leg_contact=(True, True),
    )


def obs(x=0.0, angle=0.0, left=1.0, right=1.0):
    return np.array([x, 0.0, 0.0, 0.0, angle, 0.0, left, right], dtype=np.float32)


def classify(*, terminated=True, truncated=False, o=None, p=None, seen=True, max_angle=0.35):
    return classify_outcome(
        terminated,
        truncated,
        obs() if o is None else o,
        probe() if p is None else p,
        PadLandingCriteria(max_final_abs_angle_rad=max_angle),
        leg_contact_seen=seen,
    )


def test_version_is_recorded():
    assert OUTCOME_CLASSIFIER_VERSION == 2
    assert classify().outcome_classifier_version == 2


def test_clean_upright_on_pad_landing():
    o = classify()
    assert o.pad_landing and o.landing_category == "strict_pad_landing"
    assert o.pad_geography == "within" and o.strict_failures == () and not o.landed_off_pad


def test_on_pad_landing_with_too_much_tilt_is_not_called_off_pad():
    o = classify(o=obs(angle=0.6))
    assert not o.pad_landing and not o.landed_off_pad
    assert o.landing_category == "on_pad_not_strict" and o.pad_geography == "within"
    assert o.strict_failures == ("final_angle_too_large",)


def test_on_pad_landing_without_any_leg_contact_seen():
    o = classify(o=obs(left=0, right=0), seen=False)
    assert o.landing_category == "on_pad_not_strict" and o.strict_failures == ("no_leg_contact_seen",)
    assert not o.landed_off_pad


def test_clean_landing_beside_the_pad():
    o = classify(o=obs(x=0.5), p=probe(legs=(14.0, 15.4)))
    assert o.landing_category == "landed_not_within_pad" and o.pad_geography == "outside"
    assert o.landed_off_pad and o.strict_failures == ("legs_not_within_pad",)


def test_landing_straddling_the_pad_edge_is_not_wholly_within_the_pad():
    o = classify(p=probe(legs=(11.2, 12.4)))  # one leg inside, one beyond the flag
    assert o.pad_geography == "straddling" and o.landing_category == "landed_not_within_pad"
    assert o.landed_off_pad and not o.pad_landing


def test_rest_after_body_contact_is_its_own_category():
    o = classify(p=probe(body=True, awake=False))
    assert o.env_outcome == "at_rest" and o.landing_category == "at_rest_after_body_contact"
    assert not o.pad_landing and not o.landed_off_pad and "body_contact" in o.strict_failures


@pytest.mark.parametrize(
    ("terminated", "truncated", "o", "p", "category"),
    [
        (True, False, obs(), probe(body=True, awake=True), "crash"),
        (True, False, obs(x=1.01), probe(awake=True), "out_of_bounds"),
        (False, True, obs(), probe(awake=True), "timeout"),
        (True, False, obs(x=0.1), probe(awake=True), "unknown"),
    ],
)
def test_non_landing_outcomes(terminated, truncated, o, p, category):
    out = classify(terminated=terminated, truncated=truncated, o=o, p=p)
    assert out.landing_category == category and not out.pad_landing and not out.landed_off_pad


@pytest.mark.parametrize("legs", [(math.nan, 10.0), (9.5, math.inf)])
def test_missing_or_invalid_geometry_is_unknown_not_guessed(legs):
    o = classify(p=probe(legs=legs))
    assert o.pad_geography == "unknown" and o.landing_category == "at_rest_geometry_unknown"
    assert not o.pad_landing and not o.landed_off_pad and "geometry_unknown" in o.strict_failures


def test_invalid_pad_bounds_are_unknown_too():
    o = classify(p=probe(pad=(math.nan, 12.0)))
    assert o.pad_geography == "unknown" and not o.landed_off_pad


def test_the_strict_pad_landing_definition_is_unchanged():
    """v2 adds categories; whether an episode is a strict pad landing must not change."""
    cases = [
        dict(),
        dict(o=obs(angle=0.6)),
        dict(o=obs(left=0, right=0), seen=False),
        dict(o=obs(x=0.5), p=probe(legs=(14.0, 15.4))),
        dict(p=probe(legs=(11.2, 12.4))),
        dict(p=probe(body=True)),
        dict(o=obs(left=0.0, right=0.0)),  # stale final-frame contact flags still count
    ]
    expected = [True, False, False, False, False, False, True]
    assert [classify(**c).pad_landing for c in cases] == expected


def test_legacy_episode_records_are_reclassified_only_from_what_they_stored():
    tilted = {
        "env_outcome": "at_rest",
        "body_contact": False,
        "leg_contact_seen": True,
        "legs_within_pad": True,
        "final_abs_angle_rad": 0.6,
        "pad_landing": False,
        "landed_off_pad": True,  # what v1 said
    }
    r = reclassify_legacy_episode(tilted, max_final_abs_angle_rad=0.35)
    assert r["landing_category"] == "on_pad_not_strict" and r["landed_off_pad"] is False
    assert r["pad_geography"] == "within" and r["derived_from_classifier_version"] == 1
    beside = {**tilted, "legs_within_pad": False, "final_abs_angle_rad": 0.0}
    r = reclassify_legacy_episode(beside, max_final_abs_angle_rad=0.35)
    # v1 did not store leg positions: straddling and outside cannot be told apart, and are not guessed.
    assert r["landing_category"] == "landed_not_within_pad" and r["pad_geography"] == "not_within"
    with pytest.raises(ValueError, match="missing"):
        reclassify_legacy_episode({"env_outcome": "at_rest"}, max_final_abs_angle_rad=0.35)


def test_aggregates_report_categories_and_legacy_results_say_what_they_are():
    from lunarlab.config import EvalProtocol
    from lunarlab.evaluation import aggregate, summarize_for_index

    ep = {
        "original_return": 1.0,
        "training_return": 1.0,
        "env_outcome": "at_rest",
        "length": 10,
        "actions": {"noop": 10, "left": 0, "main": 0, "right": 0},
        "hover_fraction": 0.0,
        "hover_steps": 0,
        "longest_hover_streak": 0,
        "term_returns": {},
        "body_contact": False,
        "leg_contact_seen": True,
        "legs_within_pad": True,
        "final_abs_angle_rad": 0.6,
        "pad_landing": False,
        "landed_off_pad": True,
    }
    legacy = {"aggregate": aggregate([ep], EvalProtocol()), "protocol": EvalProtocol().model_dump()}
    s = summarize_for_index(legacy, episodes=[ep])
    assert s["outcome_classifier_version"] == 1
    assert (
        s["derived_v2"]["on_pad_not_strict_rate"] == 1.0
        and s["derived_v2"]["landed_not_within_pad_rate"] == 0.0
    )
    v2 = {
        **ep,
        "landing_category": "on_pad_not_strict",
        "outcome_classifier_version": 2,
        "landed_off_pad": False,
    }
    s2 = summarize_for_index({"aggregate": aggregate([v2], EvalProtocol())}, episodes=[v2])
    assert s2["outcome_classifier_version"] == 2 and s2["on_pad_not_strict_rate"] == 1.0
    assert s2["landed_not_within_pad_rate"] == 0.0


@pytest.mark.slow
def test_real_lunarlander_episodes_carry_the_new_fields():
    from lunarlab.config import EvalProtocol
    from lunarlab.evaluation import make_eval_env, run_episode
    from lunarlab.policies import HeuristicPolicy

    env = make_eval_env(EvalProtocol(), preset("baseline"), 0.99)
    try:
        ep = run_episode(env, HeuristicPolicy(env), 20_000)
    finally:
        env.close()
    assert ep["outcome_classifier_version"] == 2 and ep["landing_category"]
    assert all(math.isfinite(x) for x in ep["leg_x_world"]) and len(ep["helipad_x_world"]) == 2
    assert ep["pad_landing"] == (ep["landing_category"] == "strict_pad_landing")


from lunarlab.rewards import preset  # noqa: E402
