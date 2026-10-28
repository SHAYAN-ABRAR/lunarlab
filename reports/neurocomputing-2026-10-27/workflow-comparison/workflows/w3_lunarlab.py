# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""W3: LunarLab's public interfaces applied to a neutral audit case.

    python w3_lunarlab.py CASE_DIR

This program maps the neutral case onto LunarLab. The checks themselves are LunarLab functions:
``check_file_digests``, ``seed_split_problems``, the ``cartpole`` adapter's terms (which refuse non-finite
parameters) and its outcome schema, ``check_recorded_episodes``, ``check_trajectory``, ``audit_policy``,
``compare_episodes``, ``compare_generic_aggregates``, ``compare_platforms`` and ``classify_reproduction``.
Checks S1-S9 run before the policy is executed. Prints one JSON object on stdout. Exit status: 0 accepted,
3 permitted numerical difference, 1 rejected.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import psutil

from lunarlab.audit import AuditInputError, audit_policy, get_adapter, seed_split_problems
from lunarlab.audit import study as st
from lunarlab.reproduce import classify_reproduction, compare_episodes, compare_platforms
from lunarlab.sysinfo import version_info


def peak_rss() -> int:
    info = psutil.Process().memory_info()
    return int(getattr(info, "peak_wset", 0) or getattr(info, "rss", 0))


def main() -> int:
    t0 = time.perf_counter()
    import torch

    torch.set_num_threads(1)
    case_dir = Path(sys.argv[1])
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    checks: dict[str, dict] = {}

    def put(key: str, results: list[tuple[str, bool, str]] | None, detail: str = "") -> None:
        if results is None:
            checks[key] = {"status": "not-run", "detail": detail}
            return
        failed = [f"{name}: {why}" if why else name for name, ok, why in results if not ok]
        checks[key] = {"status": "fail" if failed else "pass", "detail": "; ".join(failed)[:300] or detail}

    adapter = get_adapter("cartpole")
    gamma, weight = case["gamma"], case["reward"]["original_weight"]
    test_seeds, validation = case["protocol"]["test_seeds"], case["protocol"]["validation_seeds"]
    put(
        "S1",
        st.check_file_digests(
            case_dir, {case["policy"]["file"]: case["policy"]["sha256_recorded_at_selection"]}
        ),
    )
    put("S2", st.check_file_digests(case_dir, case["files"]))
    data = {n: st.load_json(case_dir / n) for n in case["files"] if (case_dir / n).is_file()}
    evaluation = data.get("evaluation.json")
    if evaluation is None:
        put("S3", None, "no recorded evaluation")
    else:
        recorded_env = evaluation.get("environment") == {
            "id": case["environment"]["id"],
            "kwargs": case["environment"]["kwargs"],
        }
        episode_seeds = [e.get("seed") for e in evaluation.get("episodes", [])]
        put(
            "S3",
            [
                ("recorded environment is the case's", recorded_env, ""),
                ("recorded gamma is the case's", evaluation.get("gamma") == gamma, ""),
                (
                    "recorded seeds are the case's test seeds",
                    evaluation.get("seeds") == test_seeds == episode_seeds,
                    "",
                ),
            ],
        )
    put("S4", [(p, False, "") for p in seed_split_problems(validation, test_seeds)])
    terms = None
    params = data.get("reward_parameters.json")
    if params is None:
        put("S5", None, "reward parameters unavailable")
    else:
        try:
            term = adapter.term("upright_potential", gamma=gamma, alpha=params["upright_potential"]["alpha"])
            terms = {term.name: term}
            st.definition_document(terms, weight)
            put("S5", [])
        except (AuditInputError, ValueError, KeyError) as exc:
            put("S5", [("reward parameters are finite", False, str(exc))])
    if evaluation is None:
        put("S6", None, "recorded evaluation unavailable")
        put("S7", None)
        episode_checks = []
    else:
        episode_checks = st.check_recorded_episodes(
            evaluation["episodes"],
            expected_seeds=list(test_seeds),
            term_names=sorted(t["name"] for t in case["reward"]["terms"]),
            original_weight=weight,
            categories=adapter.outcome_categories,
        )
        by_topic = {"channels": [], "identity": [], "outcomes": []}
        for name, ok, why in episode_checks:
            topic = (
                "identity"
                if name.startswith("training return")
                else "outcomes"
                if "categories" in name
                else "channels"
            )
            by_topic[topic].append((name, ok, why))
        put("S6", [c for c in by_topic["channels"] if "test seeds" not in c[0]])
        if any(why.startswith("not checked") for _, ok, why in by_topic["identity"] if not ok):
            put("S7", None, "not checked: the reward channels are incomplete")
        else:
            put("S7", by_topic["identity"])
    trajectory = data.get("trajectory.json")
    if trajectory is None or terms is None:
        put("S8", None, "trajectory or reward definition unavailable")
    else:
        put("S8", st.check_trajectory(trajectory, terms, gamma=gamma, original_weight=weight))
    schema = case["outcome_schema"]
    schema_ok = (
        schema.get("name") == adapter.name
        and schema.get("version") == adapter.version
        and list(schema.get("categories", [])) == list(adapter.outcome_categories)
    )
    outcome_checks = [c for c in episode_checks if "categories" in c[0]] if evaluation is not None else []
    put("S9", [("outcome schema is the adapter's", schema_ok, ""), *outcome_checks])
    result = {"workflow": "W3", "case": case.get("case"), "checks": checks, "episodes_executed": 0}
    if any(c["status"] != "pass" for c in checks.values()):
        checks["S10"] = {"status": "not-run", "detail": "an integrity check failed"}
        result.update(verdict="rejected-before-execution", execution_started_before_failure=False)
        code = 1
    else:
        from stable_baselines3 import PPO

        model = PPO.load(case_dir / case["policy"]["file"], device="cpu")
        report = audit_policy(
            adapter, st.policy_fn(model), list(test_seeds), gamma=gamma, terms=terms, original_weight=weight
        )
        recorded = evaluation["episodes"]
        comparison = compare_episodes(
            recorded, report["episodes"], fields=st.COMPARED_FIELDS, outcome_fields=st.OUTCOME_FIELDS
        )
        aggregates = st.compare_generic_aggregates(
            recorded, report["episodes"], case["outcome_schema"]["success"]
        )
        platform_cmp = compare_platforms(case.get("recorded_platform"), version_info())
        status, reason = classify_reproduction(
            integrity_ok=True, comparison=comparison, aggregates=aggregates, platform=platform_cmp
        )
        code = {"exact": 0, "numerical-difference": 3}.get(status, 1)
        verdict = {0: "accepted", 3: "accepted-numerical-difference"}.get(code, "rejected-after-execution")
        checks["S10"] = {
            "status": "pass" if code in (0, 3) else "fail",
            "detail": f"{status}: {reason}"[:300],
        }
        result.update(
            verdict=verdict,
            replay_status=status,
            episodes_executed=report["aggregate"]["n_episodes"],
            execution_started_before_failure=code == 1,
            mean_original_return=report["aggregate"]["mean_original_return"],
            completion_rate=report["aggregate"]["metrics"]["time_limit_rate"],
        )
    result.update(seconds=time.perf_counter() - t0, peak_rss_bytes_self=peak_rss())
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    sys.exit(main())
