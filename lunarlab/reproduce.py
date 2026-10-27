# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Reproducibility checks that run without the web interface.

* :func:`run_smoke` runs the whole research pipeline at a tiny budget in an isolated, temporary LunarLab
  home -- configuration, training, checkpoints, reload, validation, frozen final test, export -- and
  verifies every provenance link (configuration identity, checkpoint digests, the tested checkpoint, the
  reward accounting identity). It then repeats the final-test evaluation and requires an exact match, and
  can train the same configuration a second time to test training determinism.
* :func:`export_artifact` packages a run's tested checkpoint, configuration and recorded final-test
  evaluation (byte-identical copies plus their SHA-256 digests) so a third party can re-evaluate it.
* :func:`reproduce_artifact` re-evaluates such a package on the recorded seeds and compares every episode
  with the record.

Exactness here means equality of COMPARED_FIELDS, not a bitwise comparison of entire
trajectories. Operating-system and package-version matching is a coarse diagnostic,
not a guarantee of identical hardware or compiled numerical behavior. Across
platforms, floating-point differences can change trajectories; differences are reported.

A reproduction is classified (:data:`STATUSES`) by four separate properties:

* **artifact integrity** -- the files match their digests, and the configuration, seeds, protocol, reward and
  loaded weights are the recorded ones (always blocking when violated);
* **within-platform reproducibility** -- the selected episode-summary fields are expected to match;
* **cross-platform numerical reproducibility** -- elsewhere, per-episode differences are measured and reported;
* **aggregate regression screening** -- no compared aggregate (mean return; pad-landing, timeout, crash and out-of-bounds
  rates) may differ significantly from the record in a paired comparison over the same seeds
  (:func:`compare_aggregates`). Non-rejection does not establish equivalence or preservation of all conclusions.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import json
import math
import os
import shutil
import stat
import tempfile
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from lunarlab.storage import sha256_file, utc_now

SMOKE_PPO = {"n_envs": 2, "n_steps": 256, "batch_size": 64}  # 512 transitions per rollout
SMOKE_PROTOCOL = {
    "validation_seeds": [10_000, 10_001, 10_002],
    "test_seeds": [20_000, 20_001, 20_002, 20_003],
}
# Per-episode fields compared between two evaluations. Present in every outcome-classifier version.
COMPARED_FIELDS = ("length", "original_return", "training_return", "env_outcome", "pad_landing")
# Outcome fields whose meaning does not depend on the outcome-classifier version (``landed_off_pad`` does).
OUTCOME_FIELDS = ("terminated", "truncated", "env_outcome", "pad_landing")
# Relative return differences are reported only where the recorded return is at least this large in magnitude.
RELATIVE_FLOOR = 1.0
# Aggregate rates checked for conclusion stability (besides the mean original return).
CONSISTENCY_RATES = ("pad_landing", "timeout", "crash", "out_of_bounds")
# What bit-identical evaluation depends on: the operating system and the numerical libraries.
NUMERICAL_STACK = ("torch", "numpy", "Box2D", "gymnasium", "stable-baselines3")
ARTIFACT_SCHEMA = 1
REPRODUCTION_SCHEMA = 2
STATUSES: dict[str, dict[str, Any]] = {
    "exact": {
        "blocking": False,
        "exit_code": 0,
        "meaning": "all selected episode-summary fields match exactly",
    },
    "within-tolerance": {
        "blocking": False,
        "exit_code": 0,
        "meaning": "every episode matches the record within the tolerance the caller requested",
    },
    "numerical-difference": {
        "blocking": False,
        "exit_code": 3,
        "meaning": "episodes differ numerically on a different platform; integrity holds and no compared aggregate "
        "differs significantly from the record. Bit-identical results across platforms are not a supported "
        "guarantee, so this is reported, not failed. Equivalence has not been assessed",
    },
    "unexpected-difference": {
        "blocking": True,
        "exit_code": 1,
        "meaning": "episodes differ on the operating system and numerical libraries that recorded them, where "
        "selected episode-summary fields are expected to match",
    },
    "aggregate-disagreement": {
        "blocking": True,
        "exit_code": 1,
        "meaning": "a reproduced aggregate differs significantly from the record in the paired comparison over the "
        "same seeds; investigate its magnitude and cause",
    },
    "integrity-failure": {
        "blocking": True,
        "exit_code": 1,
        "meaning": "the artifact's files, configuration, seeds, protocol, reward or loaded weights do not match "
        "its record",
    },
}


@contextlib.contextmanager
def isolated_home(path: Path) -> Iterator[Path]:
    """Point LUNARLAB_HOME at ``path`` for the duration of the block (restored afterwards)."""
    old = os.environ.get("LUNARLAB_HOME")
    os.environ["LUNARLAB_HOME"] = str(path)
    try:
        yield path
    finally:
        if old is None:
            os.environ.pop("LUNARLAB_HOME", None)
        else:
            os.environ["LUNARLAB_HOME"] = old


def remove_tree(path: Path) -> None:
    """Delete a temporary home, including the read-only frozen checkpoints a final test creates."""

    def _writable_retry(func, p, _exc):
        os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
        func(p)

    shutil.rmtree(path, onexc=_writable_retry)


def episode_key(ep: dict, fields: tuple[str, ...] = COMPARED_FIELDS) -> tuple:
    """The compared fields of one episode (``COMPARED_FIELDS`` unless given), as a tuple."""
    return tuple(ep.get(f) for f in fields)


