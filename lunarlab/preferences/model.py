"""Reward-model inference (NumPy) and the on-disk model registry.

Weights are stored as plain arrays in ``model.npz`` and loaded with
``allow_pickle=False``: loading a reward model cannot execute code. A model
directory is written once and never modified, so its id identifies the reward
function exactly (its SHA-256 is also recorded).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from lunarlab.storage import data_dir, read_json, safe_child, sha256_file

MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,95}$")
FEATURE_DIM = 20  # obs (8) + one-hot action (4) + next obs (8)


def models_dir() -> Path:
    p = data_dir() / "reward_models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def model_path(model_id: str) -> Path:
    if not MODEL_ID_RE.match(model_id or ""):
        raise ValueError(f"invalid reward model id: {model_id!r}")
    return safe_child(models_dir(), model_id)


def features(obs: np.ndarray, action: int, next_obs: np.ndarray) -> np.ndarray:
    f = np.zeros(FEATURE_DIM, dtype=np.float32)
    f[:8] = obs[:8]
    f[8 + int(action)] = 1.0
    f[12:20] = next_obs[:8]
    return f


def batch_features(obs: np.ndarray, actions: np.ndarray, next_obs: np.ndarray) -> np.ndarray:
    """obs, next_obs: (..., 8); actions: (...) ints → (..., 20)."""
    onehot = np.eye(4, dtype=np.float32)[actions.astype(np.int64)]
    return np.concatenate(
        [obs[..., :8].astype(np.float32), onehot, next_obs[..., :8].astype(np.float32)], axis=-1
    )


@dataclass
class RewardModel:
    """r(s, a, s') = ((MLP((φ - mu) / sigma)) - out_mean) / out_std, a tanh MLP."""

    mu: np.ndarray
    sigma: np.ndarray
    weights: list[tuple[np.ndarray, np.ndarray]]
    out_mean: float
    out_std: float
    model_id: str = ""

    def raw(self, x: np.ndarray) -> np.ndarray:
        h = (x - self.mu) / self.sigma
        for i, (w, b) in enumerate(self.weights):
            h = h @ w + b
            if i < len(self.weights) - 1:
                h = np.tanh(h)
        return h[..., 0]

    def __call__(self, obs: np.ndarray, action: int, next_obs: np.ndarray) -> float:
        r = self.raw(features(obs, action, next_obs)[None, :])[0]
        return float((r - self.out_mean) / self.out_std)

    def batch(self, x: np.ndarray) -> np.ndarray:
        return (self.raw(x) - self.out_mean) / self.out_std

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=False)
        arrays = {
            "mu": self.mu,
            "sigma": self.sigma,
            "out_mean": np.float64(self.out_mean),
            "out_std": np.float64(self.out_std),
            "n_layers": np.int64(len(self.weights)),
        }
        for i, (w, b) in enumerate(self.weights):
            arrays[f"w{i}"] = w.astype(np.float32)
            arrays[f"b{i}"] = b.astype(np.float32)
        path = directory / "model.npz"
        np.savez(path, **arrays)
        return path


def load_model_file(path: Path, model_id: str = "") -> RewardModel:
    with np.load(path, allow_pickle=False) as z:
        n = int(z["n_layers"])
        weights = [(z[f"w{i}"].astype(np.float32), z[f"b{i}"].astype(np.float32)) for i in range(n)]
        return RewardModel(
            mu=z["mu"].astype(np.float32),
            sigma=z["sigma"].astype(np.float32),
            weights=weights,
            out_mean=float(z["out_mean"]),
            out_std=float(z["out_std"]),
            model_id=model_id,
        )


@lru_cache(maxsize=16)
def load_reward_model(model_id: str) -> RewardModel:
    """Load a registered reward model and verify it against the SHA-256 recorded at training time."""
    d = model_path(model_id)
    path = d / "model.npz"
    meta = read_json(d / "meta.json", default=None)
    if not path.exists() or meta is None:
        raise FileNotFoundError(f"reward model {model_id!r} not found in {models_dir()}")
    if meta.get("sha256") and sha256_file(path) != meta["sha256"]:
        raise ValueError(f"reward model {model_id!r} does not match its recorded SHA-256")
    return load_model_file(path, model_id)


def list_models() -> list[dict]:
    out = []
    for d in sorted(models_dir().iterdir(), reverse=True) if models_dir().exists() else []:
        meta = read_json(d / "meta.json", default=None)
        if meta:
            out.append(meta)
    return out
