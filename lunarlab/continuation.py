"""Resumable DQN checkpoints: replay buffer and algorithm state next to the SB3 weights.

Checkpoint contract (docs/ARCHITECTURE.md):

* **inference checkpoint**: an SB3 ``.zip`` loaded weights-only; enough to evaluate, record or replay.
* **resumable training checkpoint**: continues the same run. PPO needs the ``.zip`` (policy and
  optimizer state) and the counters in the manifest; its partial rollout at a stop is discarded and
  recorded. DQN additionally needs everything below.
* **warm restart**: a *new* run initialised from a checkpoint's weights (``lunarlab.lineage``).

What SB3 2.9.0 keeps outside the ``.zip`` for DQN, and this module therefore stores:

* the replay buffer (``observations``, ``next_observations``, ``actions``, ``rewards``, ``dones``,
  ``timeouts``, plus ``pos`` and ``full``);
* ``num_timesteps``, ``_n_updates`` (gradient steps), ``_n_calls`` (the target-network update phase:
  the target is synchronised when ``_n_calls % (target_update_interval // n_envs) == 0``),
  ``_episode_num``, ``exploration_rate`` and ``_current_progress_remaining``;
* the schedule basis (the planned transitions the exploration schedule is computed over).

The online and target Q-networks and the Adam state are inside the ``.zip`` (``policy`` and
``policy.optimizer`` state dicts) and are restored by ``set_parameters``.

Storage is a strictly validated JSON file and an uncompressed ``.npz`` of numeric arrays. Before any
array is read, every member's ``.npy`` header is checked (no object dtypes, exactly the expected
names, shapes and dtypes), so a damaged or hostile file cannot make LunarLab allocate arbitrary
memory or unpickle anything; the files must also match the SHA-256 digests in the manifest. A digest
proves integrity against the manifest, not that an arbitrary file from elsewhere is trustworthy.
"""

from __future__ import annotations

import json
import math
import os
import secrets
import zipfile
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lunarlab.runs import DQN_CONTINUATION_FORMAT, RunError
from lunarlab.storage import RunPaths, sha256_file

FORMAT = DQN_CONTINUATION_FORMAT
VERSION = 1
REPLAY_ARRAYS = ("observations", "next_observations", "actions", "rewards", "dones", "timeouts")
MAX_REPLAY_BYTES = 4_000_000_000  # far above any supported DQNConfig; a backstop, not a budget


