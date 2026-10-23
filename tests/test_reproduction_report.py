# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Reproduction reports: per-episode diagnostics, paired conclusion-stability tests, status rules, the CI summary,
per-step traces, and that CI never hides a reproduction outcome."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from lunarlab.reproduce import (
    STATUSES,
    classify_reproduction,
    compare_aggregates,
    compare_episodes,
    compare_platforms,
    holm,
    mcnemar_p_value,
    platform_key,
    reproduce_artifact,
    sign_flip_p_value,
)

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "examples" / "artifacts" / "ppo-baseline-s0"


def _recorded():
    from lunarlab.config import RunConfig
    from lunarlab.storage import read_yaml

    cfg = RunConfig.model_validate(read_yaml(ARTIFACT / "config.yaml"))
    rec = json.loads((ARTIFACT / "evaluation.json").read_text(encoding="utf-8"))
    return cfg, rec


# ---------------------------------------------------------------- per-episode comparison


def test_episode_rows_and_summary_describe_every_difference():
    _, rec = _recorded()
    landed = [e for e in rec["episodes"] if e["env_outcome"] == "at_rest" and e["pad_landing"]]
    eps = landed[:10]
    rep = copy.deepcopy(eps)
    rep[0]["original_return"] += 0.5
    rep[0]["training_return"] += 0.5
    rep[1]["original_return"] += 20.0
    rep[1]["training_return"] += 20.0
    rep[1]["length"] += 3
    rep[2]["env_outcome"], rep[2]["pad_landing"] = "crash", False
    cmp = compare_episodes(eps, rep)
    assert cmp["compared"] == 10 and cmp["exact"] == 7 and cmp["n_mismatches"] == 3
    assert len(cmp["episodes"]) == 10 and cmp["missing_seeds"] == []
    rows = {r["seed"]: r for r in cmp["episodes"]}
    r0, r1, r2 = rows[eps[0]["seed"]], rows[eps[1]["seed"]], rows[eps[2]["seed"]]
    assert r0["abs_return_difference"] == pytest.approx(0.5) and r0["length_agrees"] and r0["outcome_agrees"]
    assert r0["relative_return_difference"] == pytest.approx(0.5 / abs(eps[0]["original_return"]))
    assert not r1["length_agrees"] and r1["recorded_length"] + 3 == r1["reproduced_length"]
    assert not r2["outcome_agrees"] and r2["pad_landing"] == [eps[2]["pad_landing"], False]
    s = cmp["summary"]
    assert s["agreement"]["bit_identical"] == 0.7 and s["agreement"]["length"] == 0.9
    assert s["agreement"]["all_outcome_fields"] == 0.9 and s["agreement"]["termination"] == 1.0
    rd = s["return_difference"]
    assert rd["max_abs"] == pytest.approx(20.0) and rd["episodes_differing"] == 2
    assert rd["episodes_above_1"] == 1 and rd["episodes_above_10"] == 1
    assert rd["mean_abs"] == pytest.approx(20.5 / 10)


def test_relative_differences_skip_returns_near_zero_and_missing_seeds_are_listed():
    _, rec = _recorded()
    ep = copy.deepcopy(rec["episodes"][0])
    ep["original_return"] = 0.25
    rep = copy.deepcopy(ep)
    rep["original_return"] = 0.5
    stray = copy.deepcopy(ep)
    stray["seed"] = 99_999
    cmp = compare_episodes([ep], [rep, stray])
    assert cmp["episodes"][0]["relative_return_difference"] is None
    assert cmp["summary"]["return_difference"]["n_relative"] == 0
    assert cmp["missing_seeds"] == [99_999]


