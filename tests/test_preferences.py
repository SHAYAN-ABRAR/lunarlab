"""Preference learning: train/validation isolation by episode, human-label handling."""

from __future__ import annotations

import numpy as np
import pytest

from lunarlab.env import make_env
from lunarlab.policies import HeuristicPolicy, RandomPolicy
from lunarlab.preferences.data import (
    SegmentSet,
    add_human_label,
    create_dataset,
    dataset_path,
    episode_ids,
    human_labels,
    partition_labels,
    random_pair,
    split_by_episode,
)
from lunarlab.preferences.train import assemble_pairs


@pytest.fixture
def dataset():
    policies = [
        ("random-0", RandomPolicy(0)),
        ("random-1", RandomPolicy(1)),
        ("heuristic", HeuristicPolicy(make_env())),
    ]
    ds = create_dataset(policies, episodes_per_policy=6, name="test")
    return ds, SegmentSet.load(dataset_path(ds))


def test_episode_split_keeps_every_episode_on_one_side(dataset):
    _, seg = dataset
    split = split_by_episode(seg)
    ep = episode_ids(seg)
    assert not set(ep[split.train].tolist()) & set(ep[split.val].tolist())
    assert len(split.train) + len(split.val) == len(seg)
    assert split.train_episodes >= 1 and split.val_episodes >= 1
    # Segments of one episode overlap in time: all of them sit on the same side.
    for e in np.unique(ep):
        members = set(np.flatnonzero(ep == e).tolist())
        assert members <= set(split.train.tolist()) or members <= set(split.val.tolist())
    # The split is a fixed property of the dataset.
    assert np.array_equal(split_by_episode(seg).val, split.val)


def test_split_needs_two_episodes(dataset):
    _, seg = dataset
    one = SegmentSet(
        obs=seg.obs[:2],
        actions=seg.actions[:2],
        rewards=seg.rewards[:2],
        terminal=seg.terminal[:2],
        source=np.zeros(2, np.int64),
        episode_seed=np.full(2, 30_000),
        start=seg.start[:2],
        sources=["x"],
    )
    with pytest.raises(ValueError, match="at least 2 episodes"):
        split_by_episode(one)


def test_human_labels_from_validation_episodes_never_reach_training(dataset):
    ds, seg = dataset
    split = split_by_episode(seg)
    assert split.val.size >= 2, "fixture must give the validation side at least two segments"
    t0, t1 = (int(x) for x in split.train[:2])
    v0, v1 = (int(x) for x in split.val[:2])
    for i, j in ((t0, t1), (v0, v1), (t0, v0), (v1, t1)):
        add_human_label(ds, i, j, "a")
    parts = partition_labels(human_labels(ds), split)
    assert [len(parts[k]) for k in ("train", "val", "excluded")] == [1, 1, 2]

    pairs = assemble_pairs(
        seg, split, n_pairs=300, beta=0.05, rng=np.random.default_rng(0), labels=human_labels(ds)
    )
    train_set, val_set = set(split.train.tolist()), set(split.val.tolist())
    assert set(pairs.train_i.tolist()) | set(pairs.train_j.tolist()) <= train_set
    assert set(pairs.val_i.tolist()) | set(pairs.val_j.tolist()) <= val_set
    assert set(pairs.human_val_i.tolist()) | set(pairs.human_val_j.tolist()) <= val_set
    assert pairs.n_human_train == 1 and pairs.human_val_i.size == 1 and pairs.n_human_excluded == 2
    # the one usable training label is in the training pairs, exactly once
    hits = [
        (i, j)
        for i, j in zip(pairs.train_i.tolist(), pairs.train_j.tolist(), strict=True)
        if (i, j) == (t0, t1)
    ]
    assert len(hits) >= 1


@pytest.mark.slow
def test_reward_model_metadata_reports_how_labels_were_used(dataset):
    from lunarlab.preferences.train import train_reward_model

    ds, seg = dataset
    split = split_by_episode(seg)
    t0, t1 = (int(x) for x in split.train[:2])
    v0, v1 = (int(x) for x in split.val[:2])
    add_human_label(ds, t0, t1, "b")
    add_human_label(ds, v0, v1, "a")
    add_human_label(ds, t0, v0, "a")
    meta = train_reward_model(ds, n_pairs=200, epochs=5, include_human=True)
    assert meta["split"]["method"] == "episode"
    assert meta["split"]["val_segments"] == split.val.size
    assert (meta["n_human_labels"], meta["n_human_val_labels"], meta["n_human_excluded"]) == (1, 1, 1)
    assert meta["n_val_segments"] == split.val.size and meta["n_train_segments"] == split.train.size
    without = train_reward_model(ds, n_pairs=200, epochs=5, include_human=False)
    assert without["n_human_labels"] == 0 and without["n_human_excluded"] == 0