class ContinuationError(RunError):
    """A continuation bundle is missing, damaged or incompatible with the run."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ArraySpec(_Strict):
    shape: list[int] = Field(min_length=1, max_length=6)
    dtype: str = Field(max_length=16)


class ReplayState(_Strict):
    buffer_class: Literal["ReplayBuffer"]
    buffer_size: int = Field(ge=1, le=2_000_000)
    n_envs: int = Field(ge=1, le=64)
    pos: int = Field(ge=0)
    full: bool
    rows: int = Field(ge=0)
    optimize_memory_usage: bool
    handle_timeout_termination: bool
    obs_shape: list[int] = Field(min_length=1, max_length=4)
    action_dim: int = Field(ge=1, le=64)
    arrays: dict[str, ArraySpec]


class ContinuationState(_Strict):
    format: Literal["lunarlab.dqn-continuation"]
    version: Literal[1]
    sb3_version: str = Field(max_length=32)
    num_timesteps: int = Field(ge=0)
    n_updates: int = Field(ge=0)
    n_calls: int = Field(ge=0)
    episode_num: int = Field(ge=0)
    exploration_rate: float = Field(ge=0.0, le=1.0)
    current_progress_remaining: float = Field(ge=-1.0, le=1.0)
    total_timesteps_basis: int = Field(ge=1)
    learning_starts: int = Field(ge=0)
    target_update_interval: int = Field(ge=1)
    n_envs: int = Field(ge=1, le=64)
    replay: ReplayState
    replay_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


# --------------------------------------------------------------------------- #
# Capture and apply (pure: no files)
# --------------------------------------------------------------------------- #


def dqn_continuation_payload(model, *, total_timesteps_basis: int) -> tuple[dict, dict[str, np.ndarray]]:
    """The JSON-able state and the filled replay rows of a DQN model, at a safe boundary."""
    import stable_baselines3

    rb = model.replay_buffer
    if type(rb).__name__ != "ReplayBuffer":
        raise ContinuationError(f"unsupported replay buffer class {type(rb).__name__}")
    rows = rb.buffer_size if rb.full else rb.pos
    arrays = {
        "observations": rb.observations[:rows],
        "actions": rb.actions[:rows],
        "rewards": rb.rewards[:rows],
        "dones": rb.dones[:rows],
        "timeouts": rb.timeouts[:rows],
    }
    if not rb.optimize_memory_usage:
        arrays["next_observations"] = rb.next_observations[:rows]
    state = {
        "format": FORMAT,
        "version": VERSION,
        "sb3_version": stable_baselines3.__version__,
        "num_timesteps": int(model.num_timesteps),
        "n_updates": int(model._n_updates),
        "n_calls": int(model._n_calls),
        "episode_num": int(model._episode_num),
        "exploration_rate": float(model.exploration_rate),
        "current_progress_remaining": float(model._current_progress_remaining),
        "total_timesteps_basis": int(total_timesteps_basis),
        "learning_starts": int(model.learning_starts),
        "target_update_interval": int(model.target_update_interval),
        "n_envs": int(model.n_envs),
        "replay": {
            "buffer_class": type(rb).__name__,
            "buffer_size": int(rb.buffer_size),
            "n_envs": int(rb.n_envs),
            "pos": int(rb.pos),
            "full": bool(rb.full),
            "rows": int(rows),
            "optimize_memory_usage": bool(rb.optimize_memory_usage),
            "handle_timeout_termination": bool(rb.handle_timeout_termination),
            "obs_shape": [int(x) for x in rb.obs_shape],
            "action_dim": int(rb.action_dim),
            "arrays": {k: {"shape": list(a.shape), "dtype": a.dtype.str} for k, a in arrays.items()},
        },
    }
    return state, arrays


def _expected_arrays(replay: ReplayState) -> dict[str, tuple[tuple[int, ...], str]]:
    rows, n, obs = replay.rows, replay.n_envs, tuple(replay.obs_shape)
    shapes = {
        "observations": (rows, n, *obs),
        "actions": (rows, n, replay.action_dim),
        "rewards": (rows, n),
        "dones": (rows, n),
        "timeouts": (rows, n),
    }
    if not replay.optimize_memory_usage:
        shapes["next_observations"] = (rows, n, *obs)
    if set(replay.arrays) != set(shapes):
        raise ContinuationError(f"replay arrays {sorted(replay.arrays)} do not match the buffer layout")
    out = {}
    for k, shape in shapes.items():
        spec = replay.arrays[k]
        if tuple(spec.shape) != shape:
            raise ContinuationError(
                f"replay array {k}: declared shape {spec.shape} does not match the layout {shape}"
            )
        out[k] = (shape, spec.dtype)
    return out


def apply_dqn_continuation(model, state: dict, arrays: dict[str, np.ndarray]) -> None:
    """Restore a DQN model's replay buffer and counters from :func:`dqn_continuation_payload` output."""
    try:
        st = ContinuationState.model_validate(
            {**state, "replay_sha256": state.get("replay_sha256", "0" * 64)}
        )
    except ValidationError as exc:
        raise ContinuationError(f"invalid continuation state: {exc.errors()[0]['msg']}") from exc
    rb, rp = model.replay_buffer, st.replay
    if not hasattr(model, "_n_calls") or type(rb).__name__ != rp.buffer_class:
        raise ContinuationError("continuation state is for a DQN model with a ReplayBuffer")
    layout = {
        "buffer_size": (rb.buffer_size, rp.buffer_size),
        "n_envs": (rb.n_envs, rp.n_envs),
        "observation shape": (tuple(rb.obs_shape), tuple(rp.obs_shape)),
        "action dimension": (rb.action_dim, rp.action_dim),
        "optimize_memory_usage": (rb.optimize_memory_usage, rp.optimize_memory_usage),
        "handle_timeout_termination": (rb.handle_timeout_termination, rp.handle_timeout_termination),
        "target_update_interval": (model.target_update_interval, st.target_update_interval),
        "learning_starts": (model.learning_starts, st.learning_starts),
        "number of environments": (model.n_envs, st.n_envs),
    }
    diffs = [f"{k} {have} vs saved {saved}" for k, (have, saved) in layout.items() if have != saved]
    if diffs:
        raise ContinuationError("continuation state does not fit this model: " + "; ".join(diffs))
    if rp.full:
        if not (rp.rows == rp.buffer_size and 0 <= rp.pos < rp.buffer_size):
            raise ContinuationError("inconsistent replay state: a full buffer stores every row")
    elif rp.rows != rp.pos or rp.pos > rp.buffer_size:
        raise ContinuationError("inconsistent replay state: rows and position disagree")
    expected = _expected_arrays(rp)
    for k, (shape, dtype) in expected.items():
        a = arrays.get(k)
        if a is None or a.shape != shape or a.dtype != np.dtype(dtype) or a.dtype != getattr(rb, k).dtype:
            raise ContinuationError(f"replay array {k} has the wrong shape or dtype")
    for k in ("observations", "next_observations", "rewards"):
        if k in arrays and not np.all(np.isfinite(arrays[k])):
            raise ContinuationError(f"replay array {k} contains non-finite values")
    for k in ("dones", "timeouts"):
        if not np.all((arrays[k] == 0) | (arrays[k] == 1)):
            raise ContinuationError(f"replay array {k} must contain only 0 and 1")
    n_actions = getattr(model.action_space, "n", None)
    if (
        n_actions is not None
        and arrays["actions"].size
        and (arrays["actions"].min() < 0 or arrays["actions"].max() >= n_actions)
    ):
        raise ContinuationError("replay actions outside the action space")
    rows = rp.rows
    for k in expected:
        getattr(rb, k)[:rows] = arrays[k]
    rb.pos, rb.full = rp.pos, rp.full
    model.num_timesteps = st.num_timesteps
    model._n_updates = st.n_updates
    model._n_calls = st.n_calls
    model._episode_num = st.episode_num
    model._current_progress_remaining = st.current_progress_remaining
    # Set before learn() so the first resumed action already explores at the scheduled rate.
    model.exploration_rate = st.exploration_rate


