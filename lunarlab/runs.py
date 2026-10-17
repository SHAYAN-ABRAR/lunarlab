# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Run creation, metadata, checkpoint manifest and event log."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from lunarlab import sysinfo
from lunarlab.config import (
    DQNConfig,
    EvalProtocol,
    PhysicsRandomization,
    PPOConfig,
    RunConfig,
    TrainingConfig,
    WarmStart,
)
from lunarlab.env import environment_record
from lunarlab.locks import hold
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
    """A run operation that must not proceed (unknown run, frozen run, incompatible checkpoint, …)."""

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
    physics: PhysicsRandomization | None = None,
    warm_start: WarmStart | None = None,
    lineage: dict | None = None,
) -> RunConfig:
    """Create a run directory with its validated configuration and metadata.

    Records the configuration, reward and protocol hashes, the planned budget, the environment and a system snapshot
    (versions, hardware, source revision). An invalid evaluation protocol is refused.
    """
    ppo = ppo or PPOConfig()
    physics = physics or PhysicsRandomization()
    protocol = protocol or EvalProtocol()
    protocol.require_valid()  # a new run never starts with overlapping or duplicate seeds
    tag = reward.preset if reward.preset != "custom" else "custom"
    run_id = new_id(
        *([algo] if algo != "ppo" else []),
        tag,
        *(["rand"] if physics.enabled else []),
        f"s{seed}",
        training.profile,
    )
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
        eval_protocol=protocol,
        algo=algo,
        dqn=dqn,
        physics=physics,
        warm_start=warm_start,
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
        **({"lineage": lineage} if lineage else {}),
    }
    atomic_write_json(paths.metadata, meta)
    atomic_write_json(paths.status, {"run_id": run_id, "state": "created", "updated_at": utc_now()})
    log_event(paths, "info", "run created", config_hash=meta["config_hash"], reward=reward.preset)
    return cfg


def load_config(run_id: str) -> RunConfig:
    """The run's validated configuration (``config.yaml``)."""
    paths = RunPaths(run_id)
    if not paths.config.exists():
        raise RunError(f"unknown run: {run_id}")
    return RunConfig.model_validate(read_yaml(paths.config))


def load_metadata(run_id: str) -> dict:
    """The run's ``metadata.json``."""
    return read_json(RunPaths(run_id).metadata, default={}) or {}


def update_metadata(run_id: str, **updates: Any) -> dict:
    """Merge fields into ``metadata.json`` under the run's metadata lock."""
    return mutate_metadata(run_id, lambda meta: meta.update(updates))


def mutate_metadata(run_id: str, change: Callable[[dict], Any]) -> dict:
    """Read-modify-write ``metadata.json`` under the run's metadata lock (safe across processes)."""
    paths = RunPaths(run_id)
    with hold(paths.metadata_lock):
        meta = read_json(paths.metadata, default={}) or {}
        change(meta)
        atomic_write_json(paths.metadata, meta)
    return meta


def log_event(paths: RunPaths, level: str, message: str, **data: Any) -> None:
    """Append one event to the run's ``events.jsonl``."""
    append_jsonl(paths.events, {"time": utc_now(), "level": level, "message": message, **data})


# --------------------------------------------------------------------------- #
# Checkpoint manifest
# --------------------------------------------------------------------------- #


def read_manifest(paths: RunPaths) -> dict:
    """The run's checkpoint manifest (an empty one before the first checkpoint)."""
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
    """Add a checkpoint file to the manifest with its size, SHA-256, transitions and the caller's extra fields
    (under the metadata lock); a ``best_validation`` entry also becomes the manifest's selected checkpoint.
    """
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

    def add(manifest: dict) -> None:
        manifest["checkpoints"] = [c for c in manifest["checkpoints"] if c["name"] != file.name] + [entry]
        if kind == "best_validation":
            manifest["best_validation"] = entry

    mutate_manifest(paths, add)
    return entry


def mutate_manifest(paths: RunPaths, change: Callable[[dict], Any]) -> dict:
    """Read-modify-write the checkpoint manifest under the run's metadata lock. The manifest is the
    commit point of a checkpoint: an entry appears only after every file it names is complete."""
    with hold(paths.metadata_lock):
        manifest = read_manifest(paths)
        change(manifest)
        atomic_write_json(paths.checkpoint_manifest, manifest)
    return manifest


