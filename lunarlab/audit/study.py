# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""A small, prespecified reward-design study on any registered task, through the task-independent layer.

The workflow, each step leaving a record with digests:

1. **Protocol.** It is written before training, validated by :func:`protocol_problems` and identified by
   the SHA-256 of its canonical JSON. It fixes the reward designs, the learner settings, the budget, the
   training seeds, the training-environment seed roots, the validation and test seeds, the
   checkpoint-evaluation schedule and the selection rule.
2. **Training** (:func:`train_run`). PPO learns from one design's training reward. Every
   ``eval_every_rollouts`` rollouts the current policy is saved and audited with the *original* reward on
   the validation seeds through :func:`~lunarlab.audit.audit_policy`, never on the test seeds.
3. **Selection and freezing.** The prespecified rule picks a checkpoint. That checkpoint, and the final
   checkpoint for the prespecified secondary analysis, are copied to content-addressed read-only files by
   :func:`lunarlab.freeze.immutable_copy`, the same function the main pipeline freezes with.
4. **Final test** (:func:`final_test`). The frozen copy's digest is verified before the policy is loaded.
   The policy is then audited on the test seeds, and every episode is stored.
5. **Artifact** (:func:`export_artifact`, :func:`verify_artifact`, :func:`reproduce_artifact`). It holds the
   frozen policy, the protocol, the training record, the reward provenance and the recorded test evaluation,
   with their digests. Verification checks integrity before any episode runs. Reproduction re-evaluates the
   recorded seeds and classifies the result with the statuses of ``lunarlab reproduce-artifact``.

Seeds: ``PPO(seed=s)`` seeds the learner's random generators (Python, NumPy, PyTorch, action space). The
training environments' first reset uses ``train_env_seed_root + 1000 * s + i`` for environment ``i``. These
roots are set after the model is built, because ``PPO(seed=...)`` re-seeds the environments. Later
training episodes reset without a seed and continue each environment's random stream. Validation and test
episodes are reset with their own fixed seeds.

This module is part of the reusable research core. LunarLander-specific features (the web application,
strict pad-landing categories, the hover diagnostics, the main run registry) are not used.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import shutil
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np

from lunarlab.audit.adapters import TaskAdapter, get_adapter
from lunarlab.audit.contracts import (
    AuditInputError,
    canonical_json,
    require_finite,
    seed_problems,
    split_problems,
)
from lunarlab.audit.core import RewardTerm, Transition, rescore_transitions
from lunarlab.audit.evaluate import audit_policy
from lunarlab.audit.provenance import definition_document, definition_sha256, reward_provenance

STUDY_SCHEMA = "lunarlab.audit-study/1"
RUN_SCHEMA = "lunarlab.audit-run/1"
TEST_SCHEMA = "lunarlab.audit-test/1"
ARTIFACT_SCHEMA = "lunarlab.audit-artifact/1"
SEED_STRIDE = 1000  # training-environment seed roots: root + SEED_STRIDE * training seed + environment index
SELECTION_RULES = {
    "max-mean-original-validation-return": (
        "the evaluated checkpoint with the highest mean ORIGINAL return on the validation seeds; ties go to the "
        "earliest checkpoint. Candidates are every scheduled checkpoint after training starts and the final one"
    )
}
COMPARED_FIELDS = ("length", "original_return", "training_return", "outcome", "terminated", "truncated")
OUTCOME_FIELDS = ("terminated", "truncated", "outcome")
ARTIFACT_FILES = ("policy.zip", "protocol.json", "run.json", "evaluation.json", "reward.json")


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def _sha256_file(path: Path) -> str:
    from lunarlab.storage import sha256_file

    return sha256_file(path)


def _write_json(path: Path, obj: Any) -> None:
    from lunarlab.storage import atomic_write_bytes

    atomic_write_bytes(path, (json.dumps(obj, indent=1, allow_nan=False) + "\n").encode("utf-8"))


def load_json(path: str | Path) -> Any:
    """Read a JSON file (UTF-8)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def protocol_sha256(protocol: Mapping[str, Any]) -> str:
    """SHA-256 of the protocol's canonical JSON (sorted keys, compact, no NaN)."""
    return hashlib.sha256(canonical_json(protocol).encode()).hexdigest()


def design_of(protocol: Mapping[str, Any], name: str) -> dict[str, Any]:
    """The reward design called ``name``."""
    for d in protocol["designs"]:
        if d["name"] == name:
            return d
    raise AuditInputError(
        f"no reward design {name!r} in the protocol; designs: {[d['name'] for d in protocol['designs']]}"
    )


