# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Invalid input is refused clearly: CLI arguments and ids (exit 2 / exit 1, never a traceback) and HTTP requests
(4xx with a reason, never a 500 or a file outside the home)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lunarlab.cli import main
from lunarlab.server.main import create_app

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "examples" / "artifacts" / "ppo-baseline-s0"
H = {"X-LunarLab": "1"}


# --------------------------------------------------------------------------------------------- CLI


@pytest.mark.parametrize(
    "argv",
    [
        ["evaluate", "--run-id", "../escape", "--split", "validation"],
        ["record", "--run-id", "bad/id", "--episode-seed", "1"],
        ["rescore", "--recording-id", "..\\secret"],
        ["tune-status", "--study-id", "x" * 200],
        ["compare", "--experiment-id", "a b"],
    ],
)
def test_invalid_ids_are_usage_errors(argv, capsys):
    assert main(argv) == 2
    err = capsys.readouterr().err
    assert "is not a valid id" in err and "Traceback" not in err


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["resume", "--run-id", "no-such-run"], "unknown run: no-such-run"),
        (["test-status", "--run-id", "no-such-run"], "unknown run: no-such-run"),
        (["export-artifact", "--run-id", "no-such-run", "--out", "x"], "unknown run: no-such-run"),
        (["rescore", "--recording-id", "no-such-recording"], "unknown recording: no-such-recording"),
        (["tune-status", "--study-id", "no-such-study"], "unknown study: no-such-study"),
        (["tune-cancel", "--study-id", "no-such-study"], "unknown study: no-such-study"),
    ],
)
def test_unknown_ids_are_errors_not_tracebacks(argv, message, capsys):
    assert main(argv) == 1
    err = capsys.readouterr().err
    assert message in err and "Traceback" not in err


def test_missing_reproduction_inputs_are_usage_errors(tmp_path, capsys):
    assert main(["reproduce-artifact", "--artifact", str(tmp_path / "none")]) == 2
    assert "is not a reproduction package" in capsys.readouterr().err
    assert main(["trace-artifact", "--artifact", str(ARTIFACT), "--compare", str(tmp_path / "none.npz")]) == 2
    assert "no trace pair" in capsys.readouterr().err


def test_invalid_choices_and_missing_arguments_exit_with_argparse_status():
    for argv in (
        ["train", "--profile", "nope"],
        ["evaluate", "--run-id", "x", "--split", "nope"],
        ["evaluate"],
    ):
        with pytest.raises(SystemExit) as exc:
            main(argv)
        assert exc.value.code == 2


def test_a_keyerror_that_is_not_an_unknown_id_still_surfaces(monkeypatch):
    from lunarlab import freeze
    from lunarlab.config import TrainingConfig
    from lunarlab.rewards import preset
    from lunarlab.runs import create_run

    cfg = create_run(
        reward=preset("baseline"), seed=0, training=TrainingConfig(profile="custom", total_transitions=512)
    )

    def broken(run_id):
        raise KeyError("some-internal-key")

    monkeypatch.setattr(freeze, "test_status", broken)
    with pytest.raises(KeyError, match="some-internal-key"):  # a bug, not a user error: not swallowed
        main(["test-status", "--run-id", cfg.run_id])


# -------------------------------------------------------------------------------------------- HTTP


@pytest.fixture
def client():
    with TestClient(create_app(start_jobs=False, testing=True)) as c:
        yield c


@pytest.fixture
def run_id(client):
    r = client.post(
        "/api/runs", json={"preset": "baseline", "profile": "smoke", "seed": 1, "start": False}, headers=H
    )
    assert r.status_code == 201
    return r.json()["run"]["run_id"]


def test_run_files_are_served_only_from_their_folders(client, run_id):
    assert client.get(f"/api/runs/{run_id}/config.yaml").status_code == 200
    for url, codes in (
        (f"/api/runs/{run_id}/evaluations/..%2Fconfig.yaml", (400, 404)),
        (f"/api/runs/{run_id}/evaluations/missing.json", (404,)),
        (f"/api/runs/{run_id}/files/secrets/x.png", (404,)),
        (f"/api/runs/{run_id}/files/figures/..%2F..%2Fconfig.yaml", (400, 404)),
        (f"/api/runs/{run_id}/files/figures/none.png", (404,)),
        ("/api/runs/no-such-run/config.yaml", (404,)),
        ("/api/reports/no-such-report/report.md", (404,)),
        ("/api/reports/bad%20id/report.md", (400,)),
    ):
        r = client.get(url)
        assert r.status_code in codes, (url, r.status_code, r.text)


def test_unknown_jobs_studies_recordings_and_experiments_are_404(client):
    for method, url in (
        ("get", "/api/jobs/job-none"),
        ("get", "/api/jobs/job-none/log"),
        ("post", "/api/jobs/job-none/stop"),
        ("post", "/api/jobs/job-none/terminate"),
        ("get", "/api/tuning/no-such-study"),
        ("get", "/api/recordings/no-such-recording"),
        ("get", "/api/recordings/no-such-recording/scene"),
        ("get", "/api/experiments/no-such-experiment"),
    ):
        r = client.request(method, url, headers=H)
        assert r.status_code == 404, (url, r.status_code, r.text)


def test_state_changes_that_do_not_apply_are_refused_with_a_reason(client, run_id):
    assert client.post(f"/api/runs/{run_id}/stop", headers=H).status_code == 409  # nothing running
    r = client.post(f"/api/runs/{run_id}/resume", json={"checkpoint": "latest"}, headers=H)
    assert r.status_code == 409  # no checkpoint yet
    assert (
        client.post(f"/api/runs/{run_id}/resume", json={"checkpoint": "../x"}, headers=H).status_code == 422
    )
    r = client.post(f"/api/runs/{run_id}/warm-restart", json={"checkpoint": "latest"}, headers=H)
    assert r.status_code in (400, 422)  # a warm restart must be confirmed explicitly
    assert client.post("/api/shutdown", headers=H).status_code == 409  # not under the launcher
    for body in (
        {"preset": "baseline", "profile": "nope"},
        {"preset": "baseline", "seed": -1},
        {"unknown": 1},
    ):
        assert client.post("/api/runs", json=body, headers=H).status_code == 422, body
    assert client.post("/api/compare", json={"run_ids": "not-a-list"}, headers=H).status_code == 422
    assert (
        client.post(
            "/api/runs", content=b"{not json", headers={**H, "Content-Type": "application/json"}
        ).status_code
        == 422
    )