DQN_CONTINUATION_FORMAT = "lunarlab.dqn-continuation"
PPO_CONTINUATION_FORMAT = "lunarlab.ppo-continuation"


def is_resumable(entry: dict, algo: str) -> bool:
    """Whether a checkpoint can CONTINUE its run (see docs/ARCHITECTURE.md, checkpoint contract).

    PPO: periodic and stop checkpoints (weights, optimizer state, counters; also those written before
    the contract was named). DQN: only checkpoints that carry a complete continuation bundle
    (replay buffer and algorithm state); older DQN checkpoints are inference checkpoints."""
    if entry.get("kind") not in ("periodic", "stop"):
        return False
    if algo == "dqn":
        cont = entry.get("continuation") or {}
        return bool(
            entry.get("resumable") is True
            and cont.get("format") == DQN_CONTINUATION_FORMAT
            and not cont.get("pruned_at")
        )
    return entry.get("resumable", True) is not False


def legacy_dqn_resume_message(run_id: str, name: str) -> str:
    """Why a DQN checkpoint without a continuation bundle cannot be resumed, and what to do instead."""
    return (
        f"checkpoint {name} has no replay buffer or DQN training state (written before LunarLab stored "
        "them, or its continuation files were pruned). It still works for evaluation, recordings and replay, "
        "but resuming from it would restart DQN with an empty replay buffer and reset counters, which is "
        "not a continuation of this run. Use a warm restart instead: a new run initialised from these "
        "weights, with its lineage recorded (python -m lunarlab warm-restart --run-id "
        f"{run_id} --checkpoint {name} --confirm)."
    )


def resolve_resume_checkpoint(run_id: str, which: str, algo: str) -> tuple[Path, dict]:
    """The checkpoint a resume continues from, verified, or a RunError that says what to do instead."""
    entries = read_manifest(RunPaths(run_id)).get("checkpoints", [])
    if which == "latest":
        candidates = [(i, c) for i, c in enumerate(entries) if c["kind"] in ("periodic", "stop")]
        if not candidates:
            raise RunError("no resumable checkpoint (no periodic or stop checkpoint yet)")
        usable = [(i, c) for i, c in candidates if is_resumable(c, algo)]
        newest = max(candidates, key=lambda ic: (ic[1]["transitions"], ic[0]))[1]
        if not usable or (algo == "dqn" and not is_resumable(newest, algo)):
            raise RunError(legacy_dqn_resume_message(run_id, newest["name"]))
        name = max(usable, key=lambda ic: (ic[1]["transitions"], ic[0]))[1]["name"]
    else:
        entry = next((c for c in entries if c["name"] == which), None)
        if entry is None:
            raise RunError(f"checkpoint {which!r} is not in this run's manifest")
        if entry["kind"] == "best_validation":
            raise RunError("resume from a periodic/stop checkpoint, not the validation-selected copy")
        if entry["kind"] == "final":
            raise RunError("run already completed; nothing to resume")
        if not is_resumable(entry, algo):
            raise RunError(legacy_dqn_resume_message(run_id, entry["name"]))
        name = entry["name"]
    path, entry = resolve_checkpoint(run_id, name)
    if algo == "dqn":  # refuse early if the replay/state files are missing or altered
        from lunarlab.continuation import verify_continuation_files

        verify_continuation_files(RunPaths(run_id), entry)
    return path, entry


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
    """Load a run's policy for inference (safe, weights-only).

    ``which="frozen"`` loads the immutable copy frozen for the final test (verified against its digest);
    ``which="final-test"`` does the same, and falls back to the validation-selected checkpoint for a run
    that has not been frozen yet."""
    from lunarlab.env import make_env
    from lunarlab.policies import SB3Policy, load_policy_weights

    cfg = load_config(run_id)
    if which in ("frozen", "final-test"):
        from lunarlab.freeze import resolve_final_checkpoint

        path, entry = resolve_final_checkpoint(run_id, require_frozen=which == "frozen")
    else:
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