# --------------------------------------------------------------------------- #
# Files
# --------------------------------------------------------------------------- #


def _fsync_write(path: Path, write) -> None:
    with open(path, "wb") as f:
        write(f)
        f.flush()
        os.fsync(f.fileno())


def write_replay_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    """Uncompressed (ZIP_STORED) ``.npz`` of plain numeric arrays."""
    for k, a in arrays.items():
        if a.dtype.hasobject:
            raise ContinuationError(f"refusing to store object array {k}")
    _fsync_write(path, lambda f: np.savez(f, **arrays))


def inspect_npz(path: Path) -> dict[str, tuple[tuple[int, ...], np.dtype]]:
    """Shapes and dtypes from every member's ``.npy`` header, without reading array data."""
    out: dict[str, tuple[tuple[int, ...], np.dtype]] = {}
    try:
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                name = info.filename
                if not name.endswith(".npy") or "/" in name or "\\" in name:
                    raise ContinuationError(f"unexpected member {name!r} in {path.name}")
                if info.compress_type != zipfile.ZIP_STORED:
                    raise ContinuationError(f"{path.name}: compressed members are not accepted")
                with z.open(info) as f:
                    version = np.lib.format.read_magic(f)
                    if version == (1, 0):
                        shape, _fortran, dtype = np.lib.format.read_array_header_1_0(f)
                    elif version == (2, 0):
                        shape, _fortran, dtype = np.lib.format.read_array_header_2_0(f)
                    else:
                        raise ContinuationError(f"{path.name}: unsupported .npy version {version}")
                if dtype.hasobject:
                    raise ContinuationError(
                        f"{path.name}: {name} has an object dtype (refused, never unpickled)"
                    )
                out[name.removesuffix(".npy")] = (tuple(int(x) for x in shape), dtype)
    except (zipfile.BadZipFile, ValueError, OSError) as exc:
        raise ContinuationError(f"{path.name} is not a valid replay archive: {exc}") from exc
    return out


