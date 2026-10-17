# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Outcome classification, statistics and storage safety (pure, fast)."""

from __future__ import annotations

import numpy as np
import pytest

from lunarlab.env import LanderProbe
from lunarlab.outcomes import PadLandingCriteria, classify_outcome
from lunarlab.stats import bootstrap_ci_mean, describe, wilson_interval
from lunarlab.storage import RunPaths, atomic_write_json, read_json, safe_child, validate_run_id


def probe(*, body=False, awake=False, legs=(9.5, 10.5), pad=(8.0, 12.0)):
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


def test_clean_pad_landing():
    o = classify_outcome(True, False, obs(), probe(), leg_contact_seen=True)
    assert o.env_outcome == "at_rest" and o.pad_landing and not o.landed_off_pad


def test_pad_landing_with_stale_contact_flags_still_counts():
    # Gymnasium's per-leg boolean can read 0 while the sleeping lander rests on the pad.
    o = classify_outcome(True, False, obs(left=0.0, right=0.0), probe(), leg_contact_seen=True)
    assert o.pad_landing and not o.both_legs_contact


def test_rest_without_any_leg_contact_is_not_a_pad_landing():
    o = classify_outcome(True, False, obs(left=0, right=0), probe(), leg_contact_seen=False)
    assert o.env_outcome == "at_rest" and not o.pad_landing


def test_rest_outside_pad_is_off_pad():
    o = classify_outcome(True, False, obs(x=0.5), probe(legs=(14.0, 15.4)), leg_contact_seen=True)
    assert o.env_outcome == "at_rest" and not o.pad_landing and o.landed_off_pad


def test_one_leg_outside_flags_is_not_strict():
    o = classify_outcome(True, False, obs(), probe(legs=(11.2, 12.4)), leg_contact_seen=True)
    assert not o.legs_within_pad and not o.pad_landing


def test_tilted_rest_is_not_strict():
    o = classify_outcome(
        True,
        False,
        obs(angle=0.6),
        probe(),
        leg_contact_seen=True,
        criteria=PadLandingCriteria(max_final_abs_angle_rad=0.35),
    )
    assert not o.pad_landing


def test_crash_and_rest_after_body_contact():
    assert (
        classify_outcome(True, False, obs(), probe(body=True, awake=True), leg_contact_seen=True).env_outcome
        == "crash"
    )
    # The env pays +100 if the lander falls asleep even after body contact; we report at_rest but never pad.
    o = classify_outcome(True, False, obs(), probe(body=True, awake=False), leg_contact_seen=True)
    assert o.env_outcome == "at_rest" and o.body_contact and not o.pad_landing and not o.landed_off_pad


def test_out_of_bounds_timeout_unknown():
    assert (
        classify_outcome(True, False, obs(x=1.01), probe(awake=True), leg_contact_seen=False).env_outcome
        == "out_of_bounds"
    )
    assert (
        classify_outcome(False, True, obs(), probe(awake=True), leg_contact_seen=False).env_outcome
        == "timeout"
    )
    assert (
        classify_outcome(True, False, obs(x=0.1), probe(awake=True), leg_contact_seen=False).env_outcome
        == "unknown"
    )


def test_wilson_interval_known_values():
    lo, hi = wilson_interval(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)
    lo0, hi0 = wilson_interval(0, 10)
    assert lo0 == 0.0 and 0.25 < hi0 < 0.35
    assert wilson_interval(0, 0) is None


def test_bootstrap_is_reproducible_and_brackets_mean():
    x = np.random.default_rng(0).normal(100, 20, size=60)
    a = bootstrap_ci_mean(x, seed=3)
    assert a == bootstrap_ci_mean(x, seed=3)
    assert a[0] < x.mean() < a[1]
    assert bootstrap_ci_mean([1.0]) is None
    assert describe([])["mean"] is None


@pytest.mark.parametrize(
    "bad", ["..", "../x", "a/b", "a\\b", "C:\\Windows", "/etc/passwd", "", ".hidden", "x" * 200]
)
def test_safe_child_rejects_traversal(tmp_path, bad):
    with pytest.raises(ValueError):
        safe_child(tmp_path, bad)


def test_safe_child_accepts_plain_names(tmp_path):
    assert safe_child(tmp_path, "video-1.mp4") == (tmp_path / "video-1.mp4").resolve()


@pytest.mark.parametrize("bad", ["../runs", "a b", "", "x/y", "-start"])
def test_run_id_validation(bad):
    with pytest.raises(ValueError):
        validate_run_id(bad)
    with pytest.raises(ValueError):
        RunPaths(bad)


def test_atomic_json_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    atomic_write_json(p, {"a": np.float32(1.5), "b": [np.int64(2)]})
    assert read_json(p) == {"a": 1.5, "b": [2]}
    assert not list(tmp_path.glob("*.tmp"))


def test_csv_appender_keeps_an_existing_files_header(tmp_path):
    """Regression: a run resumed by code that logs an extra column must not misalign episodes.csv."""
    import pandas as pd

    from lunarlab.storage import CsvAppender

    path = tmp_path / "episodes.csv"
    older = CsvAppender(path, ["episode", "a", "c"])
    older.add({"episode": 0, "a": 1, "c": 3})
    older.flush()
    newer = CsvAppender(path, ["episode", "a", "b", "c"])  # newer layout: a column in the middle
    newer.add({"episode": 1, "a": 1, "b": 2, "c": 3})
    newer.flush()
    df = pd.read_csv(path)
    assert list(df.columns) == ["episode", "a", "c"]
    assert df["episode"].tolist() == [0, 1] and df["c"].tolist() == [3, 3]


def test_mixed_width_episode_log_is_recovered_without_rewriting_it(tmp_path):
    """Files written before that fix: rows after the resume have the newer layout under the older header."""
    import csv

    import pandas as pd

    from lunarlab.compare import _read_mixed_episodes
    from lunarlab.training import EPISODE_FIELDS

    assert "term_learned_reward" in EPISODE_FIELDS
    older = [f for f in EPISODE_FIELDS if f != "term_learned_reward"]

    def row(fields):  # each column holds its position in the current layout, so misalignment shows
        return ["landed" if f == "env_outcome" else EPISODE_FIELDS.index(f) for f in fields]

    path = tmp_path / "episodes.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows([older, row(older), row(older), row(EPISODE_FIELDS)])
    before = path.read_bytes()
    with pytest.raises(pd.errors.ParserError):
        pd.read_csv(path)

    df = _read_mixed_episodes(path)
    assert len(df) == 3 and path.read_bytes() == before
    for f in older:
        expected = "landed" if f == "env_outcome" else EPISODE_FIELDS.index(f)
        assert df[f].tolist() == [expected] * 3, f
    assert df["term_learned_reward"].isna().tolist() == [True, True, False]
