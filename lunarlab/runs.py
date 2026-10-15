"""Run creation, metadata, checkpoint manifest and event log."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lunarlab import sysinfo
from lunarlab.config import (
    DQNConfig,
    EvalProtocol,
    PPOConfig,
    RunConfig,
    TrainingConfig,
)
from lunarlab.env import environment_record
from lunarlab.rewards.config import RewardConfig
from lunarlab.storage import (
    RunPaths,
    append_jsonl,
    atomic_write_json,
    new_id,
    read_json,
    read_yaml,
    sha256_file,
    utc_now,
    write_yaml,
)


class RunError(RuntimeError):
    pass


def create_run(
    *,
    reward: RewardConfig,
    training: TrainingConfig,
    seed: int,
    ppo: PPOConfig | None = None,
    protocol: EvalProtocol | None = None,
    experiment_id: str | None = None,
    label: str = "",
    reward_config_id: str | None = None,
    reward_revision: int | None = None,
    algo: str = "ppo",
    dqn: DQNConfig | None = None,
) -> RunConfig:
    ppo = ppo or PPOConfig()
    tag = reward.preset if reward.preset != "custom" else "custom"
    run_id = new_id(*([algo] if algo != "ppo" else []), tag, f"s{seed}", training.profile)
    cfg = RunConfig(
        run_id=run_id,
        experiment_id=experiment_id,
        label=label,
        created_at=utc_now(),
        reward=reward,
        reward_config_id=reward_config_id,
        reward_revision=reward_revision,
        ppo=ppo,
        training=training,
        seed=seed,
        eval_protocol=protocol or EvalProtocol(),
        algo=algo,
        dqn=dqn,
    )
    paths = RunPaths(run_id)
    if paths.root.exists():
        raise RunError(f"run directory already exists: {run_id}")
    paths.create_dirs()
    write_yaml(paths.config, cfg.model_dump(mode="json"))
    meta = {
        "run_id": run_id,
        "experiment_id": experiment_id,
        "created_at": cfg.created_at,
        "config_hash": cfg.config_hash(),
        "reward_preset": reward.preset,
        "reward_name": reward.name,
        "reward_hash": reward.content_hash(),
        "reward_config_id": reward_config_id,
        "reward_revision": reward_revision,
        "eval_protocol_id": cfg.eval_protocol.protocol_id,
        "eval_protocol_hash": cfg.eval_protocol.protocol_hash(),
        "seed": seed,
        "requested_transitions": training.total_transitions,
        "planned_transitions": cfg.planned_transitions,
        "rollout_size": cfg.rollout_size,
        "algo": algo,
        "environment": environment_record(),
        "system": sysinfo.snapshot(),
        "segments": [],
        "frozen_for_test": None,
        "test_evaluations": 0,
    }
    atomic_write_json(paths.metadata, meta)
    atomic_write_json(paths.status, {"run_id": run_id, "state": "created", "updated_at": utc_now()})
    log_event(paths, "info", "run created", config_hash=meta["config_hash"], reward=reward.preset)
    return cfg


def load_config(run_id: str) -> RunConfig:
    paths = RunPaths(run_id)
    if not paths.config.exists():
        raise RunError(f"unknown run: {run_id}")
    return RunConfig.model_validate(read_yaml(paths.config))


def load_metadata(run_id: str) -> dict:
    return read_json(RunPaths(run_id).metadata, default={}) or {}


def update_metadata(run_id: str, **updates: Any) -> dict:
    paths = RunPaths(run_id)
    meta = read_json(paths.metadata, default={}) or {}
    meta.update(updates)
    atomic_write_json(paths.metadata, meta)
    return meta


def log_event(paths: RunPaths, level: str, message: str, **data: Any) -> None:
    append_jsonl(paths.events, {"time": utc_now(), "level": level, "message": message, **data})


# --------------------------------------------------------------------------- #
# Checkpoint manifest
# --------------------------------------------------------------------------- #


def read_manifest(paths: RunPaths) -> dict:
    return read_json(paths.checkpoint_manifest, default=None) or {"checkpoints": [], "best_validation": None}


def register_checkpoint(
    paths: RunPaths,
    file: Path,
    *,
    kind: str,
    transitions: int,
    updates: int,
    segment: int,
    extra: dict | None = None,
) -> dict:
    manifest = read_manifest(paths)
    entry = {
        "name": file.name,
        "kind": kind,
        "transitions": int(transitions),
        "updates": int(updates),
        "segment": int(segment),
        "created_at": utc_now(),
        "sha256": sha256_file(file),
        "size_bytes": file.stat().st_size,
        **(extra or {}),
    }
    manifest["checkpoints"] = [c for c in manifest["checkpoints"] if c["name"] != file.name] + [entry]
    if kind == "best_validation":
        manifest["best_validation"] = entry
    atomic_write_json(paths.checkpoint_manifest, manifest)
    return entry


def resolve_checkpoint(run_id: str, which: str = "best") -> tuple[Path, dict]:
    """Find a manifest-listed checkpoint and verify its integrity.

    ``which``: ``best`` (validation-selected), ``final``, ``latest``, or a
    checkpoint file name from the manifest.
    """
    paths = RunPaths(run_id)
    manifest = read_manifest(paths)
    entries = manifest.get("checkpoints", [])
    if not entries:
        raise RunError(f"run {run_id} has no checkpoints yet")
    entry: dict | None
    if which == "best":
        entry = manifest.get("best_validation")
        if entry is None:
            raise RunError("no validation-selected checkpoint yet (validation has not run)")
    elif which == "final":
        entry = next((c for c in entries if c["kind"] == "final"), None)
        if entry is None:
            raise RunError("no final checkpoint: the run has not completed")
    elif which == "latest":
        resumable = [(i, c) for i, c in enumerate(entries) if c["kind"] in ("periodic", "final", "stop")]
        if not resumable:
            raise RunError("no resumable checkpoint")
        # Most transitions wins; ties go to the most recently registered entry.
        entry = max(resumable, key=lambda ic: (ic[1]["transitions"], ic[0]))[1]
    else:
        entry = next((c for c in entries if c["name"] == which), None)
        if entry is None:
            raise RunError(f"checkpoint {which!r} is not in this run's manifest")
    path = paths.checkpoints / entry["name"]
    if not path.exists():
        raise RunError(f"checkpoint file is missing: {entry['name']}")
    if path.stat().st_size == 0:
        raise RunError(f"checkpoint file is empty (corrupt): {entry['name']}")
    digest = sha256_file(path)
    if digest != entry["sha256"]:
        raise RunError(
            f"checkpoint {entry['name']} does not match its recorded SHA-256 (corrupt or modified)"
        )
    return path, entry


def load_policy(run_id: str, which: str = "best", *, deterministic: bool = True):
    """Load a run's policy for inference (safe, weights-only)."""
    from lunarlab.env import make_env
    from lunarlab.policies import SB3Policy, load_policy_weights

    cfg = load_config(run_id)
    path, entry = resolve_checkpoint(run_id, which)
    env = make_env()
    try:
        net = load_policy_weights(
            path, cfg.ppo, env.observation_space, env.action_space, algo=cfg.algo, dqn_cfg=cfg.dqn
        )
    finally:
        env.close()
    label = (
        f"{cfg.algo.upper()} · {cfg.reward.name} · seed {cfg.seed} · {entry['name']} "
        f"({entry['transitions']:,} transitions)"
    )
    return SB3Policy(net, deterministic=deterministic, label=label, kind=cfg.algo), entry