def load_replay_npz(path: Path, *, expected: dict[str, tuple[tuple[int, ...], str]]) -> dict[str, np.ndarray]:
    """Load exactly the ``expected`` arrays after checking every header (``allow_pickle=False``)."""
    found = inspect_npz(path)
    if set(found) != set(expected):
        raise ContinuationError(f"{path.name}: arrays {sorted(found)} instead of {sorted(expected)}")
    total = 0
    for k, (shape, dtype) in expected.items():
        have_shape, have_dtype = found[k]
        if have_shape != tuple(shape):
            raise ContinuationError(f"{path.name}: {k} has shape {have_shape}, expected {tuple(shape)}")
        if have_dtype != np.dtype(dtype):
            raise ContinuationError(f"{path.name}: {k} has dtype {have_dtype}, expected {np.dtype(dtype)}")
        total += math.prod(have_shape) * have_dtype.itemsize
    if total > MAX_REPLAY_BYTES:
        raise ContinuationError(f"{path.name}: {total:,} bytes exceeds the replay size limit")
    with np.load(path, allow_pickle=False) as z:
        return {k: np.array(z[k]) for k in expected}


def stage_dqn_continuation(model, directory: Path, stem: str, *, total_timesteps_basis: int) -> dict:
    """Write the state and replay files to temporary names in ``directory`` and validate them.

    Returns the staged paths, their intended final names and digests. Nothing is final until
    the caller moves the files into place and publishes the manifest entry (the commit point).
    """
    token = secrets.token_hex(3)
    state, arrays = dqn_continuation_payload(model, total_timesteps_basis=total_timesteps_basis)
    replay_tmp = directory / f"{stem}.replay.npz.{token}.tmp"
    state_tmp = directory / f"{stem}.state.json.{token}.tmp"
    write_replay_npz(replay_tmp, arrays)
    expected = _expected_arrays(ReplayState.model_validate(state["replay"]))
    found = inspect_npz(replay_tmp)
    if {k: (s, d.str) for k, (s, d) in found.items()} != {
        k: (s, np.dtype(d).str) for k, (s, d) in expected.items()
    }:
        raise ContinuationError("the replay archive just written does not match its declared layout")
    state["replay_sha256"] = sha256_file(replay_tmp)
    ContinuationState.model_validate(state)
    _fsync_write(state_tmp, lambda f: f.write(json.dumps(state, indent=1).encode("utf-8")))
    return {
        "files": [(replay_tmp, f"{stem}.replay.npz"), (state_tmp, f"{stem}.state.json")],
        "replay_sha256": state["replay_sha256"],
        "replay_rows": state["replay"]["rows"],
    }


def verify_continuation_files(paths: RunPaths, entry: dict) -> None:
    """Cheap integrity check of a bundle's files (presence, size, SHA-256) without loading arrays."""
    cont = entry.get("continuation") or {}
    for part in ("state", "replay"):
        name = cont.get(f"{part}_file")
        if not isinstance(name, str) or Path(name).name != name:
            raise ContinuationError(f"invalid {part} file name in the manifest")
        p = paths.checkpoints / name
        if not p.exists():
            raise ContinuationError(f"continuation file is missing: {name}")
        if p.stat().st_size != cont.get(f"{part}_bytes") or sha256_file(p) != cont.get(f"{part}_sha256"):
            raise ContinuationError(f"{name} does not match its recorded SHA-256 (corrupt or modified)")


