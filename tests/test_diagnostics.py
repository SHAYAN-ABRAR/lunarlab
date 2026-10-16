"""Policy diagnostics stored with recordings (PPO probabilities/entropy/value, DQN Q-values)."""

from __future__ import annotations

import math

import pytest

from lunarlab.config import DQNConfig, EvalProtocol, PPOConfig, TrainingConfig
from lunarlab.rewards import preset

pytestmark = pytest.mark.slow


def _trained(algo: str) -> str:
    from lunarlab.runs import create_run
    from lunarlab.training import EXIT_COMPLETED, train

    cfg = create_run(
        reward=preset("baseline"),
        seed=0,
        algo=algo,
        ppo=PPOConfig(n_envs=2, n_steps=64, batch_size=32),
        dqn=DQNConfig(buffer_size=1000, batch_size=32, net_arch=[32], learning_starts=64)
        if algo == "dqn"
        else None,
        protocol=EvalProtocol(validation_seeds=[10_000]),
        training=TrainingConfig(
            profile="custom", total_transitions=256, checkpoint_every=256, validation_every=256
        ),
    )
    assert train(cfg.run_id) == EXIT_COMPLETED
    return cfg.run_id


def _telemetry(recording_id: str) -> dict:
    from lunarlab.recording import find_recording
    from lunarlab.storage import read_json

    return read_json(find_recording(recording_id)[0])


def test_ppo_recordings_store_probabilities_entropy_and_value():
    from lunarlab.recording import record_run

    rec = record_run(_trained("ppo"), episode_seed=20_000, checkpoint="final")
    t = _telemetry(rec["recording_id"])
    assert set(t["policy_diagnostics"]["fields"]) == {"probs", "entropy", "value"}
    assert "policy" not in t["rows"][0]  # frame 0: no decision yet
    for r in t["rows"][1:]:
        p = r["policy"]
        assert sum(p["probs"]) == pytest.approx(1.0, abs=1e-4)
        assert 0.0 <= p["entropy"] <= math.log(4) + 1e-4 and math.isfinite(p["value"])
        assert p["probs"][r["action"]] == max(p["probs"])  # deterministic: a most probable action (ties kept)


def test_dqn_recordings_store_action_values():
    from lunarlab.recording import record_run

    rec = record_run(_trained("dqn"), episode_seed=20_000, checkpoint="final")
    t = _telemetry(rec["recording_id"])
    assert set(t["policy_diagnostics"]["fields"]) == {"q"}
    for r in t["rows"][1:]:
        q = r["policy"]["q"]
        assert len(q) == 4
        assert q[r["action"]] == max(q)  # greedy; rounding can tie values, never reorder them


def test_demonstrations_have_no_policy_diagnostics():
    from lunarlab.recording import record_demo

    t = _telemetry(record_demo("heuristic", episode_seed=20_000)["recording_id"])
    assert "policy_diagnostics" not in t and all("policy" not in r for r in t["rows"])