def _episode_row(
    rec: dict, ep: dict, exact: bool, outcome_fields: tuple[str, ...] = OUTCOME_FIELDS
) -> dict[str, Any]:
    r0, r1 = float(rec["original_return"]), float(ep["original_return"])
    row: dict[str, Any] = {
        "seed": int(ep["seed"]),
        "exact": exact,
        "recorded_return": r0,
        "reproduced_return": r1,
        "abs_return_difference": abs(r1 - r0),
        "relative_return_difference": abs(r1 - r0) / abs(r0) if abs(r0) >= RELATIVE_FLOOR else None,
        "recorded_length": rec.get("length"),
        "reproduced_length": ep.get("length"),
        "length_agrees": rec.get("length") == ep.get("length"),
    }
    present = [f for f in outcome_fields if f in rec and f in ep]
    for f in present:
        row[f] = [rec[f], ep[f]]
    row["outcome_agrees"] = all(rec[f] == ep[f] for f in present)
    a, b = rec.get("final_obs"), ep.get("final_obs")
    if a is not None and b is not None and len(a) == len(b):
        row["final_obs_max_abs_difference"] = max(abs(float(x) - float(y)) for x, y in zip(a, b, strict=True))
    return row


def _fraction(rows: list[dict], agrees: Callable[[dict], bool | None]) -> float | None:
    values = [v for v in (agrees(r) for r in rows) if v is not None]
    return sum(values) / len(values) if values else None


def summarize_episode_rows(rows: list[dict]) -> dict[str, Any]:
    """Agreement fractions and the distribution of per-episode return differences."""
    import numpy as np

    n = len(rows)
    if n == 0:
        return {"n": 0}
    d = np.array([r["abs_return_difference"] for r in rows], dtype=float)
    rel = [r["relative_return_difference"] for r in rows if r["relative_return_difference"] is not None]

    def same(field: str) -> Callable[[dict], bool | None]:
        return lambda r: (r[field][0] == r[field][1]) if field in r else None

    return {
        "n": n,
        "agreement": {
            "bit_identical": sum(r["exact"] for r in rows) / n,
            "length": sum(r["length_agrees"] for r in rows) / n,
            "termination": _fraction(
                rows,
                lambda r: (
                    (r["terminated"][0] == r["terminated"][1] and r["truncated"][0] == r["truncated"][1])
                    if "terminated" in r and "truncated" in r
                    else None
                ),
            ),
            "env_outcome": _fraction(rows, same("env_outcome")),
            "pad_landing": _fraction(rows, same("pad_landing")),
            "all_outcome_fields": sum(r["outcome_agrees"] for r in rows) / n,
        },
        "return_difference": {
            "mean_abs": float(d.mean()),
            "median_abs": float(np.median(d)),
            "p90_abs": float(np.quantile(d, 0.9)),
            "max_abs": float(d.max()),
            "median_relative": float(np.median(rel)) if rel else None,
            "n_relative": len(rel),
            "relative_floor": RELATIVE_FLOOR,
            "episodes_differing": int((d > 0).sum()),
            "episodes_above_1": int((d > 1).sum()),
            "episodes_above_10": int((d > 10).sum()),
        },
    }


def compare_episodes(
    recorded: list[dict],
    reproduced: list[dict],
    *,
    tolerance: float = 0.0,
    fields: tuple[str, ...] = COMPARED_FIELDS,
    outcome_fields: tuple[str, ...] = OUTCOME_FIELDS,
) -> dict[str, Any]:
    """Compare two evaluations seed by seed on ``fields`` (:data:`COMPARED_FIELDS` unless given).

    Returns are compared with ``tolerance`` (absolute; 0 = numeric equality), everything else exactly. Besides the
    counts, every episode gets a row (``episodes``: returns and their difference, length, termination and
    outcome agreement over ``outcome_fields``, final-observation difference) and ``summary`` aggregates them.
    The generic audit study passes its own task-independent fields.
    """
    by_seed = {int(e["seed"]): e for e in recorded}
    exact = within = 0
    max_diff = 0.0
    mismatches = []
    rows = []
    missing = []
    for ep in reproduced:
        rec = by_seed.get(int(ep["seed"]))
        if rec is None:
            mismatches.append({"seed": ep["seed"], "reason": "seed not in the recorded evaluation"})
            missing.append(int(ep["seed"]))
            continue
        is_exact = episode_key(rec, fields) == episode_key(ep, fields)
        rows.append(_episode_row(rec, ep, is_exact, outcome_fields))
        if is_exact:
            exact += 1
            within += 1
            continue
        diffs = {}
        for f in fields:
            a, b = rec.get(f), ep.get(f)
            if isinstance(a, float) and isinstance(b, float):
                d = abs(a - b)
                max_diff = max(max_diff, d)
                if d > tolerance:
                    diffs[f] = [a, b]
            elif a != b:
                diffs[f] = [a, b]
        if diffs:
            mismatches.append({"seed": ep["seed"], "fields": diffs})
        else:
            within += 1
    return {
        "compared_fields": list(fields),
        "exactness_scope": "numeric equality of selected episode-summary fields; not full-trajectory or bitwise identity",
        "compared": len(reproduced),
        "exact": exact,
        "within_tolerance": within,
        "tolerance": tolerance,
        "max_abs_return_difference": max_diff,
        # Retain the legacy mixed-reward maximum above for compatibility, but
        # expose the two reward scales separately for scientific reporting.
        "max_abs_original_return_difference": max((r["abs_return_difference"] for r in rows), default=0.0),
        "max_abs_training_return_difference": max(
            (
                abs(float(ep["training_return"]) - float(by_seed[int(ep["seed"])]["training_return"]))
                for ep in reproduced
                if int(ep["seed"]) in by_seed
            ),
            default=0.0,
        ),
        "mismatches": mismatches[:20],
        "n_mismatches": len(reproduced) - within,
        "missing_seeds": missing,
        "summary": summarize_episode_rows(rows),
        "episodes": rows,
    }


CONSISTENCY_ALPHA = 0.05  # family-wise, Holm-corrected across the compared aggregates
PERMUTATIONS = 10_000