def read_continuation(paths: RunPaths, entry: dict) -> tuple[dict, dict[str, np.ndarray]]:
    """Verify and load a manifest entry's continuation bundle (state, replay arrays)."""
    cont = entry.get("continuation") or {}
    if cont.get("format") != FORMAT or cont.get("version") != VERSION:
        raise ContinuationError(f"checkpoint {entry.get('name')} has no supported DQN continuation bundle")
    if cont.get("pruned_at"):
        raise ContinuationError(
            f"the continuation files of {entry['name']} were pruned on {cont['pruned_at']}"
        )
    files = {}
    for part in ("state", "replay"):
        name = cont.get(f"{part}_file")
        if not isinstance(name, str) or Path(name).name != name:
            raise ContinuationError(f"invalid {part} file name in the manifest")
        p = paths.checkpoints / name
        if not p.exists():
            raise ContinuationError(f"continuation file is missing: {name}")
        if p.stat().st_size != cont.get(f"{part}_bytes"):
            raise ContinuationError(f"{name} does not have its recorded size (corrupt or replaced)")
        if sha256_file(p) != cont.get(f"{part}_sha256"):
            raise ContinuationError(f"{name} does not match its recorded SHA-256 (corrupt or modified)")
        files[part] = p
    try:
        raw = json.loads(files["state"].read_text(encoding="utf-8"))
        state = ContinuationState.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ContinuationError(f"invalid continuation state file: {exc}") from exc
    if state.replay_sha256 != cont.get("replay_sha256"):
        raise ContinuationError("state file and manifest disagree about the replay archive digest")
    if state.num_timesteps != entry.get("transitions"):
        raise ContinuationError("continuation state and checkpoint are at different transition counts")
    arrays = load_replay_npz(files["replay"], expected=_expected_arrays(state.replay))
    return state.model_dump(mode="json"), arrays


def restore_dqn_continuation(model, paths: RunPaths, entry: dict, *, total_timesteps_basis: int) -> dict:
    """Load a resumable DQN checkpoint's bundle into ``model`` (after ``set_parameters``)."""
    state, arrays = read_continuation(paths, entry)
    if state["total_timesteps_basis"] != total_timesteps_basis:
        raise ContinuationError(
            f"the exploration schedule was computed over {state['total_timesteps_basis']:,} transitions, "
            f"this run plans {total_timesteps_basis:,}"
        )
    if state["n_updates"] != entry.get("sb3_n_updates", state["n_updates"]):
        raise ContinuationError("continuation state and checkpoint disagree about the update count")
    apply_dqn_continuation(model, state, arrays)
    return state


def prune_continuations(paths: RunPaths, *, keep: int, now: str) -> list[str]:
    """Remove the replay/state files of all but the ``keep`` most recent resumable DQN checkpoints.

    Only superseded *training state* is removed; the checkpoint weights stay and remain usable for
    inference. Their manifest entries say when the continuation was pruned and stop being resumable.
    """
    from lunarlab.runs import mutate_manifest

    removed: list[str] = []

    def prune(manifest: dict) -> None:
        live = [
            c
            for c in manifest["checkpoints"]
            if (c.get("continuation") or {}).get("format") == FORMAT
            and not c["continuation"].get("pruned_at")
        ]
        live.sort(key=lambda c: c["transitions"], reverse=True)
        for c in live[keep:]:
            for part in ("replay", "state"):
                p = paths.checkpoints / c["continuation"][f"{part}_file"]
                try:
                    p.unlink()
                    removed.append(p.name)
                except FileNotFoundError:
                    pass
                except OSError:
                    return  # locked (e.g. an antivirus scan): try again at the next checkpoint
            c["continuation"]["pruned_at"] = now
            c["resumable"] = False

    mutate_manifest(paths, prune)
    return removed


def describe_entry(entry: dict, algo: str) -> dict[str, Any]:
    """What a checkpoint can be used for, in words the UI and CLI show."""
    from lunarlab.runs import is_resumable

    resumable = is_resumable(entry, algo)
    if entry.get("kind") in ("best_validation", "final"):
        role = "inference"
    elif resumable:
        role = "resumable"
    else:
        role = "inference (legacy: no continuation state)" if algo == "dqn" else "inference"
    return {"name": entry.get("name"), "role": role, "resumable": resumable}
