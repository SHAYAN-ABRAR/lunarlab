# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Every refusal of the DQN continuation loader: a resumed run must never start from bad or foreign state."""

from __future__ import annotations

import copy
import zipfile

import gymnasium as gym
import numpy as np
import pytest

import lunarlab.continuation as cont
from lunarlab.continuation import (
    ContinuationError,
    _expected_arrays,
    apply_dqn_continuation,
    dqn_continuation_payload,
    inspect_npz,
    load_replay_npz,
    write_replay_npz,
)


def _dqn(buffer_size=1000, steps=200):
    from stable_baselines3 import DQN

    model = DQN(
        "MlpPolicy", gym.make("CartPole-v1"), buffer_size=buffer_size, learning_starts=0, seed=0, device="cpu"
    )
    if steps:
        model.learn(steps)
    return model


@pytest.fixture(scope="module")
def payload():
    model = _dqn()
    state, arrays = dqn_continuation_payload(model, total_timesteps_basis=1000)
    return model, state, arrays


def test_round_trip_restores_buffer_and_counters(payload):
    model, state, arrays = payload
    fresh = _dqn(steps=0)
    apply_dqn_continuation(fresh, copy.deepcopy(state), {k: v.copy() for k, v in arrays.items()})
    rows = state["replay"]["rows"]
    assert np.array_equal(fresh.replay_buffer.observations[:rows], model.replay_buffer.observations[:rows])
    assert (fresh.replay_buffer.pos, fresh.replay_buffer.full) == (
        model.replay_buffer.pos,
        model.replay_buffer.full,
    )
    assert fresh.num_timesteps == model.num_timesteps and fresh._n_calls == model._n_calls
    assert fresh.exploration_rate == pytest.approx(model.exploration_rate)


def _expect(state, arrays, match, model=None):
    with pytest.raises(ContinuationError, match=match):
        apply_dqn_continuation(model or _dqn(steps=0), state, arrays)


def test_invalid_or_unknown_state_fields_are_refused(payload):
    _, state, arrays = payload
    bad = copy.deepcopy(state)
    bad["unexpected"] = 1
    _expect(bad, arrays, "invalid continuation state")
    bad = copy.deepcopy(state)
    bad["exploration_rate"] = 2.0
    _expect(bad, arrays, "invalid continuation state")


def test_state_for_a_different_model_is_refused(payload):
    _, state, arrays = payload
    _expect(copy.deepcopy(state), arrays, "does not fit this model", model=_dqn(buffer_size=2000, steps=0))


def test_inconsistent_buffer_positions_are_refused(payload):
    _, state, arrays = payload
    bad = copy.deepcopy(state)
    bad["replay"]["pos"] = bad["replay"]["rows"] - 1
    _expect(bad, arrays, "rows and position disagree")
    bad = copy.deepcopy(state)
    bad["replay"]["full"] = True
    _expect(bad, arrays, "a full buffer stores every row")


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (lambda a: a.update(observations=a["observations"][:-1]), "wrong shape or dtype"),
        (lambda a: a.update(rewards=a["rewards"].astype(np.float64)), "wrong shape or dtype"),
        (lambda a: a["observations"].__setitem__((0, 0, 0), np.nan), "non-finite"),
        (lambda a: a["dones"].__setitem__((0, 0), 2.0), "only 0 and 1"),
        (lambda a: a["actions"].__setitem__((0, 0, 0), 7), "outside the action space"),
    ],
    ids=["shape", "dtype", "nan", "flag", "action"],
)
def test_invalid_replay_arrays_are_refused(payload, change, match):
    _, state, arrays = payload
    bad = {k: v.copy() for k, v in arrays.items()}
    change(bad)
    _expect(copy.deepcopy(state), bad, match)


def test_declared_layout_must_match(payload):
    _, state, _ = payload
    replay = cont.ContinuationState.model_validate({**state, "replay_sha256": "0" * 64}).replay
    missing = replay.model_copy(update={"arrays": {k: v for k, v in replay.arrays.items() if k != "rewards"}})
    with pytest.raises(ContinuationError, match="do not match the buffer layout"):
        _expected_arrays(missing)
    arrays = dict(replay.arrays)
    arrays["rewards"] = arrays["rewards"].model_copy(update={"shape": [1, 1]})
    with pytest.raises(ContinuationError, match="does not match the layout"):
        _expected_arrays(replay.model_copy(update={"arrays": arrays}))


def test_replay_archives_are_checked_before_any_data_is_read(tmp_path, payload, monkeypatch):
    _, state, arrays = payload
    expected = {k: (a.shape, a.dtype.str) for k, a in arrays.items()}
    good = tmp_path / "good.npz"
    write_replay_npz(good, arrays)
    loaded = load_replay_npz(good, expected=expected)
    assert all(np.array_equal(loaded[k], arrays[k]) for k in arrays)

    with pytest.raises(ContinuationError, match="object array"):
        write_replay_npz(tmp_path / "obj.npz", {"x": np.array([object()], dtype=object)})

    compressed = tmp_path / "compressed.npz"
    np.savez_compressed(compressed, **arrays)
    with pytest.raises(ContinuationError, match="compressed members"):
        inspect_npz(compressed)

    pickled = tmp_path / "pickled.npz"
    np.savez(pickled, x=np.array([{"a": 1}], dtype=object))
    with pytest.raises(ContinuationError, match="object dtype"):
        inspect_npz(pickled)

    stray = tmp_path / "stray.npz"
    with zipfile.ZipFile(stray, "w") as z:
        z.writestr("notes.txt", "hello")
    with pytest.raises(ContinuationError, match="unexpected member"):
        inspect_npz(stray)

    junk = tmp_path / "junk.npz"
    junk.write_bytes(b"not a zip file")
    with pytest.raises(ContinuationError, match="not a valid replay archive"):
        inspect_npz(junk)

    with pytest.raises(ContinuationError, match="instead of"):
        load_replay_npz(good, expected={**expected, "extra": ((1,), "<f4")})
    first = next(iter(expected))
    with pytest.raises(ContinuationError, match="has shape"):
        load_replay_npz(good, expected={**expected, first: ((1,), expected[first][1])})
    with pytest.raises(ContinuationError, match="has dtype"):
        load_replay_npz(good, expected={**expected, first: (expected[first][0], "<i8")})
    monkeypatch.setattr(cont, "MAX_REPLAY_BYTES", 16)
    with pytest.raises(ContinuationError, match="exceeds the replay size limit"):
        load_replay_npz(good, expected=expected)
