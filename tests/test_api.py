# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""HTTP API: safety middleware, validation, revisions, job endpoints, path safety."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lunarlab.server.main import create_app

H = {"X-LunarLab": "1"}


@pytest.fixture
def client():
    app = create_app(start_jobs=False, testing=True)
    with TestClient(app) as c:
        yield c


def test_health_and_meta(client):
    assert client.get("/api/health").json()["status"] == "ok"
    meta = client.get("/api/meta").json()
    assert [a["label"] for a in meta["actions"]][2] == "Fire main engine"
    assert meta["ppo_defaults"]["gamma"] == 0.999 and meta["rollout_size"] == 4096
    assert len(meta["eval_protocol"]["test_seeds"]) == 100


def test_mutations_require_header_and_same_origin(client):
    body = {"policy": "random"}
    assert client.post("/api/demos", json=body).status_code == 403
    r = client.post("/api/demos", json=body, headers={**H, "Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post("/api/demos", json=body, headers={**H, "Origin": "http://127.0.0.1:8765"})
    assert r.status_code == 200 and r.json()["state"] == "queued"


def test_untrusted_host_rejected():
    app = create_app(start_jobs=False)  # not testing: only loopback hosts allowed
    with TestClient(app, base_url="http://attacker.example") as c:
        assert c.get("/api/health").status_code == 400


def test_request_validation_rejects_unknown_fields_and_bounds(client):
    assert client.post("/api/demos", json={"policy": "random", "evil": 1}, headers=H).status_code == 422
    assert client.post("/api/demos", json={"policy": "python"}, headers=H).status_code == 422
    assert client.post("/api/runs", json={"preset": "baseline", "seed": 5000}, headers=H).status_code == 422
    assert (
        client.post(
            "/api/runs", json={"preset": "baseline", "profile": "extended", "start": False}, headers=H
        ).status_code
        == 400
    )  # needs explicit confirmation


def test_reward_config_revisions_are_immutable(client):
    presets = client.get("/api/reward-configs").json()
    hover = next(p for p in presets if p["preset"] == "hover-bonus")
    assert hover["builtin"] and hover["warnings"]
    cfg = dict(hover["config"], name="My hover", preset="custom")
    first = client.post(
        "/api/reward-configs", json={"config": cfg, "parent_id": hover["id"]}, headers=H
    ).json()
    assert first["revision"] == 1 and first["family"] != hover["family"]
    cfg2 = dict(cfg, hover_bonus=dict(cfg["hover_bonus"], bonus_per_step=0.5))
    second = client.post(
        "/api/reward-configs", json={"config": cfg2, "parent_id": first["id"]}, headers=H
    ).json()
    assert second["family"] == first["family"] and second["revision"] == 2
    assert second["content_hash"] != first["content_hash"]
    again = client.get(f"/api/reward-configs/{first['id']}").json()
    assert again["config"]["hover_bonus"]["bonus_per_step"] == 1.0  # the old revision is unchanged


def test_reward_validate_import_export(client):
    bad = client.post(
        "/api/reward-configs/validate", json={"config": {"name": "x", "potential": {"alpha": -1}}}, headers=H
    ).json()
    assert bad["valid"] is False and bad["errors"]
    good = client.post("/api/reward-configs/validate", json={"config": {"name": "x"}}, headers=H).json()
    assert good["valid"] and good["active_terms"] == []
    y = client.get("/api/reward-configs/preset-potential-r1/export").text
    assert "potential" in y
    imported = client.post(
        "/api/reward-configs/import",
        json={"yaml": y.replace("Potential-based shaping", "Imported")},
        headers=H,
    )
    assert imported.status_code == 201
    assert (
        client.post("/api/reward-configs/import", json={"yaml": "name: [unclosed"}, headers=H).status_code
        == 400
    )
    assert (
        client.post(
            "/api/reward-configs/import", json={"yaml": "!!python/object:os.system {}"}, headers=H
        ).status_code
        == 400
    )


def test_run_creation_job_conflicts_and_test_confirmation(client):
    r = client.post(
        "/api/runs", json={"preset": "baseline", "profile": "smoke", "seed": 3, "start": False}, headers=H
    )
    assert r.status_code == 201
    run_id = r.json()["run"]["run_id"]
    assert r.json()["job"] is None
    detail = client.get(f"/api/runs/{run_id}").json()
    assert detail["summary"]["evidence"] == "technical test only"
    assert detail["config"]["reward"]["preset"] == "baseline"
    j = client.post(f"/api/runs/{run_id}/train", headers=H)
    assert j.status_code == 200 and j.json()["state"] == "queued"
    assert client.post(f"/api/runs/{run_id}/train", headers=H).status_code == 409
    assert client.post(f"/api/runs/{run_id}/evaluate", json={"split": "test"}, headers=H).status_code == 400
    # queued job can be cancelled
    stopped = client.post(f"/api/runs/{run_id}/stop", headers=H).json()
    assert stopped["job"]["state"] == "stopped"


def test_idempotent_run_creation(client):
    body = {"preset": "potential", "profile": "smoke", "seed": 1, "idempotency_key": "click-abc"}
    a = client.post("/api/runs", json=body, headers=H).json()
    b = client.post("/api/runs", json=body, headers=H).json()
    assert a["run"]["run_id"] == b["run"]["run_id"] and a["job"]["id"] == b["job"]["id"]
    assert len(client.get("/api/runs").json()) == 1


@pytest.mark.parametrize(
    "url",
    [
        "/api/runs/..%2F..%2Fdata/config.yaml",
        "/api/runs/bad%20id",
        "/api/recordings/..%2F..%2Fsecret/video",
        "/api/reports/x/..%5C..%5Cdata%5Clunarlab.sqlite",
        "/api/reports/..%2Fdata/report.html",
    ],
)
def test_artifact_paths_cannot_escape(client, url):
    assert client.get(url).status_code in (400, 404)


@pytest.mark.slow
def test_recording_endpoints_and_rescore(client):
    from lunarlab.recording import record_demo

    meta = record_demo("random", episode_seed=20_005)
    rid = meta["recording_id"]
    listed = client.get("/api/recordings").json()
    assert listed[0]["recording_id"] == rid
    t = client.get(f"/api/recordings/{rid}").json()
    assert t["n_frames"] == len(t["rows"])
    v = client.get(f"/api/recordings/{rid}/video", headers={"Range": "bytes=0-99"})
    assert v.status_code == 206 and len(v.content) == 100
    res = client.post(
        f"/api/recordings/{rid}/rescore", json={"presets": ["baseline", "potential"]}, headers=H
    ).json()
    assert "not retraining" in res["disclaimer"] and len(res["configs"]) == 2


def test_experiment_plan_warns_for_large_suites(client):
    plan = client.post(
        "/api/experiments/plan",
        json={
            "presets": ["baseline", "time-penalty", "hover-bonus", "potential"],
            "seeds": [0, 1, 2],
            "profile": "standard",
        },
        headers=H,
    ).json()
    assert plan["n_runs"] == 12 and plan["warnings"]
    r = client.post(
        "/api/experiments",
        json={
            "presets": ["baseline", "potential"],
            "seeds": [0, 1, 2, 3],
            "profile": "smoke",
            "start": False,
        },
        headers=H,
    )
    assert r.status_code == 400  # 8 runs needs confirm_large
    r = client.post(
        "/api/experiments",
        json={
            "presets": ["baseline", "potential"],
            "seeds": [0, 1],
            "profile": "smoke",
            "start": False,
            "name": "tiny",
        },
        headers=H,
    )
    assert r.status_code == 201 and len(r.json()["run_ids"]) == 4
    cmp = client.post(
        "/api/compare", json={"run_ids": r.json()["run_ids"], "split": "validation"}, headers=H
    ).json()
    assert not cmp["compatibility"]["compatible"]  # smoke runs are flagged
    assert {g["reward_preset"] for g in cmp["groups"]} == {"baseline", "potential"}


@pytest.mark.slow
def test_keyboard_flight_is_recorded_like_any_episode(client):
    r = client.post("/api/flights", json={"seed": 40_001, "opponent": "heuristic"}, headers=H)
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["seed"] == 40_001 and f["seed_split"] == "flight"
    assert f["scene"]["terrain"] and f["row"]["t"] == 0
    ghost = f["ghost"]
    assert ghost["source"]["type"] == "heuristic" and len(ghost["rows"]) == ghost["episode"]["length"] + 1
    sid = f["session_id"]

    assert client.post(f"/api/flights/{sid}/step", json={"actions": [7]}, headers=H).status_code == 422
    assert client.post(f"/api/flights/{sid}/step", json={"actions": []}, headers=H).status_code == 422
    rows, done = [], False
    for _ in range(40):  # doing nothing: the lander falls and the episode ends
        out = client.post(f"/api/flights/{sid}/step", json={"actions": [0] * 50}, headers=H).json()
        rows += out["rows"]
        if out["done"]:
            done = True
            break
    assert done
    assert [row["t"] for row in rows] == list(range(1, len(rows) + 1))
    rec = out["recording"]
    assert rec["policy"]["kind"] == "human" and rec["length"] == len(rows)
    assert out["episode"]["original_return"] == pytest.approx(rows[-1]["cum_original"])
    listed = {m["recording_id"]: m for m in client.get("/api/recordings").json()}
    assert rec["recording_id"] in listed
    tele = client.get(f"/api/recordings/{rec['recording_id']}").json()
    assert tele["source"]["type"] == "flight" and tele["source"]["opponent"]["type"] == "heuristic"
    assert client.get(f"/api/recordings/{rec['recording_id']}/scene").status_code == 200
    # the session is closed once the episode has ended
    assert client.post(f"/api/flights/{sid}/step", json={"actions": [0]}, headers=H).status_code == 404


def test_flight_validation(client):
    assert client.post("/api/flights", json={"opponent": "../etc"}, headers=H).status_code == 422
    assert (
        client.post(
            "/api/flights", json={"opponent": "20260101-000000-missing-s0-smoke-abcd"}, headers=H
        ).status_code
        == 400
    )
    assert client.post("/api/flights", json={"seed": -1}, headers=H).status_code == 422
    assert client.delete("/api/flights/nope", headers=H).json() == {"abandoned": False}
    f = client.post("/api/flights", json={}, headers=H).json()
    assert 40_000 <= f["seed"] < 50_000 and f["ghost"] is None
    assert client.delete(f"/api/flights/{f['session_id']}", headers=H).json() == {"abandoned": True}
    assert (
        client.post(f"/api/flights/{f['session_id']}/step", json={"actions": [0]}, headers=H).status_code
        == 404
    )


def test_preference_labelling_endpoints(client):
    from lunarlab.env import make_env
    from lunarlab.policies import HeuristicPolicy, RandomPolicy
    from lunarlab.preferences.data import create_dataset

    ds = create_dataset(
        [("random", RandomPolicy(0)), ("heuristic", HeuristicPolicy(make_env()))], episodes_per_policy=2
    )
    listed = client.get("/api/preferences").json()
    assert [d["dataset_id"] for d in listed] == [ds] and listed[0]["human_labels"] == 0
    pair = client.get(f"/api/preferences/{ds}/pair").json()
    assert pair["i"] != pair["j"]
    assert len(pair["a"]["obs"]) == len(pair["a"]["actions"]) + 1 and pair["a"]["scene"]["terrain"]
    assert "source" not in pair["a"]  # the labeller judges the flight, not its origin
    body = {"i": pair["i"], "j": pair["j"], "choice": "a"}
    r = client.post(f"/api/preferences/{ds}/labels", json=body, headers=H)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["n_labels"] == 1 and out["agrees"] == (out["reward_prefers"] == "a")
    assert (
        client.post(f"/api/preferences/{ds}/labels", json={**body, "choice": "maybe"}, headers=H).status_code
        == 422
    )
    assert (
        client.post(f"/api/preferences/{ds}/labels", json={**body, "j": pair["i"]}, headers=H).status_code
        == 400
    )
    assert client.get("/api/preferences/nope/pair").status_code == 404
    assert client.get("/api/preferences/..%2F..%2Fetc/pair").status_code in (400, 404)
    assert client.get("/api/reward-models").json() == []
