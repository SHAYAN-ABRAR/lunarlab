"""Reports and the portfolio summary are built only from stored data."""

from __future__ import annotations

import pytest

from lunarlab.config import EvalProtocol, PPOConfig, TrainingConfig, training_for_profile
from lunarlab.evaluation import evaluate_run
from lunarlab.report import NOT_MEASURED, build_report
from lunarlab.rewards import preset
from lunarlab.runs import create_run
from lunarlab.training import EXIT_COMPLETED, train

pytestmark = pytest.mark.slow

PROTOCOL = EvalProtocol(validation_seeds=[10_000], test_seeds=[20_000, 20_001, 20_002])
PPO = PPOConfig(n_envs=2, n_steps=64, batch_size=32)


def _trained(profile_training: TrainingConfig, name: str = "baseline"):
    cfg = create_run(reward=preset(name), training=profile_training, seed=0, ppo=PPO, protocol=PROTOCOL)
    assert train(cfg.run_id, quiet=True) == EXIT_COMPLETED
    evaluate_run(cfg.run_id, "test")
    return cfg


def test_smoke_runs_never_produce_portfolio_numbers(tmp_path):
    cfg = _trained(
        training_for_profile("smoke", total_transitions=256, checkpoint_every=256, validation_every=256)
    )
    assert cfg.training.profile == "custom"  # changed budget is no longer the named profile
    smoke = create_run(
        reward=preset("potential"),
        training=TrainingConfig(
            profile="smoke", total_transitions=256, checkpoint_every=256, validation_every=256
        ),
        seed=1,
        ppo=PPO,
        protocol=PROTOCOL,
    )
    assert train(smoke.run_id, quiet=True) == EXIT_COMPLETED
    evaluate_run(smoke.run_id, "test")
    out = build_report([cfg.run_id, smoke.run_id], title="t", report_id="report-test-1", out_root=tmp_path)
    folder = tmp_path / "report-test-1"
    for f in ("report.md", "report.html", "portfolio_summary.md", "data.json"):
        assert (folder / f).stat().st_size > 0
    assert "training_curves" in out["figures"] and "outcomes" in out["figures"]
    portfolio = (folder / "portfolio_summary.md").read_text(encoding="utf-8")
    # The custom-budget baseline has real test evaluations; the SMOKE potential run must not.
    assert "Original baseline** (1 training seed(s), 3 test episodes each)" in portfolio
    assert f"**Potential-based shaping**: {NOT_MEASURED}" in portfolio
    report = (folder / "report.md").read_text(encoding="utf-8")
    assert "Includes SMOKE runs" in report
    assert "not evidence of real-world rocket-control capability" in report


def test_validation_split_report_does_not_fill_portfolio(tmp_path):
    cfg = _trained(
        TrainingConfig(profile="custom", total_transitions=256, checkpoint_every=256, validation_every=256)
    )
    evaluate_run(cfg.run_id, "validation")
    build_report([cfg.run_id], title="t", report_id="report-test-2", split="validation", out_root=tmp_path)
    portfolio = (tmp_path / "report-test-2" / "portfolio_summary.md").read_text(encoding="utf-8")
    assert f"**Original baseline**: {NOT_MEASURED}" in portfolio
