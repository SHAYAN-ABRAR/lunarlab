# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""The task-independent study workflow: protocol validation, training, selection, freezing, testing, artifacts.

A tiny CartPole protocol (128 transitions per run) runs the whole workflow once. The exported artifact is
then tampered with in several ways, each of which must be caught before any episode runs.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path

import pytest

from lunarlab.audit import AuditInputError
from lunarlab.audit import study as st
from lunarlab.cli import main


def tiny_protocol(**changes) -> dict:
    p = {
        "schema": st.STUDY_SCHEMA,
        "study_id": "test-study",
        "adapter": {"name": "cartpole", "version": "1"},
        "env_kwargs": {},
        "gamma": 0.98,
        "algorithm": {
            "name": "ppo",
            "policy": "MlpPolicy",
            "n_envs": 2,
            "kwargs": {
                "n_steps": 32,
                "batch_size": 64,
                "n_epochs": 2,
                "gae_lambda": 0.8,
                "ent_coef": 0.0,
                "learning_rate": {"linear": 0.001},
                "clip_range": {"linear": 0.2},
            },
        },
        "budget_transitions": 128,
        "eval_every_rollouts": 1,
        "designs": [
            {"name": "original", "original_weight": 1.0, "terms": []},
            {
                "name": "failure-bonus",
                "original_weight": 1.0,
                "terms": [{"term": "failure_bonus", "params": {"bonus": 1000.0}}],
            },
        ],
        "training_seeds": [7],
        "train_env_seed_root": 1_000_000,
        "validation_seeds": [110_000, 110_001],
        "test_seeds": [210_000, 210_001, 210_002],
        "selection": {"rule": "max-mean-original-validation-return"},
        "success_outcome": "balanced_to_time_limit",
        "torch_threads": 1,
    }
    p.update(changes)
    return p


@pytest.mark.parametrize(
    "changes, fragment",
    [
        ({"validation_seeds": [1, 2], "test_seeds": [2, 3]}, "overlap"),
        ({"training_seeds": [True]}, "training seeds must be nonnegative integers"),
        ({"test_seeds": []}, "test seeds must not be empty"),
        ({"train_env_seed_root": 110_000 - 7000}, "are validation or test seeds"),
        ({"designs": [{"name": "x", "terms": [{"term": "hover_bonus"}]}]}, "no reward term"),
        ({"adapter": {"name": "cartpole", "version": "2"}}, "is version '1'"),
        ({"success_outcome": "landed"}, "success_outcome"),
        ({"gamma": float("nan")}, "gamma must be finite"),
        ({"budget_transitions": 0}, "budget_transitions must be a positive integer"),
        (
            {"designs": [{"name": "p", "terms": [{"term": "upright_potential", "params": {"gamma": 0.5}}]}]},
            "not the learner's",
        ),
    ],
)
def test_invalid_protocols_are_refused_with_a_reason(changes, fragment):
    assert st.protocol_problems(tiny_protocol()) == []
    problems = st.protocol_problems(tiny_protocol(**changes))
    assert any(fragment in p for p in problems), problems
    with pytest.raises(AuditInputError):
        st.require_valid_protocol(tiny_protocol(**changes))


def test_selection_takes_the_best_validation_return_and_the_earliest_tie():
    def c(step, mean):
        return {"step": step, "validation": {"mean_original_return": mean}}

    assert (
        st.select_checkpoint([c(10, 5.0), c(20, 9.0), c(30, 9.0)], "max-mean-original-validation-return")[
            "step"
        ]
        == 20
    )
    with pytest.raises(AuditInputError):
        st.select_checkpoint([c(10, 1.0)], "best-test-return")
    with pytest.raises(AuditInputError):
        st.select_checkpoint([], "max-mean-original-validation-return")