def build_terms(adapter: TaskAdapter, design: Mapping[str, Any], gamma: float) -> dict[str, RewardTerm]:
    """The design's reward terms, built by the adapter's factories. Potential terms use the learner's gamma."""
    terms: dict[str, RewardTerm] = {}
    for spec in design.get("terms", []):
        name = spec["term"]
        if name not in adapter.term_factories:
            raise AuditInputError(f"adapter {adapter.name!r} has no reward term {name!r}")
        params = dict(spec.get("params", {}))
        if "gamma" in inspect.signature(adapter.term_factories[name]).parameters:
            if "gamma" in params and params["gamma"] != gamma:
                raise AuditInputError(
                    f"term {name!r} sets gamma {params['gamma']!r}, not the learner's {gamma!r}"
                )
            params["gamma"] = gamma
        term = adapter.term(name, **params)
        if term.name in terms:
            raise AuditInputError(f"design {design['name']!r} lists the term {term.name!r} twice")
        terms[term.name] = term
    return terms


def train_env_seeds(protocol: Mapping[str, Any], seed: int) -> list[int]:
    """First-reset seeds of the training environments for one training seed."""
    n_envs = int(protocol["algorithm"]["n_envs"])
    return [int(protocol["train_env_seed_root"]) + SEED_STRIDE * int(seed) + i for i in range(n_envs)]


def rollout_size(protocol: Mapping[str, Any]) -> int:
    """Transitions per PPO rollout (environments x steps per environment)."""
    algo = protocol["algorithm"]
    return int(algo["n_envs"]) * int(algo["kwargs"]["n_steps"])


