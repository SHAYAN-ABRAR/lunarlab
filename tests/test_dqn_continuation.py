"""DQN continuation: resumable checkpoints restore the replay buffer and every counter SB3 needs.

The reference point is SB3 2.9.0 (``stable_baselines3.dqn.dqn.DQN``,
``common.off_policy_algorithm.OffPolicyAlgorithm``, ``common.buffers.ReplayBuffer``).
"""

from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from lunarlab.config import DQNConfig, EvalProtocol, PPOConfig, TrainingConfig
from lunarlab.rewards import preset
from lunarlab.runs import RunError, create_run, load_metadata, read_manifest
from lunarlab.storage import RunPaths

pytestmark = pytest.mark.slow

TINY_DQN = DQNConfig(
    buffer_size=1000,
    batch_size=32,
    net_arch=[32],
    learning_starts=0,
    target_update_interval=50,
    exploration_fraction=0.5,
)
TINY_PROTOCOL = EvalProtocol(validation_seeds=[10_000], test_seeds=[20_000, 20_001])


def dqn_run(total=1024, every=256, validation_every=512):
    return create_run(
        reward=preset("baseline"),
        seed=0,
        algo="dqn",
        dqn=TINY_DQN,
        protocol=TINY_PROTOCOL,
        training=TrainingConfig(
            profile="custom",
            total_transitions=total,
            checkpoint_every=every,
            validation_every=validation_every,
        ),
    )


def stop_after_validation_at(transitions: int):
    """on_validation hook: ask for a stop right after the validation at ``transitions`` (a safe boundary)."""
    return lambda n, _mean: n >= transitions


@pytest.fixture
def learn_spy(monkeypatch):
    """Record the DQN state at the start of every ``learn()`` call (i.e. before the first resumed action)."""
    from stable_baselines3 import DQN

    seen: list[dict] = []
    original = DQN.learn

    def spy(self, *args, **kwargs):
        seen.append(
            {
                "num_timesteps": self.num_timesteps,
                "replay_size": self.replay_buffer.size(),
                "replay_pos": self.replay_buffer.pos,
                "replay_full": self.replay_buffer.full,
                "exploration_rate": self.exploration_rate,
                "n_calls": self._n_calls,
                "n_updates": self._n_updates,
                "target": {k: v.clone() for k, v in self.q_net_target.state_dict().items()},
                # A deep copy: the optimizer updates its state tensors in place once training continues.
                "optimizer": copy.deepcopy(self.policy.optimizer.state_dict()),
                "observations": self.replay_buffer.observations[: self.replay_buffer.size()].copy(),
            }
        )
        return original(self, *args, **kwargs)

    monkeypatch.setattr(DQN, "learn", spy)
    return seen


def test_dqn_stop_and_resume_continue_the_same_training_state(learn_spy):
    from lunarlab.training import EXIT_COMPLETED, EXIT_STOPPED, train

    cfg = dqn_run()
    assert train(cfg.run_id, quiet=True, on_validation=stop_after_validation_at(512)) == EXIT_STOPPED
    paths = RunPaths(cfg.run_id)
    stop = next(c for c in read_manifest(paths)["checkpoints"] if c["kind"] == "stop")
    assert stop["transitions"] == 512
    assert stop["resumable"] is True and stop["continuation"]["format"] == "lunarlab.dqn-continuation"

    assert train(cfg.run_id, resume=True, quiet=True) == EXIT_COMPLETED
    resumed = learn_spy[-1]
    # Replay buffer: every transition stored before the stop boundary is back, in place.
    assert resumed["num_timesteps"] == 512
    assert resumed["replay_size"] == 512 and resumed["replay_pos"] == 512 and not resumed["replay_full"]
    # Exploration continues on the original schedule (1.0 -> 0.1 over the first half of 1,024 transitions)
    # instead of a fresh model's 0.0; the target-update phase continues from 512 environment steps.
    assert resumed["exploration_rate"] == pytest.approx(0.1)
    assert resumed["n_calls"] == 512
    assert resumed["n_updates"] == stop["sb3_n_updates"] > 0

    # Transition accounting: the segments meet at the boundary; the one interaction taken after the stop
    # request (and never stored or trained on) is recorded instead of disappearing.
    segs = load_metadata(cfg.run_id)["segments"]
    assert segs[0]["end_transitions"] == segs[1]["start_transitions"] == 512
    assert segs[0]["discarded_interactions"] == 1
    assert segs[1]["end_transitions"] == cfg.planned_transitions