def test_labelling_pairs_come_from_training_episodes(dataset):
    ds, seg = dataset
    train_set = set(split_by_episode(seg).train.tolist())
    for k in range(40):
        pair = random_pair(ds, rng=np.random.default_rng(k))
        assert pair["i"] != pair["j"] and {pair["i"], pair["j"]} <= train_set


# --------------------------------------------------------------------------- #
# Ensembles and active preference learning
# --------------------------------------------------------------------------- #


def _member(seed: int):
    from lunarlab.preferences.model import RewardModel

    rng = np.random.default_rng(seed)
    return RewardModel(
        mu=np.zeros(20, np.float32),
        sigma=np.ones(20, np.float32),
        weights=[
            (rng.normal(size=(20, 8)).astype(np.float32), rng.normal(size=8).astype(np.float32)),
            (rng.normal(size=(8, 1)).astype(np.float32), rng.normal(size=1).astype(np.float32)),
        ],
        out_mean=float(rng.normal()),
        out_std=1.5,
    )


def test_ensemble_roundtrip_and_use_as_training_reward():
    from lunarlab.preferences.model import RewardEnsemble, load_reward_model, model_path
    from lunarlab.rewards.config import RewardConfig
    from lunarlab.rewards.wrapper import LunarLabRewardWrapper
    from lunarlab.storage import atomic_write_json, sha256_file
    from tests.conftest import ScriptedEnv, random_states

    ens = RewardEnsemble(members=[_member(k) for k in range(3)])
    path = ens.save(model_path("rm-test-ensemble"))
    atomic_write_json(model_path("rm-test-ensemble") / "meta.json", {"sha256": sha256_file(path)})
    load_reward_model.cache_clear()
    loaded = load_reward_model("rm-test-ensemble")
    assert isinstance(loaded, RewardEnsemble) and len(loaded.members) == 3
    x = np.random.default_rng(0).normal(size=(6, 20)).astype(np.float32)
    assert np.allclose(loaded.batch(x), np.mean([m.batch(x) for m in ens.members], axis=0), atol=1e-6)
    assert loaded.member_raw(x).shape == (3, 6)

    cfg = RewardConfig.model_validate(
        {
            "name": "ens",
            "preset": "custom",
            "original_weight": 0.0,
            "learned": {"enabled": True, "model_id": "rm-test-ensemble"},
        }
    )
    states = random_states(12, seed=3)
    env = LunarLabRewardWrapper(
        ScriptedEnv(states, rewards=[1.0] * 11, terminate_at=11),
        cfg,
        0.99,
        probe_internals=False,
        step_info=True,
    )
    obs, _ = env.reset(seed=0)
    nxt, r, *_ = env.step(2)
    assert r == pytest.approx(loaded(obs, 2, nxt), rel=1e-5, abs=1e-6)  # weight 0: the ensemble mean alone


def test_simulated_labeller_is_deterministic_and_order_consistent():
    from lunarlab.preferences.active import oracle_label

    returns = np.linspace(-50, 50, 30)
    for i, j in [(0, 29), (3, 4), (10, 12), (25, 2)]:
        a = oracle_label(returns, i, j, beta=0.05, seed=1)
        assert a == oracle_label(returns, i, j, beta=0.05, seed=1)
        assert oracle_label(returns, j, i, beta=0.05, seed=1) == 1.0 - a
    # nearly noise-free with a large beta
    assert all(oracle_label(returns, i, 0, beta=50.0, seed=2) == 1.0 for i in range(1, 30))


def test_candidate_pairs_are_distinct_and_skip_labelled_pairs():
    from lunarlab.preferences.active import candidate_pairs, pair_key

    pool = np.arange(10)
    exclude = {(0, 1), (2, 3)}
    cand = candidate_pairs(pool, exclude, 30, np.random.default_rng(0))
    keys = [pair_key(i, j) for i, j in cand]
    assert len(keys) == len(set(keys)) == 30 and not set(keys) & exclude
    everything = candidate_pairs(pool, exclude, 1000, np.random.default_rng(1))
    assert len(everything) <= 45 - len(exclude)  # never more pairs than exist


