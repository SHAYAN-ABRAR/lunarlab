# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""PPO training: checkpoints, validation-based selection, cooperative stop, resume.

Budgets are counted in **environment transitions** (``model.num_timesteps``,
which SB3 increments by ``n_envs`` per vector step), never in vector-step calls.
PPO completes whole rollouts, so the actual budget is rounded up to a multiple
of ``n_envs * n_steps`` and recorded.

Stopping is cooperative. The supervisor (or Ctrl+C in a terminal) creates
``control/stop_requested.json``; the callback notices within ~0.25 s. The safe
boundary is the start of a rollout, right after the previous update:

* PPO stops at once; the partially collected rollout is discarded (never trained
  on), counters roll back to the last update, and the discarded environment
  interactions are recorded in the segment (``discarded_interactions``).
* DQN stores every transition in its replay buffer as it goes and trains after
  each rollout of ``train_freq`` steps, so it keeps collecting until the current
  rollout is complete and trained on, and stops at the first step of the next
  one: that single step (one interaction per environment) is neither stored nor
  trained on, and is recorded as discarded.

Checkpoints are written as bundles (``save_model_atomic``): every file goes to a
temporary name, is validated, moved into place under a name the manifest does
not yet reference, and only then is the manifest entry published, which is the
commit point. A failed or interrupted save leaves the previous checkpoints valid.
Periodic and stop checkpoints are resumable (DQN ones carry the replay buffer and
algorithm state, see ``lunarlab.continuation``); validation-selected and final
checkpoints are inference checkpoints.
"""

from __future__ import annotations

import collections
import contextlib
import functools
import os
import secrets
import shutil
import signal
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import psutil

from lunarlab.config import RunConfig
from lunarlab.locks import FileLock, LockBusy
from lunarlab.physics import PHYSICS_FIELDS
from lunarlab.rewards.config import TERM_KEYS
from lunarlab.runs import (
    DQN_CONTINUATION_FORMAT,
    PPO_CONTINUATION_FORMAT,
    RunError,
    load_config,
    load_metadata,
    log_event,
    read_manifest,
    register_checkpoint,
    resolve_resume_checkpoint,
    update_metadata,
)
from lunarlab.storage import (
    CsvAppender,
    RunPaths,
    append_jsonl,
    atomic_write_json,
    read_json,
    replace_file,
    sha256_file,
    utc_now,
)

EPISODE_FIELDS = [
    "episode",
    "segment",
    "env_index",
    "transitions",
    "wall_time_s",
    "original_return",
    "training_return",
    "length",
    "env_outcome",
    "pad_landing",
    "body_contact",
    *[f"term_{k}" for k in TERM_KEYS],
    "hover_steps",
    "longest_hover_streak",
    "bonus_eligible_steps",
    "a_noop",
    "a_left",
    "a_main",
    "a_right",
]
DQN_DIAG_EVERY = 10_000  # DQN updates every few steps; log its diagnostics every 10k transitions
PPO_DIAGNOSTIC_KEYS = (
    "train/approx_kl",
    "train/clip_fraction",
    "train/entropy_loss",
    "train/policy_gradient_loss",
    "train/value_loss",
    "train/explained_variance",
    "train/learning_rate",
    "train/clip_range",
    "train/loss",
    "rollout/exploration_rate",
)

EXIT_COMPLETED, EXIT_FAILED, EXIT_BUSY, EXIT_STOPPED, EXIT_INTERRUPTED = 0, 1, 2, 3, 4
REPLACE_TIMEOUT_S = 60.0  # how long a locked destination file is retried before using a unique name
KEEP_CONTINUATIONS = 2  # DQN replay/state files kept for the most recent resumable checkpoints
PPO_CONTRACT = (
    "policy and value networks, optimizer state, transition and update counters; a partial rollout at "
    "a stop is discarded and recorded; environments restart from new episodes; random-number streams "
    "are not restored, so a resumed run is not bit-identical to an uninterrupted one"
)
DQN_CONTRACT = (
    "online and target Q-networks, optimizer state, replay buffer (with position and wrap state), "
    "transition, update and target-update counters, exploration rate and schedule basis; "
    "environments restart from new episodes; random-number streams are not restored, so a resumed run "
    "is not bit-identical to an uninterrupted one"
)


# --------------------------------------------------------------------------- #
# Environment factory (top-level + partial => picklable for SubprocVecEnv/spawn)
# --------------------------------------------------------------------------- #


def _build_training_env(
    reward_json: dict, gamma: float, detector_json: dict, pad_json: dict, physics_json: dict | None = None
):
    from stable_baselines3.common.monitor import Monitor

    from lunarlab.config import PhysicsRandomization
    from lunarlab.env import make_env
    from lunarlab.hover import HoverThresholds
    from lunarlab.outcomes import PadLandingCriteria
    from lunarlab.physics import PhysicsRandomizer
    from lunarlab.rewards.config import RewardConfig
    from lunarlab.rewards.wrapper import LunarLabRewardWrapper

    env = make_env(render_mode=None)
    physics = PhysicsRandomization.model_validate(physics_json or {})
    if physics.enabled:  # per-episode wind / turbulence / gravity, below the reward wrapper
        env = PhysicsRandomizer(env, physics)
    env = LunarLabRewardWrapper(
        env,
        RewardConfig.model_validate(reward_json),
        gamma,
        apply=True,
        detector=HoverThresholds.model_validate(detector_json),
        pad_criteria=PadLandingCriteria.model_validate(pad_json),
    )
    # Monitor is outermost: its episode "r" is the TRAINING (shaped) return.
    return Monitor(env)


def build_vec_env(cfg: RunConfig, kind: str | None = None):
    """The run's vectorised training environments: ``n_envs`` copies of LunarLander (with the optional physics
    randomiser) under ``LunarLabRewardWrapper(apply=True)`` and ``Monitor``, in a DummyVecEnv or a SubprocVecEnv.
    """
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

    fn = functools.partial(
        _build_training_env,
        cfg.reward.model_dump(mode="json"),
        cfg.gamma,
        cfg.eval_protocol.hover_detector.model_dump(mode="json"),
        cfg.eval_protocol.pad_landing.model_dump(mode="json"),
        cfg.physics.model_dump(mode="json"),
    )
    fns = [fn for _ in range(cfg.n_envs)]
    if (kind or cfg.training.vec_env) == "subproc":
        return SubprocVecEnv(fns, start_method="spawn")
    return DummyVecEnv(fns)


def build_model(cfg: RunConfig, venv, device: str):
    """SB3's own ``PPO`` or ``DQN`` with the run's hyperparameters, network and seed (LunarLab adds no learning code)."""
    import torch.nn as nn
    from stable_baselines3 import DQN, PPO

    if cfg.algo == "dqn":
        d = cfg.dqn
        return DQN(
            "MlpPolicy",
            venv,
            learning_rate=d.learning_rate,
            batch_size=d.batch_size,
            buffer_size=d.buffer_size,
            learning_starts=d.learning_starts,
            gamma=d.gamma,
            target_update_interval=d.target_update_interval,
            train_freq=d.train_freq,
            gradient_steps=d.gradient_steps,
            exploration_fraction=d.exploration_fraction,
            exploration_final_eps=d.exploration_final_eps,
            policy_kwargs={"net_arch": list(d.net_arch)},
            seed=cfg.seed,
            device=device,
            verbose=0,
        )
    p = cfg.ppo
    return PPO(
        "MlpPolicy",
        venv,
        learning_rate=p.learning_rate,
        n_steps=p.n_steps,
        batch_size=p.batch_size,
        n_epochs=p.n_epochs,
        gamma=p.gamma,
        gae_lambda=p.gae_lambda,
        clip_range=p.clip_range,
        ent_coef=p.ent_coef,
        vf_coef=p.vf_coef,
        max_grad_norm=p.max_grad_norm,
        policy_kwargs={
            "net_arch": {"pi": list(p.net_arch_pi), "vf": list(p.net_arch_vf)},
            "activation_fn": {"tanh": nn.Tanh, "relu": nn.ReLU}[p.activation],
        },
        seed=cfg.seed,
        device=device,
        verbose=0,
    )


def resolve_device(requested: str) -> str:
    """``cpu``, or ``cuda`` when requested (``cuda``/``auto``) and available; requesting ``cuda`` without it is an error."""
    if requested == "cpu":
        return "cpu"
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if requested == "cuda":
        raise RunError("device 'cuda' requested but torch.cuda.is_available() is False (CPU torch build?)")
    return "cpu"


# --------------------------------------------------------------------------- #
# Callback
# --------------------------------------------------------------------------- #


@dataclass
class TrainingContext:
    cfg: RunConfig
    paths: RunPaths
    segment: int
    job_id: str | None
    started_at: str
    target: int
    # Called after every validation with (transitions, mean original return); returning True asks the
    # run to stop at the next safe boundary (used by tuning to prune or cancel a trial).
    on_validation: Callable[[int, float], bool] | None = None


def _flatten_episode(
    ep: dict, *, episode: int, segment: int, env_index: int, transitions: int, wall: float
) -> dict:
    row = {
        "episode": episode,
        "segment": segment,
        "env_index": env_index,
        "transitions": transitions,
        "wall_time_s": round(wall, 3),
        "original_return": round(ep["original_return"], 5),
        "training_return": round(ep["training_return"], 5),
        "length": ep["length"],
        "env_outcome": ep.get("env_outcome", "unknown"),
        "pad_landing": int(bool(ep.get("pad_landing"))),
        "body_contact": int(bool(ep.get("body_contact"))),
        "hover_steps": ep["hover_steps"],
        "longest_hover_streak": ep["longest_hover_streak"],
        "bonus_eligible_steps": ep["bonus_eligible_steps"],
    }
    for k in TERM_KEYS:
        row[f"term_{k}"] = round(ep["term_returns"].get(k, 0.0), 5)
    for k, v in ep["actions"].items():
        row[f"a_{k}"] = v
    for k, v in (ep.get("physics") or {}).items():  # randomized-physics runs only
        row[k] = int(v) if isinstance(v, bool) else round(float(v), 4)
    return row


def _make_callback_class():
    from stable_baselines3.common.callbacks import BaseCallback

    from lunarlab.evaluation import EvaluationAborted, evaluate_policy, summarize_for_index
    from lunarlab.policies import PPOPolicy

    class LunarLabCallback(BaseCallback):
        def __init__(
            self, ctx: TrainingContext, *, first_episode: int, best_val: float | None, validate_at_start: bool
        ) -> None:
            super().__init__(verbose=0)
            self.ctx = ctx
            tc = ctx.cfg.training
            fields = EPISODE_FIELDS + (list(PHYSICS_FIELDS) if ctx.cfg.physics.enabled else [])
            self.episodes = CsvAppender(ctx.paths.episodes, fields)
            self.episode_index = first_episode
            self.best_val = best_val
            self.validate_at_start = validate_at_start
            self.ckpt_every = tc.checkpoint_every
            self.val_every = tc.validation_every
            self.stop_requested = False
            self.stop_reason: str | None = None
            self.boundary_transitions = 0
            self.updates_done = 0
            self.recent = collections.deque(maxlen=100)
            self.rollout_eps: list[dict] = []
            self.speed = collections.deque(maxlen=60)
            self.phase = "starting"
            self.last_status = 0.0
            self.last_stop_check = 0.0
            self.last_flush = 0.0
            self.t0 = time.monotonic()
            self.proc = psutil.Process()
            self.proc.cpu_percent(None)
            self.last_diag_updates = -1
            self.last_diag_transitions = 0
            self.last_validation_at: int | None = None

        # -------------------------------------------------------------- #
        def _on_training_start(self) -> None:
            n = self.model.num_timesteps
            self.boundary_transitions = n
            self.next_ckpt = (n // self.ckpt_every + 1) * self.ckpt_every
            self.next_val = 0 if self.validate_at_start else (n // self.val_every + 1) * self.val_every
            self.last_diag_updates = self.model._n_updates
            self.last_diag_transitions = n
            self.phase = "collecting"
            self.write_status(force=True)

        def _on_rollout_start(self) -> None:
            # Called after the previous PPO update finished: a clean boundary.
            n = self.model.num_timesteps
            self.boundary_transitions = n
            self.capture_update_diagnostics()
            if self.stop_requested:
                return
            if n >= self.next_ckpt:
                self.save_checkpoint("periodic")
                self.next_ckpt = (n // self.ckpt_every + 1) * self.ckpt_every
            if n >= self.next_val:
                self.validate()
                self.next_val = (n // self.val_every + 1) * self.val_every
            self.phase = "collecting"
            self.write_status(force=True)

        def _on_step(self) -> bool:
            now = time.monotonic()
            infos = self.locals["infos"]
            dones = self.locals["dones"]
            for i, done in enumerate(dones):
                if done and "lunarlab_episode" in infos[i]:
                    ep = infos[i]["lunarlab_episode"]
                    self.episode_index += 1
                    row = _flatten_episode(
                        ep,
                        episode=self.episode_index,
                        segment=self.ctx.segment,
                        env_index=i,
                        transitions=self.model.num_timesteps,
                        wall=now - self.t0,
                    )
                    self.episodes.add(row)
                    self.recent.append(row)
                    self.rollout_eps.append(row)
            if now - self.last_flush > 2.0 or len(self.episodes) >= 200:
                self.episodes.flush()
                self.last_flush = now
            if now - self.last_stop_check > 0.25:
                self.last_stop_check = now
                if self.ctx.paths.stop_request.exists():
                    req = read_json(self.ctx.paths.stop_request, default={}) or {}
                    self.stop_requested = True
                    self.stop_reason = req.get("reason", "user")
            if self.stop_requested:
                if self.ctx.cfg.algo == "dqn" and self.locals.get("num_collected_steps", 1) != 1:
                    # DQN already stored this rollout's transitions in its replay buffer: finish the
                    # rollout and its gradient steps, stop at the first step of the next one.
                    self.phase = "stopping"
                    return True
                self.phase = "stopping"
                self.write_status(force=True)
                return False
            self.write_status()
            return True

        def _on_training_end(self) -> None:
            self.episodes.flush()
            if not self.stop_requested:
                self.capture_update_diagnostics(force=True)

        # -------------------------------------------------------------- #
        def capture_update_diagnostics(self, force: bool = False) -> None:
            n_updates = self.model._n_updates
            if n_updates == self.last_diag_updates:
                return
            if (
                self.ctx.cfg.algo == "dqn"
                and not force
                and self.model.num_timesteps - self.last_diag_transitions < DQN_DIAG_EVERY
            ):
                return
            self.last_diag_transitions = self.model.num_timesteps
            self.last_diag_updates = n_updates
            self.updates_done += 1
            vals = self.model.logger.name_to_value
            row: dict[str, Any] = {
                "time": utc_now(),
                "segment": self.ctx.segment,
                "update": n_updates // max(getattr(self.model, "n_epochs", 1), 1),
                "transitions": self.model.num_timesteps,
                "elapsed_s": round(time.monotonic() - self.t0, 2),
            }
            for k in PPO_DIAGNOSTIC_KEYS:
                if k in vals:
                    row[k.split("/", 1)[1]] = float(vals[k])
            eps = self.rollout_eps
            self.rollout_eps = []
            row["episodes_in_rollout"] = len(eps)
            if eps:
                row["original_return_mean"] = float(np.mean([e["original_return"] for e in eps]))
                row["training_return_mean"] = float(np.mean([e["training_return"] for e in eps]))
            row["throughput_tps"] = self.throughput()
            append_jsonl(self.ctx.paths.metrics, row)

        def throughput(self) -> float | None:
            if len(self.speed) < 2:
                return None
            (t0, n0), (t1, n1) = self.speed[0], self.speed[-1]
            return (n1 - n0) / (t1 - t0) if t1 > t0 else None

        def save_checkpoint(
            self, kind: str, *, transitions: int | None = None, extra: dict | None = None
        ) -> dict:
            prev_phase = self.phase
            self.phase = "checkpointing"
            n = self.model.num_timesteps if transitions is None else transitions
            name = {
                "periodic": f"ckpt_{n:010d}.zip",
                "final": "final.zip",
                "stop": f"stop_{n:010d}.zip",
                # One file per selection: the manifest's best entry moves, no referenced file is rewritten.
                "best_validation": f"best_validation-{n:010d}.zip",
            }[kind]
            resumable = kind in ("periodic", "stop")
            entry = save_model_atomic(
                self.model,
                self.ctx.paths,
                name,
                kind=kind,
                transitions=n,
                segment=self.ctx.segment,
                config_hash=self.ctx.cfg.config_hash(),
                extra=extra,
                continuation=(self.ctx.cfg.algo if resumable else None),
                total_timesteps_basis=self.ctx.target,
            )
            log_event(self.ctx.paths, "info", f"{kind} checkpoint saved", file=entry["name"], transitions=n)
            self.phase = prev_phase
            return entry

        def validate(self) -> None:
            cfg = self.ctx.cfg
            n = self.model.num_timesteps
            if self.last_validation_at == n:
                return
            self.phase = "validating"
            self.write_status(force=True)
            policy = PPOPolicy(
                self.model.policy, deterministic=cfg.eval_protocol.deterministic, label="live", kind=cfg.algo
            )

            def should_stop() -> bool:
                if self.ctx.paths.stop_request.exists():
                    self.stop_requested = True
                    req = read_json(self.ctx.paths.stop_request, default={}) or {}
                    self.stop_reason = req.get("reason", "user")
                    return True
                return False

            try:
                res = evaluate_policy(
                    policy,
                    cfg.eval_protocol.validation_seeds,
                    protocol=cfg.eval_protocol,
                    reward=cfg.reward,
                    gamma=cfg.gamma,
                    should_stop=should_stop,
                )
            except EvaluationAborted:
                log_event(self.ctx.paths, "info", "validation aborted by stop request", transitions=n)
                return
            self.last_validation_at = n
            summary = {
                "time": utc_now(),
                "segment": self.ctx.segment,
                "transitions": n,
                **summarize_for_index({"aggregate": res["aggregate"]}),
            }
            mean = summary["mean_original_return"]
            is_best = self.best_val is None or mean > self.best_val
            summary["is_best"] = is_best
            append_jsonl(self.ctx.paths.validation_history, summary)
            log_event(
                self.ctx.paths,
                "info",
                "validation",
                transitions=n,
                mean_original_return=round(mean, 2),
                pad_landing_rate=summary["pad_landing_rate"],
                best=is_best,
            )
            if is_best:
                self.best_val = mean
                self.save_checkpoint(
                    "best_validation",
                    extra={
                        "selected_by": "mean original return on validation seeds",
                        "validation_mean_original_return": mean,
                        "validation_pad_landing_rate": summary["pad_landing_rate"],
                        "validation_n_episodes": summary["n_episodes"],
                    },
                )
            hook = self.ctx.on_validation
            if hook is not None and hook(n, mean) and not self.stop_requested:
                self.stop_requested = True
                self.stop_reason = "caller"
                log_event(
                    self.ctx.paths,
                    "info",
                    "stop requested after validation by the caller (tuning)",
                    transitions=n,
                )

        def write_status(self, force: bool = False, state: str = "running", **extra: Any) -> None:
            now = time.monotonic()
            if not force and now - self.last_status < 1.0:
                return
            self.last_status = now
            n = self.model.num_timesteps if self.model is not None else 0
            self.speed.append((now, n))
            recent = list(self.recent)
            mem = self.proc.memory_info().rss
            status = {
                "run_id": self.ctx.cfg.run_id,
                "job_id": self.ctx.job_id,
                "state": state,
                "phase": self.phase,
                "pid": os.getpid(),
                "segment": self.ctx.segment,
                "started_at": self.ctx.started_at,
                "updated_at": utc_now(),
                "elapsed_s": round(now - self.t0, 1),
                "transitions": n,
                "boundary_transitions": self.boundary_transitions,
                "target_transitions": self.ctx.target,
                "requested_transitions": self.ctx.cfg.training.total_transitions,
                "progress": min(1.0, n / self.ctx.target) if self.ctx.target else None,
                "throughput_tps": self.throughput(),
                "episodes": self.episode_index,
                "updates_this_segment": self.updates_done,
                "best_validation_mean_original_return": self.best_val,
                "recent_window": len(recent),
                "recent_original_return_mean": float(np.mean([r["original_return"] for r in recent]))
                if recent
                else None,
                "recent_training_return_mean": float(np.mean([r["training_return"] for r in recent]))
                if recent
                else None,
                "recent_pad_landing_rate": float(np.mean([r["pad_landing"] for r in recent]))
                if recent
                else None,
                "recent_timeout_rate": float(np.mean([r["env_outcome"] == "timeout" for r in recent]))
                if recent
                else None,
                "recent_mean_length": float(np.mean([r["length"] for r in recent])) if recent else None,
                "process": {"cpu_percent": self.proc.cpu_percent(None), "rss_mb": round(mem / 1e6, 1)},
                **extra,
            }
            atomic_write_json(self.ctx.paths.status, status)

    return LunarLabCallback


def _unique_name(dst: Path, transitions: int) -> Path:
    tag = f"{transitions:010d}"
    stem = dst.name.removesuffix(dst.suffix)
    token = secrets.token_hex(2)
    return dst.with_name(
        f"{stem}-{token}{dst.suffix}" if tag in stem else f"{stem}-{tag}-{token}{dst.suffix}"
    )


def _referenced_names(paths: RunPaths) -> set[str]:
    names = set()
    for c in read_manifest(paths).get("checkpoints", []):
        names.add(c["name"])
        cont = c.get("continuation") or {}
        names.update(v for k, v in cont.items() if k.endswith("_file") and isinstance(v, str))
    return names


def _finalize(
    src: Path, dst: Path, paths: RunPaths, *, kind: str, transitions: int, referenced: set[str]
) -> Path:
    """Move a staged file into place. A name the manifest already references is never rewritten (its
    bytes back a valid checkpoint), and a destination that stays locked gets a unique name instead."""
    if dst.name in referenced:
        dst = _unique_name(dst, transitions)
    try:
        replace_file(src, dst, timeout_s=REPLACE_TIMEOUT_S)
    except PermissionError:
        # Windows: another process (typically a real-time antivirus scan of the new file) kept the
        # destination locked. Keep the run alive: store this file under a unique name instead.
        # Checkpoints are always resolved through the manifest, which records the actual name.
        dst = _unique_name(dst, transitions)
        shutil.copyfile(src, dst)
        with contextlib.suppress(OSError):
            src.unlink()
        log_event(
            paths,
            "warning",
            "checkpoint file was locked by another process; saved under a unique name",
            file=dst.name,
            kind=kind,
        )
    return dst


def save_model_atomic(
    model,
    paths: RunPaths,
    name: str,
    *,
    kind: str,
    transitions: int,
    segment: int,
    config_hash: str,
    extra: dict | None = None,
    continuation: str | None = None,
    total_timesteps_basis: int | None = None,
) -> dict:
    """Write a checkpoint bundle crash-safely; the manifest entry is published last (the commit point).

    ``continuation``: ``None`` for an inference checkpoint, ``"ppo"`` or ``"dqn"`` for a resumable one
    (DQN adds its replay buffer and algorithm state, ``lunarlab.continuation``).
    """
    staged: list[tuple[Path, str]] = []
    digests: dict[str, str] = {}
    cont_info: dict[str, Any] | None = None
    tmp = paths.checkpoints / f"{name}.{secrets.token_hex(3)}.tmp"
    try:
        model.save(str(tmp))
        staged.append((tmp, name))
        digests[name] = sha256_file(tmp)
        if continuation == "dqn":
            from lunarlab.continuation import stage_dqn_continuation

            st = stage_dqn_continuation(
                model,
                paths.checkpoints,
                Path(name).stem,
                total_timesteps_basis=int(total_timesteps_basis or 0),
            )
            for src, target in st["files"]:
                staged.append((src, target))
                digests[target] = sha256_file(src)
            cont_info = st
        referenced = _referenced_names(paths)
        finals: dict[str, Path] = {}
        for src, target in list(staged):
            finals[target] = _finalize(
                src,
                paths.checkpoints / target,
                paths,
                kind=kind,
                transitions=transitions,
                referenced=referenced,
            )
            staged.remove((src, target))
        for target, path in finals.items():
            if sha256_file(path) != digests[target]:
                raise RunError(f"checkpoint component {path.name} changed while it was being saved")
    except BaseException:
        for src, _ in staged:  # nothing staged is ever registered; previous checkpoints stay valid
            with contextlib.suppress(OSError):
                src.unlink()
        raise
    meta: dict[str, Any] = {
        "config_hash": config_hash,
        "sb3_n_updates": int(model._n_updates),
        **(extra or {}),
    }
    if continuation == "dqn" and cont_info is not None:
        stem = Path(name).stem
        replay, state = finals[f"{stem}.replay.npz"], finals[f"{stem}.state.json"]
        meta.update(
            role="resumable",
            resumable=True,
            continuation={
                "format": DQN_CONTINUATION_FORMAT,
                "version": 1,
                "contract": DQN_CONTRACT,
                "replay_file": replay.name,
                "replay_sha256": digests[f"{stem}.replay.npz"],
                "replay_bytes": replay.stat().st_size,
                "replay_rows": cont_info["replay_rows"],
                "state_file": state.name,
                "state_sha256": digests[f"{stem}.state.json"],
                "state_bytes": state.stat().st_size,
            },
        )
    elif continuation == "ppo":
        meta.update(
            role="resumable",
            resumable=True,
            continuation={"format": PPO_CONTINUATION_FORMAT, "version": 1, "contract": PPO_CONTRACT},
        )
    else:
        meta.update(role="inference", resumable=False)
    entry = register_checkpoint(
        paths,
        finals[name],
        kind=kind,
        transitions=transitions,
        updates=model._n_updates // max(getattr(model, "n_epochs", 1), 1),
        segment=segment,
        extra=meta,
    )
    if continuation == "dqn":
        from lunarlab.continuation import prune_continuations

        removed = prune_continuations(paths, keep=KEEP_CONTINUATIONS, now=utc_now())
        if removed:
            log_event(
                paths, "info", "superseded DQN continuation files removed (weights kept)", files=removed
            )
    return entry


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def _count_episode_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as f:
        return max(sum(1 for _ in f) - 1, 0)


class _SigintToStop:
    """First Ctrl+C requests a cooperative stop; a second one interrupts immediately."""

    def __init__(self, paths: RunPaths) -> None:
        self.paths = paths
        self.prev = None
        self.count = 0

    def __enter__(self):
        if threading.current_thread() is threading.main_thread():
            self.prev = signal.signal(signal.SIGINT, self._handler)
        return self

    def _handler(self, signum, frame):
        self.count += 1
        if self.count >= 2:
            raise KeyboardInterrupt
        request_stop(self.paths, reason="user", source="ctrl-c")
        print("\nStop requested — finishing at the next safe boundary (Ctrl+C again to abort).", flush=True)

    def __exit__(self, *exc):
        if self.prev is not None:
            signal.signal(signal.SIGINT, self.prev)


def request_stop(
    paths: RunPaths, *, reason: str = "user", source: str = "api", job_id: str | None = None
) -> None:
    """Ask a running worker to stop at its next safe boundary.

    ``job_id`` addresses a specific supervised job. A worker that starts *after* a request for its
    own job was written honours it immediately instead of discarding it as stale.
    """
    paths.control.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        paths.stop_request,
        {"requested_at": utc_now(), "reason": reason, "source": source, "job_id": job_id},
    )


def train(
    run_id: str,
    *,
    resume: bool = False,
    checkpoint: str = "latest",
    job_id: str | None = None,
    quiet: bool = False,
    on_validation: Callable[[int, float], bool] | None = None,
) -> int:
    """Train (or continue) a run. Returns a worker exit code."""
    paths = RunPaths(run_id)
    cfg = load_config(run_id)
    lock = FileLock(paths.lock)
    try:
        lock.acquire()
    except LockBusy:
        log_event(paths, "error", "another worker already holds this run's lock; refusing to start")
        return EXIT_BUSY
    try:
        with _SigintToStop(paths):
            return _train_locked(
                cfg,
                paths,
                resume=resume,
                checkpoint=checkpoint,
                job_id=job_id,
                quiet=quiet,
                on_validation=on_validation,
            )
    finally:
        lock.release()


def _code_revision() -> dict | None:
    """The source revision this segment trained with (provenance), or None outside a git checkout."""
    try:
        from lunarlab.sysinfo import git_state

        return git_state()
    except Exception:  # noqa: BLE001 - provenance must never stop training
        return None


def _parallel_slots() -> int | None:
    """How many runs the launcher of this process trains at the same time (``--parallel N``, or the app's
    training lane); None when it was started on its own. Wall-clock times depend on it."""
    from lunarlab.parallel import PARALLEL_SLOTS_ENV

    try:
        return max(1, int(os.environ[PARALLEL_SLOTS_ENV]))
    except (KeyError, ValueError):
        return None


def _train_locked(
    cfg: RunConfig,
    paths: RunPaths,
    *,
    resume: bool,
    checkpoint: str,
    job_id: str | None,
    quiet: bool,
    on_validation: Callable[[int, float], bool] | None = None,
) -> int:
    import torch

    torch.set_num_threads(cfg.training.torch_threads)
    meta = load_metadata(cfg.run_id)
    # Checked here, under the run lock, so a job accepted before a freeze can never train afterwards.
    frozen = meta.get("frozen_for_test")
    if frozen:
        raise RunError(
            f"this run was frozen for the final test on {frozen.get('frozen_at')} "
            f"({frozen.get('checkpoint')}); a frozen run never trains again under the same run ID. "
            "To train further, create a warm restart (a new run with its lineage recorded); its results "
            "on the same test seeds are exploratory, not a new held-out test."
        )
    try:
        cfg.eval_protocol.require_valid()
    except ValueError as exc:
        raise RunError(f"{exc}. This run can be inspected, but not trained.") from exc
    segments = list(meta.get("segments", []))
    segment = len(segments)
    started_at = utc_now()
    target = cfg.planned_transitions

    # A stop request addressed to this job (e.g. Stop clicked while the job was still starting) is
    # honoured before any training happens. Any other request is stale (an earlier segment) and cleared.
    pending = read_json(paths.stop_request, default=None)
    if pending is not None and job_id is not None and pending.get("job_id") == job_id:
        reason = pending.get("reason", "user")
        state = "interrupted" if reason == "shutdown" else "stopped"
        log_event(
            paths, "info", f"{state} before training started (stop requested while the job was starting)"
        )
        _write_terminal_status(paths, cfg, state, job_id, error=None)
        with contextlib.suppress(FileNotFoundError):
            paths.stop_request.unlink()
        return EXIT_INTERRUPTED if state == "interrupted" else EXIT_STOPPED
    with contextlib.suppress(FileNotFoundError):
        paths.stop_request.unlink()

    parent_entry = None
    warm_path = None
    if resume:
        if any(c["kind"] == "final" for c in read_manifest(paths)["checkpoints"]):
            raise RunError("run already completed; nothing to resume")
        ckpt_path, parent_entry = resolve_resume_checkpoint(cfg.run_id, checkpoint, cfg.algo)
        if parent_entry.get("config_hash") != cfg.config_hash():
            raise RunError("checkpoint was produced by a different configuration; refusing to resume")
    elif segments or read_manifest(paths)["checkpoints"]:
        raise RunError("run already has training history; use resume instead of starting again")
    elif cfg.warm_start is not None:
        from lunarlab.lineage import resolve_warm_start

        warm_path = resolve_warm_start(cfg)

    device = resolve_device(cfg.training.device)
    seeds = cfg.worker_seeds(segment)
    seg_record = {
        "index": segment,
        "kind": "resume" if resume else "initial",
        "job_id": job_id,
        "pid": os.getpid(),
        "started_at": started_at,
        "start_transitions": parent_entry["transitions"] if parent_entry else 0,
        "parent_checkpoint": parent_entry["name"] if parent_entry else None,
        "parent_checkpoint_sha256": parent_entry["sha256"] if parent_entry else None,
        "worker_seeds": seeds,
        "vec_env": cfg.training.vec_env,
        "device": device,
        "torch_threads": cfg.training.torch_threads,
        "parallel_slots": _parallel_slots(),
        "code": _code_revision(),
        "continuation": (parent_entry.get("continuation") or {}).get("format") if parent_entry else None,
        "end_state": None,
    }
    segments.append(seg_record)
    update_metadata(cfg.run_id, segments=segments, target_transitions=target)
    log_event(
        paths,
        "info",
        "training segment started",
        segment=segment,
        resume=resume,
        parent_checkpoint=seg_record["parent_checkpoint"],
        device=device,
    )

    venv = build_vec_env(cfg)
    final_state = "failed"
    code = EXIT_FAILED
    callback = None
    try:
        model = build_model(cfg, venv, device)
        # PPO(seed=...) seeds the VecEnv with seed+rank; override with the recorded,
        # disjoint worker seeds. They take effect at the first reset inside learn().
        venv.seed(seeds[0])
        best_val = None
        if resume:
            # Weights-only: the online/target networks and the optimizer state (no pickled objects).
            model.set_parameters(str(ckpt_path), exact_match=True, device=device)
            model.num_timesteps = int(parent_entry["transitions"])
            model._n_updates = int(
                parent_entry.get(
                    "sb3_n_updates", parent_entry["updates"] * max(getattr(model, "n_epochs", 1), 1)
                )
            )
            if cfg.algo == "dqn":
                from lunarlab.continuation import restore_dqn_continuation

                restored = restore_dqn_continuation(model, paths, parent_entry, total_timesteps_basis=target)
                log_event(
                    paths,
                    "info",
                    "DQN continuation state restored",
                    replay_rows=restored["replay"]["rows"],
                    exploration_rate=restored["exploration_rate"],
                    n_calls=restored["n_calls"],
                )
            best = read_manifest(paths).get("best_validation")
            best_val = best.get("validation_mean_original_return") if best else None
        elif warm_path is not None:
            model.set_parameters(str(warm_path), exact_match=True, device=device)
            log_event(
                paths,
                "info",
                "warm restart: networks and optimizer state initialised from the parent checkpoint",
                parent_run_id=cfg.warm_start.parent_run_id,
                parent_checkpoint=cfg.warm_start.checkpoint,
            )
        ctx = TrainingContext(
            cfg=cfg,
            paths=paths,
            segment=segment,
            job_id=job_id,
            started_at=started_at,
            target=target,
            on_validation=on_validation,
        )
        Callback = _make_callback_class()
        callback = Callback(
            ctx,
            first_episode=_count_episode_rows(paths.episodes),
            best_val=best_val,
            validate_at_start=not resume,
        )
        remaining = max(target - model.num_timesteps, 0)
        if not quiet:
            print(
                f"[lunarlab] {cfg.run_id}: training to {target:,} transitions "
                f"({remaining:,} remaining) on {device}, {cfg.algo.upper()}, {cfg.n_envs} env(s) ({cfg.training.vec_env})",
                flush=True,
            )
        model.learn(
            total_timesteps=remaining, callback=callback, reset_num_timesteps=False, log_interval=None
        )

        interactions = int(model.num_timesteps) - int(seg_record["start_transitions"])
        seg_record["env_interactions"] = interactions
        seg_record["discarded_interactions"] = 0
        if callback.stop_requested:
            # Roll back to the safe boundary. PPO: the partial rollout was never trained on. DQN: only the
            # first step of a new rollout was taken; it was neither stored nor trained on. Either way the
            # environment interactions happened, so they are recorded rather than silently dropped.
            discarded = model.num_timesteps - callback.boundary_transitions
            seg_record["discarded_interactions"] = int(discarded)
            model.num_timesteps = callback.boundary_transitions
            callback.save_checkpoint("stop", transitions=model.num_timesteps)
            final_state = "interrupted" if callback.stop_reason == "shutdown" else "stopped"
            code = EXIT_INTERRUPTED if final_state == "interrupted" else EXIT_STOPPED
            log_event(
                paths,
                "info",
                f"training {final_state} at a safe boundary",
                transitions=model.num_timesteps,
                discarded_partial_rollout_transitions=discarded,
            )
        else:
            callback.save_checkpoint("final")
            callback.validate()
            final_state = "completed"
            code = EXIT_COMPLETED
            log_event(
                paths,
                "info",
                "training completed",
                transitions=model.num_timesteps,
                requested=cfg.training.total_transitions,
            )
        seg_record.update(end_state=final_state, ended_at=utc_now(), end_transitions=int(model.num_timesteps))
        callback.phase = "ended"
        callback.write_status(force=True, state=final_state)
    except KeyboardInterrupt:
        final_state, code = "interrupted", EXIT_INTERRUPTED
        seg_record.update(
            end_state=final_state,
            ended_at=utc_now(),
            note="aborted by a second Ctrl+C; resume from the latest checkpoint",
        )
        log_event(paths, "warning", "training aborted without a stop checkpoint")
        _write_terminal_status(paths, cfg, final_state, job_id, error=None)
    except Exception as exc:
        final_state, code = "failed", EXIT_FAILED
        tb = traceback.format_exc(limit=20)
        seg_record.update(end_state=final_state, ended_at=utc_now(), error=str(exc)[:500])
        log_event(paths, "error", f"training failed: {exc}", traceback=tb)
        _write_terminal_status(paths, cfg, final_state, job_id, error=str(exc)[:1000])
    finally:
        if callback is not None:
            # Episodes buffered since the last flush are real data even if training failed.
            with contextlib.suppress(Exception):
                callback.episodes.flush()
        with contextlib.suppress(Exception):
            venv.close()
        segments[-1] = seg_record
        update_metadata(cfg.run_id, segments=segments)
    if not quiet:
        print(f"[lunarlab] {cfg.run_id}: {final_state}", flush=True)
    return code


def _write_terminal_status(
    paths: RunPaths, cfg: RunConfig, state: str, job_id: str | None, error: str | None
) -> None:
    status = read_json(paths.status, default={}) or {}
    status.update(
        {
            "run_id": cfg.run_id,
            "job_id": job_id,
            "state": state,
            "phase": "ended",
            "updated_at": utc_now(),
            "error": error,
        }
    )
    atomic_write_json(paths.status, status)