def sign_flip_p_value(differences: list[float], *, permutations: int = PERMUTATIONS, seed: int = 0) -> float:
    """Two-sided paired permutation test of a zero mean difference (random sign flips, fixed seed)."""
    import numpy as np

    d = np.asarray(differences, dtype=float)
    if d.size == 0 or not np.any(d):
        return 1.0
    observed = abs(d.mean())
    signs = np.random.default_rng(seed).choice((-1.0, 1.0), size=(permutations, d.size))
    null = np.abs((signs * d).mean(axis=1))
    return float((np.sum(null >= observed - 1e-12) + 1) / (permutations + 1))


def mcnemar_p_value(gained: int, lost: int) -> float:
    """Exact two-sided McNemar test: ``gained``/``lost`` are the episodes whose outcome flipped each way."""
    n = gained + lost
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(gained, lost) + 1)) / 2**n
    return min(1.0, 2.0 * tail)


def holm(p_values: dict[str, float], alpha: float = CONSISTENCY_ALPHA) -> dict[str, bool]:
    """Holm's step-down procedure: which hypotheses are rejected at family-wise level ``alpha``."""
    ordered = sorted(p_values, key=p_values.get)
    rejected, m = {}, len(ordered)
    still = True
    for i, name in enumerate(ordered):
        still = still and p_values[name] <= alpha / (m - i)
        rejected[name] = still
    return rejected


def compare_aggregates(recorded: list[dict], reproduced: list[dict], protocol) -> dict[str, Any]:
    """Aggregate regression screen, not an equivalence or conclusion-stability certificate.

    A reproduction re-flies the recorded seeds, so the comparison is paired. The mean original return is tested
    with a sign-flip permutation test on the per-seed differences; each outcome rate (pad landing, timeout, crash,
    out of bounds) with an exact McNemar test on the episodes whose outcome flipped. Holm's correction keeps the
    family-wise false-alarm rate at 5 %. Symmetric numerical noise (episodes flipping both ways, differences
    centred on zero) is not flagged; a shift such as a broken policy or environment is. This is a test for
    regressions, not a proof of equivalence. Both sides are also aggregated by :func:`lunarlab.evaluation.aggregate`
    over the same seeds, with the recorded interval for reference.
    """
    from lunarlab.evaluation import aggregate
    from lunarlab.stats import bootstrap_ci_mean

    seeds = {int(e["seed"]) for e in reproduced}
    rec = [e for e in recorded if int(e["seed"]) in seeds]
    by_seed = {int(e["seed"]): e for e in rec}
    pairs = [(by_seed[int(e["seed"])], e) for e in reproduced if int(e["seed"]) in by_seed]
    a0, a1 = aggregate(rec, protocol), aggregate(reproduced, protocol)
    diffs = [float(b["original_return"]) - float(a["original_return"]) for a, b in pairs]
    ci = bootstrap_ci_mean(
        diffs, level=protocol.ci_level, resamples=protocol.bootstrap_resamples, seed=protocol.bootstrap_seed
    )
    metrics: dict[str, dict[str, Any]] = {
        "mean_original_return": {
            "recorded": a0["original_return"]["mean"],
            "reproduced": a1["original_return"]["mean"],
            "recorded_ci": a0["original_return"].get("ci"),
            "paired_mean_difference": sum(diffs) / len(diffs) if diffs else None,
            "paired_difference_ci": ci,
            "test": "sign-flip permutation test of the paired differences",
            "p_value": sign_flip_p_value(diffs, seed=protocol.bootstrap_seed),
        }
    }
    flags = {
        "pad_landing": lambda e: bool(e.get("pad_landing")),
        "timeout": lambda e: e.get("env_outcome") == "timeout",
        "crash": lambda e: e.get("env_outcome") == "crash",
        "out_of_bounds": lambda e: e.get("env_outcome") == "out_of_bounds",
    }
    for name in CONSISTENCY_RATES:
        f = flags[name]
        gained = sum(not f(a) and f(b) for a, b in pairs)
        lost = sum(f(a) and not f(b) for a, b in pairs)
        metrics[f"{name}_rate"] = {
            "recorded": a0[name]["rate"],
            "reproduced": a1[name]["rate"],
            "recorded_ci": a0[name].get("ci"),
            "episodes_gained": gained,
            "episodes_lost": lost,
            "test": "exact McNemar test",
            "p_value": mcnemar_p_value(gained, lost),
        }
    rejected = holm({k: m["p_value"] for k, m in metrics.items()})
    for k, m in metrics.items():
        m["significant"] = rejected[k]
    return {
        "equivalence_assessed": False,
        "interpretation": "Non-rejection of paired difference tests does not establish equivalence. No equivalence margins were specified.",
        "criterion": "no compared aggregate differs significantly in the paired comparison over the same seeds "
        f"(permutation test for the mean return, exact McNemar tests for rates; Holm, family-wise alpha = {CONSISTENCY_ALPHA})",
        "metrics": metrics,
        "paired_return_difference": {
            "mean": sum(diffs) / len(diffs) if diffs else None,
            "ci": ci,
            "ci_contains_zero": bool(ci and ci[0] <= 0.0 <= ci[1]),
        },
        "consistent": not any(rejected.values()),
    }


def platform_key(info: dict | None) -> dict[str, str | None]:
    """The operating system and numerical-library versions of a :func:`lunarlab.sysinfo.version_info` record."""
    info = info or {}
    plat = str(info.get("platform") or "")
    packages = info.get("packages") or {}
    return {"os": plat.split("-", 1)[0] or None, **{p: packages.get(p) for p in NUMERICAL_STACK}}


