"""Run lineage: warm restarts, test exposure and the evidence role of a run's final-test result.

A **warm restart** is a new run whose networks (and optimizer state) start from another run's
checkpoint. It is never presented as a continuation: it gets its own run ID, its configuration hash
differs (``RunConfig.warm_start``), so comparisons never group it with uninterrupted runs, and its
metadata lists which state was preserved and which was reset.

**Test exposure.** Once a final-test result of a protocol's test seeds has been seen, those seeds are
no longer unseen for decisions made afterwards. ``data/test_exposure.jsonl`` records every completed
final test per test-seed set. A run derived from a tested run (a warm restart of it), or created from
a tuning study that started after the test seeds were exposed, is labelled **exploratory**: its result
on the same seeds is not a new held-out test. A confirmatory claim needs an untouched holdout, i.e. a
protocol whose test seeds have never been used (see docs/EVALUATION.md).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from lunarlab.config import EvalProtocol, RunConfig, WarmStart
from lunarlab.locks import hold
from lunarlab.runs import RunError, create_run, load_config, load_metadata, log_event, resolve_checkpoint
from lunarlab.storage import RunPaths, append_jsonl, data_dir, read_jsonl, utc_now

PRESERVED = {
    "ppo": ["network weights (policy and value networks)", "optimizer state"],
    "dqn": ["network weights (online and target Q-networks)", "optimizer state"],
}
RESET = {
    "ppo": [
        "transition and update counters (start at 0, full training budget)",
        "environment state (new episodes)",
        "random-number streams",
    ],
    "dqn": [
        "replay buffer (starts empty)",
        "transition, update and target-network update counters (start at 0, full training budget)",
        "exploration schedule (starts again from its initial rate)",
        "environment state (new episodes)",
        "random-number streams",
    ],
}


# --------------------------------------------------------------------------- #
# Warm restarts
# --------------------------------------------------------------------------- #


def create_warm_restart(
    run_id: str, checkpoint: str = "latest", *, confirm: bool, label: str | None = None
) -> RunConfig:
    """Create (do not train) a new run initialised from ``run_id``'s checkpoint. Needs ``confirm=True``."""
    if not confirm:
        raise RunError(
            "a warm restart creates a NEW run initialised from these weights; it is not a resume. "
            "Confirm it explicitly (confirm=True, --confirm in the CLI)."
        )
    parent = load_config(run_id)
    meta = load_metadata(run_id)
    frozen = meta.get("frozen_for_test")
    if checkpoint == "frozen":
        from lunarlab.freeze import resolve_frozen_checkpoint

        _path, entry = resolve_frozen_checkpoint(run_id)
    else:
        _path, entry = resolve_checkpoint(run_id, checkpoint)
    tested = bool(frozen) or bool(meta.get("test_attempts")) or int(meta.get("test_evaluations") or 0) > 0
    algo = parent.algo
    lineage = {
        "kind": "warm_restart",
        "parent_run_id": run_id,
        "parent_checkpoint": entry["name"],
        "parent_checkpoint_sha256": entry["sha256"],
        "parent_transitions": entry.get("transitions"),
        "parent_config_hash": parent.config_hash(),
        "preserved": PRESERVED[algo],
        "reset": RESET[algo],
        "post_test": tested,
        "parent_frozen_sha256": (frozen or {}).get("checkpoint_sha256"),
        "created_at": utc_now(),
        "note": (
            "Created after the parent's final test: results of this run on the same test seeds are "
            "exploratory, not a new held-out test."
            if tested
            else "Not a continuation of the parent run; compare it separately."
        ),
    }
    child = create_run(
        reward=parent.reward,
        training=parent.training,
        seed=parent.seed,
        ppo=parent.ppo,
        protocol=parent.eval_protocol,
        experiment_id=None,
        label=label or f"warm restart of {run_id} from {entry['name']}"[:120],
        reward_config_id=parent.reward_config_id,
        reward_revision=parent.reward_revision,
        algo=algo,
        dqn=parent.dqn,
        physics=parent.physics,
        warm_start=WarmStart(
            parent_run_id=run_id,
            checkpoint=entry["name"],
            checkpoint_sha256=entry["sha256"],
            parent_config_hash=parent.config_hash(),
        ),
        lineage=lineage,
    )
    log_event(RunPaths(run_id), "info", "warm restart created from this run", child_run_id=child.run_id)
    log_event(
        RunPaths(child.run_id),
        "info",
        "warm restart created",
        **{k: lineage[k] for k in ("parent_run_id", "parent_checkpoint")},
    )
    return child