def test_budget_rounding_and_environment_seeds():
    p = tiny_protocol(budget_transitions=100)
    assert st.rollout_size(p) == 64 and st.actual_transitions(p) == 128
    assert st.train_env_seeds(p, 7) == [1_007_000, 1_007_001]


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    base = tmp_path_factory.mktemp("study")
    protocol = tiny_protocol()
    runs = {}
    for design in ("original", "failure-bonus"):
        run_dir = base / design
        st.train_run(protocol, design, 7, run_dir, echo=lambda _m: None)
        st.final_test(run_dir)
        runs[design] = run_dir
    return base, runs


@pytest.mark.slow
def test_the_workflow_records_seeds_budget_selection_and_frozen_digests(trained):
    _, runs = trained
    run = json.loads((runs["original"] / "run.json").read_text(encoding="utf-8"))
    assert run["transitions"] == {"configured": 128, "actual": 128, "rollout_size": 64, "rollouts": 2}
    assert run["seeding"]["effective_first_reset_seeds"] == [1_007_000, 1_007_001]
    assert run["seeding"]["later_resets_with_a_seed"] == 0
    assert [c["step"] for c in run["checkpoints"]] == [64, 128]
    chosen = max(run["checkpoints"], key=lambda c: (c["validation"]["mean_original_return"], -c["step"]))
    assert run["selection"]["step"] == chosen["step"] and run["selection"]["sha256"] == chosen["sha256"]
    for entry in run["frozen"].values():
        path = runs["original"] / entry["file"]
        assert st._sha256_file(path) == entry["sha256"]
        assert not os.access(path, os.W_OK)  # read-only
    for c in run["checkpoints"]:
        assert [e["seed"] for e in c["validation"]["episodes"]] == [110_000, 110_001]  # never test seeds
    test = json.loads((runs["original"] / "test-selected.json").read_text(encoding="utf-8"))
    assert test["checkpoint_sha256"] == run["frozen"]["selected"]["sha256"]
    assert [e["seed"] for e in test["report"]["episodes"]] == [210_000, 210_001, 210_002]
    with pytest.raises(AuditInputError, match="recorded once"):
        st.final_test(runs["original"])
    with pytest.raises(AuditInputError, match="never retrained in place"):
        st.train_run(tiny_protocol(), "original", 7, runs["original"])


@pytest.mark.slow
def test_the_failure_bonus_pays_exactly_on_true_termination(trained):
    _, runs = trained
    test = json.loads((runs["failure-bonus"] / "test-selected.json").read_text(encoding="utf-8"))
    for e in test["report"]["episodes"]:
        bonus = 1000.0 if e["terminated"] else 0.0
        assert e["term_returns"]["failure_bonus"] == bonus
        assert e["training_return"] == pytest.approx(e["original_return"] + bonus, abs=1e-9)
        assert (
            e["original_return"] == e["length"]
        )  # CartPole-v1 pays +1 per step, the terminating one included


@pytest.fixture()
def artifact(trained, tmp_path):
    _, runs = trained
    out = tmp_path / "artifact"
    st.export_artifact(runs["original"], out)
    return out