def test_resumed_target_network_optimizer_and_replay_match_the_stop_checkpoint(learn_spy):
    import torch

    from lunarlab.continuation import read_continuation
    from lunarlab.training import EXIT_STOPPED, train

    cfg = dqn_run()
    assert train(cfg.run_id, quiet=True, on_validation=stop_after_validation_at(512)) == EXIT_STOPPED
    paths = RunPaths(cfg.run_id)
    stop = next(c for c in read_manifest(paths)["checkpoints"] if c["kind"] == "stop")
    state, arrays = read_continuation(paths, stop)
    learn_spy.clear()
    train(cfg.run_id, resume=True, quiet=True)
    resumed = learn_spy[0]
    np.testing.assert_array_equal(resumed["observations"], arrays["observations"][:512])
    # The target network and Adam moments come back exactly as saved.
    from stable_baselines3.common.save_util import load_from_zip_file

    _, params, _ = load_from_zip_file(str(paths.checkpoints / stop["name"]), load_data=False)
    for k, v in resumed["target"].items():
        torch.testing.assert_close(v, params["policy"][f"q_net_target.{k}"])
    saved_opt = params["policy.optimizer"]["state"]
    for idx, st in resumed["optimizer"]["state"].items():
        torch.testing.assert_close(st["exp_avg"], saved_opt[idx]["exp_avg"])
    assert state["n_calls"] == 512 and state["num_timesteps"] == 512


def test_legacy_dqn_checkpoint_without_replay_state_cannot_masquerade_as_a_resume():
    from lunarlab.lineage import create_warm_restart
    from lunarlab.storage import atomic_write_json
    from lunarlab.training import EXIT_STOPPED, train

    cfg = dqn_run()
    assert train(cfg.run_id, quiet=True, on_validation=stop_after_validation_at(512)) == EXIT_STOPPED
    paths = RunPaths(cfg.run_id)
    # Make the stop checkpoint look like one written before replay buffers were stored.
    manifest = read_manifest(paths)
    for c in manifest["checkpoints"]:
        for k in ("resumable", "continuation", "role"):
            c.pop(k, None)
    atomic_write_json(paths.checkpoint_manifest, manifest)
    with pytest.raises(RunError, match="warm restart"):
        train(cfg.run_id, resume=True, quiet=True)

    with pytest.raises(RunError, match="confirm"):
        create_warm_restart(cfg.run_id, checkpoint="latest", confirm=False)
    child = create_warm_restart(cfg.run_id, checkpoint="latest", confirm=True)
    assert child.run_id != cfg.run_id and child.warm_start is not None
    meta = load_metadata(child.run_id)
    lineage = meta["lineage"]
    assert lineage["kind"] == "warm_restart" and lineage["parent_run_id"] == cfg.run_id
    assert "replay buffer" in " ".join(lineage["reset"]) and "network weights" in " ".join(
        lineage["preserved"]
    )
    assert child.config_hash() != cfg.config_hash()  # never grouped with uninterrupted runs

    from lunarlab.compare import run_summary

    assert "warm restart" in run_summary(child.run_id)["variant"]


