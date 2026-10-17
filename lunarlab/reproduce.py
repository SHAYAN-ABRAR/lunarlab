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

Exactness. For a fixed checkpoint, seed list, environment version and software stack the evaluation is
deterministic, so a repeat on the same machine must match bit for bit. Across operating systems, CPUs or
PyTorch/Box2D builds, floating-point differences can change a trajectory; such reproductions are reported
episode by episode (with the largest difference) instead of being assumed exact.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import json
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
ARTIFACT_SCHEMA = 1


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


def episode_key(ep: dict) -> tuple:
    """The compared fields of one episode (``COMPARED_FIELDS``), as a tuple."""
    return tuple(ep.get(f) for f in COMPARED_FIELDS)


def compare_episodes(
    recorded: list[dict], reproduced: list[dict], *, tolerance: float = 0.0
) -> dict[str, Any]:
    """Compare two evaluations seed by seed on :data:`COMPARED_FIELDS`.

    Returns are compared with ``tolerance`` (absolute; 0 = bit-identical), everything else exactly.
    """
    by_seed = {int(e["seed"]): e for e in recorded}
    exact = within = 0
    max_diff = 0.0
    mismatches = []
    for ep in reproduced:
        rec = by_seed.get(int(ep["seed"]))
        if rec is None:
            mismatches.append({"seed": ep["seed"], "reason": "seed not in the recorded evaluation"})
            continue
        if episode_key(rec) == episode_key(ep):
            exact += 1
            within += 1
            continue
        diffs = {}
        for f in COMPARED_FIELDS:
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
        "compared": len(reproduced),
        "exact": exact,
        "within_tolerance": within,
        "tolerance": tolerance,
        "max_abs_return_difference": max_diff,
        "mismatches": mismatches[:20],
        "n_mismatches": len(reproduced) - within,
    }


class _Checks:
    def __init__(self, echo: Callable[[str], None]) -> None:
        self.items: list[dict[str, Any]] = []
        self.echo = echo

    def __call__(self, name: str, ok: bool, detail: str = "") -> bool:
        self.items.append({"check": name, "ok": bool(ok), "detail": detail})
        self.echo(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))
        return bool(ok)

    @property
    def ok(self) -> bool:
        return all(c["ok"] for c in self.items)


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
    h = hashlib.sha256()
    params = _policy_tensors(path)
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
    atomic_write_json(out / "artifact.json", manifest)
    return manifest


def reproduce_artifact(
    artifact_dir: Path,
    *,
    episodes: int | None = None,
    tolerance: float = 0.0,
    echo: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Verify an exported artifact and re-evaluate its checkpoint on the recorded final-test seeds."""
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
        actual = sha256_file(artifact_dir / name)
        check(f"{name} matches its recorded SHA-256", actual == info["sha256"], actual[:16])
    cfg = RunConfig.model_validate(read_yaml(artifact_dir / "config.yaml"))
    check(
        "configuration hash matches the record",
        cfg.config_hash() == manifest["config_hash"],
        cfg.config_hash(),
    )
    recorded = json.loads((artifact_dir / "evaluation.json").read_text(encoding="utf-8"))
    check(
        "the recorded evaluation used this checkpoint",
        recorded["checkpoint"]["sha256"] == manifest["files"]["checkpoint.zip"]["sha256"],
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
    policy = SB3Policy(net, deterministic=bool(recorded.get("deterministic", True)), kind=cfg.algo)
    t0 = time.perf_counter()
    res = evaluate_policy(policy, seeds, protocol=cfg.eval_protocol, reward=cfg.reward, gamma=cfg.gamma)
    cmp = compare_episodes(recorded["episodes"], res["episodes"], tolerance=tolerance)
    rec_eps = [e for e in recorded["episodes"] if int(e["seed"]) in set(seeds)]
    recorded_mean = sum(e["original_return"] for e in rec_eps) / len(rec_eps)
    reproduced_mean = sum(e["original_return"] for e in res["episodes"]) / len(res["episodes"])
    exact = tolerance == 0.0
    check(
        "every re-evaluated episode matches the record" + (" exactly" if exact else f" within {tolerance:g}"),
        cmp["n_mismatches"] == 0,
        f"{cmp['within_tolerance']}/{cmp['compared']} episodes; largest return difference {cmp['max_abs_return_difference']:.3g}",
    )
    return {
        "kind": "lunarlab.reproduce-artifact",
        "schema": 1,
        "artifact": manifest["source_run_id"],
        "reproduced_at": utc_now(),
        "software": version_info(),
        "hardware": hardware(),
        "episodes": len(seeds),
        "recorded_mean_original_return": recorded_mean,
        "reproduced_mean_original_return": reproduced_mean,
        "recorded_pad_landing_rate": sum(bool(e["pad_landing"]) for e in rec_eps) / len(rec_eps),
        "reproduced_pad_landing_rate": res["aggregate"]["pad_landing"]["rate"],
        "comparison": cmp,
        "elapsed_s": round(time.perf_counter() - t0, 2),
        "checks": check.items,
        "ok": check.ok,
    }