def compare_platforms(recorded: dict | None, current: dict) -> dict[str, Any]:
    """Whether this machine has the recording platform's operating system and numerical libraries.

    The recorded side is the artifact's ``exported_with`` (for the supplied artifacts, the machine that trained,
    tested and exported them). An unknown recorded platform counts as different.
    """
    k0, k1 = platform_key(recorded), platform_key(current)
    differences = {k: [k0[k], k1[k]] for k in k0 if k0[k] != k1[k]}
    known = all(v is not None for v in k0.values())
    return {
        "basis": "operating system and numerical libraries ("
        + ", ".join(NUMERICAL_STACK)
        + ") of artifact.json "
        "'exported_with' versus this machine",
        "recorded": {
            "platform": (recorded or {}).get("platform"),
            "python": (recorded or {}).get("python"),
            **k0,
        },
        "reproduced": {"platform": current.get("platform"), "python": current.get("python"), **k1},
        "differences": differences,
        "same_platform": known and not differences,
    }


def classify_reproduction(
    *, integrity_ok: bool, comparison: dict, aggregates: dict, platform: dict, tolerance: float = 0.0
) -> tuple[str, str]:
    """The reproduction status (a key of :data:`STATUSES`) and the reason for it."""
    n, exact = comparison["compared"], comparison["exact"]
    if not integrity_ok:
        return "integrity-failure", STATUSES["integrity-failure"]["meaning"]
    if n and exact == n:
        return "exact", f"all {n} episodes match on the selected summary fields"
    if tolerance > 0 and comparison["n_mismatches"] == 0:
        return (
            "within-tolerance",
            f"all {n} episodes match within an absolute return tolerance of {tolerance:g}",
        )
    s = comparison["summary"]
    diff = (
        f"{n - exact} of {n} episodes differ; median |return difference| {s['return_difference']['median_abs']:.3g}, "
        f"largest {s['return_difference']['max_abs']:.3g}; outcomes agree in {s['agreement']['all_outcome_fields']:.0%}"
    )
    if platform["same_platform"]:
        return "unexpected-difference", f"{diff}, on the platform and numerical libraries that recorded them"
    if not aggregates["consistent"]:
        outside = ", ".join(k for k, m in aggregates["metrics"].items() if m["significant"])
        return "aggregate-disagreement", f"{diff}; significant paired differences: {outside}"
    return "numerical-difference", (
        f"{diff}, on a different platform ({', '.join(platform['differences'])} differ); no compared aggregate "
        "differs significantly from the record"
    )


class _Checks:
    def __init__(self, echo: Callable[[str], None]) -> None:
        self.items: list[dict[str, Any]] = []
        self.echo = echo

    def __call__(self, name: str, ok: bool, detail: str = "", *, kind: str = "check") -> bool:
        self.items.append({"check": name, "ok": bool(ok), "detail": detail, "kind": kind})
        self.echo(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))
        return bool(ok)

    @property
    def ok(self) -> bool:
        return all(c["ok"] for c in self.items)

    def ok_of(self, kind: str) -> bool:
        return all(c["ok"] for c in self.items if c["kind"] == kind)


def _verify_manifest(run_id: str, config_hash: str) -> tuple[bool, list[dict]]:
    from lunarlab.runs import read_manifest
    from lunarlab.storage import RunPaths

    paths = RunPaths(run_id)
    entries = []
    ok = True
    for e in read_manifest(paths)["checkpoints"]:
        f = paths.checkpoints / e["name"]
        good = (
            f.exists()
            and f.stat().st_size == e["size_bytes"]
            and sha256_file(f) == e["sha256"]
            and e.get("config_hash") == config_hash
        )
        ok &= good
        entries.append(
            {"name": e["name"], "kind": e["kind"], "transitions": e["transitions"], "sha256": e["sha256"]}
        )
    return ok and bool(entries), entries


def _training_episodes(run_id: str) -> list[dict]:
    from lunarlab.storage import RunPaths

    with RunPaths(run_id).episodes.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _policy_tensors(path: Path) -> dict:
    from stable_baselines3.common.save_util import load_from_zip_file

    _, params, _ = load_from_zip_file(str(path), load_data=False, device="cpu")
    return params["policy"]


def weights_digest(path: Path) -> str:
    """SHA-256 of a checkpoint's policy tensors (names, shapes, dtypes, values).

    Unlike the checkpoint file's digest it ignores zip metadata such as file times, so two trainings can be
    compared across processes and days.
    """
    return tensors_digest(_policy_tensors(path))


def tensors_digest(params: dict) -> str:
    """SHA-256 of named tensors (names, shapes, dtypes, values), as :func:`weights_digest` computes it."""
    h = hashlib.sha256()
    for name in sorted(params):
        t = params[name].detach().cpu().contiguous()
        h.update(f"{name}|{tuple(t.shape)}|{t.dtype}|".encode())
        h.update(t.numpy().tobytes())
    return h.hexdigest()


