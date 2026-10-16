"""Automatic tuning with Optuna: algorithm hyperparameters and reward weights, on validation only.

A *study* searches a bounded space for one algorithm and one reward preset:

* every trial is a normal LunarLab run (marked ``tuning`` in its metadata) trained with the sampled
  settings for ``trial_transitions`` transitions and the same training seed as every other trial of the
  study (common random numbers: differences come from the settings);
* the run's periodic validations (default physics, the protocol's validation seeds, original reward) are
  reported to Optuna; after a warm-up, a median pruner may stop trials that fall behind;
* a trial's value is its best validation mean original return, the same criterion that selects a run's
  checkpoint. Trial runs are **never** evaluated on the final-test seeds (``evaluate_run`` refuses);
  ``apply_best`` creates fresh, normal runs from the best settings, and only those are final-tested.

Studies persist in ``data/tuning/<study_id>/`` (``study.json``, ``optuna.sqlite3``, ``status.json``) and
can be resumed; cancelling stops the running trial at its next safe boundary.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lunarlab.config import DQNConfig, PPOConfig, TrainingConfig
from lunarlab.rewards.config import RewardConfig, preset
from lunarlab.storage import atomic_write_json, data_dir, new_id, read_json, safe_child, utc_now

OBJECTIVE = "best validation mean original return (default physics, validation seeds)"
DEFAULT_TRAINING_SEED = 900

# name -> spec. Bounds stay inside each config's own validation limits.
SPACE: dict[str, dict[str, Any]] = {
    "ppo.learning_rate": {"type": "float", "low": 1e-4, "high": 1e-3, "log": True},
    "ppo.ent_coef": {"type": "float", "low": 1e-4, "high": 0.05, "log": True},
    "ppo.gamma": {"type": "categorical", "choices": [0.99, 0.995, 0.999]},
    "ppo.gae_lambda": {"type": "float", "low": 0.9, "high": 0.99},
    "ppo.clip_range": {"type": "float", "low": 0.1, "high": 0.3},
    "ppo.n_epochs": {"type": "int", "low": 3, "high": 10},
    "ppo.batch_size": {"type": "categorical", "choices": [32, 64, 128]},
    "dqn.learning_rate": {"type": "float", "low": 1e-4, "high": 2e-3, "log": True},
    "dqn.batch_size": {"type": "categorical", "choices": [64, 128, 256]},
    "dqn.gamma": {"type": "categorical", "choices": [0.98, 0.99, 0.995]},
    "dqn.target_update_interval": {"type": "categorical", "choices": [250, 500, 1000]},
    "dqn.exploration_fraction": {"type": "float", "low": 0.05, "high": 0.3},
    "dqn.exploration_final_eps": {"type": "float", "low": 0.01, "high": 0.1},
    "reward.time_penalty.cost_per_step": {"type": "float", "low": 0.0, "high": 0.1},
    "reward.hover_bonus.bonus_per_step": {"type": "float", "low": 0.0, "high": 2.0},
    "reward.potential.alpha": {"type": "float", "low": 1.0, "high": 50.0, "log": True},
    "reward.potential.weights.x": {"type": "float", "low": 0.0, "high": 2.0},
    "reward.potential.weights.y": {"type": "float", "low": 0.0, "high": 2.0},
    "reward.potential.weights.speed": {"type": "float", "low": 0.0, "high": 2.0},
    "reward.potential.weights.angle": {"type": "float", "low": 0.0, "high": 2.0},
}
REWARD_PARAMS = {
    "baseline": [],
    "time-penalty": ["reward.time_penalty.cost_per_step"],
    "hover-bonus": ["reward.hover_bonus.bonus_per_step"],
    "potential": [
        "reward.potential.alpha",
        "reward.potential.weights.x",
        "reward.potential.weights.y",
        "reward.potential.weights.speed",
        "reward.potential.weights.angle",
    ],
}
DEFAULT_PARAMS = {
    "ppo": ["ppo.learning_rate", "ppo.ent_coef", "ppo.gae_lambda"],
    "dqn": ["dqn.learning_rate", "dqn.exploration_fraction", "dqn.target_update_interval"],
}


class TuningError(RuntimeError):
    pass


class TuningCancelled(Exception):
    pass


def tuning_dir() -> Path:
    p = data_dir() / "tuning"
    p.mkdir(parents=True, exist_ok=True)
    return p


def study_dir(study_id: str) -> Path:
    return safe_child(tuning_dir(), study_id)


def allowed_params(algo: str, preset_name: str) -> list[str]:
    return [k for k in SPACE if k.startswith(f"{algo}.")] + REWARD_PARAMS.get(preset_name, [])


def _storage_url(study_id: str) -> str:
    return f"sqlite:///{(study_dir(study_id) / 'optuna.sqlite3').resolve().as_posix()}"


def _optuna_study(spec: dict[str, Any]):
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    return optuna.create_study(
        study_name=spec["study_id"],
        storage=_storage_url(spec["study_id"]),
        direction="maximize",
        sampler=optuna.samplers.TPESampler(
            seed=spec["sampler_seed"], n_startup_trials=spec["startup_trials"]
        ),
        pruner=optuna.pruners.MedianPruner(
            n_startup_trials=spec["startup_trials"], n_warmup_steps=spec["warmup_transitions"]
        ),
        load_if_exists=True,
    )


def create_study(
    *,
    name: str,
    algo: str = "ppo",
    preset_name: str = "baseline",
    params: list[str] | None = None,
    n_trials: int = 20,
    trial_transitions: int = 200_000,
    validation_every: int = 25_000,
    warmup_transitions: int | None = None,
    startup_trials: int = 4,
    sampler_seed: int = 0,
    training_seed: int = DEFAULT_TRAINING_SEED,
    base_ppo: dict | None = None,
    base_dqn: dict | None = None,
) -> dict[str, Any]:
    """Define and persist a study. Nothing trains until ``run_study``."""
    if algo not in ("ppo", "dqn"):
        raise TuningError("algo must be 'ppo' or 'dqn'")
    if preset_name not in REWARD_PARAMS:
        raise TuningError(f"unknown preset {preset_name!r}")
    params = list(params) if params else DEFAULT_PARAMS[algo] + REWARD_PARAMS[preset_name][:1]
    allowed = allowed_params(algo, preset_name)
    bad = [p for p in params if p not in allowed]
    if bad:
        raise TuningError(
            f"cannot tune {bad} for {algo} with the {preset_name} reward; allowed: {', '.join(allowed)}"
        )
    if not 1 <= n_trials <= 500:
        raise TuningError("n_trials must be between 1 and 500")
    training = TrainingConfig(
        profile="custom",
        total_transitions=trial_transitions,
        checkpoint_every=max(validation_every, 256),
        validation_every=validation_every,
    )
    PPOConfig(**(base_ppo or {}))  # validate the base settings now
    DQNConfig(**(base_dqn or {}))
    study_id = new_id(name or "study", prefix="tune")
    spec = {
        "study_id": study_id,
        "name": name,
        "created_at": utc_now(),
        "algo": algo,
        "preset": preset_name,
        "params": params,
        "space": {p: SPACE[p] for p in params},
        "n_trials": n_trials,
        "trial_transitions": training.total_transitions,
        "validation_every": training.validation_every,
        "checkpoint_every": training.checkpoint_every,
        "warmup_transitions": int(
            warmup_transitions if warmup_transitions is not None else 2 * validation_every
        ),
        "startup_trials": startup_trials,
        "sampler_seed": sampler_seed,
        "training_seed": training_seed,
        "base_ppo": base_ppo or {},
        "base_dqn": base_dqn or {},
        "objective": OBJECTIVE,
        **_exposure_fields(),
    }
    study_dir(study_id).mkdir(parents=True, exist_ok=False)
    atomic_write_json(study_dir(study_id) / "study.json", spec)
    _optuna_study(spec)  # creates the storage
    _write_status(study_id, state="created")
    return spec


def load_spec(study_id: str) -> dict[str, Any]:
    spec = read_json(study_dir(study_id) / "study.json", default=None)
    if not spec:
        raise KeyError(study_id)
    return spec


def _write_status(study_id: str, **fields: Any) -> dict[str, Any]:
    path = study_dir(study_id) / "status.json"
    status = read_json(path, default={}) or {}
    status.update(fields, updated_at=utc_now())
    atomic_write_json(path, status)
    return status


def _sample(trial, space: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for name, spec in space.items():
        if spec["type"] == "float":
            out[name] = trial.suggest_float(name, spec["low"], spec["high"], log=spec.get("log", False))
        elif spec["type"] == "int":
            out[name] = trial.suggest_int(name, spec["low"], spec["high"])
        else:
            out[name] = trial.suggest_categorical(name, spec["choices"])
    return out


def build_configs(
    spec: dict[str, Any], values: dict[str, Any]
) -> tuple[PPOConfig, DQNConfig | None, RewardConfig]:
    """The algorithm settings and reward of a parameter assignment (applied over the study's base)."""
    ppo = dict(spec.get("base_ppo") or {})
    dqn = dict(spec.get("base_dqn") or {})
    reward = preset(spec["preset"]).model_dump(mode="json")
    changed_reward = False
    for name, v in values.items():
        head, _, rest = name.partition(".")
        if head == "ppo":
            ppo[rest] = v
        elif head == "dqn":
            dqn[rest] = v
        elif head == "reward":
            node = reward
            *path, leaf = rest.split(".")
            for key in path:
                node = node[key]
            node[leaf] = v
            changed_reward = True
    if changed_reward:
        reward["name"] = f"{reward['name']} - tuned"[:64]
    return (
        PPOConfig(**ppo),
        DQNConfig(**dqn) if spec["algo"] == "dqn" else None,
        RewardConfig.model_validate(reward),
    )


def _best_validation(run_id: str) -> float | None:
    from lunarlab.runs import read_manifest
    from lunarlab.storage import RunPaths

    best = read_manifest(RunPaths(run_id)).get("best_validation")
    return None if best is None else float(best["validation_mean_original_return"])


def _fail_stale_trials(study) -> int:
    """Trials left RUNNING by an interrupted session can never finish: mark them failed."""
    from optuna.trial import TrialState

    n = 0
    for t in study.get_trials(deepcopy=False, states=(TrialState.RUNNING,)):
        study._storage.set_trial_user_attr(t._trial_id, "interrupted", True)
        study._storage.set_trial_state_values(t._trial_id, TrialState.FAIL)
        n += 1
    return n


def cancel_file(study_id: str) -> Path:
    return study_dir(study_id) / "cancel.json"


def request_cancel(study_id: str) -> dict[str, Any]:
    """Stop the study: the running trial stops at its next safe boundary; the study can be resumed."""
    from lunarlab.storage import RunPaths
    from lunarlab.training import request_stop

    load_spec(study_id)
    atomic_write_json(cancel_file(study_id), {"requested_at": utc_now()})
    status = read_json(study_dir(study_id) / "status.json", default={}) or {}
    rid = status.get("current_run_id")
    if rid and status.get("state") == "running":
        request_stop(RunPaths(rid), reason="tuning cancelled", source="tuning")
    return _write_status(study_id, cancel_requested=True)


class _CancelWatcher:
    """Stops the running trial promptly (next safe boundary) when a cancel arrives mid-trial."""

    def __init__(self, cancelled: Callable[[], bool], run_id: str) -> None:
        import threading

        self._cancelled = cancelled
        self._run_id = run_id
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._done.set()
        self._thread.join(timeout=5)

    def _loop(self) -> None:
        from lunarlab.storage import RunPaths
        from lunarlab.training import request_stop

        while not self._done.wait(0.5):
            if self._cancelled():
                request_stop(RunPaths(self._run_id), reason="tuning cancelled", source="tuning")
                return


def run_study(
    study_id: str,
    *,
    n_trials: int | None = None,
    timeout_s: float | None = None,
    should_stop: Callable[[], bool] | None = None,
    echo: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Run (or resume) a study until its trial budget, the timeout, or a cancel request."""
    import optuna
    from optuna.trial import TrialState

    from lunarlab.runs import create_run, update_metadata
    from lunarlab.training import EXIT_COMPLETED, train

    spec = load_spec(study_id)
    cancel_file(study_id).unlink(missing_ok=True)
    study = _optuna_study(spec)
    stale = _fail_stale_trials(study)
    if stale:
        echo(f"{stale} trial(s) interrupted earlier marked as failed")
    finished = len(study.get_trials(deepcopy=False, states=(TrialState.COMPLETE, TrialState.PRUNED)))
    remaining = spec["n_trials"] - finished
    if n_trials is not None:
        remaining = min(remaining, n_trials)
    if remaining <= 0:
        _write_status(study_id, state="completed", pid=None, current_run_id=None)
        return study_summary(study_id)
    _write_status(study_id, state="running", pid=os.getpid(), started_at=utc_now(), cancel_requested=False)

    def cancelled() -> bool:
        return cancel_file(study_id).exists() or bool(should_stop and should_stop())

    def objective(trial) -> float:
        values = _sample(trial, spec["space"])
        ppo, dqn, reward = build_configs(spec, values)
        training = TrainingConfig(
            profile="custom",
            total_transitions=spec["trial_transitions"],
            checkpoint_every=spec["checkpoint_every"],
            validation_every=spec["validation_every"],
        )
        cfg = create_run(
            reward=reward,
            training=training,
            seed=spec["training_seed"],
            ppo=ppo,
            algo=spec["algo"],
            dqn=dqn,
            label=f"tuning {spec['name']} · trial {trial.number}",
        )
        update_metadata(cfg.run_id, tuning={"study_id": study_id, "trial": trial.number})
        trial.set_user_attr("run_id", cfg.run_id)
        _write_status(study_id, current_trial=trial.number, current_run_id=cfg.run_id)
        echo(f"trial {trial.number}: {values} -> run {cfg.run_id}")
        flags = {"pruned_at": None, "cancelled": False}
        watcher = _CancelWatcher(cancelled, cfg.run_id)
        watcher.start()

        def on_validation(transitions: int, mean: float) -> bool:
            trial.report(mean, step=transitions)
            if cancelled():
                flags["cancelled"] = True
                return True
            if trial.should_prune():
                flags["pruned_at"] = transitions
                return True
            return False

        try:
            code = train(cfg.run_id, on_validation=on_validation, quiet=True)
        finally:
            watcher.stop()
        best = _best_validation(cfg.run_id)
        if best is not None:
            trial.set_user_attr("best_validation", best)
        if flags["cancelled"] or (code != EXIT_COMPLETED and cancelled()):
            trial.set_user_attr("cancelled", True)
            raise TuningCancelled()
        if flags["pruned_at"] is not None:
            trial.set_user_attr("pruned_at", flags["pruned_at"])
            echo(f"trial {trial.number}: pruned at {flags['pruned_at']:,} transitions")
            raise optuna.TrialPruned()
        if code != EXIT_COMPLETED or best is None:
            raise TuningError(f"trial run {cfg.run_id} ended with exit code {code}")
        echo(f"trial {trial.number}: best validation {best:.1f}")
        return best

    def after_trial(study, _trial) -> None:
        if cancelled():
            study.stop()

    t0 = time.monotonic()
    state = "completed"
    try:
        study.optimize(
            objective,
            n_trials=remaining,
            timeout=timeout_s,
            catch=(TuningCancelled, TuningError),
            callbacks=[after_trial],
            gc_after_trial=True,
        )
        if cancelled():
            state = "stopped"
        elif (
            len(study.get_trials(deepcopy=False, states=(TrialState.COMPLETE, TrialState.PRUNED)))
            < spec["n_trials"]
        ):
            state = "stopped"  # timeout or a per-session trial limit: resumable
    except BaseException:
        state = "failed"
        raise
    finally:
        _write_status(
            study_id,
            state=state,
            pid=None,
            current_trial=None,
            current_run_id=None,
            session_seconds=round(time.monotonic() - t0, 1),
        )
        cancel_file(study_id).unlink(missing_ok=True)
    return study_summary(study_id)


def study_summary(study_id: str) -> dict[str, Any]:
    from optuna.trial import TrialState

    spec = load_spec(study_id)
    status = read_json(study_dir(study_id) / "status.json", default={}) or {}
    study = _optuna_study(spec)
    trials = []
    for t in study.get_trials(deepcopy=False):
        trials.append(
            {
                "number": t.number,
                "state": t.state.name.lower(),
                "value": t.value,
                "params": t.params,
                "run_id": t.user_attrs.get("run_id"),
                "best_validation": t.user_attrs.get("best_validation"),
                "pruned_at": t.user_attrs.get("pruned_at"),
                "cancelled": bool(t.user_attrs.get("cancelled")),
                "interrupted": bool(t.user_attrs.get("interrupted")),
                "intermediate": sorted([int(k), float(v)] for k, v in t.intermediate_values.items()),
                "started_at": t.datetime_start.isoformat() if t.datetime_start else None,
                "completed_at": t.datetime_complete.isoformat() if t.datetime_complete else None,
            }
        )
    complete = [t for t in trials if t["state"] == "complete"]
    best = max(complete, key=lambda t: t["value"]) if complete else None
    counts = {s.name.lower(): sum(1 for t in trials if t["state"] == s.name.lower()) for s in TrialState}
    return {
        **spec,
        "status": status,
        "counts": counts,
        "finished": counts.get("complete", 0) + counts.get("pruned", 0),
        "best": best,
        "trials": trials,
    }


def list_studies() -> list[dict[str, Any]]:
    out = []
    for d in sorted(tuning_dir().iterdir(), reverse=True):
        if not (d / "study.json").exists():
            continue
        try:
            s = study_summary(d.name)
        except Exception:  # an unreadable study must not hide the others
            continue
        s.pop("trials")
        out.append(s)
    return out


def _exposure_fields() -> dict[str, Any]:
    """Whether the final-test seeds that apply_best's runs will use had already been seen."""
    from lunarlab.config import EvalProtocol
    from lunarlab.lineage import first_test_exposure

    exposure = first_test_exposure(EvalProtocol())
    return {
        "test_set_previously_exposed": exposure is not None,
        "test_exposure": exposure,
    }


def apply_best(
    study_id: str,
    *,
    seeds: list[int],
    profile: str = "standard",
    experiment_name: str | None = None,
    protocol=None,
) -> dict[str, Any]:
    """Create normal (not tuning) runs with the best trial's settings, ready to train and final-test."""
    from lunarlab.config import training_for_profile
    from lunarlab.experiments import create_experiment

    summary = study_summary(study_id)
    best = summary["best"]
    if best is None:
        raise TuningError("no completed trial yet")
    ppo, dqn, reward = build_configs(summary, best["params"])
    from lunarlab.config import PhysicsRandomization

    variant = {
        "name": summary["algo"].upper(),
        "algo": summary["algo"],
        "gamma": None,
        "physics": PhysicsRandomization(),
    }
    exp = create_experiment(
        name=experiment_name or f"{summary['name']}-best",
        rewards=[reward],
        seeds=seeds,
        profile=profile,
        description=(
            f"Best settings of tuning study {study_id} (trial {best['number']}, best validation {best['value']:.1f}): "
            + ", ".join(
                f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}" for k, v in best["params"].items()
            )
        ),
        variants=[variant],
        ppo_overrides=ppo.model_dump(mode="json") if summary["algo"] == "ppo" else None,
        dqn_overrides=dqn.model_dump(mode="json") if dqn else None,
        protocol=protocol,
    )
    training_for_profile(profile)  # validate the profile name
    # Settings chosen by a study are exploratory on test seeds that were already used for a final test
    # when these runs were created; a holdout of untouched seeds keeps them confirmatory.
    from lunarlab.config import EvalProtocol
    from lunarlab.lineage import first_test_exposure
    from lunarlab.runs import update_metadata

    exposure = first_test_exposure(protocol or EvalProtocol())
    exposed = exposure is not None

    for rid in exp["run_ids"]:
        update_metadata(
            rid,
            selection={
                "kind": "tuning",
                "study_id": study_id,
                "trial": best["number"],
                "test_set_previously_exposed": bool(exposed),
                "test_exposure": exposure,
            },
        )
    exp["test_set_previously_exposed"] = bool(exposed)
    return exp