def _rewrite(artifact_dir: Path, name: str, change) -> None:
    """Edit one artifact file and update its manifest digest, so only the targeted check can catch it."""
    p = artifact_dir / name
    data = json.loads(p.read_text(encoding="utf-8"))
    change(data)
    p.write_text(json.dumps(data), encoding="utf-8")
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"][name]["sha256"] = st._sha256_file(p)
    (artifact_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.slow
def test_a_clean_artifact_verifies_and_reproduces_exactly(artifact, tmp_path):
    assert st.verify_artifact(artifact)["ok"]
    result = st.reproduce_artifact(artifact, echo=lambda _m: None)
    assert result["status"] == "exact" and result["exit_code"] == 0
    assert main(["audit-artifact", "verify", "--artifact", str(artifact)]) == 0
    report = tmp_path / "r.json"
    assert main(["audit-artifact", "reproduce", "--artifact", str(artifact), "--report", str(report)]) == 0
    assert json.loads(report.read_text(encoding="utf-8"))["status"] == "exact"


def _make_writable(p: Path) -> None:
    os.chmod(p, stat.S_IWRITE | stat.S_IREAD)


TAMPERING = {
    "changed policy bytes": (
        lambda a: (_make_writable(a / "policy.zip"), (a / "policy.zip").write_bytes(b"not a model")),
        "policy.zip has its recorded SHA-256",
    ),
    "missing policy": (
        lambda a: (_make_writable(a / "policy.zip"), (a / "policy.zip").unlink()),
        "policy.zip is present",
    ),
    "changed test seeds": (
        lambda a: _rewrite(a, "protocol.json", lambda d: d.update(test_seeds=[1, 2, 3])),
        "protocol digest matches",
    ),
    "overlapping seeds": (
        lambda a: _rewrite(a, "protocol.json", lambda d: d.update(test_seeds=[110_000, 210_001, 210_002])),
        "protocol is valid",
    ),
    "inconsistent recorded totals": (
        lambda a: _rewrite(
            a, "evaluation.json", lambda d: d["report"]["episodes"][0].update(training_return=-1.0)
        ),
        "training return = weight x original return",
    ),
    "absent original-reward channel": (
        lambda a: _rewrite(a, "evaluation.json", lambda d: d["report"]["episodes"][1].pop("original_return")),
        "original and training reward channels",
    ),
    "non-finite recorded value": (
        lambda a: _rewrite(
            a,
            "evaluation.json",
            lambda d: d["report"]["episodes"][0].update(discounted_training_return=1e400),
        ),
        "finite number",
    ),
    "outcome outside the schema": (
        lambda a: _rewrite(
            a, "evaluation.json", lambda d: d["report"]["episodes"][2].update(outcome="landed")
        ),
        "one of the adapter's categories",
    ),
    "outcome schema version": (
        lambda a: _rewrite_manifest(a, lambda m: m["adapter"].update(version="2")),
        "outcome schema matches",
    ),
    "reward definition changed": (
        lambda a: _rewrite(a, "reward.json", lambda d: d.update(definition_sha256="0" * 64)),
        "reward definition rebuilt",
    ),
    "malformed manifest": (
        lambda a: _rewrite_manifest(a, lambda m: m.pop("protocol_sha256")),
        "artifact records are complete",
    ),
}


def _rewrite_manifest(artifact_dir: Path, change) -> None:
    p = artifact_dir / "manifest.json"
    m = json.loads(p.read_text(encoding="utf-8"))
    change(m)
    p.write_text(json.dumps(m), encoding="utf-8")


@pytest.mark.slow
@pytest.mark.parametrize("case", sorted(TAMPERING))
def test_tampering_is_caught_before_any_episode_runs(artifact, case, monkeypatch):
    tamper, failing_check = TAMPERING[case]
    tamper(artifact)
    verification = st.verify_artifact(artifact)
    assert not verification["ok"]
    failed = [c["check"] for c in verification["checks"] if not c["ok"]]
    assert any(failing_check in name for name in failed), failed
    ran = []
    monkeypatch.setattr(st, "audit_policy", lambda *a, **k: ran.append(1))
    result = st.reproduce_artifact(artifact, echo=lambda _m: None)
    assert result["status"] == "integrity-failure" and result["exit_code"] == 1
    assert result["evaluation_skipped"] and not ran
    assert main(["audit-artifact", "verify", "--artifact", str(artifact)]) == 1


def test_the_cli_refuses_a_folder_without_a_manifest(tmp_path):
    assert main(["audit-artifact", "verify", "--artifact", str(tmp_path)]) == 2


@pytest.mark.slow
def test_a_modified_frozen_checkpoint_is_refused_before_loading(trained, tmp_path):
    _, runs = trained
    copy = tmp_path / "run"
    shutil.copytree(runs["original"], copy)
    run = json.loads((copy / "run.json").read_text(encoding="utf-8"))
    frozen = copy / run["frozen"]["final"]["file"]
    _make_writable(frozen)
    frozen.write_bytes(frozen.read_bytes() + b"x")
    with pytest.raises(AuditInputError, match="has digest"):
        st.final_test(copy, which="final")
    assert not (copy / "test-final.json").exists()
