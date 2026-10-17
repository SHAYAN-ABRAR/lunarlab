# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Evaluation-protocol validation: seed lists, declared vs executed environment, schema compatibility."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lunarlab.config import DQNConfig, EvalProtocol, RunConfig, TrainingConfig, training_for_profile
from lunarlab.rewards import preset
from lunarlab.runs import RunError, create_run


def test_the_default_protocol_is_valid():
    p = EvalProtocol()
    assert p.problems() == []
    p.require_valid()  # no exception


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"validation_seeds": [10_000, 10_000]}, "duplicate"),
        ({"test_seeds": [20_000, 20_001, 20_001]}, "duplicate"),
        ({"validation_seeds": [20_000], "test_seeds": [20_000, 20_001]}, "overlap"),
        ({"test_seeds": [-1]}, "range"),
        ({"test_seeds": [1_000_000]}, "range"),  # would collide with training worker seeds
        ({"env_id": "CartPole-v1"}, "environment"),
        ({"env_kwargs": {"continuous": False, "gravity": -5.0}}, "env_kwargs"),
        ({"env_kwargs": {"continuous": True}}, "env_kwargs"),
    ],
)
def test_invalid_protocols_are_reported_with_an_actionable_reason(kwargs, match):
    p = EvalProtocol(**kwargs)  # historical artifacts must stay loadable ...
    assert any(match in problem for problem in p.problems())
    with pytest.raises(ValueError, match=match):  # ... but never used for new work
        p.require_valid()


@pytest.mark.parametrize("seeds", [[True, 5], ["7"], [3.0], [None]])
def test_seed_types_are_never_coerced(seeds):
    with pytest.raises(ValidationError):
        EvalProtocol(test_seeds=seeds)


def test_empty_seed_lists_are_rejected():
    with pytest.raises(ValidationError):
        EvalProtocol(validation_seeds=[])
    with pytest.raises(ValidationError):
        EvalProtocol(test_seeds=[])


def test_new_runs_refuse_an_invalid_protocol():
    with pytest.raises(ValueError, match="overlap"):
        create_run(
            reward=preset("baseline"),
            training=training_for_profile("smoke"),
            seed=0,
            protocol=EvalProtocol(validation_seeds=[20_000], test_seeds=[20_000]),
        )


def test_a_historical_invalid_protocol_can_be_inspected_but_not_trained_or_tested(lab_home):
    from lunarlab.compare import run_summary
    from lunarlab.evaluation import evaluate_run
    from lunarlab.runs import load_config
    from lunarlab.storage import RunPaths, read_yaml, write_yaml
    from lunarlab.training import train

    cfg = create_run(reward=preset("baseline"), training=training_for_profile("smoke"), seed=0)
    paths = RunPaths(cfg.run_id)
    raw = read_yaml(paths.config)
    raw["eval_protocol"]["test_seeds"] = [10_000, 20_000]  # overlaps validation: written by hand
    write_yaml(paths.config, raw)
    loaded = load_config(cfg.run_id)
    assert loaded.eval_protocol.problems()
    assert run_summary(cfg.run_id)["protocol_valid"] is False
    with pytest.raises(RunError, match="overlap"):
        train(cfg.run_id, quiet=True)
    with pytest.raises(RunError, match="overlap"):
        evaluate_run(cfg.run_id, "test")


def _historical(algo: str) -> RunConfig:
    """Configs exactly as published runs stored them (2026-10-15)."""
    if algo == "dqn":
        return RunConfig(
            run_id="20261015-224317-dqn-baseline-s0-custom-2fe1",
            created_at="2026-10-15T16:43:17+00:00",
            reward=preset("baseline"),
            training=TrainingConfig(
                profile="custom", total_transitions=100_000, checkpoint_every=20_000, validation_every=10_000
            ),
            seed=0,
            algo="dqn",
            dqn=DQNConfig(),
        )
    return RunConfig(
        run_id="20261015-223113-baseline-s0-standard-c5af",
        created_at="2026-10-15T16:31:13+00:00",
        reward=preset("baseline"),
        training=training_for_profile("standard"),
        seed=0,
    )


def test_published_configurations_keep_their_recorded_hashes():
    # Values from runs/<id>/metadata.json of the published study: if these change, every historical
    # checkpoint would look like it came from another configuration and resuming would be refused.
    assert _historical("ppo").config_hash() == "4b544ec6345deaa9"
    assert _historical("dqn").config_hash() == "70de6039ef5e09c6"
    assert _historical("ppo").eval_protocol.protocol_hash() == "2340c66c35b045bc"


def test_evaluations_record_the_environment_that_actually_ran(lab_home):
    from lunarlab.evaluation import evaluate_policy
    from lunarlab.policies import RandomPolicy

    p = EvalProtocol(validation_seeds=[10_000], test_seeds=[20_000])
    res = evaluate_policy(
        RandomPolicy(action_seed=0), [20_000], protocol=p, reward=preset("baseline"), gamma=0.99
    )
    env = res["environment"]
    assert env["env_id"] == p.env_id and env["kwargs"] == p.env_kwargs
    assert env["effective"]["gravity"] == -10.0 and env["effective"]["enable_wind"] is False
    assert env["matches_protocol"] is True
    windy = evaluate_policy(
        RandomPolicy(action_seed=0),
        [20_000],
        protocol=p,
        reward=preset("baseline"),
        gamma=0.99,
        env_overrides={"enable_wind": True, "wind_power": 5.0},
    )
    assert windy["environment"]["effective"]["enable_wind"] is True
    assert windy["environment"]["overrides"] == {"enable_wind": True, "wind_power": 5.0}


def test_comparisons_name_a_genuine_protocol_difference():
    from lunarlab.compare import compatibility

    base = {
        "env": {"id": "LunarLander-v3"},
        "algo": "ppo",
        "algo_key": {"algo": "ppo"},
        "ppo_key": {},
        "planned_transitions": 1,
        "profile": "standard",
        "physics": {"enabled": False},
    }
    issues = compatibility([{**base, "protocol_hash": "a"}, {**base, "protocol_hash": "b"}])["issues"]
    assert any("evaluation protocols" in i for i in issues)


def test_a_holdout_is_untouched_only_if_none_of_its_seeds_were_used_for_a_final_test():
    from lunarlab.cli import _holdout_protocol
    from lunarlab.config import ProtocolError
    from lunarlab.experiments import create_experiment, load_experiment
    from lunarlab.lineage import first_test_exposure, record_test_exposure
    from lunarlab.runs import load_config

    record_test_exposure(EvalProtocol(), "20261015-000000-baseline-s0-standard-aaaa", "test-x.json")
    assert first_test_exposure(EvalProtocol()) is not None
    assert first_test_exposure(_holdout_protocol("20050:100")) is not None  # overlaps 20050..20099
    fresh = _holdout_protocol("30000:100")
    assert first_test_exposure(fresh) is None
    with pytest.raises(ProtocolError, match="overlap"):
        _holdout_protocol("10005:10")  # collides with the validation seeds

    exp = create_experiment(name="holdout", presets=["baseline"], seeds=[0], profile="smoke", protocol=fresh)
    assert load_config(exp["run_ids"][0]).eval_protocol.test_seeds == list(range(30_000, 30_100))
    stored = load_experiment(exp["experiment_id"])
    assert stored["test_seeds"] == {"first": 30_000, "last": 30_099, "count": 100}
    assert stored["test_seeds_previously_exposed"] is False
    default = create_experiment(name="default", presets=["baseline"], seeds=[0], profile="smoke")
    assert load_experiment(default["experiment_id"])["test_seeds_previously_exposed"] is True
