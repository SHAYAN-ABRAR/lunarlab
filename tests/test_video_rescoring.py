"""Recording (MP4 + fallback), telemetry indexing, and trajectory re-scoring."""

from __future__ import annotations

import pytest

from lunarlab.config import EvalProtocol
from lunarlab.policies import RandomPolicy
from lunarlab.recording import find_recording, list_recordings, mp4_available, record_demo, record_episode
from lunarlab.rescoring import rescore
from lunarlab.rewards import preset
from lunarlab.storage import read_json

pytestmark = pytest.mark.slow


def test_mp4_demo_is_verified_and_synchronised():
    ok, why = mp4_available()
    if not ok:
        pytest.skip(f"MP4 encoder unavailable here: {why}")
    meta = record_demo("random", episode_seed=20_002, action_seed=1)
    tpath, vdir = find_recording(meta["recording_id"])
    t = read_json(tpath)
    video = vdir / t["video"]["file"]
    assert video.exists() and video.stat().st_size > 0
    assert t["video"]["verified"] and t["video"]["frames"] == t["n_frames"]
    assert len(t["rows"]) == t["n_frames"] == t["episode"]["length"] + 1  # reset frame + one per step
    assert t["rows"][0]["action"] is None and t["rows"][0]["t"] == 0
    assert t["rows"][-1]["terminated"] or t["rows"][-1]["truncated"]
    assert t["rows"][-1]["cum_original"] == pytest.approx(t["episode"]["original_return"])
    assert t["policy"]["kind"] == "random" and t["seed_split"] == "test"
    assert any(m["recording_id"] == meta["recording_id"] for m in list_recordings())


def test_jpeg_fallback_sink(tmp_path):
    meta = record_episode(
        RandomPolicy(2),
        episode_seed=10_003,
        out_dir=tmp_path,
        video_dir=tmp_path,
        reward=preset("hover-bonus"),
        gamma=0.999,
        protocol=EvalProtocol(),
        source={"type": "test"},
        prefer="frames",
    )
    assert meta["video"]["format"] == "jpeg-frames" and meta["video"]["verified"]
    frames = list((tmp_path / meta["video"]["file"]).glob("*.jpg"))
    assert len(frames) == meta["n_frames"]
    assert meta["seed_split"] == "validation"


def test_find_recording_rejects_traversal():
    with pytest.raises(KeyError):
        find_recording("../../secrets")


def test_rescoring_matches_recorded_terms_and_flags_scope():
    meta = record_demo("heuristic", episode_seed=20_004)
    t = read_json(find_recording(meta["recording_id"])[0])
    res = rescore(
        t,
        [preset("baseline"), preset("potential"), preset("hover-bonus")],
        gamma=0.999,
        detector=EvalProtocol().hover_detector,
    )
    assert "not retraining" in res["disclaimer"]
    base, pot, hov = res["configs"]
    assert base["undiscounted"]["training"] == pytest.approx(t["episode"]["original_return"], abs=1e-6)
    assert base["undiscounted"]["original"] == pytest.approx(t["episode"]["original_return"], abs=1e-6)
    # Terminated episode: discounted potential term telescopes to -alpha * Phi(s0).
    from lunarlab.rewards import potential

    if t["episode"]["terminated"]:
        phi0 = potential(t["rows"][0]["obs"], preset("potential").potential.weights)
        assert pot["discounted"]["terms"]["potential_shaping"] == pytest.approx(-10.0 * phi0, abs=1e-4)
    assert set(hov["by_phase"]["hover_bonus"]) == {"hover", "airborne", "ground_contact", "final_step"}
    assert len(res["cumulative_original"]) == len(res["series_index"])


def test_recorded_scene_matches_seed_rederivation():
    from lunarlab.env import scene_for_seed

    meta = record_demo("random", episode_seed=20_006)
    t = read_json(find_recording(meta["recording_id"])[0])
    assert t["scene"] == scene_for_seed(20_006)
