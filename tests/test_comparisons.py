"""PPO-DQN comparisons: the discount-factor ablation, difference intervals and wall-clock context."""

from __future__ import annotations

import pandas as pd
import pytest

from lunarlab.compare import (
    REFERENCE_GAMMA,
    compatibility,
    elapsed_seconds,
    gamma_ablation,
    group_by_reward,
    wall_clock_notes,
)
from lunarlab.rl_stats import bootstrap_difference_ci


def _summary(algo: str, gamma: float, seed: int, score: float, *, budget: int = 303_104, **extra) -> dict:
    reference = abs(gamma - REFERENCE_GAMMA[algo]) < 1e-12
    return {
        "run_id": f"{algo}-g{gamma:g}-s{seed}",
        "algo": algo,
        "gamma": gamma,
        "seed": seed,
        "reward_name": "Original baseline",
        "reward_preset": "baseline",
        "reward_hash": "r1",
        "active_terms": [],
        "variant": "" if reference else f"gamma {gamma:g}",
        "variant_key": f"g{gamma:g}|fixed",
        "physics": {"enabled": False},
        "physics_label": "fixed (default physics)",
        "latest_test": {"mean_original_return": score, "pad_landing_rate": 0.5},
        "latest_validation": None,
        "checkpoint_transitions": budget,
        "state": "completed",
        "planned_transitions": budget,
        "algo_key": {"algo": algo, "gamma": gamma, "learning_rate": 1e-3},
        "ppo_key": {},
        "protocol_hash": "p",
        "profile": "standard",
        "env": {"id": "LunarLander-v3"},
        **extra,
    }


def _factorial(scores: dict[tuple[str, float], list[float]], **kw) -> list[dict]:
    return [
        _summary(algo, gamma, seed, v, **kw)
        for (algo, gamma), vals in scores.items()
        for seed, v in enumerate(vals)
    ]


TWO_BY_TWO = {
    ("ppo", 0.99): [150.0, 160.0, 140.0],
    ("ppo", 0.999): [200.0, 210.0, 190.0],
    ("dqn", 0.99): [100.0, 110.0, 90.0],
    ("dqn", 0.999): [50.0, 60.0, 40.0],
}


def test_difference_interval_brackets_the_observed_difference():
    x, y = [10.0, 12.0, 11.0, 13.0], [1.0, 2.0, 3.0, 2.0]
    lo, hi = bootstrap_difference_ci(x, y)
    assert 10.0 - 3.0 <= lo <= 11.5 - 2.0 <= hi <= 13.0 - 1.0  # within [min x - max y, max x - min y]
    assert bootstrap_difference_ci([1.0], y) is None


def test_gamma_ablation_separates_the_discount_factor_from_the_algorithm():
    summaries = _factorial(TWO_BY_TWO)
    blocks = gamma_ablation(group_by_reward(summaries), summaries)
    assert len(blocks) == 1
    b = blocks[0]
    assert [(c["algo"], c["gamma"], c["n_seeds"]) for c in b["cells"]] == [
        ("ppo", 0.99, 3),
        ("ppo", 0.999, 3),
        ("dqn", 0.99, 3),
        ("dqn", 0.999, 3),
    ]
    assert [c["reference"] for c in b["cells"]] == [False, True, True, False]
    # Within each algorithm, against its reference gamma.
    effects = {(e["algo"], e["gamma"], e["vs_gamma"]): e for e in b["gamma_effects"]}
    assert effects[("ppo", 0.99, 0.999)]["difference"] == pytest.approx(-50.0)
    assert effects[("dqn", 0.999, 0.99)]["difference"] == pytest.approx(-50.0)
    assert effects[("ppo", 0.99, 0.999)]["p_improvement"] == 0.0
    # PPO - DQN at matched gammas, and the confounded reference setups (0.999 vs 0.99).
    assert {e["gamma"]: e["difference"] for e in b["algorithm_effects"]} == pytest.approx(
        {0.99: 50.0, 0.999: 150.0}
    )
    assert b["reference_setups"]["difference"] == pytest.approx(100.0)
    assert (b["reference_setups"]["ppo_gamma"], b["reference_setups"]["dqn_gamma"]) == (0.999, 0.99)
    assert any("As few as 3" in c for c in b["caveats"])
    assert not any("budget" in c for c in b["caveats"])


def test_gamma_ablation_needs_a_controlled_contrast():
    # Each algorithm only at its own reference gamma: nothing separates gamma from the algorithm.
    summaries = _factorial({("ppo", 0.999): [200.0, 210.0], ("dqn", 0.99): [100.0, 90.0]})
    assert gamma_ablation(group_by_reward(summaries), summaries) == []


def test_gamma_ablation_flags_uncontrolled_cells():
    summaries = _factorial({("ppo", 0.99): [150.0, 160.0]}, budget=100_000) + _factorial(
        {("ppo", 0.999): [200.0, 210.0]}
    )
    [b] = gamma_ablation(group_by_reward(summaries), summaries)
    assert any("budgets differ" in c for c in b["caveats"])
    assert b["algorithm_effects"] == [] and b["reference_setups"] is None


def test_compatibility_names_a_gamma_only_difference_as_an_ablation():
    summaries = _factorial({("ppo", 0.99): [1.0], ("ppo", 0.999): [1.0]})
    [issue] = compatibility(summaries)["issues"]
    assert "discount factors (gamma 0.99, 0.999)" in issue and "ablation" in issue


def test_elapsed_time_accumulates_over_resumed_segments():
    df = pd.DataFrame({"segment": [0, 0, 0, 1, 1], "wall_time_s": [1.0, 2.0, 3.0, 0.5, 2.0]})
    assert elapsed_seconds(df).tolist() == [1.0, 2.0, 3.0, 3.5, 5.0]


def test_wall_clock_notes_name_what_differs():
    def conds(cpu, slots, segments=1):
        return {
            "training_conditions": {
                "cpu": cpu,
                "segments": segments,
                "parallel_slots": slots,
                "device": ["cpu"],
                "torch_threads": [1],
            }
        }

    assert wall_clock_notes([conds("A", [2]), conds("A", [2])]) == []
    notes = " ".join(wall_clock_notes([conds("A", [1]), conds("B", [6], segments=2)]))
    assert "different machines" in notes and "1 at a time, 6 at a time" in notes and "resumed" in notes
    assert "not recorded" in " ".join(wall_clock_notes([conds("A", [0])]))
