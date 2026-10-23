# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""tools/compare_study_summaries.py recomputes published numbers from raw episodes and classifies differences."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _tool():
    spec = importlib.util.spec_from_file_location(
        "compare_study_summaries", ROOT / "tools" / "compare_study_summaries.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _episode(ret: float, landed: bool = False, outcome: str = "landed") -> dict:
    return {"original_return": ret, "pad_landing": landed, "env_outcome": outcome}


def _study(tmp_path: Path, runs_episodes: list[list[dict]]) -> tuple[dict, Path]:
    """A published summary and an exported bundle for one group of runs, consistent with each other."""
    bundle = tmp_path / "bundle"
    inventory, per_seed = [], []
    for i, eps in enumerate(runs_episodes):
        rid = f"run-{i}"
        (bundle / "group" / rid).mkdir(parents=True)
        (bundle / "group" / rid / "evaluation.json").write_text(
            json.dumps({"episodes": eps}), encoding="utf-8"
        )
        inventory.append({"run_id": rid, "folder": f"group/{rid}"})
        n = len(eps)
        evaluation = {
            "n_episodes": n,
            "mean_original_return": sum(e["original_return"] for e in eps) / n,
            "pad_landing_rate": sum(e["pad_landing"] for e in eps) / n,
            "timeout_rate": sum(e["env_outcome"] == "timeout" for e in eps) / n,
        }
        per_seed.append({"run_id": rid, "evaluation": evaluation})
    (bundle / "inventory.json").write_text(json.dumps({"runs": inventory}), encoding="utf-8")
    means = sorted(p["evaluation"]["mean_original_return"] for p in per_seed)
    k = len(means) // 4
    iqm = sum(means[k : len(means) - k]) / (len(means) - 2 * k)
    published = {
        "groups": [{"reward_name": "G", "per_seed": per_seed}],
        "robust_stats": {"groups": {"G": {"iqm": iqm}}},
    }
    return published, bundle


RUNS = [
    [_episode(250.0, True), _episode(240.0, True)],
    [_episode(-30.0, outcome="timeout"), _episode(10.0)],
    [_episode(260.0, True), _episode(-100.0, outcome="crash")],
    [_episode(270.0, True), _episode(268.0, True)],
    [_episode(100.0), _episode(120.0, True)],
]


def test_a_consistent_bundle_reproduces_every_policy_and_the_trimmed_group_mean(tmp_path):
    tool = _tool()
    published, bundle = _study(tmp_path, RUNS)
    result = tool.recompute(published, bundle)
    assert result["all_match"] and result["policies"] == 5 and result["episodes"] == 10
    group = result["groups"][0]
    assert group["iqm_matches"]
    # five policies: the lowest and highest means are trimmed, the middle three averaged
    assert group["iqm_from_raw_episodes"] == pytest.approx((80.0 + 110.0 + 245.0) / 3)


def test_a_changed_episode_or_outcome_is_reported_as_a_mismatch(tmp_path):
    tool = _tool()
    published, bundle = _study(tmp_path, RUNS)
    path = bundle / "group" / "run-1" / "evaluation.json"
    episodes = json.loads(path.read_text(encoding="utf-8"))["episodes"]
    episodes[0]["original_return"] += 0.5
    episodes[1]["pad_landing"] = True
    path.write_text(json.dumps({"episodes": episodes}), encoding="utf-8")
    result = tool.recompute(published, bundle)
    assert not result["all_match"]
    policy = result["groups"][0]["per_policy"][1]
    assert policy["matches_published"] == {
        "n_episodes": True,
        "mean_original_return": False,
        "pad_landing_rate": False,
        "timeout_rate": True,
    }


def test_differences_separate_changed_values_from_added_fields_and_ignore_generation_metadata():
    tool = _tool()
    published = {"a": 1.0, "generated_at": "then", "b": {"c": 2, "items": [1, 2]}}
    regenerated = {"a": 1.5, "generated_at": "now", "b": {"c": 2, "items": [1, 2, 3], "d": None}}
    diff = {d["path"]: d for d in tool.differences(published, regenerated)}
    assert set(diff) == {"/a", "/b/items", "/b/d"}
    assert diff["/a"]["abs_difference"] == pytest.approx(0.5)
    assert diff["/b/d"]["published"] == "<absent>"
    assert diff["/b/items"]["published"] == "list of 2"


def test_the_command_fails_when_a_published_value_differs(tmp_path, monkeypatch):
    tool = _tool()
    published, bundle = _study(tmp_path, RUNS)
    (tmp_path / "published.json").write_text(json.dumps(published), encoding="utf-8")
    regenerated = tmp_path / "regenerated"
    regenerated.mkdir()
    args = ["--published", str(tmp_path / "published.json"), "--artifacts", str(bundle)]
    args += ["--regenerated", str(regenerated), "--out", str(tmp_path / "out.json")]
    monkeypatch.setattr(sys, "argv", ["compare_study_summaries.py", *args])

    added = json.loads(json.dumps(published))
    added["groups"][0]["per_seed"][0]["evaluation"]["checkpoint_sha256"] = "abc"  # newer code adds a field
    (regenerated / "results.json").write_text(json.dumps(added), encoding="utf-8")
    assert tool.main() == 0
    report = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert report["regeneration"]["counts"] == {
        "published_value_changed": 0,
        "published_field_missing": 0,
        "field_added_by_current_code": 1,
    }

    changed = json.loads(json.dumps(published))
    changed["robust_stats"]["groups"]["G"]["iqm"] += 1.0
    (regenerated / "results.json").write_text(json.dumps(changed), encoding="utf-8")
    assert tool.main() == 1
