"""Training under varied physics: configuration, the per-episode randomizer, training and comparison."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from lunarlab.config import (
    EvalProtocol,
    PhysicsRandomization,
    PPOConfig,
    RunConfig,
    TrainingConfig,
    resume_compatibility,
)
from lunarlab.env import make_env, scene_geometry
from lunarlab.physics import PhysicsRandomizer, sample_physics
from lunarlab.rewards import preset

RANDOM = PhysicsRandomization(enabled=True)


def run_config(**kw) -> RunConfig:
    return RunConfig(
        run_id="r",
        created_at="2026-01-01T00:00:00+00:00",
        reward=preset("baseline"),
        training=TrainingConfig(profile="standard", total_transitions=1_000_000),
        seed=1,
        **kw,
    )


def test_physics_ranges_are_validated():
    for bad in (
        {"gravity": (-12.5, -9.0)},
        {"gravity": (-9.0, -11.0)},
        {"wind_power": (0.0, 25.0)},
        {"turbulence_power": (-0.1, 1.0)},
        {"wind_probability": 1.5},
    ):
        with pytest.raises(ValidationError):
            PhysicsRandomization(enabled=True, **bad)
    assert "randomized" in RANDOM.describe() and PhysicsRandomization().describe().startswith("fixed")


def test_fixed_physics_runs_hash_as_before_and_randomized_ones_differ():
    base = run_config()
    assert run_config(physics=PhysicsRandomization()).config_hash() == base.config_hash()
    assert run_config(physics=RANDOM).config_hash() != base.config_hash()
    other = RANDOM.model_copy(update={"wind_probability": 0.5})
    assert run_config(physics=other).config_hash() != run_config(physics=RANDOM).config_hash()


def test_resume_refuses_a_change_of_training_physics():
    assert any(
        "training physics" in p for p in resume_compatibility(run_config(), run_config(physics=RANDOM))
    )
    assert resume_compatibility(run_config(physics=RANDOM), run_config(physics=RANDOM)) == []


def test_sampling_is_reproducible_and_within_range():
    cfg = PhysicsRandomization(
        enabled=True, wind_probability=0.5, wind_power=(2.0, 6.0), gravity=(-11.5, -8.5)
    )
    a = [sample_physics(cfg, rng) for rng in [np.random.default_rng(7)] for _ in range(200)]
    b = [sample_physics(cfg, rng) for rng in [np.random.default_rng(7)] for _ in range(200)]
    assert a == b
    winds = [p for p in a if p["wind"]]
    assert 60 < len(winds) < 140  # about half the episodes have wind
    assert all(2.0 <= p["wind_power"] <= 6.0 and 0.0 <= p["turbulence_power"] <= 1.0 for p in winds)
    assert all(p["wind_power"] == 0.0 and p["turbulence_power"] == 0.0 for p in a if not p["wind"])
    assert all(-11.5 <= p["gravity"] <= -8.5 for p in a)


def test_randomizer_applies_physics_per_episode_without_changing_the_terrain():
    plain = make_env()
    env = PhysicsRandomizer(make_env(), RANDOM)
    try:
        _, info = env.reset(seed=123)
        phys = info["lunarlab_physics"]
        u = env.unwrapped
        assert u.gravity == pytest.approx(phys["gravity"]) and tuple(u.world.gravity) == pytest.approx(
            (0, phys["gravity"])
        )
        assert u.enable_wind == phys["wind"]
        plain.reset(seed=123)
        # the episode seed still fixes the terrain and the pad, whatever the physics
        assert scene_geometry(env)["terrain"] == scene_geometry(plain)["terrain"]
        draws = [phys]
        for _ in range(4):  # auto-resets (no seed) continue the same reproducible stream
            draws.append(env.reset()[1]["lunarlab_physics"])
        again = PhysicsRandomizer(make_env(), RANDOM)
        replay = [again.reset(seed=123)[1]["lunarlab_physics"]] + [
            again.reset()[1]["lunarlab_physics"] for _ in range(4)
        ]
        assert replay == draws and len({d["gravity"] for d in draws}) == 5
        # the final step of an episode reports its physics too
        env.reset(seed=5)
        while True:
            _, _, te, tr, info = env.step(0)
            if te or tr:
                break
        assert info["lunarlab_physics"] == env.current
        again.close()
    finally:
        env.close()
        plain.close()


@pytest.mark.slow
def test_randomized_training_logs_the_physics_of_every_episode():
    from lunarlab.runs import create_run
    from lunarlab.storage import RunPaths
    from lunarlab.training import EXIT_COMPLETED, train

    cfg = create_run(
        reward=preset("baseline"),
        seed=0,
        ppo=PPOConfig(n_envs=2, n_steps=128, batch_size=64),
        protocol=EvalProtocol(validation_seeds=[10_000]),
        training=TrainingConfig(
            profile="custom", total_transitions=1024, checkpoint_every=512, validation_every=512
        ),
        physics=PhysicsRandomization(enabled=True, wind_probability=0.5, gravity=(-11.0, -9.5)),
    )
    assert "-rand-" in cfg.run_id
    assert train(cfg.run_id) == EXIT_COMPLETED
    df = pd.read_csv(RunPaths(cfg.run_id).episodes)
    assert len(df) > 3 and {"wind", "wind_power", "turbulence_power", "gravity"} <= set(df.columns)
    assert df["gravity"].between(-11.0, -9.5).all() and df["gravity"].nunique() == len(df)
    assert (df.loc[df["wind"] == 0, "wind_power"] == 0).all()


def test_variants_and_matched_budgets():
    from lunarlab.experiments import build_variants, plan_suite

    v = build_variants(algos=["ppo"], physics="both")
    assert [x["physics"].enabled for x in v] == [False, True] and v[1]["name"] == "PPO · randomized physics"
    plan = plan_suite(
        ["baseline"],
        [0, 1],
        "standard",
        variants=build_variants(algos=["ppo", "dqn"]),
        training_overrides={"total_transitions": 300_000},
    )
    budgets = {x["transitions_per_run"] for x in plan["variants"]}
    assert budgets == {303_104} and plan["n_runs"] == 4  # both algorithms train exactly the same budget
    with pytest.raises(ValueError):
        build_variants(physics="sometimes")


@pytest.mark.slow
def test_compare_pairs_fixed_and_randomized_training():
    from lunarlab.compare import compare_runs
    from lunarlab.evaluation import evaluate_run
    from lunarlab.experiments import build_variants, create_experiment
    from lunarlab.robustness import evaluate_robustness
    from lunarlab.training import EXIT_COMPLETED, train

    exp = create_experiment(
        name="physics-test",
        presets=["baseline"],
        seeds=[0],
        profile="smoke",
        variants=build_variants(physics="both"),
    )
    for rid in exp["run_ids"]:
        assert train(rid) == EXIT_COMPLETED
        evaluate_run(rid, "test", checkpoint="best")
        evaluate_robustness(rid, "wind-10", episodes=3)
    data = compare_runs(exp["run_ids"], split="test")
    names = sorted(g["reward_name"] for g in data["groups"])
    assert names == ["Original baseline", "Original baseline · randomized physics"]
    assert any("training physics" in i for i in data["compatibility"]["issues"])
    (pair,) = data["physics_comparison"]
    by = {c["condition"]: c for c in pair["conditions"]}
    assert by["calm"]["fixed"] and by["calm"]["randomized"] and by["wind-10"]["difference"] is not None
    assert by["calm"]["ci"] is None  # one policy per side: no interval, never a made-up one
    assert by["wind-15"]["fixed"] is None  # not evaluated: reported as missing, never filled in


def test_api_accepts_training_physics_and_rejects_bad_ranges():
    from fastapi.testclient import TestClient

    from lunarlab.server.main import create_app

    h = {"X-LunarLab": "1"}
    with TestClient(create_app(start_jobs=False, testing=True)) as c:
        body = {"preset": "baseline", "start": False, "physics": {"enabled": True, "gravity": [-11.0, -9.0]}}
        r = c.post("/api/runs", json=body, headers=h)
        assert r.status_code == 201, r.text
        assert "randomized" in r.json()["run"]["physics_label"]
        bad = {**body, "physics": {"enabled": True, "gravity": [-13.0, -9.0]}}
        assert c.post("/api/runs", json=bad, headers=h).status_code == 422
        plan = c.post(
            "/api/experiments/plan",
            json={"presets": ["baseline"], "seeds": [0, 1], "physics": "both"},
            headers=h,
        ).json()
        assert plan["n_runs"] == 4 and len(plan["variants"]) == 2
