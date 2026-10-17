# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Automatic tuning with Optuna: studies, pruning, cancel/resume, best settings, and test-set isolation."""

from __future__ import annotations

import pytest

from lunarlab.runs import RunError, load_config, load_metadata, read_manifest
from lunarlab.storage import RunPaths
from lunarlab.tuning import (
    TuningError,
    build_configs,
    create_study,
    load_spec,
    request_cancel,
    run_study,
    study_summary,
)

SMALL = {"n_envs": 2, "n_steps": 64, "batch_size": 32}  # 128-transition rollouts


def small_study(**kw):
    args = dict(
        name="t",
        algo="ppo",
        preset_name="potential",
        params=["ppo.learning_rate", "reward.potential.alpha"],
        n_trials=3,
        trial_transitions=768,
        validation_every=256,
        warmup_transitions=0,
        startup_trials=1,
        base_ppo=SMALL,
    )
    args.update(kw)
    return create_study(**args)


def test_study_definition_is_validated_and_persisted():
    with pytest.raises(TuningError, match="cannot tune"):
        create_study(name="x", algo="ppo", preset_name="baseline", params=["dqn.learning_rate"])
    with pytest.raises(TuningError, match="cannot tune"):
        create_study(name="x", algo="ppo", preset_name="baseline", params=["reward.potential.alpha"])
    spec = small_study()
    assert load_spec(spec["study_id"]) == spec
    assert spec["objective"].startswith("best validation")


def test_sampled_values_reach_the_run_configuration():
    spec = small_study()
    values = {"ppo.learning_rate": 7e-4, "reward.potential.alpha": 3.5, "reward.potential.weights.x": 0.25}
    ppo, dqn, reward = build_configs(spec, values)
    assert ppo.learning_rate == 7e-4 and ppo.n_envs == 2 and dqn is None
    assert (
        reward.potential.alpha == 3.5 and reward.potential.weights.x == 0.25 and reward.name.endswith("tuned")
    )
    assert reward.preset == "potential" and reward.potential.enabled


@pytest.mark.slow
def test_a_study_trains_trials_on_validation_and_never_touches_the_test_seeds():
    from lunarlab.evaluation import evaluate_run

    spec = small_study()
    summary = run_study(spec["study_id"], echo=lambda *_: None)
    assert summary["status"]["state"] == "completed" and summary["finished"] == 3
    assert summary["counts"]["complete"] == 3 and summary["best"] is not None
    for t in summary["trials"]:
        assert t["intermediate"] and t["intermediate"][0][0] == 0  # validation before training starts
        meta = load_metadata(t["run_id"])
        assert meta["tuning"] == {"study_id": spec["study_id"], "trial": t["number"]}
        assert load_config(t["run_id"]).seed == spec["training_seed"]  # common random numbers
        assert t["value"] == pytest.approx(t["best_validation"])
    with pytest.raises(RunError, match="tuning trial"):
        evaluate_run(summary["trials"][0]["run_id"], "test")
    # nothing left to do: running again is a no-op
    assert run_study(spec["study_id"], echo=lambda *_: None)["status"]["state"] == "completed"


@pytest.mark.slow
def test_pruning_stops_a_trial_early(monkeypatch):
    import optuna

    calls = {"n": 0}

    def prune_after_second_report(self):
        calls["n"] += 1
        return calls["n"] >= 2

    monkeypatch.setattr(optuna.trial.Trial, "should_prune", prune_after_second_report)
    spec = small_study(n_trials=1, trial_transitions=1280)
    summary = run_study(spec["study_id"], echo=lambda *_: None)
    (t,) = summary["trials"]
    assert t["state"] == "pruned" and t["pruned_at"] == 256
    trained = max(c["transitions"] for c in read_manifest(RunPaths(t["run_id"]))["checkpoints"])
    assert trained < 1280  # stopped at a safe boundary, not trained to the end


@pytest.mark.slow
def test_cancel_then_resume_completes_the_study():
    spec = small_study(n_trials=2)
    sid = spec["study_id"]
    reports = {"n": 0}

    def stop_after_first_validation():
        reports["n"] += 1
        return reports["n"] > 2  # asked during the first trial

    summary = run_study(sid, should_stop=stop_after_first_validation, echo=lambda *_: None)
    assert summary["status"]["state"] == "stopped"
    first = summary["trials"][0]
    assert first["state"] == "fail" and first["cancelled"]
    resumed = run_study(sid, echo=lambda *_: None)
    assert resumed["status"]["state"] == "completed" and resumed["finished"] == 2
    assert resumed["counts"]["complete"] == 2 and resumed["counts"]["fail"] == 1