def actual_transitions(protocol: Mapping[str, Any]) -> int:
    """The configured budget rounded up to whole rollouts, as PPO collects it."""
    size = rollout_size(protocol)
    return -(-int(protocol["budget_transitions"]) // size) * size


def protocol_problems(protocol: Mapping[str, Any]) -> list[str]:
    """Why the protocol cannot be used (empty list: it is valid)."""
    out: list[str] = []
    try:
        if protocol.get("schema") != STUDY_SCHEMA:
            out.append(f"schema must be {STUDY_SCHEMA!r}, got {protocol.get('schema')!r}")
        try:
            adapter = get_adapter(protocol["adapter"]["name"])
        except KeyError as exc:
            return out + [str(exc)]
        if protocol["adapter"].get("version") != adapter.version:
            out.append(
                f"adapter {adapter.name!r} is version {adapter.version!r}, the protocol names "
                f"{protocol['adapter'].get('version')!r}"
            )
        try:
            gamma = require_finite(protocol["gamma"], "gamma")
        except AuditInputError as exc:
            return out + [str(exc)]
        if not 0.0 < gamma <= 1.0:
            out.append(f"gamma must be in (0, 1], got {gamma!r}")
        algo = protocol["algorithm"]
        if algo.get("name") != "ppo":
            out.append(f"only PPO is supported, got {algo.get('name')!r}")
        for key in ("n_envs",):
            if not (isinstance(algo.get(key), int) and not isinstance(algo.get(key), bool) and algo[key] > 0):
                out.append(f"algorithm.{key} must be a positive integer")
        n_steps = algo.get("kwargs", {}).get("n_steps")
        if not (isinstance(n_steps, int) and not isinstance(n_steps, bool) and n_steps > 0):
            out.append("algorithm.kwargs.n_steps must be a positive integer")
        for key in ("budget_transitions", "eval_every_rollouts"):
            v = protocol.get(key)
            if not (isinstance(v, int) and not isinstance(v, bool) and v > 0):
                out.append(f"{key} must be a positive integer")
        designs = protocol.get("designs") or []
        names = [d.get("name") for d in designs]
        if not designs:
            out.append("the protocol needs at least one reward design")
        if len(set(names)) != len(names):
            out.append(f"design names must be unique: {names}")
        for d in designs:
            try:
                definition_document(build_terms(adapter, d, gamma), d.get("original_weight", 1.0))
            except (AuditInputError, KeyError, TypeError, ValueError) as exc:
                out.append(f"design {d.get('name')!r}: {exc}")
        out += seed_problems(protocol.get("training_seeds"), "training seeds")
        out += split_problems(protocol.get("validation_seeds"), protocol.get("test_seeds"))
        if protocol.get("selection", {}).get("rule") not in SELECTION_RULES:
            out.append(f"selection.rule must be one of {sorted(SELECTION_RULES)}")
        if protocol.get("success_outcome") not in adapter.outcome_categories:
            out.append(
                f"success_outcome {protocol.get('success_outcome')!r} is not one of {adapter.outcome_categories}"
            )
        if not out:
            held_out = set(protocol["validation_seeds"]) | set(protocol["test_seeds"])
            for s in protocol["training_seeds"]:
                clash = sorted(set(train_env_seeds(protocol, s)) & held_out)
                if clash:
                    out.append(
                        f"training seed {s}: environment seeds {clash[:5]} are validation or test seeds"
                    )
    except (KeyError, TypeError) as exc:
        out.append(f"malformed protocol: missing or invalid {exc}")
    return out


def require_valid_protocol(protocol: Mapping[str, Any]) -> None:
    """Raise :class:`AuditInputError` listing every problem of an invalid protocol."""
    problems = protocol_problems(protocol)
    if problems:
        raise AuditInputError("invalid study protocol: " + "; ".join(problems))


def _schedule(value: Any, what: str) -> Any:
    if isinstance(value, Mapping):
        if set(value) != {"linear"}:
            raise AuditInputError(f"{what}: a schedule is {{'linear': initial value}}, got {dict(value)}")
        start = require_finite(value["linear"], f"{what}.linear")
        return lambda progress_remaining: progress_remaining * start
    return require_finite(value, what)


def make_model(protocol: Mapping[str, Any], venv: Any, seed: int) -> Any:
    """The protocol's PPO learner on ``venv``, with learner seed ``seed`` (linear schedules supported)."""
    from stable_baselines3 import PPO

    algo = protocol["algorithm"]
    kwargs = dict(algo["kwargs"])
    for key in ("learning_rate", "clip_range"):
        if key in kwargs:
            kwargs[key] = _schedule(kwargs[key], f"algorithm.kwargs.{key}")
    return PPO(
        algo.get("policy", "MlpPolicy"),
        venv,
        gamma=protocol["gamma"],
        seed=int(seed),
        device="cpu",
        verbose=0,
        **kwargs,
    )


def policy_fn(model: Any) -> Callable[[np.ndarray], Any]:
    """The deterministic policy of an SB3 model as an observation -> action callable."""

    def act(obs: np.ndarray) -> Any:
        action = np.asarray(model.predict(obs, deterministic=True)[0])
        return action.item() if action.ndim == 0 else action

    return act


def _slim(report: Mapping[str, Any]) -> dict[str, Any]:
    """An audit report without its per-call provenance record (kept once per run)."""
    out = dict(report)
    out["reward"] = {k: v for k, v in report["reward"].items() if k != "provenance"}
    return out


def _set_threads(protocol: Mapping[str, Any]) -> int:
    import torch

    n = int(protocol.get("torch_threads", 1))
    torch.set_num_threads(n)
    return torch.get_num_threads()


class _ResetLog(gym.Wrapper):
    """Records the seed of every reset of one training environment."""

    def __init__(self, env: gym.Env, index: int, log: list[dict]) -> None:
        super().__init__(env)
        self.index, self.log = index, log

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        self.log.append({"env": self.index, "seed": seed})
        return self.env.reset(seed=seed, options=options)


# --------------------------------------------------------------------------- #
# Training, selection, freezing
# --------------------------------------------------------------------------- #


def select_checkpoint(checkpoints: list[dict[str, Any]], rule: str) -> dict[str, Any]:
    """Apply the prespecified selection rule to the evaluated checkpoints."""
    if rule not in SELECTION_RULES:
        raise AuditInputError(f"unknown selection rule {rule!r}")
    if not checkpoints:
        raise AuditInputError("no evaluated checkpoint to select from")
    return max(checkpoints, key=lambda c: (c["validation"]["mean_original_return"], -c["step"]))


def train_run(
    protocol: Mapping[str, Any],
    design_name: str,
    seed: int,
    run_dir: str | Path,
    *,
    echo: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Train one policy, evaluate scheduled checkpoints on the validation seeds, select and freeze.

    Writes ``run_dir/protocol.json``, ``checkpoints/``, ``frozen/`` and ``run.json``. Refuses an existing run
    directory: a run is never retrained in place.
    """
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.vec_env import DummyVecEnv

    from lunarlab.freeze import immutable_copy
    from lunarlab.storage import utc_now
    from lunarlab.sysinfo import version_info

    require_valid_protocol(protocol)
    run_dir = Path(run_dir)
    if run_dir.exists() and any(run_dir.iterdir()):
        raise AuditInputError(f"{run_dir} already holds a run; a run is never retrained in place")
    if seed not in protocol["training_seeds"]:
        raise AuditInputError(
            f"training seed {seed} is not one of the protocol's {protocol['training_seeds']}"
        )
    adapter = get_adapter(protocol["adapter"]["name"])
    design = design_of(protocol, design_name)
    gamma = float(protocol["gamma"])
    weight = float(design.get("original_weight", 1.0))
    terms = build_terms(adapter, design, gamma)
    threads = _set_threads(protocol)
    ckpt_dir = run_dir / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    _write_json(run_dir / "protocol.json", protocol)
    started = utc_now()
    t_start = time.perf_counter()

    resets: list[dict] = []

    env_kwargs = dict(protocol.get("env_kwargs") or {})

    def make(index: int) -> Callable[[], gym.Env]:
        def build() -> gym.Env:
            inner = _ResetLog(adapter.make_env(**env_kwargs), index, resets)
            return Monitor(_accounting(inner, terms, gamma, weight, adapter))

        return build

    venv = DummyVecEnv([make(i) for i in range(int(protocol["algorithm"]["n_envs"]))])
    model = make_model(protocol, venv, seed)
    env_seeds = train_env_seeds(protocol, seed)
    venv.seed(env_seeds[0])  # after the model: PPO(seed=...) re-seeds the environments
    size = rollout_size(protocol)
    every = int(protocol["eval_every_rollouts"])
    validation_seeds = list(protocol["validation_seeds"])
    checkpoints: list[dict[str, Any]] = []
    evaluated: set[int] = set()

    def checkpoint(m: Any) -> None:
        step = int(m.num_timesteps)
        if step in evaluated:
            return
        evaluated.add(step)
        path = ckpt_dir / f"step-{step:08d}.zip"
        m.save(path)
        sha = _sha256_file(path)
        t0 = time.perf_counter()
        report = audit_policy(
            adapter,
            policy_fn(m),
            validation_seeds,
            gamma=gamma,
            terms=terms,
            original_weight=weight,
            env_kwargs=env_kwargs,
        )
        agg = report["aggregate"]
        success = sum(e["outcome"] == protocol["success_outcome"] for e in report["episodes"]) / len(
            report["episodes"]
        )
        checkpoints.append(
            {
                "step": step,
                "rollouts": step // size,
                "file": path.relative_to(run_dir).as_posix(),
                "sha256": sha,
                "validation": {
                    "mean_original_return": agg["mean_original_return"],
                    "mean_training_return": agg["mean_training_return"],
                    "success_rate": success,
                    "outcomes": agg["outcomes"],
                    "episodes": report["episodes"],
                },
                "validation_seconds": time.perf_counter() - t0,
            }
        )
        echo(
            f"  {design_name} seed {seed}: step {step:,} validation original return "
            f"{agg['mean_original_return']:.1f}, success {success:.0%}"
        )

    class Evaluate(BaseCallback):
        def _on_rollout_start(self) -> None:
            done = self.model.num_timesteps // size
            if done > 0 and done % every == 0:
                checkpoint(self.model)

        def _on_step(self) -> bool:
            return True

    model.learn(int(protocol["budget_transitions"]), callback=Evaluate())
    checkpoint(model)  # the final checkpoint is always a candidate
    venv.close()
    training_seconds = time.perf_counter() - t_start
    rule = protocol["selection"]["rule"]
    chosen = select_checkpoint(checkpoints, rule)
    final = max(checkpoints, key=lambda c: c["step"])
    frozen = {}
    for label, entry in (("selected", chosen), ("final", final)):
        dst = immutable_copy(
            run_dir / entry["file"], run_dir / "frozen" / f"{entry['sha256']}.zip", entry["sha256"]
        )
        if _sha256_file(dst) != entry["sha256"]:
            raise AuditInputError(f"the frozen copy of {entry['file']} does not have its recorded digest")
        frozen[label] = {
            "step": entry["step"],
            "sha256": entry["sha256"],
            "file": dst.relative_to(run_dir).as_posix(),
        }
    first = {}
    later = []
    for r in resets:
        if r["env"] not in first:
            first[r["env"]] = r["seed"]
        else:
            later.append(r["seed"])
    record = {
        "schema": RUN_SCHEMA,
        "study_id": protocol["study_id"],
        "protocol_sha256": protocol_sha256(protocol),
        "design": design_name,
        "training_seed": int(seed),
        "started_at": started,
        "finished_at": utc_now(),
        "training_seconds": training_seconds,
        "torch_threads": threads,
        "transitions": {
            "configured": int(protocol["budget_transitions"]),
            "actual": int(model.num_timesteps),
            "rollout_size": size,
            "rollouts": int(model.num_timesteps) // size,
        },
        "seeding": {
            "learner_seed": int(seed),
            "intended_first_reset_seeds": env_seeds,
            "effective_first_reset_seeds": [first.get(i) for i in range(len(env_seeds))],
            "later_resets": len(later),
            "later_resets_with_a_seed": sum(s is not None for s in later),
            "validation_seeds": validation_seeds,
            "note": "later training episodes reset without a seed and continue each environment's random stream",
        },
        "reward": {
            "design": design,
            "definition_sha256": definition_sha256(terms, weight),
            "provenance": reward_provenance(terms, weight, adapter=adapter),
        },
        "checkpoints": checkpoints,
        "selection": {
            "rule": rule,
            "meaning": SELECTION_RULES[rule],
            "step": chosen["step"],
            "sha256": chosen["sha256"],
        },
        "frozen": frozen,
        "software": version_info(),
    }
    if record["seeding"]["effective_first_reset_seeds"] != env_seeds:
        raise AuditInputError(
            f"training environments were reset with {record['seeding']['effective_first_reset_seeds']}, "
            f"not the intended {env_seeds}"
        )
    _write_json(run_dir / "run.json", record)
    return record


def _accounting(
    env: gym.Env, terms: Mapping[str, RewardTerm], gamma: float, weight: float, adapter: TaskAdapter
):
    from lunarlab.audit.core import RewardAccountingWrapper

    return RewardAccountingWrapper(
        env, terms, gamma=gamma, original_weight=weight, apply=True, adapter=adapter
    )


# --------------------------------------------------------------------------- #
# Final test
# --------------------------------------------------------------------------- #


def verify_frozen(run_dir: str | Path, which: str = "selected") -> tuple[Path, dict[str, Any]]:
    """The frozen checkpoint's path, after checking its digest against the run record."""
    run_dir = Path(run_dir)
    run = load_json(run_dir / "run.json")
    entry = run["frozen"][which]
    path = run_dir / entry["file"]
    if not path.is_file():
        raise AuditInputError(f"frozen checkpoint {entry['file']} is missing")
    actual = _sha256_file(path)
    if actual != entry["sha256"]:
        raise AuditInputError(
            f"frozen checkpoint {entry['file']} has digest {actual}, the run recorded {entry['sha256']}"
        )
    return path, run


def final_test(run_dir: str | Path, *, which: str = "selected") -> dict[str, Any]:
    """Audit the frozen ``selected`` (or ``final``) checkpoint on the protocol's test seeds.

    The frozen file's digest and the protocol's digest are verified before the policy is loaded. An existing
    test record is never overwritten.
    """
    from stable_baselines3 import PPO

    from lunarlab.storage import utc_now
    from lunarlab.sysinfo import version_info

    run_dir = Path(run_dir)
    out = run_dir / f"test-{which}.json"
    if out.exists():
        raise AuditInputError(f"{out} exists; a final test is recorded once")
    path, run = verify_frozen(run_dir, which)
    protocol = load_json(run_dir / "protocol.json")
    if protocol_sha256(protocol) != run["protocol_sha256"]:
        raise AuditInputError("protocol.json no longer matches the protocol digest recorded at training")
    require_valid_protocol(protocol)
    adapter = get_adapter(protocol["adapter"]["name"])
    design = design_of(protocol, run["design"])
    gamma = float(protocol["gamma"])
    weight = float(design.get("original_weight", 1.0))
    terms = build_terms(adapter, design, gamma)
    threads = _set_threads(protocol)
    model = PPO.load(path, device="cpu")
    t0 = time.perf_counter()
    report = audit_policy(
        adapter,
        policy_fn(model),
        list(protocol["test_seeds"]),
        gamma=gamma,
        terms=terms,
        original_weight=weight,
        env_kwargs=dict(protocol.get("env_kwargs") or {}),
    )
    record = {
        "schema": TEST_SCHEMA,
        "which": which,
        "design": run["design"],
        "training_seed": run["training_seed"],
        "checkpoint_step": run["frozen"][which]["step"],
        "checkpoint_sha256": run["frozen"][which]["sha256"],
        "protocol_sha256": run["protocol_sha256"],
        "tested_at": utc_now(),
        "test_seconds": time.perf_counter() - t0,
        "torch_threads": threads,
        "tested_with": version_info(),
        "report": report,
    }
    _write_json(out, record)
    return record


# --------------------------------------------------------------------------- #
# Artifacts
# --------------------------------------------------------------------------- #


def export_artifact(run_dir: str | Path, out_dir: str | Path, *, which: str = "selected") -> dict[str, Any]:
    """Package the frozen policy, protocol, training record, reward provenance and recorded test evaluation."""
    from lunarlab.storage import utc_now
    from lunarlab.sysinfo import version_info

    run_dir, out_dir = Path(run_dir), Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise AuditInputError(f"{out_dir} is not empty")
    path, run = verify_frozen(run_dir, which)
    test = load_json(run_dir / f"test-{which}.json")
    if test["checkpoint_sha256"] != run["frozen"][which]["sha256"]:
        raise AuditInputError("the recorded test evaluated a different checkpoint")
    protocol = load_json(run_dir / "protocol.json")
    adapter = get_adapter(protocol["adapter"]["name"])
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, out_dir / "policy.zip")
    shutil.copyfile(run_dir / "protocol.json", out_dir / "protocol.json")
    shutil.copyfile(run_dir / "run.json", out_dir / "run.json")
    shutil.copyfile(run_dir / f"test-{which}.json", out_dir / "evaluation.json")
    _write_json(out_dir / "reward.json", run["reward"])
    files = {
        name: {"sha256": _sha256_file(out_dir / name), "bytes": (out_dir / name).stat().st_size}
        for name in ARTIFACT_FILES
    }
    manifest = {
        "schema": ARTIFACT_SCHEMA,
        "study_id": run["study_id"],
        "design": run["design"],
        "training_seed": run["training_seed"],
        "which": which,
        "adapter": {
            "name": adapter.name,
            "version": adapter.version,
            "outcome_categories": list(adapter.outcome_categories),
        },
        "protocol_sha256": run["protocol_sha256"],
        "policy_sha256": run["frozen"][which]["sha256"],
        "reward_definition_sha256": run["reward"]["definition_sha256"],
        "test_seeds": list(protocol["test_seeds"]),
        "files": files,
        "recorded_with": test["tested_with"],
        "exported_with": version_info(),
        "exported_at": utc_now(),
    }
    _write_json(out_dir / "manifest.json", manifest)
    return manifest


def check_file_digests(root: str | Path, expected: Mapping[str, str]) -> list[tuple[str, bool, str]]:
    """Each file under ``root`` named in ``expected`` exists and has the recorded SHA-256: (name, passed, detail)."""
    out = []
    for name, sha in expected.items():
        p = Path(root) / name
        if not p.is_file():
            out.append((f"{name} is present", False, "missing"))
            continue
        actual = _sha256_file(p)
        out.append(
            (f"{name} has its recorded SHA-256", actual == sha, "" if actual == sha else f"{actual} != {sha}")
        )
    return out


def check_recorded_episodes(
    episodes: list[dict[str, Any]],
    *,
    expected_seeds: list[int],
    term_names: list[str],
    original_weight: float,
    categories: tuple[str, ...] | list[str],
) -> list[tuple[str, bool, str]]:
    """Checks of a recorded evaluation that need no policy execution: (name, passed, detail) for each."""
    out = []
    seeds = [e.get("seed") for e in episodes]
    out.append(
        (
            "recorded episodes are the protocol's test seeds, once each and in order",
            seeds == list(expected_seeds),
            "",
        )
    )
    missing = [i for i, e in enumerate(episodes) if "original_return" not in e or "training_return" not in e]
    out.append(
        (
            "every episode records the original and training reward channels",
            not missing,
            f"missing in {missing[:5]}" if missing else "",
        )
    )
    bad = []
    for i, e in enumerate(episodes):
        values = [
            e.get(k)
            for k in (
                "original_return",
                "training_return",
                "discounted_original_return",
                "discounted_training_return",
            )
        ]
        values += list((e.get("term_returns") or {}).values())
        if any(
            not isinstance(v, (int, float)) or isinstance(v, bool) or not np.isfinite(v)
            for v in values
            if v is not None
        ):
            bad.append(i)
    out.append(
        ("every recorded reward value is a finite number", not bad, f"episodes {bad[:5]}" if bad else "")
    )
    wrong_terms = [
        i for i, e in enumerate(episodes) if sorted(e.get("term_returns") or {}) != sorted(term_names)
    ]
    out.append(
        (
            "every episode records exactly the design's terms",
            not wrong_terms,
            f"episodes {wrong_terms[:5]}" if wrong_terms else "",
        )
    )
    broken = []
    if not missing and not bad and not wrong_terms:
        for i, e in enumerate(episodes):
            expected = original_weight * e["original_return"] + sum(e["term_returns"].values())
            if abs(e["training_return"] - expected) > 1e-9 * max(1.0, abs(expected)):
                broken.append(i)
    out.append(
        (
            "training return = weight x original return + term returns, in every episode",
            not (missing or bad or wrong_terms or broken),
            f"episodes {broken[:5]}"
            if broken
            else ("not checked: channels incomplete" if missing or bad or wrong_terms else ""),
        )
    )
    outside = sorted({e.get("outcome") for e in episodes} - set(categories), key=str)
    out.append(
        ("every outcome is one of the adapter's categories", not outside, f"{outside}" if outside else "")
    )
    return out


def check_trajectory(
    trajectory: Mapping[str, Any],
    terms: Mapping[str, RewardTerm],
    *,
    gamma: float,
    original_weight: float = 1.0,
) -> list[tuple[str, bool, str]]:
    """Re-score a recorded trajectory and compare every step's recorded term values with the re-scored ones.

    ``trajectory`` holds ``observations`` (T + 1 rows), ``actions``, ``original_rewards``, ``terminated`` and
    ``truncated`` (the final step's flags) and ``term_values`` ({term: T values}).
    """
    obs = [np.asarray(o, dtype=np.float64) for o in trajectory["observations"]]
    n = len(trajectory["original_rewards"])
    transitions = [
        Transition(
            obs[t],
            trajectory["actions"][t],
            float(trajectory["original_rewards"][t]),
            obs[t + 1],
            bool(trajectory["terminated"]) and t == n - 1,
            bool(trajectory["truncated"]) and t == n - 1,
        )
        for t in range(n)
    ]
    rescored = rescore_transitions(transitions, terms, gamma=gamma, original_weight=original_weight)
    out = []
    for name in terms:
        recorded = trajectory["term_values"].get(name)
        if recorded is None:
            out.append(
                (
                    f"recorded per-step values of {name!r} match the re-scored definition",
                    False,
                    "not recorded",
                )
            )
            continue
        worst = max(
            (abs(float(r) - s["terms"][name]) for r, s in zip(recorded, rescored["steps"], strict=True)),
            default=0.0,
        )
        out.append(
            (
                f"recorded per-step values of {name!r} match the re-scored definition",
                worst <= 1e-9,
                f"largest difference {worst:.3g}",
            )
        )
    return out


def compare_generic_aggregates(
    recorded: list[dict[str, Any]], reproduced: list[dict[str, Any]], success_outcome: str, *, seed: int = 0
) -> dict[str, Any]:
    """Paired aggregate screen over the same seeds: mean original return and the success rate.

    Uses the main pipeline's sign-flip permutation test, exact McNemar test and Holm correction. A regression
    screen, not an equivalence test.
    """
    from lunarlab.reproduce import CONSISTENCY_ALPHA, holm, mcnemar_p_value, sign_flip_p_value

    by_seed = {int(e["seed"]): e for e in recorded}
    pairs = [(by_seed[int(e["seed"])], e) for e in reproduced if int(e["seed"]) in by_seed]
    diffs = [float(b["original_return"]) - float(a["original_return"]) for a, b in pairs]
    gained = sum(a["outcome"] != success_outcome and b["outcome"] == success_outcome for a, b in pairs)
    lost = sum(a["outcome"] == success_outcome and b["outcome"] != success_outcome for a, b in pairs)
    p = {
        "mean_original_return": sign_flip_p_value(diffs, seed=seed),
        "success_rate": mcnemar_p_value(gained, lost),
    }
    rejected = holm(p)
    metrics = {
        "mean_original_return": {
            "paired_mean_difference": sum(diffs) / len(diffs) if diffs else None,
            "test": "sign-flip permutation test of the paired differences",
            "p_value": p["mean_original_return"],
            "significant": rejected["mean_original_return"],
        },
        "success_rate": {
            "episodes_gained": gained,
            "episodes_lost": lost,
            "test": "exact McNemar test",
            "p_value": p["success_rate"],
            "significant": rejected["success_rate"],
        },
    }
    return {
        "equivalence_assessed": False,
        "interpretation": "Non-rejection of paired difference tests does not establish equivalence.",
        "criterion": f"Holm-corrected family-wise alpha = {CONSISTENCY_ALPHA}",
        "metrics": metrics,
        "consistent": not any(rejected.values()),
    }


def verify_artifact(artifact_dir: str | Path) -> dict[str, Any]:
    """Every integrity check of an exported artifact. Nothing is executed: no environment, no policy.

    A malformed record (a missing key, a wrong type) is reported as a failed check naming the problem.
    """
    root = Path(artifact_dir)
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> bool:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    try:
        return _verify(root, checks, check)
    except (KeyError, TypeError, IndexError, AuditInputError) as exc:
        check("artifact records are complete and well formed", False, f"{type(exc).__name__}: {exc}"[:300])
        return {"ok": False, "checks": checks}


def _verify(root: Path, checks: list[dict[str, Any]], check: Callable[..., bool]) -> dict[str, Any]:
    try:
        manifest = load_json(root / "manifest.json")
    except (OSError, ValueError) as exc:
        check("manifest.json is present and readable", False, str(exc)[:200])
        return {"ok": False, "checks": checks}
    check("manifest.json is present and readable", True)
    if not check(
        "artifact schema is supported", manifest.get("schema") == ARTIFACT_SCHEMA, str(manifest.get("schema"))
    ):
        return {"ok": False, "checks": checks}
    files_ok = True
    for name in ARTIFACT_FILES:
        info = (manifest.get("files") or {}).get(name)
        p = root / name
        if info is None:
            files_ok &= check(f"{name} is listed in the manifest", False)
        elif not p.is_file():
            files_ok &= check(f"{name} is present", False, "missing")
        else:
            actual = _sha256_file(p)
            files_ok &= check(
                f"{name} has its recorded SHA-256",
                actual == info["sha256"],
                "" if actual == info["sha256"] else f"{actual[:16]}... != {info['sha256'][:16]}...",
            )
    if not files_ok:
        return {"ok": False, "checks": checks}
    try:
        protocol = load_json(root / "protocol.json")
        run = load_json(root / "run.json")
        test = load_json(root / "evaluation.json")
        reward = load_json(root / "reward.json")
    except ValueError as exc:
        check("JSON files parse", False, str(exc)[:200])
        return {"ok": False, "checks": checks}
    digest = protocol_sha256(protocol)
    check(
        "protocol digest matches the manifest, the training record and the test record",
        digest == manifest["protocol_sha256"] == run["protocol_sha256"] == test["protocol_sha256"],
    )
    problems = protocol_problems(protocol)
    check(
        "protocol is valid (seed contract, disjoint splits, known adapter and terms)",
        not problems,
        "; ".join(problems)[:300],
    )
    if problems:
        return {"ok": False, "checks": checks}
    adapter = get_adapter(protocol["adapter"]["name"])
    declared = manifest.get("adapter") or {}
    check(
        "outcome schema matches the registered adapter (name, version, categories)",
        declared.get("name") == adapter.name
        and declared.get("version") == adapter.version == protocol["adapter"]["version"]
        and list(declared.get("outcome_categories") or []) == list(adapter.outcome_categories),
        f"artifact {declared}, registered {adapter.name} v{adapter.version} {list(adapter.outcome_categories)}",
    )
    design = design_of(protocol, manifest["design"])
    weight = float(design.get("original_weight", 1.0))
    try:
        terms = build_terms(adapter, design, float(protocol["gamma"]))
        rebuilt = definition_sha256(terms, weight)
    except AuditInputError as exc:
        check("reward definition can be rebuilt from the protocol", False, str(exc))
        return {"ok": False, "checks": checks}
    check(
        "reward definition rebuilt from the protocol has the recorded digest",
        rebuilt
        == manifest["reward_definition_sha256"]
        == reward.get("definition_sha256")
        == run["reward"]["definition_sha256"],
        f"rebuilt {rebuilt[:16]}..., recorded {str(manifest.get('reward_definition_sha256'))[:16]}...",
    )
    policy_sha = manifest["files"]["policy.zip"]["sha256"]
    check(
        "policy is the checkpoint the run froze and the test evaluated",
        policy_sha
        == manifest["policy_sha256"]
        == run["frozen"][manifest["which"]]["sha256"]
        == test["checkpoint_sha256"],
    )
    check(
        "test seeds equal the protocol's",
        list(manifest["test_seeds"]) == list(protocol["test_seeds"]) == list(test["report"]["seeds"]),
    )
    for name, ok, detail in check_recorded_episodes(
        test["report"]["episodes"],
        expected_seeds=list(protocol["test_seeds"]),
        term_names=sorted(terms),
        original_weight=weight,
        categories=adapter.outcome_categories,
    ):
        check(name, ok, detail)
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


def reproduce_artifact(artifact_dir: str | Path, *, echo: Callable[[str], None] = print) -> dict[str, Any]:
    """Verify an artifact, then re-evaluate its policy on the recorded seeds and classify the result.

    Statuses and exit codes are those of :data:`lunarlab.reproduce.STATUSES`. An integrity failure skips the
    evaluation: no episode runs.
    """
    from stable_baselines3 import PPO

    from lunarlab.reproduce import STATUSES, classify_reproduction, compare_episodes, compare_platforms
    from lunarlab.sysinfo import version_info

    root = Path(artifact_dir)
    verification = verify_artifact(root)
    for c in verification["checks"]:
        echo(f"  [{'ok' if c['ok'] else 'FAIL'}] {c['check']}" + (f": {c['detail']}" if c["detail"] else ""))
    current = version_info()
    if not verification["ok"]:
        status = "integrity-failure"
        return {
            "status": status,
            "exit_code": STATUSES[status]["exit_code"],
            "reason": STATUSES[status]["meaning"],
            "evaluation_skipped": True,
            "checks": verification["checks"],
            "reproduced_with": current,
        }
    manifest = load_json(root / "manifest.json")
    protocol = load_json(root / "protocol.json")
    test = load_json(root / "evaluation.json")
    adapter = get_adapter(protocol["adapter"]["name"])
    design = design_of(protocol, manifest["design"])
    weight = float(design.get("original_weight", 1.0))
    terms = build_terms(adapter, design, float(protocol["gamma"]))
    _set_threads(protocol)
    model = PPO.load(root / "policy.zip", device="cpu")
    report = audit_policy(
        adapter,
        policy_fn(model),
        list(protocol["test_seeds"]),
        gamma=float(protocol["gamma"]),
        terms=terms,
        original_weight=weight,
        env_kwargs=dict(protocol.get("env_kwargs") or {}),
    )
    recorded = test["report"]["episodes"]
    comparison = compare_episodes(
        recorded, report["episodes"], fields=COMPARED_FIELDS, outcome_fields=OUTCOME_FIELDS
    )
    aggregates = compare_generic_aggregates(recorded, report["episodes"], protocol["success_outcome"])
    platform = compare_platforms(manifest.get("recorded_with"), current)
    status, reason = classify_reproduction(
        integrity_ok=True, comparison=comparison, aggregates=aggregates, platform=platform
    )
    echo(f"  status: {status}: {reason}")
    return {
        "status": status,
        "exit_code": STATUSES[status]["exit_code"],
        "reason": reason,
        "evaluation_skipped": False,
        "checks": verification["checks"],
        "comparison": comparison,
        "aggregates": aggregates,
        "platform": platform,
        "reproduced_with": current,
        "reproduced_episodes": report["episodes"],
    }


def environment_record() -> dict[str, Any]:
    """Threads and numerical settings that affect results, for study records."""
    import torch

    return {
        "torch_threads": torch.get_num_threads(),
        "torch_deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        "mkl_num_threads": os.environ.get("MKL_NUM_THREADS"),
        "float_dtype": "float32 policy network (SB3 default); float64 reward accounting",
    }
