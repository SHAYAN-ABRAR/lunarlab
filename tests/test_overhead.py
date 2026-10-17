# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""The overhead benchmark: equivalent workloads, honest summaries, reproducible tables and figures."""

from __future__ import annotations

import json

import pytest

from lunarlab.config import actual_budget
from lunarlab.overhead import CONFIGS, _summarize, _table, render, run_benchmark

HP = {
    "n_envs": 4,
    "n_steps": 1024,
    "batch_size": 64,
    "n_epochs": 4,
    "gamma": 0.999,
    "net_arch": "x",
    "parameters": 1,
}


def _row(config, rep, loop_s, *, validation_s=0.0, checkpoint_s=0.0):
    return {
        "config": config,
        "repetition": rep,
        "transitions": 10_000,
        "wall_s": loop_s + validation_s + checkpoint_s,
        "loop_s": loop_s,
        "validation_s": validation_s,
        "validation_env_steps": 500 if validation_s else 0,
        "checkpoint_s": checkpoint_s,
        "checkpoint_save_s": 0.01,
        "cpu_s": loop_s,
        "peak_memory_bytes": 300e6,
        "artifact_bytes": {"model.zip": 150_000},
        "hyperparameters": HP,
    }


def test_summary_excludes_validation_and_checkpoints_from_the_training_loop():
    rows = [
        _row("sb3", 0, 10.0),
        _row("sb3", 1, 12.0),
        _row("accounting", 0, 11.0),
        _row("accounting", 1, 11.0),
        _row("lunarlab", 0, 11.5, validation_s=4.0, checkpoint_s=0.5),
        _row("lunarlab", 1, 11.5, validation_s=4.0, checkpoint_s=0.5),
    ]
    s = _summarize(rows)
    assert list(s) == list(CONFIGS)
    assert s["sb3"]["loop_s"]["mean"] == 11.0 and s["sb3"]["loop_s"]["sd"] == pytest.approx(1.4142, abs=1e-4)
    assert s["lunarlab"]["loop_time_relative_to_sb3"] == pytest.approx(11.5 / 11.0)
    assert s["lunarlab"]["validation_s"]["mean"] == 4.0
    assert s["lunarlab"]["loop_transitions_per_s"]["mean"] == pytest.approx(10_000 / 11.5)
    meta = {
        "created_at": "t",
        "transitions": 10_000,
        "repeats": 2,
        "torch_threads": 1,
        "system": {
            "hardware": {"cpu": "cpu", "platform": "os"},
            "software": {"python": "3", "lunarlab": "0", "git": {"revision": "abc", "dirty": False}},
        },
    }
    table = _table(s, meta)
    assert "1.05×" in table and "4.0 (500)" in table and table.count("\n| ") == 4


@pytest.mark.slow
def test_benchmark_runs_every_configuration_on_an_equivalent_workload(tmp_path):
    res = run_benchmark("smoke", transitions=1024, repeats=1, out=tmp_path / "bench", echo=lambda _m: None)
    meta = res["meta"]
    # PPO completes whole rollouts (4 x 1024 transitions): all three configurations train the same rounded budget.
    assert meta["equivalent_hyperparameters"] and meta["transitions_done"] == [actual_budget(1024, 4096)] == [
        4096
    ]
    rows = [json.loads(line) for line in (tmp_path / "bench" / "raw.jsonl").read_text().splitlines()]
    assert sorted(r["config"] for r in rows) == sorted(CONFIGS)
    c = next(r for r in rows if r["config"] == "lunarlab")
    assert c["validation_env_steps"] > 0 and c["n_checkpoints"] >= 2 and c["recording"]["steps"] > 0
    assert c["loop_s"] < c["wall_s"] and c["peak_memory_bytes"] > 0
    for name in ("summary.json", "table.md", "overhead.png", "overhead.pdf", "overhead.svg"):
        assert (tmp_path / "bench" / name).exists()
    (tmp_path / "bench" / "table.md").unlink()
    assert "overhead.png" in render(tmp_path / "bench") and (tmp_path / "bench" / "table.md").exists()