def resolve_warm_start(cfg: RunConfig) -> Path:
    """The parent checkpoint file a warm restart starts from, verified against the recorded digest."""
    ws = cfg.warm_start
    if ws is None:
        raise RunError("not a warm restart")
    from lunarlab.freeze import frozen_artifact_for

    path = frozen_artifact_for(ws.parent_run_id, ws.checkpoint_sha256)
    if path is None:
        path, entry = resolve_checkpoint(ws.parent_run_id, ws.checkpoint)
        if entry["sha256"] != ws.checkpoint_sha256:
            raise RunError(
                f"the parent checkpoint {ws.checkpoint} of run {ws.parent_run_id} no longer has the bytes this "
                "warm restart was created from"
            )
    return path


# --------------------------------------------------------------------------- #
# Test exposure and evidence role
# --------------------------------------------------------------------------- #


def test_seed_set_hash(protocol: EvalProtocol) -> str:
    canonical = json.dumps(sorted(protocol.test_seeds), separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _exposure_file() -> Path:
    return data_dir() / "test_exposure.jsonl"


def record_test_exposure(protocol: EvalProtocol, run_id: str, evaluation_file: str) -> None:
    """Note that a final-test result on these test seeds now exists (append-only)."""
    path = _exposure_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with hold(path.with_suffix(".lock")):
        append_jsonl(
            path,
            {
                "time": utc_now(),
                "test_seed_set": test_seed_set_hash(protocol),
                "test_seeds": sorted(protocol.test_seeds),
                "protocol_hash": protocol.protocol_hash(),
                "run_id": run_id,
                "evaluation_file": evaluation_file,
            },
        )


def first_test_exposure(protocol: EvalProtocol) -> dict | None:
    """The first recorded final-test result that used ANY of this protocol's test seeds, if any.

    Overlap counts, not only the identical set: a "holdout" that shares seeds with a test set whose
    results were already seen is not untouched. Runs tested before this registry existed are found
    through their test evaluation files too.
    """
    key = test_seed_set_hash(protocol)
    mine = set(protocol.test_seeds)

    def overlaps(r: dict) -> bool:
        seeds = r.get("test_seeds")
        return bool(mine & set(seeds)) if seeds else r.get("test_seed_set") == key

    recorded = [r for r in read_jsonl(_exposure_file()) if overlaps(r)]
    if recorded:
        return min(recorded, key=lambda r: r["time"])
    from lunarlab.storage import list_run_ids

    earliest: dict | None = None
    for rid in list_run_ids():
        try:
            cfg = load_config(rid)
        except Exception:  # noqa: BLE001 - an unreadable run cannot have exposed anything we can use
            continue
        if not mine & set(cfg.eval_protocol.test_seeds):
            continue
        for p in sorted(RunPaths(rid).evaluations.glob("test-*.json")):
            stamp = p.stem.rsplit("-", 1)[-1]
            if earliest is None or stamp < earliest["stamp"]:
                earliest = {"run_id": rid, "evaluation_file": p.name, "stamp": stamp, "time": None}
    return earliest


def evidence_role(meta: dict[str, Any]) -> str:
    """``confirmatory`` unless the run's design was influenced by an already-seen final test."""
    lineage = meta.get("lineage") or {}
    selection = meta.get("selection") or {}
    if lineage.get("post_test") or selection.get("test_set_previously_exposed"):
        return "exploratory"
    return "confirmatory"


def evidence_note(meta: dict[str, Any]) -> str | None:
    lineage = meta.get("lineage") or {}
    selection = meta.get("selection") or {}
    if lineage.get("post_test"):
        return (
            f"Derived from run {lineage.get('parent_run_id')} after its final test: a result on the same "
            "test seeds is exploratory, not a new held-out test."
        )
    if selection.get("test_set_previously_exposed"):
        return (
            "Settings selected by a study that started after these test seeds had already been used: "
            "exploratory. A confirmatory claim needs a protocol with untouched test seeds."
        )
    if lineage.get("kind") == "warm_restart":
        return f"Warm restart of run {lineage.get('parent_run_id')}: not a continuation of it."
    return None