def test_return_scales_and_exactness_scope_are_explicit():
    _, rec = _recorded()
    ep = copy.deepcopy(rec["episodes"][0])
    rep = copy.deepcopy(ep)
    rep["original_return"] += 0.25
    rep["training_return"] += 125.0
    cmp = compare_episodes([ep], [rep])
    assert cmp["max_abs_original_return_difference"] == pytest.approx(0.25)
    assert cmp["max_abs_training_return_difference"] == pytest.approx(125.0)
    assert cmp["max_abs_return_difference"] == pytest.approx(125.0)  # legacy mixed scale
    assert cmp["compared_fields"] == [
        "length",
        "original_return",
        "training_return",
        "env_outcome",
        "pad_landing",
    ]
    assert "not full-trajectory" in cmp["exactness_scope"]
    # Final observations are diagnostic, not included in the historical exact-match key.
    rep = copy.deepcopy(ep)
    rep["final_obs"] = [99.0] * 8
    assert compare_episodes([ep], [rep])["exact"] == 1


# ---------------------------------------------------------------- paired tests


def test_paired_test_building_blocks():
    assert mcnemar_p_value(0, 0) == 1.0 and mcnemar_p_value(0, 1) == 1.0 and mcnemar_p_value(5, 5) == 1.0
    assert mcnemar_p_value(0, 10) == pytest.approx(2 / 1024)
    assert sign_flip_p_value([0.0] * 50) == 1.0
    assert sign_flip_p_value([0.0] * 99 + [7.0]) == 1.0  # one difference cannot be significant
    assert sign_flip_p_value([-1.0] * 30 + [0.0] * 70) < 0.001
    assert holm({"a": 0.001, "b": 0.04, "c": 0.5}) == {"a": True, "b": False, "c": False}
    assert holm({"a": 0.011, "b": 0.012}) == {"a": True, "b": True}  # 0.011 <= 0.05/2, then 0.012 <= 0.05
    assert holm({"a": 0.03, "b": 0.04}) == {"a": False, "b": False}  # 0.03 > 0.05/2 stops the procedure


def test_aggregates_flag_systematic_shifts_but_not_symmetric_noise():
    cfg, rec = _recorded()
    eps = rec["episodes"]
    same = compare_aggregates(eps, copy.deepcopy(eps), cfg.eval_protocol)
    assert same["consistent"] and all(m["p_value"] == 1.0 for m in same["metrics"].values())
    assert same["equivalence_assessed"] is False
    assert "does not establish equivalence" in same["interpretation"]
    assert same["metrics"]["mean_original_return"]["recorded"] == rec["aggregate"]["original_return"]["mean"]
    assert same["metrics"]["mean_original_return"]["recorded_ci"] == rec["aggregate"]["original_return"]["ci"]
    # one episode changes category and a few returns move both ways: noise, not a regression
    noisy = copy.deepcopy(eps)
    crash = next(i for i, e in enumerate(noisy) if e["env_outcome"] == "crash")
    noisy[crash]["env_outcome"] = "out_of_bounds"
    for i, e in enumerate(noisy[:20]):
        e["original_return"] += 0.01 if i % 2 else -0.01
    assert compare_aggregates(eps, noisy, cfg.eval_protocol)["consistent"]
    # twenty pad landings turn into crashes: a regression
    broken = copy.deepcopy(eps)
    turned = 0
    for e in broken:
        if e["pad_landing"] and turned < 20:
            e.update(pad_landing=False, env_outcome="crash", original_return=e["original_return"] - 250.0)
            turned += 1
    agg = compare_aggregates(eps, broken, cfg.eval_protocol)
    assert not agg["consistent"]
    assert agg["metrics"]["pad_landing_rate"]["significant"] and agg["metrics"]["crash_rate"]["significant"]
    assert agg["metrics"]["pad_landing_rate"]["episodes_lost"] == 20
    assert agg["metrics"]["mean_original_return"]["significant"]


# ---------------------------------------------------------------- platforms and statuses

WINDOWS = {
    "platform": "Windows-11-10.0.26300-SP0",
    "python": "3.12.13",
    "packages": {"torch": "2.14.1", "numpy": "2.5.4", "Box2D": "2.3.10", "gymnasium": "1.4.0",
                 "stable-baselines3": "2.9.0"},
}  # fmt: skip