@pytest.mark.slow
def test_a_trial_left_running_by_a_crash_is_failed_on_resume():
    from lunarlab.tuning import _optuna_study

    spec = small_study(n_trials=1)
    study = _optuna_study(spec)
    study.ask()  # a RUNNING trial whose process died
    summary = run_study(spec["study_id"], echo=lambda *_: None)
    states = sorted(t["state"] for t in summary["trials"])
    assert states == ["complete", "fail"]
    assert any(t["interrupted"] for t in summary["trials"])


def test_cancel_request_on_an_idle_study_is_recorded():
    spec = small_study()
    status = request_cancel(spec["study_id"])
    assert status["cancel_requested"] is True


@pytest.mark.slow
def test_apply_best_creates_normal_testable_runs():
    from lunarlab.tuning import apply_best

    spec = small_study(n_trials=2)
    with pytest.raises(TuningError, match="no completed trial"):
        apply_best(spec["study_id"], seeds=[0], profile="smoke")
    run_study(spec["study_id"], echo=lambda *_: None)
    best = study_summary(spec["study_id"])["best"]
    exp = apply_best(spec["study_id"], seeds=[0, 1], profile="smoke")
    assert len(exp["run_ids"]) == 2
    for rid in exp["run_ids"]:
        cfg = load_config(rid)
        assert cfg.ppo.learning_rate == pytest.approx(best["params"]["ppo.learning_rate"])
        assert cfg.reward.potential.alpha == pytest.approx(best["params"]["reward.potential.alpha"])
        assert cfg.ppo.n_envs == 2  # the study's base settings carry over
        assert "tuning" not in load_metadata(rid)
        selection = load_metadata(rid)["selection"]
        assert selection["study_id"] == spec["study_id"] and selection["test_set_previously_exposed"] is False


def test_a_study_started_after_a_final_test_on_the_same_seeds_is_exploratory():
    from lunarlab.config import EvalProtocol
    from lunarlab.lineage import evidence_role, record_test_exposure
    from lunarlab.tuning import create_study

    assert (
        create_study(name="before", n_trials=1, trial_transitions=512)["test_set_previously_exposed"] is False
    )
    record_test_exposure(EvalProtocol(), "20261015-000000-baseline-s0-standard-aaaa", "test-x.json")
    after = create_study(name="after", n_trials=1, trial_transitions=512)
    assert after["test_set_previously_exposed"] is True and after["test_exposure"]["run_id"].endswith("aaaa")
    assert evidence_role({"selection": {"test_set_previously_exposed": True}}) == "exploratory"


def test_tuning_api():
    from fastapi.testclient import TestClient

    from lunarlab.server.main import create_app

    h = {"X-LunarLab": "1"}
    with TestClient(create_app(start_jobs=False, testing=True)) as c:
        space = c.get("/api/tuning/space?algo=dqn&preset=time-penalty").json()
        assert (
            "dqn.learning_rate" in space["params"] and "reward.time_penalty.cost_per_step" in space["params"]
        )
        assert "ppo.learning_rate" not in space["params"]
        body = {
            "name": "api",
            "algo": "ppo",
            "preset": "baseline",
            "params": ["ppo.learning_rate"],
            "n_trials": 2,
            "trial_transitions": 8192,
            "validation_every": 4096,
            "start": False,
        }
        r = c.post("/api/tuning", json=body, headers=h)
        assert r.status_code == 201, r.text
        sid = r.json()["study"]["study_id"]
        bad = {**body, "params": ["reward.potential.alpha"]}
        assert c.post("/api/tuning", json=bad, headers=h).status_code == 400
        detail = c.get(f"/api/tuning/{sid}").json()
        assert detail["finished"] == 0 and detail["jobs"] == []
        assert [s["study_id"] for s in c.get("/api/tuning").json()] == [sid]
        job = c.post(f"/api/tuning/{sid}/resume", headers=h).json()
        assert job["kind"] == "tune" and job["params"]["study_id"] == sid
        assert c.post(f"/api/tuning/{sid}/resume", headers=h).status_code == 409  # one job per study
        assert c.post(f"/api/tuning/{sid}/apply", json={"seeds": [0]}, headers=h).status_code == 409
        cancel = c.post(f"/api/tuning/{sid}/cancel", headers=h).json()
        assert cancel["jobs"][0]["state"] == "stopped"  # the queued job never starts
        assert c.get("/api/tuning/nope").status_code == 404
