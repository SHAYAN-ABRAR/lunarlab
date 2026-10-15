"""Portfolio extensions: learned rewards (RLHF), DQN runs, robustness evaluation, robust statistics."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from lunarlab.config import (
    DQNConfig,
    EvalProtocol,
    PPOConfig,
    RunConfig,
    TrainingConfig,
    resume_compatibility,
)
from lunarlab.env import make_env
from lunarlab.policies import HeuristicPolicy, RandomPolicy
from lunarlab.preferences.data import SegmentSet, collect_segments, create_dataset, dataset_path, oracle_pairs
from lunarlab.preferences.model import RewardModel, load_reward_model, model_path
from lunarlab.rewards import RewardConfig, preset
from lunarlab.rewards.wrapper import LunarLabRewardWrapper
from lunarlab.rl_stats import (
    bootstrap_ci,
    iqm,
    performance_profile,
    probability_of_improvement,
    summarize_groups,
)
from lunarlab.storage import atomic_write_json, sha256_file
from tests.conftest import ScriptedEnv, random_states

# --------------------------------------------------------------------------- #
# Backward compatibility: new fields must not change existing hashes
# --------------------------------------------------------------------------- #

# Values computed by the release before learned rewards / DQN existed.
PRESET_HASHES = {
    "baseline": "10e0e32fdeb75ce7",
    "time-penalty": "9f3f7db7204f5ca3",
    "hover-bonus": "cc996f60d6550365",
    "potential": "55ba1d4da088b94a",
}
RUN_HASHES = {
    "baseline": "cf712d90cb1b23f6",
    "hover-bonus": "bb2e49866a6dd7a1",
    "potential": "cc12577eae0026da",
}


def fixed_run_config(name: str, **kw) -> RunConfig:
    return RunConfig(
        run_id="r",
        created_at="2026-01-01T00:00:00+00:00",
        reward=preset(name),
        training=TrainingConfig(
            profile="standard", total_transitions=1_000_000, checkpoint_every=50_000, validation_every=50_000
        ),
        seed=3,
        **kw,
    )


@pytest.mark.parametrize("name", list(PRESET_HASHES))
def test_preset_reward_hashes_unchanged(name):
    assert preset(name).content_hash() == PRESET_HASHES[name]


@pytest.mark.parametrize("name", list(RUN_HASHES))
def test_ppo_run_hashes_unchanged(name):
    assert fixed_run_config(name).config_hash() == RUN_HASHES[name]


# --------------------------------------------------------------------------- #
# Learned reward term and original_weight
# --------------------------------------------------------------------------- #


def learned_config(model_id: str, *, weight: float = 0.0, scale: float = 1.0) -> RewardConfig:
    return RewardConfig.model_validate(
        {
            "name": "Learned",
            "preset": "custom",
            "original_weight": weight,
            "learned": {"enabled": True, "model_id": model_id, "scale": scale},
        }
    )


def register_model(model_id: str, seed: int = 0) -> RewardModel:
    rng = np.random.default_rng(seed)
    model = RewardModel(
        mu=rng.normal(size=20).astype(np.float32),
        sigma=rng.uniform(0.5, 2, size=20).astype(np.float32),
        weights=[
            (rng.normal(size=(20, 8)).astype(np.float32), rng.normal(size=8).astype(np.float32)),
            (rng.normal(size=(8, 1)).astype(np.float32), rng.normal(size=1).astype(np.float32)),
        ],
        out_mean=0.3,
        out_std=2.0,
    )
    d = model_path(model_id)
    path = model.save(d)
    atomic_write_json(d / "meta.json", {"model_id": model_id, "sha256": sha256_file(path)})
    return model


def test_learned_reward_requires_a_model_id():
    with pytest.raises(ValidationError):
        RewardConfig.model_validate({"name": "x", "preset": "custom", "learned": {"enabled": True}})
    with pytest.raises(ValidationError):
        RewardConfig.model_validate({"name": "x", "preset": "custom", "original_weight": 1.5})


def test_learned_config_changes_the_hash_and_is_not_original():
    a, b = learned_config("rm-a"), learned_config("rm-b")
    assert a.content_hash() != b.content_hash()
    assert a.content_hash() != learned_config("rm-a", weight=0.5).content_hash()
    assert not a.is_original()
    assert "learned_reward" in a.active_terms()


@pytest.mark.parametrize("weight", [0.0, 0.5, 1.0])
def test_training_reward_invariant_with_learned_term(weight):
    model = register_model("rm-test-invariant", seed=1)
    load_reward_model.cache_clear()
    states = random_states(30, seed=4)
    original = list(np.linspace(-2, 2, 29))
    cfg = learned_config("rm-test-invariant", weight=weight, scale=0.5)
    env = LunarLabRewardWrapper(
        ScriptedEnv(states, rewards=original, terminate_at=29),
        cfg,
        0.99,
        probe_internals=False,
        step_info=True,
        record_steps=True,
    )
    obs, _ = env.reset(seed=0)
    t = 0
    while True:
        action = t % 4
        next_obs, r, te, tr, info = env.step(action)
        d = info["lunarlab"]
        expected_term = 0.5 * model(obs, action, next_obs)
        assert d["terms"]["learned_reward"] == pytest.approx(expected_term, rel=1e-5, abs=1e-6)
        assert d["original_reward"] == pytest.approx(original[t])
        assert r == pytest.approx(weight * original[t] + expected_term, rel=1e-5, abs=1e-6)
        obs, t = next_obs, t + 1
        if te or tr:
            break
    ep = info["lunarlab_episode"]
    assert ep["original_return"] == pytest.approx(sum(original), abs=1e-6)  # evaluation reward untouched


def test_reward_model_roundtrip_and_tamper_detection():
    model = register_model("rm-roundtrip", seed=2)
    load_reward_model.cache_clear()
    loaded = load_reward_model("rm-roundtrip")
    x = np.random.default_rng(0).normal(size=(5, 20)).astype(np.float32)
    assert np.allclose(loaded.batch(x), model.batch(x), atol=1e-6)
    # a model directory is immutable
    with pytest.raises(FileExistsError):
        model.save(model_path("rm-roundtrip"))
    # modified weights no longer match the recorded hash
    path = model_path("rm-roundtrip") / "model.npz"
    with np.load(path) as z:
        arrays = {k: z[k] for k in z.files}
    arrays["b0"] = arrays["b0"] + 1
    np.savez(path, **arrays)
    load_reward_model.cache_clear()
    with pytest.raises(ValueError, match="SHA-256"):
        load_reward_model("rm-roundtrip")


@pytest.mark.parametrize("bad", ["../etc", "a/b", "", ".hidden", "x" * 200])
def test_reward_model_ids_are_validated(bad):
    with pytest.raises(ValueError):
        model_path(bad)


# --------------------------------------------------------------------------- #
# Preferences
# --------------------------------------------------------------------------- #


def test_oracle_labels_follow_returns():
    rng = np.random.default_rng(0)
    returns = np.linspace(-100, 100, 50)
    idx = np.arange(50)
    i, j, y, y_true = oracle_pairs(returns, idx, 2000, beta=10.0, rng=rng)  # nearly noise-free
    assert (i != j).all()
    assert np.mean(y == y_true) > 0.99
    i, j, y, y_true = oracle_pairs(returns, idx, 4000, beta=1e-6, rng=rng)  # pure coin flips
    assert 0.45 < np.mean(y == y_true) < 0.55


def test_segments_are_slices_of_real_episodes():
    policies = [("random", RandomPolicy(0)), ("heuristic", HeuristicPolicy(make_env()))]
    seg = collect_segments(policies, episodes_per_policy=2, segment_len=20, segments_per_episode=2)
    assert seg.obs.shape[1:] == (21, 8) and seg.actions.shape[1] == 20
    assert set(seg.source.tolist()) == {0, 1}
    assert (seg.episode_seed >= 30_000).all()  # disjoint from training/validation/test seeds
    # every recorded segment ending in a termination is the final window of its episode
    assert seg.terminal.any()


@pytest.mark.slow
def test_dataset_roundtrip_and_reward_model_training():
    from lunarlab.preferences.train import train_reward_model

    policies = [
        ("random-0", RandomPolicy(0)),
        ("random-1", RandomPolicy(1)),
        ("heuristic", HeuristicPolicy(make_env())),
    ]
    dataset_id = create_dataset(policies, episodes_per_policy=6, name="test")
    seg = SegmentSet.load(dataset_path(dataset_id))
    assert len(seg) > 30
    assert np.allclose(seg.returns, seg.rewards.sum(axis=1))
    meta = train_reward_model(dataset_id, n_pairs=400, epochs=25, seed=0)
    m = meta["metrics"]
    # random vs heuristic segments are easy to order: a working pipeline must beat chance clearly
    assert m["val_accuracy_vs_true_order"] > 0.7
    assert m["segment_return_correlation"] > 0.5
    load_reward_model.cache_clear()
    model = load_reward_model(meta["model_id"])
    assert np.isfinite(model(seg.obs[0, 0], int(seg.actions[0, 0]), seg.obs[0, 1]))


# --------------------------------------------------------------------------- #
# DQN configuration
# --------------------------------------------------------------------------- #


def test_dqn_config_defaults_and_validation():
    cfg = fixed_run_config("baseline", algo="dqn")
    assert cfg.dqn == DQNConfig()
    assert cfg.gamma == 0.99 and cfg.n_envs == 1 and cfg.rollout_size == 4
    with pytest.raises(ValidationError):
        fixed_run_config("baseline", dqn=DQNConfig())  # DQN settings on a PPO run
    assert (
        fixed_run_config("baseline", algo="dqn").config_hash() != fixed_run_config("baseline").config_hash()
    )


def test_resume_refuses_algorithm_or_setting_changes():
    ppo = fixed_run_config("baseline")
    dqn = fixed_run_config("baseline", algo="dqn")
    assert any("algorithm differs" in p for p in resume_compatibility(ppo, dqn))
    other = fixed_run_config("baseline", algo="dqn", dqn=DQNConfig(learning_rate=1e-3))
    assert any("DQN settings differ" in p for p in resume_compatibility(dqn, other))
    assert resume_compatibility(dqn, fixed_run_config("baseline", algo="dqn")) == []


@pytest.mark.slow
def test_dqn_run_trains_checkpoints_and_reloads():
    from lunarlab.runs import create_run, load_policy, read_manifest
    from lunarlab.storage import RunPaths
    from lunarlab.training import EXIT_COMPLETED, train

    cfg = create_run(
        reward=preset("baseline"),
        seed=0,
        algo="dqn",
        dqn=DQNConfig(buffer_size=1000, batch_size=32, net_arch=[32], learning_starts=64),
        ppo=PPOConfig(),
        protocol=EvalProtocol(validation_seeds=[10_000]),
        training=TrainingConfig(
            profile="custom", total_transitions=512, checkpoint_every=256, validation_every=256
        ),
    )
    assert cfg.run_id.split("-")[2] == "dqn"
    assert train(cfg.run_id) == EXIT_COMPLETED
    names = [c["name"] for c in read_manifest(RunPaths(cfg.run_id))["checkpoints"]]
    assert "final.zip" in names
    p1, _ = load_policy(cfg.run_id, "final", deterministic=True)
    p2, _ = load_policy(cfg.run_id, "final", deterministic=True)
    obs = np.array(random_states(20, seed=5))
    assert [p1.act(o) for o in obs] == [p2.act(o) for o in obs]
    assert p1.kind == "dqn" and p1.label.startswith("DQN")


# --------------------------------------------------------------------------- #
# Robustness
# --------------------------------------------------------------------------- #


def test_env_overrides_are_restricted():
    env = make_env(overrides={"enable_wind": True, "wind_power": 7.0})
    try:
        assert env.unwrapped.enable_wind and env.unwrapped.wind_power == 7.0
    finally:
        env.close()
    with pytest.raises(ValueError, match="unsupported"):
        make_env(overrides={"continuous": True})


@pytest.mark.slow
def test_robustness_evaluation_is_separate_from_the_final_test():
    from lunarlab.evaluation import list_evaluations
    from lunarlab.robustness import evaluate_robustness, latest_robustness
    from lunarlab.runs import create_run
    from lunarlab.training import EXIT_COMPLETED, train

    cfg = create_run(
        reward=preset("baseline"),
        seed=0,
        ppo=PPOConfig(n_envs=2, n_steps=64, batch_size=32),
        protocol=EvalProtocol(validation_seeds=[10_000]),
        training=TrainingConfig(
            profile="custom", total_transitions=256, checkpoint_every=256, validation_every=256
        ),
    )
    assert train(cfg.run_id) == EXIT_COMPLETED
    with pytest.raises(ValueError):
        evaluate_robustness(cfg.run_id, "hurricane")
    res = evaluate_robustness(cfg.run_id, "wind-10", episodes=2)
    assert res["split"] == "robustness:wind-10"
    assert res["seeds"] == list(cfg.eval_protocol.test_seeds)[:2]
    assert res["env_overrides"]["wind_power"] == 10.0
    assert set(latest_robustness(cfg.run_id)) == {"wind-10"}
    assert not [e for e in list_evaluations(cfg.run_id) if e["split"] == "test"]  # final test untouched


# --------------------------------------------------------------------------- #
# Robust statistics
# --------------------------------------------------------------------------- #


def scipy_trim_mean_25(values):
    """Reference implementation of scipy.stats.trim_mean(x, 0.25)."""
    a = np.sort(np.asarray(values, float))
    k = int(0.25 * a.size)
    return a[k : a.size - k].mean()


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 7, 8, 10])
def test_iqm_matches_rliable_definition(n):
    values = np.random.default_rng(n).normal(size=n)
    assert iqm(values) == pytest.approx(scipy_trim_mean_25(values))
    assert iqm([]) is None


def test_iqm_ignores_one_extreme_seed():
    scores = [100, 101, 99, 100, -500]  # n=5: drop one run from each end, average the middle three
    assert iqm(scores) == pytest.approx((99 + 100 + 100) / 3)
    assert np.mean(scores) < 0


def test_probability_of_improvement():
    assert probability_of_improvement([3, 4], [1, 2]) == 1.0
    assert probability_of_improvement([1, 2], [3, 4]) == 0.0
    assert probability_of_improvement([1, 2], [1, 2]) == 0.5
    assert probability_of_improvement([2], [1, 3]) == 0.5
    assert probability_of_improvement([], [1]) is None


def test_bootstrap_interval_contains_point_and_is_reproducible():
    x = [1.0, 2.0, 3.0, 4.0, 10.0]
    ci = bootstrap_ci(x, np.mean, reps=500)
    assert ci[0] <= np.mean(x) <= ci[1]
    assert ci == bootstrap_ci(x, np.mean, reps=500)
    assert bootstrap_ci([1.0]) is None


def test_performance_profile_is_monotone():
    taus = np.linspace(-100, 300, 41)
    prof = performance_profile([[0, 100, 250], [50, 200, 280]], taus, reps=200)
    frac = np.array(prof["fraction"])
    assert (np.diff(frac) <= 1e-12).all()
    assert frac[0] == 1.0 and frac[-1] == 0.0
    assert all(
        lo <= f + 1e-12 and f <= hi + 1e-12 for lo, f, hi in zip(prof["lo"], frac, prof["hi"], strict=True)
    )


def test_summarize_groups_uses_first_group_as_reference():
    groups = {
        "A": {
            "run_scores": [100, 110, 120],
            "pad_rates": [0.5, 0.6, 0.7],
            "episode_returns": [[100], [110], [120]],
        },
        "B": {
            "run_scores": [200, 210, 220],
            "pad_rates": [0.9, 0.9, 1.0],
            "episode_returns": [[200], [210], [220]],
        },
    }
    out = summarize_groups(groups)
    assert out["reference"] == "A"
    assert out["probability_of_improvement"]["B"]["p"] == 1.0
    assert out["groups"]["A"]["iqm"] == pytest.approx(110)


# --------------------------------------------------------------------------- #
# RLHF study orchestration and training on a learned reward
# --------------------------------------------------------------------------- #


@pytest.mark.slow
def test_rlhf_study_creates_learned_reward_runs_that_train():
    import argparse

    from lunarlab.cli import cmd_rlhf_study
    from lunarlab.experiments import list_experiments
    from lunarlab.runs import load_config, read_manifest
    from lunarlab.storage import RunPaths
    from lunarlab.training import EXIT_COMPLETED, train

    args = argparse.Namespace(
        dataset_id=None,
        from_experiment=None,
        source_seeds="0",
        episodes=4,
        pairs="200",
        include_human=False,
        rm_seed=0,
        seeds="0",
        profile="smoke",
        name="rlhf-test",
        parallel=1,
        create_only=True,
    )
    assert cmd_rlhf_study(args) == 0
    (exp,) = list_experiments()
    (run_id,) = exp["run_ids"]
    cfg = load_config(run_id)
    assert cfg.reward.original_weight == 0.0 and cfg.reward.learned.enabled
    load_reward_model.cache_clear()
    assert load_reward_model(cfg.reward.learned.model_id) is not None

    # Train a few hundred transitions on the learned reward alone.
    from lunarlab.evaluation import evaluate_run
    from lunarlab.runs import create_run

    small = create_run(
        reward=cfg.reward,
        seed=0,
        ppo=PPOConfig(n_envs=2, n_steps=64, batch_size=32),
        protocol=EvalProtocol(validation_seeds=[10_000]),
        training=TrainingConfig(
            profile="custom", total_transitions=256, checkpoint_every=256, validation_every=256
        ),
    )
    assert train(small.run_id) == EXIT_COMPLETED
    assert any(c["kind"] == "final" for c in read_manifest(RunPaths(small.run_id))["checkpoints"])
    # evaluation scores the original reward, whatever the policy trained on
    res = evaluate_run(small.run_id, "validation", checkpoint="final")
    ep = res["episodes"][0]
    assert "learned_reward" in ep["term_returns"]
    # original weight 0: the learned-reward view of the episode is the learned term alone ...
    assert ep["training_return"] == pytest.approx(sum(ep["term_returns"].values()), abs=1e-6)
    # ... while the reported score is the environment's own return
    assert res["aggregate"]["original_return"]["mean"] == pytest.approx(ep["original_return"])


# --------------------------------------------------------------------------- #
# Static demo export
# --------------------------------------------------------------------------- #


def test_demo_names_match_the_frontend():
    from lunarlab.demo import compare_key, demo_name, fnv1a

    # The same inputs give the same outputs in frontend/src/lib/demo.ts (checked with node).
    assert demo_name("/api/runs/20261015-223113-baseline-s0-standard-c5af/events?limit=120") == (
        "runs_2f20261015-223113-baseline-s0-standard-c5af_2fevents_3flimit_3d120"
    )
    assert demo_name("/api/jobs?active=true") == "jobs_3factive_3dtrue"
    assert demo_name("/api/preferences/ds_x/pair") == "preferences_2fds_5fx_2fpair"
    assert (fnv1a(""), fnv1a("validation:a,b"), fnv1a("héllo")) == ("811c9dc5", "0b88593d", "4aa48540")
    assert compare_key(["b-2", "a-1"], "test") == "9dd69773"


@pytest.mark.slow
def test_export_demo_writes_a_filtered_scrubbed_snapshot(tmp_path, lab_home):
    import json

    from lunarlab.demo import compare_key, demo_name, export_demo
    from lunarlab.experiments import create_experiment
    from lunarlab.recording import record_run
    from lunarlab.training import EXIT_COMPLETED, train

    exp = create_experiment(name="demo-test", rewards=[preset("baseline")], seeds=[0], profile="smoke")
    (rid,) = exp["run_ids"]
    assert train(rid) == EXIT_COMPLETED
    rec = record_run(rid, episode_seed=20_000, checkpoint="final")
    other = create_experiment(name="not-exported", rewards=[preset("potential")], seeds=[0], profile="smoke")

    out = tmp_path / "site" / "demo-api"
    manifest = export_demo(out, experiment_ids=[exp["experiment_id"]], echo=lambda *_: None)
    assert manifest["runs"] == 1 and manifest["recordings"] == 1
    runs = json.loads((out / f"{demo_name('/api/runs')}.json").read_text())
    assert [r["run_id"] for r in runs] == [rid]  # the other experiment's run is filtered out
    assert other["run_ids"][0] not in (out / f"{demo_name('/api/overview')}.json").read_text()
    for path in (
        f"/api/runs/{rid}",
        f"/api/runs/{rid}/curve",
        f"/api/runs/{rid}/events?limit=120",
        f"/api/recordings/{rec['recording_id']}",
        f"/api/recordings/{rec['recording_id']}/scene",
    ):
        assert (out / f"{demo_name(path)}.json").exists(), path
    video = demo_name(f"/api/recordings/{rec['recording_id']}/video")
    assert (out / f"{video}.mp4").stat().st_size > 1000
    assert (out / "compare" / f"{compare_key([rid], 'validation')}.json").exists()
    # no absolute local paths survive
    home = str(lab_home)
    for f in out.rglob("*.json"):
        text = f.read_text()
        assert (
            home not in text
            and home.replace("\\", "/") not in text
            and home.replace("\\", "\\\\") not in text
        ), f


@pytest.mark.slow
def test_results_figures_and_tables_from_final_test_data(tmp_path):
    from lunarlab.evaluation import evaluate_run
    from lunarlab.experiments import create_experiment
    from lunarlab.results import build_results
    from lunarlab.training import EXIT_COMPLETED, train

    exp = create_experiment(
        name="results-test",
        rewards=[preset("baseline"), preset("hover-bonus")],
        seeds=[0, 1],
        profile="smoke",
    )
    for rid in exp["run_ids"]:
        assert train(rid) == EXIT_COMPLETED
        evaluate_run(rid, "test", checkpoint="best")
    out = build_results([exp["experiment_id"]], tmp_path / "results", echo=lambda *_: None)
    assert {"headline", "learning_curves", "performance_profiles"} <= set(out["figures"])
    for f in out["figures"].values():
        assert (tmp_path / "results" / f).stat().st_size > 5_000
    md = (tmp_path / "results" / "tables.md").read_text(encoding="utf-8")
    assert "| Original baseline | 2 |" in md and "reference" in md
    assert md.count("`2") >= 4  # one row per policy (run ids start with the date)


@pytest.mark.slow
def test_showcase_composes_footage_and_captured_3d_frames(tmp_path):
    import json

    from PIL import Image

    from lunarlab.recording import record_demo
    from lunarlab.results import make_showcase

    rec = record_demo("random", episode_seed=20_000)
    rid = rec["recording_id"]
    gif = make_showcase([rid], ["random"], tmp_path / "footage.gif", cols=1, tile=(150, 100))
    assert gif["frames"] > 5 and (tmp_path / "footage.gif").stat().st_size > 1000
    # frames as written by frontend/tools/capture3d.mjs
    d = tmp_path / "frames" / rid
    d.mkdir(parents=True)
    for k in range(6):
        Image.new("RGB", (120, 80), (40 * k, 20, 0)).save(d / f"{k:05d}.jpg")
    (d / "meta.json").write_text(json.dumps({"frames": 6, "episode_end_frame": 4, "dt": 0.06}))
    out = make_showcase(
        [rid], ["random"], tmp_path / "replay.webp", frames_dir=tmp_path / "frames", cols=1, tile=(120, 80)
    )
    im = Image.open(tmp_path / "replay.webp")
    assert im.format == "WEBP" and im.n_frames == 6
    assert out["endings"][0].endswith(f"return {rec['original_return']:.0f}")