def test_platform_identity_is_the_operating_system_and_numerical_libraries():
    assert platform_key(WINDOWS)["os"] == "Windows"
    other_python = {**WINDOWS, "python": "3.13.12"}
    assert compare_platforms(WINDOWS, other_python)["same_platform"]
    linux = {**WINDOWS, "platform": "Linux-6.17.0-1022-azure-x86_64-with-glibc2.39",
             "packages": {**WINDOWS["packages"], "torch": "2.14.1+cpu"}}  # fmt: skip
    p = compare_platforms(WINDOWS, linux)
    assert not p["same_platform"] and set(p["differences"]) == {"os", "torch"}
    assert not compare_platforms(None, WINDOWS)["same_platform"]  # unknown recording platform


def _cmp(n=100, exact=100, mismatches=None):
    return {
        "compared": n,
        "exact": exact,
        "n_mismatches": n - exact if mismatches is None else mismatches,
        "summary": {
            "return_difference": {"median_abs": 0.002, "max_abs": 0.3},
            "agreement": {"all_outcome_fields": 1.0, "length": 1.0},
        },
    }


def test_status_rules_and_exit_codes():
    ok = {"consistent": True, "metrics": {}}
    bad = {"consistent": False, "metrics": {"pad_landing_rate": {"significant": True}}}
    same = {"same_platform": True, "differences": {}}
    other = {"same_platform": False, "differences": {"os": ["Windows", "Linux"]}}

    def status(**kw):
        args = {"integrity_ok": True, "comparison": _cmp(), "aggregates": ok, "platform": other} | kw
        return classify_reproduction(**args)[0]

    assert status() == "exact"
    assert status(integrity_ok=False) == "integrity-failure"  # integrity comes first
    assert status(comparison=_cmp(exact=0), platform=other) == "numerical-difference"
    assert status(comparison=_cmp(exact=0), platform=same) == "unexpected-difference"
    assert status(comparison=_cmp(exact=0), aggregates=bad) == "aggregate-disagreement"
    assert status(comparison=_cmp(exact=0, mismatches=0), tolerance=0.5) == "within-tolerance"
    assert {k: v["exit_code"] for k, v in STATUSES.items()} == {
        "exact": 0, "within-tolerance": 0, "numerical-difference": 3,
        "unexpected-difference": 1, "aggregate-disagreement": 1, "integrity-failure": 1,
    }  # fmt: skip
    assert [k for k, v in STATUSES.items() if v["blocking"]] == [
        "unexpected-difference", "aggregate-disagreement", "integrity-failure",
    ]  # fmt: skip


# ---------------------------------------------------------------- the CI summary


