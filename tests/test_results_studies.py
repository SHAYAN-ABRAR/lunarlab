# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Published-result generation for the study types beyond the basic reward comparison: matched-budget PPO vs
DQN, the discount-factor ablation and robustness of frozen policies (tiny budgets; the numbers mean nothing)."""

from __future__ import annotations

import json

import pytest

from lunarlab.config import EvalProtocol


@pytest.mark.slow
def test_results_cover_algorithm_comparison_discount_ablation_and_robustness(tmp_path):
    from lunarlab.evaluation import evaluate_run
    from lunarlab.experiments import build_variants, create_experiment
    from lunarlab.results import build_results
    from lunarlab.robustness import CONDITIONS, evaluate_robustness
    from lunarlab.training import EXIT_COMPLETED, train

    exp = create_experiment(
        name="results-studies",
        presets=["baseline"],
        seeds=[0, 1],
        profile="smoke",
        variants=build_variants(algos=["ppo", "dqn"], gammas=[0.99, 0.999]),
        training_overrides={"total_transitions": 2048, "checkpoint_every": 2048, "validation_every": 2048},
        protocol=EvalProtocol(validation_seeds=[10_000, 10_001], test_seeds=[20_000, 20_001, 20_002]),
    )
    assert len(exp["run_ids"]) == 8
    for rid in exp["run_ids"]:
        assert train(rid, quiet=True) == EXIT_COMPLETED
        evaluate_run(rid, "test")
        for condition in CONDITIONS:
            evaluate_robustness(rid, condition, episodes=2)

    out = build_results([exp["experiment_id"]], tmp_path / "results", echo=lambda *_: None)
    assert {"headline", "learning_curves", "algorithm_comparison", "robustness"} <= set(out["figures"])
    for name in out["figures"].values():
        assert (tmp_path / "results" / name).stat().st_size > 5_000
    data = json.loads((tmp_path / "results" / "results.json").read_text(encoding="utf-8"))
    assert data["gamma_ablation"], "the 2 x 2 algorithm x discount design yields ablation blocks"
    assert len({g["algo"] for g in data["groups"]}) == 2
    assert all(row["conditions"] for row in data["robustness"]["rows"])
    tables = (tmp_path / "results" / "tables.md").read_text(encoding="utf-8")
    assert "DQN" in tables and "PPO" in tables
    assert data["generated_by"]["analysis_code"] is not None