def test_corrupt_missing_or_incompatible_replay_state_fails_clearly():
    from lunarlab.continuation import read_continuation
    from lunarlab.training import EXIT_STOPPED, train

    cfg = dqn_run()
    assert train(cfg.run_id, quiet=True, on_validation=stop_after_validation_at(512)) == EXIT_STOPPED
    paths = RunPaths(cfg.run_id)
    stop = next(c for c in read_manifest(paths)["checkpoints"] if c["kind"] == "stop")
    replay = paths.checkpoints / stop["continuation"]["replay_file"]
    state_file = paths.checkpoints / stop["continuation"]["state_file"]
    original = replay.read_bytes()

    replay.write_bytes(original[:-7] + b"tampers")  # same size, different bytes
    with pytest.raises(RunError, match="SHA-256"):
        read_continuation(paths, stop)
    replay.unlink()
    with pytest.raises(RunError, match="missing"):
        read_continuation(paths, stop)
    replay.write_bytes(original)

    # A state file claiming another buffer layout is refused before any array is allocated.
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["replay"]["buffer_size"] = 999
    state_file.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(RunError, match="digest|SHA-256|layout|size"):
        read_continuation(paths, stop)


def test_replay_arrays_are_numeric_only_and_bounded(tmp_path):
    from lunarlab.continuation import ContinuationError, load_replay_npz

    path = tmp_path / "bad.npz"
    np.savez(path, observations=np.array([object()], dtype=object))
    with pytest.raises(ContinuationError):
        load_replay_npz(path, expected={"observations": ((1,), "float32")})
    # A header declaring far more rows than expected is rejected without loading the data.
    big = tmp_path / "big.npz"
    np.savez(big, observations=np.zeros((5, 1, 8), dtype=np.float32))
    with pytest.raises(ContinuationError, match="shape"):
        load_replay_npz(big, expected={"observations": ((4, 1, 8), "float32")})


def test_partial_and_wrapped_replay_buffers_round_trip(tmp_path):
    """Directly on SB3 models: a partly filled buffer and one that has wrapped around."""
    from stable_baselines3 import DQN

    from lunarlab.continuation import apply_dqn_continuation, dqn_continuation_payload
    from lunarlab.env import make_env

    for steps, size in ((40, 64), (150, 64)):
        env = make_env()
        model = DQN("MlpPolicy", env, buffer_size=size, learning_starts=0, batch_size=8, train_freq=4, seed=1)
        model.learn(steps)
        state, arrays = dqn_continuation_payload(model, total_timesteps_basis=steps * 2)
        fresh = DQN("MlpPolicy", make_env(), buffer_size=size, learning_starts=0, batch_size=8, seed=2)
        apply_dqn_continuation(fresh, state, arrays)
        rb, rf = model.replay_buffer, fresh.replay_buffer
        stored = model.num_timesteps  # learn() completes whole rollouts of train_freq steps (one env)
        assert (
            (rf.pos, rf.full)
            == (rb.pos, rb.full)
            == ((stored % size, True) if stored > size else (stored, False))
        )
        assert rb.full is (steps > size)  # the second case really wraps around
        n = rb.buffer_size if rb.full else rb.pos
        for k in ("observations", "next_observations", "actions", "rewards", "dones", "timeouts"):
            np.testing.assert_array_equal(getattr(rf, k)[:n], getattr(rb, k)[:n])
        assert fresh.num_timesteps == model.num_timesteps and fresh._n_calls == model._n_calls
        assert fresh.exploration_rate == model.exploration_rate
        env.close()


def test_ppo_checkpoints_keep_their_contract_and_inference_still_works():
    from lunarlab.runs import load_policy
    from lunarlab.training import EXIT_COMPLETED, train

    cfg = create_run(
        reward=preset("baseline"),
        seed=0,
        ppo=PPOConfig(n_envs=2, n_steps=64, batch_size=32),
        protocol=TINY_PROTOCOL,
        training=TrainingConfig(
            profile="custom", total_transitions=512, checkpoint_every=256, validation_every=256
        ),
    )
    assert train(cfg.run_id, quiet=True) == EXIT_COMPLETED
    entries = {c["kind"]: c for c in read_manifest(RunPaths(cfg.run_id))["checkpoints"]}
    assert entries["periodic"]["resumable"] is True and entries["periodic"]["continuation"]["format"] == (
        "lunarlab.ppo-continuation"
    )
    assert entries["final"]["role"] == "inference" and entries["best_validation"]["role"] == "inference"
    policy, _ = load_policy(cfg.run_id, "final")
    assert policy.act(np.zeros(8, dtype=np.float32)) in range(4)