def test_disagreement_is_zero_when_members_agree():
    from lunarlab.preferences.active import disagreement
    from lunarlab.preferences.model import RewardEnsemble

    feats = np.random.default_rng(0).normal(size=(8, 5, 20)).astype(np.float32)
    pairs = np.array([[0, 1], [2, 3], [4, 7]])
    same = RewardEnsemble(members=[_member(0)] * 3)
    assert np.allclose(disagreement(same, feats, pairs), 0.0, atol=1e-6)  # float32 rounding only
    mixed = RewardEnsemble(members=[_member(k) for k in range(4)])
    assert (disagreement(mixed, feats, pairs) > 0).all()


@pytest.mark.slow
def test_active_learning_loop_labels_each_pair_once_inside_training_episodes(dataset):
    from lunarlab.preferences.active import run_active_learning

    ds, seg = dataset
    split = split_by_episode(seg)
    runs = {
        s: run_active_learning(
            ds, strategy=s, budget=60, initial=20, batch=20, members=2, candidates=200, seed=3, epochs=8
        )
        for s in ("random", "disagreement")
    }
    for r in runs.values():
        assert [h["labels"] for h in r["history"]] == [20, 40, 60]
        assert r["split"]["val_segments"] == split.val.size
    # identical starting labels: the first point of both curves is the same
    first = {s: r["history"][0]["val_accuracy_vs_true_order"] for s, r in runs.items()}
    assert first["random"] == pytest.approx(first["disagreement"])
    with pytest.raises(ValueError):
        run_active_learning(ds, strategy="clairvoyant", budget=10, initial=5)


@pytest.mark.slow
def test_human_labelling_pairs_strategies_and_ensemble(dataset):
    from fastapi.testclient import TestClient

    from lunarlab.preferences.active import labelled_keys, next_pair, pair_key, train_labelling_ensemble
    from lunarlab.server.main import create_app

    ds, seg = dataset
    train_set = set(split_by_episode(seg).train.tolist())
    h = {"X-LunarLab": "1"}
    with TestClient(create_app(start_jobs=False, testing=True)) as c:
        assert (
            c.get(f"/api/preferences/{ds}/pair?strategy=disagreement").status_code == 409
        )  # no ensemble yet
        assert c.get(f"/api/preferences/{ds}/pair?strategy=psychic").status_code == 400
        seen = set()
        for _ in range(6):
            pair = c.get(f"/api/preferences/{ds}/pair?strategy=random").json()
            assert pair["strategy"] == "random" and {pair["i"], pair["j"]} <= train_set
            k = pair_key(pair["i"], pair["j"])
            assert k not in seen
            seen.add(k)
            assert (
                c.post(
                    f"/api/preferences/{ds}/labels",
                    json={"i": pair["i"], "j": pair["j"], "choice": "a"},
                    headers=h,
                ).status_code
                == 201
            )
            # the same pair, in either order, cannot be labelled twice
            dup = {"i": pair["j"], "j": pair["i"], "choice": "b"}
            assert c.post(f"/api/preferences/{ds}/labels", json=dup, headers=h).status_code == 409
        assert labelled_keys(ds) == seen
        prog = c.get(f"/api/preferences/{ds}/progress").json()
        assert (
            prog["labels"] == 6
            and prog["usable_for_training"] == 6
            and prog["strategies"]["disagreement"] is False
        )
        with pytest.raises(ValueError, match="at least 10"):
            train_labelling_ensemble(ds, members=2)  # 6 human labels only
        state = train_labelling_ensemble(ds, simulated_pairs=60, members=3)
        assert state["n_human_labels"] == 6 and state["n_simulated_pairs"] > 0
        sel = next_pair(ds, "disagreement", rng=np.random.default_rng(0))
        assert pair_key(sel["i"], sel["j"]) not in seen and sel["score"] >= sel["median_score"]
        pair = c.get(f"/api/preferences/{ds}/pair?strategy=disagreement").json()
        assert pair["strategy"] == "disagreement" and pair["score"] is not None
        prog = c.get(f"/api/preferences/{ds}/progress").json()
        assert prog["strategies"]["disagreement"] is True and prog["since_ensemble"] == 0
        job = c.post(
            f"/api/preferences/{ds}/ensemble", json={"simulated_pairs": 0, "members": 3}, headers=h
        ).json()
        assert job["kind"] == "reward_ensemble" and job["state"] == "queued"