def episodes_digest(episodes: list[dict]) -> str:
    """SHA-256 of the compared fields of every episode, in seed order (exact float representations)."""
    rows = sorted((int(e["seed"]), *(repr(e.get(f)) for f in COMPARED_FIELDS)) for e in episodes)
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def run_smoke(
    workdir: Path | None = None,
    *,
    transitions: int = 4096,
    seed: int = 0,
    preset_name: str = "potential",
    algo: str = "ppo",
    training_determinism: bool = False,
    keep: bool = False,
    echo: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Run the bounded end-to-end pipeline in an isolated home and return a report (``report["ok"]``)."""
    from lunarlab.config import DQNConfig, EvalProtocol, PPOConfig, TrainingConfig
    from lunarlab.evaluation import evaluate_policy, evaluate_run
    from lunarlab.rewards.config import preset
    from lunarlab.runs import create_run, load_config, load_metadata, load_policy, resolve_checkpoint
    from lunarlab.storage import RunPaths, atomic_write_json
    from lunarlab.sysinfo import hardware, version_info
    from lunarlab.training import EXIT_COMPLETED, train

    t_start = time.perf_counter()
    started_at = utc_now()
    base = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="lunarlab-repro-"))
    home = base / "home"
    home.mkdir(parents=True, exist_ok=False)
    check = _Checks(echo)
    report: dict[str, Any] = {
        "kind": "lunarlab.reproduce-smoke",
        "schema": 1,
        "started_at": started_at,
        "software": version_info(),
        "hardware": hardware(),
        "settings": {
            "transitions": transitions,
            "seed": seed,
            "preset": preset_name,
            "algo": algo,
            "ppo": SMOKE_PPO if algo == "ppo" else None,
            "protocol": SMOKE_PROTOCOL,
        },
    }
    try:
        with isolated_home(home):
            half = max(256, transitions // 2)

            def make_config():
                return create_run(
                    reward=preset(preset_name),
                    training=TrainingConfig(
                        profile="custom",
                        total_transitions=transitions,
                        checkpoint_every=half,
                        validation_every=half,
                    ),
                    seed=seed,
                    ppo=PPOConfig(**SMOKE_PPO),
                    algo=algo,
                    dqn=DQNConfig() if algo == "dqn" else None,
                    protocol=EvalProtocol(**SMOKE_PROTOCOL),
                    label="reproducibility smoke test",
                )

            echo(f"isolated home: {home}")
            cfg = make_config()
            run_id = cfg.run_id
            meta = load_metadata(run_id)
            reloaded = load_config(run_id)
            report.update(
                run_id=run_id,
                config_hash=cfg.config_hash(),
                reward_hash=cfg.reward.content_hash(),
                protocol_hash=cfg.eval_protocol.protocol_hash(),
            )
            check(
                "configuration identity survives a reload",
                reloaded.config_hash() == cfg.config_hash() == meta["config_hash"],
                cfg.config_hash(),
            )
            check(
                "reward configuration recorded",
                meta["reward_hash"] == cfg.reward.content_hash(),
                meta["reward_hash"],
            )
            check(
                "validation and final-test seeds are disjoint and valid",
                not cfg.eval_protocol.problems(),
                f"{len(cfg.eval_protocol.validation_seeds)} validation, {len(cfg.eval_protocol.test_seeds)} test seeds",
            )

            t0 = time.perf_counter()
            code = train(run_id, quiet=True)
            report["training_seconds"] = round(time.perf_counter() - t0, 2)
            meta = load_metadata(run_id)
            seg = meta["segments"][0]
            check("training completed", code == EXIT_COMPLETED, f"exit code {code}")
            check(
                "training budget recorded in environment transitions",
                seg.get("end_transitions") == cfg.planned_transitions == seg.get("env_interactions"),
                f"{seg.get('env_interactions')} transitions (requested {transitions}, planned {cfg.planned_transitions})",
            )
            check(
                "worker seeds and source revision recorded",
                bool(seg.get("worker_seeds")) and seg.get("code") is not None,
                f"worker seeds {seg.get('worker_seeds')}",
            )
            ok, entries = _verify_manifest(run_id, cfg.config_hash())
            report["checkpoints"] = entries
            check(
                "every checkpoint matches its recorded size, SHA-256 and configuration hash",
                ok,
                f"{len(entries)} checkpoints",
            )

            rows = _training_episodes(run_id)
            w = cfg.reward.original_weight
            # episodes.csv stores returns and term returns rounded to 5 decimals, so re-adding them can be off by
            # half a unit in the last place per value (the per-transition identity itself is exact and tested).
            term_cols = [k for k in (rows[0] if rows else {}) if k.startswith("term_")]
            csv_tolerance = (2 + len(term_cols)) * 0.5e-5 + 1e-9
            worst = max(
                (
                    abs(
                        float(r["training_return"])
                        - w * float(r["original_return"])
                        - sum(float(r[k]) for k in r if k.startswith("term_") and r[k] not in ("", None))
                    )
                    for r in rows
                ),
                default=float("nan"),
            )
            shaped = any(abs(float(r["training_return"]) - float(r["original_return"])) > 1e-9 for r in rows)
            check(
                "training episodes record original and shaped returns separately (identity holds)",
                bool(rows) and worst <= csv_tolerance and (shaped or preset_name == "baseline"),
                f"{len(rows)} episodes, largest identity error {worst:.1e} (CSV rounding bound {csv_tolerance:.1e})",
            )

            policy, entry = load_policy(run_id, "best")
            check("validation-selected checkpoint reloads (weights only)", policy is not None, entry["name"])
            val = evaluate_run(run_id, "validation")
            check(
                "validation evaluation uses the original reward and records the shaped return",
                all(e["reward_applied"] is False for e in val["episodes"])
                and all("training_return" in e for e in val["episodes"]),
                f"mean original return {val['aggregate']['original_return']['mean']:.2f}",
            )

            test = evaluate_run(run_id, "test")
            meta = load_metadata(run_id)
            frozen = meta["frozen_for_test"]
            frozen_path = RunPaths(run_id).root / frozen["artifact"]
            best_path, best_entry = resolve_checkpoint(run_id, "best")
            check(
                "final test evaluated the frozen copy of the validation-selected checkpoint",
                test["checkpoint"]["sha256"]
                == frozen["checkpoint_sha256"]
                == sha256_file(frozen_path)
                == best_entry["sha256"],
                frozen["checkpoint_sha256"][:16],
            )
            check(
                "frozen checkpoint is read-only on disk",
                not os.access(frozen_path, os.W_OK),
                frozen["artifact"],
            )
            report["frozen_checkpoint_sha256"] = frozen["checkpoint_sha256"]
            # Content digests that can be compared between separate invocations (file digests include zip times).
            report["final_weights_sha256"] = weights_digest(RunPaths(run_id).checkpoints / "final.zip")
            report["frozen_weights_sha256"] = weights_digest(frozen_path)
            report["final_test_episodes_sha256"] = episodes_digest(test["episodes"])

            repeat_policy, _ = load_policy(run_id, "frozen")
            again = evaluate_policy(
                repeat_policy,
                cfg.eval_protocol.test_seeds,
                protocol=cfg.eval_protocol,
                reward=cfg.reward,
                gamma=cfg.gamma,
            )
            cmp = compare_episodes(test["episodes"], again["episodes"])
            report["repeated_evaluation"] = cmp
            check(
                "a repeated final-test evaluation matches the saved one exactly",
                cmp["exact"] == cmp["compared"] == len(cfg.eval_protocol.test_seeds),
                f"{cmp['exact']}/{cmp['compared']} episodes identical",
            )

            export_dir = base / "export"
            export_dir.mkdir()
            summary = {
                "run_id": run_id,
                "config_hash": cfg.config_hash(),
                "checkpoint_sha256": test["checkpoint"]["sha256"],
                "aggregate": test["aggregate"],
                "episodes": [{k: e.get(k) for k in ("seed", *COMPARED_FIELDS)} for e in test["episodes"]],
            }
            atomic_write_json(export_dir / "final_test_summary.json", summary)
            exported = json.loads((export_dir / "final_test_summary.json").read_text(encoding="utf-8"))
            check(
                "exported results re-read identically",
                exported == json.loads(json.dumps(summary)),
                f"sha256 {sha256_file(export_dir / 'final_test_summary.json')[:16]}",
            )
            report["export_sha256"] = sha256_file(export_dir / "final_test_summary.json")
            report["final_test"] = {
                "mean_original_return": test["aggregate"]["original_return"]["mean"],
                "n_episodes": len(test["episodes"]),
            }

            if training_determinism:
                twin = make_config()
                code2 = train(twin.run_id, quiet=True)
                _, twin_entries = _verify_manifest(twin.run_id, twin.config_hash())
                a = _policy_tensors(RunPaths(run_id).checkpoints / "final.zip")
                b = _policy_tensors(RunPaths(twin.run_id).checkpoints / "final.zip")
                same_weights = a.keys() == b.keys() and all(bool((a[k] == b[k]).all()) for k in a)
                same_episodes = [(r["original_return"], r["length"]) for r in rows] == [
                    (r["original_return"], r["length"]) for r in _training_episodes(twin.run_id)
                ]
                report["training_determinism"] = {
                    "second_run_id": twin.run_id,
                    "same_config_hash": twin.config_hash() == cfg.config_hash(),
                    "identical_final_weights": same_weights,
                    "identical_training_episodes": same_episodes,
                }
                check(
                    "training the same configuration twice gives identical weights and episodes (this machine)",
                    code2 == EXIT_COMPLETED and same_weights and same_episodes,
                    "same process, same software stack; not a cross-platform guarantee",
                )
    finally:
        report["checks"] = check.items
        report["ok"] = check.ok
        report["elapsed_s"] = round(time.perf_counter() - t_start, 2)
        report["workdir"] = str(base) if keep else None
        if not keep:
            with contextlib.suppress(OSError):
                remove_tree(base)
    return report


def _final_test_evaluation(run_id: str, sha: str) -> Path:
    from lunarlab.storage import RunPaths

    candidates = []
    for p in sorted(RunPaths(run_id).evaluations.glob("test-*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        if r.get("split") == "test" and (r.get("checkpoint") or {}).get("sha256") == sha:
            candidates.append((r.get("repeat_index", 0), r.get("created_at", ""), p))
    if not candidates:
        raise FileNotFoundError(f"{run_id}: no final-test evaluation of the frozen checkpoint")
    return sorted(candidates)[0][2]  # the first completed final test


def export_artifact(run_id: str, out: Path) -> dict[str, Any]:
    """Copy a run's tested checkpoint, configuration and first final-test evaluation into ``out``.

    Reads the run without modifying it. ``out/artifact.json`` records the digests of the copies (identical
    to the originals) and the documented metric, so :func:`reproduce_artifact` can verify both.
    """
    from lunarlab.freeze import resolve_final_checkpoint
    from lunarlab.runs import load_config, load_metadata
    from lunarlab.storage import RunPaths, atomic_write_json
    from lunarlab.sysinfo import version_info

    cfg = load_config(run_id)
    meta = load_metadata(run_id)
    if not meta.get("frozen_for_test"):
        raise ValueError(f"{run_id} has no final test; only tested checkpoints are exported")
    ckpt_path, entry = resolve_final_checkpoint(run_id, require_frozen=True)
    sha = sha256_file(ckpt_path)
    eval_path = _final_test_evaluation(run_id, sha)
    recorded = json.loads(eval_path.read_text(encoding="utf-8"))
    # Learned rewards are needed for re-scoring even in original-reward evaluation.
    # Validate before creating an export; never substitute or retrain an old model.
    reward_files: dict[str, Path] = {}
    if cfg.reward.learned.enabled:
        from lunarlab.preferences.model import load_model_file, model_path

        model_dir = model_path(str(cfg.reward.learned.model_id))
        reward_files = {f"reward_model/{name}": model_dir / name for name in ("model.npz", "meta.json")}
        if not all(path.is_file() for path in reward_files.values()):
            raise FileNotFoundError(f"export requires the original reward model and metadata in {model_dir}")
        model_meta = json.loads((model_dir / "meta.json").read_text(encoding="utf-8"))
        if model_meta.get("sha256") != sha256_file(model_dir / "model.npz"):
            raise ValueError("the reward model does not match its metadata SHA-256; refusing to export")
        load_model_file(model_dir / "model.npz", str(cfg.reward.learned.model_id))
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(ckpt_path, out / "checkpoint.zip")
    shutil.copyfile(RunPaths(run_id).config, out / "config.yaml")
    shutil.copyfile(eval_path, out / "evaluation.json")
    agg = recorded["aggregate"]
    manifest = {
        "schema": ARTIFACT_SCHEMA,
        "kind": "lunarlab.artifact",
        "source_run_id": run_id,
        "experiment_id": meta.get("experiment_id"),
        "algo": cfg.algo,
        "reward": {"preset": cfg.reward.preset, "name": cfg.reward.name, "hash": cfg.reward.content_hash()},
        "config_hash": cfg.config_hash(),
        "protocol_hash": cfg.eval_protocol.protocol_hash(),
        "files": {
            "checkpoint.zip": {
                "sha256": sha256_file(out / "checkpoint.zip"),
                "source": f"runs/{run_id}/checkpoints/{ckpt_path.name}",
                "checkpoint_name": entry.get("name"),
                "transitions": entry.get("transitions"),
            },
            "config.yaml": {
                "sha256": sha256_file(out / "config.yaml"),
                "source": f"runs/{run_id}/config.yaml",
            },
            "evaluation.json": {
                "sha256": sha256_file(out / "evaluation.json"),
                "source": f"runs/{run_id}/evaluations/{eval_path.name}",
            },
        },
        "documented_metric": {
            "split": "test",
            "n_episodes": len(recorded["episodes"]),
            "mean_original_return": agg["original_return"]["mean"],
            "pad_landing_rate": agg["pad_landing"]["rate"],
            "timeout_rate": agg["timeout"]["rate"],
            "evaluated_at": recorded.get("created_at"),
            "outcome_classifier_version": agg.get("outcome_classifier_version", 1),
        },
        "exported_at": utc_now(),
        "exported_with": version_info(),
    }
    if manifest["files"]["checkpoint.zip"]["sha256"] != recorded["checkpoint"]["sha256"]:
        raise RuntimeError("the copied checkpoint is not the one the recorded final test evaluated")
    if reward_files:
        model_id = str(cfg.reward.learned.model_id)
        manifest["reward_model"] = {"id": model_id}
        for name, source in reward_files.items():
            target = out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            manifest["files"][name] = {
                "sha256": sha256_file(target),
                "source": f"data/reward_models/{model_id}/{source.name}",
            }
    atomic_write_json(out / "artifact.json", manifest)
    return manifest


def _reward_dependency_ok(artifact_dir: Path, cfg: Any, manifest: dict, check: _Checks) -> bool:
    """Require bundled, digest-checked learned rewards; never use the caller's registry."""
    if not cfg.reward.learned.enabled:
        return True
    from lunarlab.preferences.model import MODEL_ID_RE, load_model_file

    model_id = str(cfg.reward.learned.model_id)
    names = ("reward_model/model.npz", "reward_model/meta.json")
    ok = bool(MODEL_ID_RE.fullmatch(model_id)) and (manifest.get("reward_model") or {}).get("id") == model_id
    ok = ok and all(
        name in manifest["files"]
        and (artifact_dir / name).is_file()
        and sha256_file(artifact_dir / name) == manifest["files"][name]["sha256"]
        for name in names
    )
    try:
        if ok:
            meta = json.loads((artifact_dir / names[1]).read_text(encoding="utf-8"))
            ok = meta.get("sha256") == sha256_file(artifact_dir / names[0])
            if ok:
                load_model_file(artifact_dir / names[0], model_id)
    except (OSError, ValueError, KeyError, TypeError):
        ok = False
    check(
        "the learned reward model is bundled and matches its identity and digests",
        ok,
        model_id if ok else f"re-export with the original model.npz and meta.json for {model_id}",
        kind="integrity",
    )
    return ok


@contextlib.contextmanager
def _artifact_reward_home(artifact_dir: Path, cfg: Any) -> Iterator[None]:
    """Evaluate learned rewards from the package in a disposable registry (CLI use)."""
    if not cfg.reward.learned.enabled:
        yield
        return
    from lunarlab.preferences.model import load_reward_model

    with tempfile.TemporaryDirectory(prefix="lunarlab-artifact-") as temporary:
        home = Path(temporary)
        target = home / "data" / "reward_models" / str(cfg.reward.learned.model_id)
        target.mkdir(parents=True)
        for name in ("model.npz", "meta.json"):
            shutil.copyfile(artifact_dir / "reward_model" / name, target / name)
        # Registry cache keys omit the home; clear both boundaries to avoid a
        # cached local model masking a missing or incorrect artifact dependency.
        load_reward_model.cache_clear()
        try:
            with isolated_home(home):
                yield
        finally:
            load_reward_model.cache_clear()


def reproduce_artifact(
    artifact_dir: Path,
    *,
    episodes: int | None = None,
    tolerance: float = 0.0,
    echo: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Verify an exported artifact and re-evaluate its checkpoint on the recorded final-test seeds.

    The report's ``status`` (see :data:`STATUSES`) separates integrity failures, bit-identical reproduction,
    cross-platform numerical differences and aggregate disagreement; ``exit_code`` is what the command returns.
    """
    from lunarlab.config import RunConfig
    from lunarlab.env import make_env
    from lunarlab.evaluation import evaluate_policy
    from lunarlab.policies import SB3Policy, load_policy_weights
    from lunarlab.storage import read_yaml
    from lunarlab.sysinfo import hardware, version_info

    artifact_dir = Path(artifact_dir)
    manifest = json.loads((artifact_dir / "artifact.json").read_text(encoding="utf-8"))
    check = _Checks(echo)
    for name, info in manifest["files"].items():
        path = artifact_dir / name
        actual = sha256_file(path) if path.is_file() else "missing"
        check(f"{name} matches its recorded SHA-256", actual == info["sha256"], actual[:16], kind="integrity")
    cfg = RunConfig.model_validate(read_yaml(artifact_dir / "config.yaml"))
    if not _reward_dependency_ok(artifact_dir, cfg, manifest, check):
        software = version_info()
        reason = (
            "required learned-reward dependency is absent, inconsistent or corrupt; evaluation was not run"
        )
        echo(f"  status: integrity-failure (blocking): {reason}")
        return {
            "kind": "lunarlab.reproduce-artifact",
            "schema": REPRODUCTION_SCHEMA,
            "artifact": manifest["source_run_id"],
            "reproduced_at": utc_now(),
            "status": "integrity-failure",
            "status_reason": reason,
            "status_meaning": STATUSES["integrity-failure"]["meaning"],
            "blocking": True,
            "exit_code": 1,
            "integrity_ok": False,
            "ok": False,
            "evaluation_skipped": True,
            "episodes": 0,
            "comparison": None,
            "aggregates": None,
            "software": software,
            "hardware": hardware(),
            "platform": compare_platforms(manifest.get("exported_with"), software),
            "checks": check.items,
        }
    check(
        "configuration hash matches the record",
        cfg.config_hash() == manifest["config_hash"],
        cfg.config_hash(),
        kind="integrity",
    )
    recorded = json.loads((artifact_dir / "evaluation.json").read_text(encoding="utf-8"))
    check(
        "the recorded evaluation used this checkpoint",
        recorded["checkpoint"]["sha256"] == manifest["files"]["checkpoint.zip"]["sha256"],
        kind="integrity",
    )
    check(
        "the recorded evaluation is the final test on the configuration's test seeds",
        recorded.get("split") == "test" and list(recorded["seeds"]) == list(cfg.eval_protocol.test_seeds),
        f"{len(recorded['seeds'])} seeds",
        kind="integrity",
    )
    check(
        "the recorded evaluation used the configuration's protocol and reward",
        recorded.get("protocol_hash") == cfg.eval_protocol.protocol_hash() == manifest["protocol_hash"]
        and recorded.get("reward_hash") == cfg.reward.content_hash() == manifest["reward"]["hash"],
        kind="integrity",
    )
    check(
        "the recorded episodes are exactly the recorded seeds",
        sorted(int(e["seed"]) for e in recorded["episodes"]) == sorted(int(s) for s in recorded["seeds"]),
        kind="integrity",
    )
    seeds = list(recorded["seeds"])[: episodes or None]
    env = make_env()
    try:
        net = load_policy_weights(
            artifact_dir / "checkpoint.zip",
            cfg.ppo,
            env.observation_space,
            env.action_space,
            algo=cfg.algo,
            dqn_cfg=cfg.dqn,
        )
    finally:
        env.close()
    check(
        "the evaluated network holds exactly the checkpoint's weights",
        tensors_digest(net.state_dict()) == weights_digest(artifact_dir / "checkpoint.zip"),
        kind="integrity",
    )
    policy = SB3Policy(net, deterministic=bool(recorded.get("deterministic", True)), kind=cfg.algo)
    t0 = time.perf_counter()
    with _artifact_reward_home(artifact_dir, cfg):
        res = evaluate_policy(policy, seeds, protocol=cfg.eval_protocol, reward=cfg.reward, gamma=cfg.gamma)
    cmp = compare_episodes(recorded["episodes"], res["episodes"], tolerance=tolerance)
    rec_eps = [e for e in recorded["episodes"] if int(e["seed"]) in set(seeds)]
    recorded_mean = sum(e["original_return"] for e in rec_eps) / len(rec_eps)
    reproduced_mean = sum(e["original_return"] for e in res["episodes"]) / len(res["episodes"])
    exact = tolerance == 0.0
    check(
        "every re-evaluated episode matches the record" + (" exactly" if exact else f" within {tolerance:g}"),
        cmp["n_mismatches"] == 0,
        f"{cmp['within_tolerance']}/{cmp['compared']} episode summaries; largest original-return difference "
        f"{cmp['max_abs_original_return_difference']:.3g}; largest training-return difference "
        f"{cmp['max_abs_training_return_difference']:.3g}",
        kind="reproduction",
    )
    aggregates = compare_aggregates(recorded["episodes"], res["episodes"], cfg.eval_protocol)
    check(
        "no aggregate differs significantly from the record (paired tests, Holm-corrected)",
        aggregates["consistent"],
        ", ".join(
            f"{k} {m['recorded']:.4g} -> {m['reproduced']:.4g} (p {m['p_value']:.2g})"
            for k, m in aggregates["metrics"].items()
        ),
        kind="conclusion",
    )
    software = version_info()
    platform = compare_platforms(manifest.get("exported_with"), software)
    status, reason = classify_reproduction(
        integrity_ok=check.ok_of("integrity") and not cmp["missing_seeds"],
        comparison=cmp,
        aggregates=aggregates,
        platform=platform,
        tolerance=tolerance,
    )
    echo(f"  status: {status} ({'blocking' if STATUSES[status]['blocking'] else 'not blocking'}): {reason}")
    return {
        "kind": "lunarlab.reproduce-artifact",
        "schema": REPRODUCTION_SCHEMA,
        "artifact": manifest["source_run_id"],
        "reproduced_at": utc_now(),
        "status": status,
        "status_reason": reason,
        "status_meaning": STATUSES[status]["meaning"],
        "blocking": STATUSES[status]["blocking"],
        "exit_code": STATUSES[status]["exit_code"],
        "integrity_ok": check.ok_of("integrity"),
        "software": software,
        "hardware": hardware(),
        "platform": platform,
        "episodes": len(seeds),
        "recorded_mean_original_return": recorded_mean,
        "reproduced_mean_original_return": reproduced_mean,
        "recorded_pad_landing_rate": sum(bool(e["pad_landing"]) for e in rec_eps) / len(rec_eps),
        "reproduced_pad_landing_rate": res["aggregate"]["pad_landing"]["rate"],
        "comparison": cmp,
        "aggregates": aggregates,
        "elapsed_s": round(time.perf_counter() - t0, 2),
        "checks": check.items,
        "ok": status in ("exact", "within-tolerance"),
    }