def _summary_tool():
    spec = importlib.util.spec_from_file_location(
        "reproduction_summary", ROOT / "tools" / "reproduction_summary.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _report(status, *, exact=100):
    return {
        "schema": 2,
        "status": status,
        "status_reason": f"because {status}",
        "integrity_ok": status != "integrity-failure",
        "platform": {"same_platform": False, "differences": {"os": ["Windows", "Linux"]}},
        "episodes": 100,
        "comparison": {"exact": exact, **_cmp(exact=exact)},
        "recorded_mean_original_return": 1.0,
        "reproduced_mean_original_return": 1.1,
        "recorded_pad_landing_rate": 0.5,
        "reproduced_pad_landing_rate": 0.5,
        "aggregates": {"consistent": status != "aggregate-disagreement"},
    }


def test_ci_summary_tolerates_only_cross_platform_differences_and_catches_hidden_failures(tmp_path):
    tool = _summary_tool()
    paths = {}
    for name, status, exact in (("a-s0", "exact", 100), ("b-s0", "numerical-difference", 0)):
        paths[name] = tmp_path / f"reproduce-{name}-linux.json"
        paths[name].write_text(json.dumps(_report(status, exact=exact)), encoding="utf-8")
    s = tool.summarize(list(paths.values()), [], {"a-s0": 0, "b-s0": 3}, "linux")
    assert s["ok"] and s["problems"] == []
    tolerated = [r for r in s["artifacts"] if r["tolerated_because"]]
    assert [r["artifact"] for r in tolerated] == ["b-s0"]
    md = tool.markdown(s)
    assert md.isascii() and "numerical-difference" in md and "Tolerated (not failed): b-s0" in md
    # an exit code that contradicts the report, a missing report, and a blocking status all fail
    assert not tool.summarize(list(paths.values()), [], {"a-s0": 1, "b-s0": 3}, "linux")["ok"]
    assert not tool.summarize(list(paths.values()), [], {"a-s0": 0, "b-s0": 3, "c-s0": 1}, "linux")["ok"]
    paths["b-s0"].write_text(json.dumps(_report("aggregate-disagreement", exact=0)), encoding="utf-8")
    blocked = tool.summarize(list(paths.values()), [], {"a-s0": 0, "b-s0": 1}, "linux")
    assert not blocked["ok"] and any("aggregate-disagreement" in p for p in blocked["problems"])
    old = tmp_path / "reproduce-c-s0-linux.json"
    old.write_text(json.dumps({"schema": 1, "ok": False}), encoding="utf-8")
    assert not tool.summarize([old], [], {}, "linux")["ok"]  # an old report without a status is not accepted


def test_ci_never_discards_a_reproduction_exit_code():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for line in ci.splitlines():
        if "reproduce-artifact" in line or "trace-artifact" in line:
            assert "|| true" not in line, line
    assert ci.count("tools/reproduction_summary.py") + ci.count("tools\\reproduction_summary.py") == 2


# ---------------------------------------------------------------- full reports and traces


@pytest.mark.integration
def test_reproduce_artifact_report_separates_integrity_reproduction_and_conclusions():
    report = reproduce_artifact(ARTIFACT, episodes=4, echo=lambda _m: None)
    assert report["schema"] == 2 and report["integrity_ok"] and not report["blocking"]
    if report["platform"]["same_platform"]:  # the recording platform: bit-identical or it is a regression
        assert report["status"] == "exact" and report["exit_code"] == 0 and report["ok"]
    else:  # elsewhere (e.g. Linux CI) numerical differences are reported, not failed
        assert report["status"] in ("exact", "numerical-difference") and report["exit_code"] in (0, 3)
    kinds = {c["check"]: c["kind"] for c in report["checks"]}
    for name in (
        "the recorded evaluation is the final test on the configuration's test seeds",
        "the recorded evaluation used the configuration's protocol and reward",
        "the recorded episodes are exactly the recorded seeds",
        "the evaluated network holds exactly the checkpoint's weights",
    ):
        assert kinds[name] == "integrity", name
    assert report["aggregates"]["consistent"] and len(report["comparison"]["episodes"]) == 4


@pytest.mark.integration
def test_wrong_seeds_or_weights_are_integrity_failures(tmp_path, monkeypatch):
    from lunarlab import policies
    from lunarlab.storage import sha256_file

    art = tmp_path / "artifact"
    shutil.copytree(ARTIFACT, art)
    rec = json.loads((art / "evaluation.json").read_text(encoding="utf-8"))
    rec["seeds"][0], rec["seeds"][1] = rec["seeds"][1], rec["seeds"][0]  # an evaluation with other seeds
    (art / "evaluation.json").write_text(json.dumps(rec), encoding="utf-8")
    manifest = json.loads((art / "artifact.json").read_text(encoding="utf-8"))
    manifest["files"]["evaluation.json"]["sha256"] = sha256_file(art / "evaluation.json")
    (art / "artifact.json").write_text(json.dumps(manifest), encoding="utf-8")
    r = reproduce_artifact(art, episodes=2, echo=lambda _m: None)
    assert r["status"] == "integrity-failure" and r["exit_code"] == 1
    failed = {c["check"] for c in r["checks"] if not c["ok"] and c["kind"] == "integrity"}
    assert failed == {"the recorded evaluation is the final test on the configuration's test seeds"}

    real = policies.load_policy_weights

    def nudged(*a, **kw):
        net = real(*a, **kw)
        next(net.parameters()).data.view(-1)[0] += 1e-3
        return net

    monkeypatch.setattr(policies, "load_policy_weights", nudged)
    r = reproduce_artifact(ARTIFACT, episodes=1, echo=lambda _m: None)
    assert r["status"] == "integrity-failure"
    assert {c["check"] for c in r["checks"] if not c["ok"]} >= {
        "the evaluated network holds exactly the checkpoint's weights"
    }


@pytest.mark.integration
def test_traces_round_trip_and_locate_the_source_of_a_difference(tmp_path, monkeypatch):
    import gymnasium.envs.box2d.lunar_lander as ll
    import numpy as np

    from lunarlab import divergence
    from lunarlab.cli import main

    out = tmp_path / "trace.npz"
    meta = divergence.record_traces(ARTIFACT, [20_000], out)
    assert out.with_suffix(".json").exists()
    recorded_on = json.loads((ARTIFACT / "artifact.json").read_text(encoding="utf-8"))["exported_with"]
    if compare_platforms(recorded_on, meta["software"])["same_platform"]:
        assert meta["episodes"][0]["matches_recorded_return"]  # a trace replicates the recorded evaluation
    assert main(["trace-artifact", "--artifact", str(ARTIFACT), "--compare", str(out)]) == 0  # identical here

    same = divergence.diagnose(ARTIFACT, out)
    assert (
        same["identical"] and same["episodes"][0]["closed_loop"]["first_observation_difference_step"] is None
    )

    # inference: outputs nudged, greedy actions unchanged
    real_outputs = divergence.policy_outputs
    monkeypatch.setattr(divergence, "policy_outputs", lambda p, o: real_outputs(p, o) + np.float32(1e-3))
    e = divergence.diagnose(ARTIFACT, out)["episodes"][0]
    assert e["source"] == "policy inference" and e["inference"]["first_output_difference_step"] == 0
    assert e["dynamics"]["first_observation_difference_step"] is None
    monkeypatch.setattr(divergence, "policy_outputs", real_outputs)

    # dynamics: the simulator moved by one float32 ulp after reset
    real_reset = ll.LunarLander.reset

    def nudged_reset(self, *, seed=None, options=None):
        result = real_reset(self, seed=seed, options=options)
        v = self.lander.linearVelocity
        self.lander.linearVelocity = (float(np.nextafter(np.float32(v.x), np.float32(np.inf))), v.y)
        return result

    monkeypatch.setattr(ll.LunarLander, "reset", nudged_reset)
    e = divergence.diagnose(ARTIFACT, out)["episodes"][0]
    assert e["source"] == "simulator dynamics" and e["inference"]["first_output_difference_step"] is None
    assert e["dynamics"]["first_observation_difference_step"] >= 1
    monkeypatch.setattr(ll.LunarLander, "reset", real_reset)

    # a trace that does not match its recorded digest is refused
    data = bytearray(out.read_bytes())
    data[-30] ^= 0xFF
    out.write_bytes(bytes(data))
    with pytest.raises(ValueError, match="digest"):
        divergence.load_traces(out)


def test_first_difference_handles_equal_different_and_shorter_arrays():
    import numpy as np

    from lunarlab.divergence import _first_difference

    a = np.arange(12, dtype=np.float32).reshape(6, 2)
    assert _first_difference(a, a.copy()) is None
    b = a.copy()
    b[3, 1] = np.nextafter(b[3, 1], np.float32(100))
    assert _first_difference(a, b) == 3
    assert _first_difference(a, a[:4]) == 4
    assert _first_difference(np.array([0, 1, 2]), np.array([0, 1, 3])) == 2
