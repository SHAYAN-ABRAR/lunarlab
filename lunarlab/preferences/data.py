# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Trajectory segments and preference labels.

Segments are short windows (default 40 steps = 0.8 s of simulated time) cut from real
episodes flown by a mix of policies: random, Gymnasium's heuristic and PPO checkpoints at
several training stages. The mix matters: a reward model only learns about states it is
shown, and the policy trained on it will find the states it was not shown.

Labels come from a *simulated human*: for a pair (A, B) it prefers A with probability
sigmoid(beta * (R_A - R_B)), where R is the segment's original environment return
(Bradley–Terry noise; small differences are hard to judge). Noise-free labels are kept
separately to measure how well a reward model recovers the true ordering. Real human labels
from the UI are stored next to the dataset and can be mixed in.

Episode seeds for collection start at 30,000, disjoint from training workers, validation
(10,000+) and final test (20,000+).

Train/validation isolation is by **whole episode**: segments cut from one episode overlap in
time and look alike, so all of them sit on the same side of the split. The split is a fixed
property of the dataset (``split_by_episode`` with the default seed), so pairs shown to people
for labelling are drawn from training episodes only, and labels that touch validation episodes
are never used for training.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from lunarlab.env import make_env
from lunarlab.policies import Policy
from lunarlab.storage import (
    append_jsonl,
    atomic_write_json,
    data_dir,
    new_id,
    read_json,
    read_jsonl,
    safe_child,
    utc_now,
)

SEGMENT_LEN = 40
COLLECTION_SEED_BASE = 30_000
VAL_FRACTION = 0.2  # fraction of *episodes* held out for validation
SPLIT_SEED = 0  # the dataset's fixed split; reward models and the labelling UI share it


def datasets_dir() -> Path:
    p = data_dir() / "preferences"
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class SegmentSet:
    obs: np.ndarray  # (N, L+1, 8) float32
    actions: np.ndarray  # (N, L) int64
    rewards: np.ndarray  # (N, L) float32, original environment reward
    terminal: np.ndarray  # (N,) bool: the segment ends with a true termination
    source: np.ndarray  # (N,) int64 index into ``sources``
    episode_seed: np.ndarray  # (N,) int64
    start: np.ndarray  # (N,) int64 step index of the segment start within its episode
    sources: list[str]

    def __len__(self) -> int:
        return int(self.obs.shape[0])

    @property
    def returns(self) -> np.ndarray:
        return self.rewards.sum(axis=1)

    def save(self, directory: Path, meta: dict) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "segments.npz",
            obs=self.obs,
            actions=self.actions,
            rewards=self.rewards,
            terminal=self.terminal,
            source=self.source,
            episode_seed=self.episode_seed,
            start=self.start,
        )
        atomic_write_json(directory / "meta.json", {**meta, "sources": self.sources, "n_segments": len(self)})

    @classmethod
    def load(cls, directory: Path) -> SegmentSet:
        meta = read_json(directory / "meta.json")
        with np.load(directory / "segments.npz", allow_pickle=False) as z:
            return cls(
                obs=z["obs"],
                actions=z["actions"],
                rewards=z["rewards"],
                terminal=z["terminal"],
                source=z["source"],
                episode_seed=z["episode_seed"],
                start=z["start"],
                sources=list(meta["sources"]),
            )


@dataclass(frozen=True)
class EpisodeSplit:
    """Segment indices of the training and validation episodes (sorted, disjoint)."""

    train: np.ndarray
    val: np.ndarray
    train_episodes: int
    val_episodes: int
    seed: int
    val_fraction: float

    def describe(self) -> dict:
        return {
            "method": "episode",
            "seed": self.seed,
            "val_fraction": self.val_fraction,
            "train_episodes": self.train_episodes,
            "val_episodes": self.val_episodes,
            "train_segments": int(self.train.size),
            "val_segments": int(self.val.size),
        }


def episode_ids(seg: SegmentSet) -> np.ndarray:
    """One integer per segment identifying its episode (policy source + episode seed)."""
    keys = np.stack([seg.source.astype(np.int64), seg.episode_seed.astype(np.int64)], axis=1)
    _, inverse = np.unique(keys, axis=0, return_inverse=True)
    return inverse.reshape(-1)


def split_by_episode(
    seg: SegmentSet, *, val_fraction: float = VAL_FRACTION, seed: int = SPLIT_SEED
) -> EpisodeSplit:
    """Hold out whole episodes for validation (deterministic for a given dataset and seed)."""
    ep = episode_ids(seg)
    n_ep = int(ep.max()) + 1 if ep.size else 0
    if n_ep < 2:
        raise ValueError("a preference dataset needs segments from at least 2 episodes to split")
    n_val = min(n_ep - 1, max(1, int(round(val_fraction * n_ep))))
    order = np.random.default_rng(seed).permutation(n_ep)
    val_mask = np.isin(ep, order[:n_val])
    return EpisodeSplit(
        train=np.flatnonzero(~val_mask),
        val=np.flatnonzero(val_mask),
        train_episodes=n_ep - n_val,
        val_episodes=n_val,
        seed=seed,
        val_fraction=val_fraction,
    )


def label_value(choice: str) -> float:
    return 1.0 if choice == "a" else 0.0 if choice == "b" else 0.5


def partition_labels(labels: list[dict], split: EpisodeSplit) -> dict[str, list[dict]]:
    """Sort labelled pairs by where their segments lie: both in training episodes ('train'),
    both in validation episodes ('val'), or one on each side ('excluded': never used)."""
    train_set = frozenset(int(x) for x in split.train)
    val_set = frozenset(int(x) for x in split.val)
    out: dict[str, list[dict]] = {"train": [], "val": [], "excluded": []}
    for lab in labels:
        i, j = int(lab["i"]), int(lab["j"])
        if i in train_set and j in train_set:
            out["train"].append(lab)
        elif i in val_set and j in val_set:
            out["val"].append(lab)
        else:
            out["excluded"].append(lab)
    return out


class DuplicateLabel(ValueError):
    """The pair (in either order) has already been labelled."""


def run_episode_record(policy: Policy, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, bool]:
    env = make_env()
    try:
        obs, _ = env.reset(seed=int(seed))
        policy.reset(int(seed))
        if hasattr(policy, "network"):  # stochastic SB3 policies sample with torch: make it reproducible
            import torch

            torch.manual_seed(int(seed))
        observations, actions, rewards = [obs.copy()], [], []
        terminated = False
        while True:
            a = policy.act(obs)
            obs, r, terminated, truncated, _ = env.step(a)
            observations.append(obs.copy())
            actions.append(a)
            rewards.append(float(r))
            if terminated or truncated:
                break
        return (
            np.array(observations, np.float32),
            np.array(actions, np.int64),
            np.array(rewards, np.float32),
            bool(terminated),
        )
    finally:
        env.close()


def collect_segments(
    policies: list[tuple[str, Policy]],
    *,
    episodes_per_policy: int,
    segment_len: int = SEGMENT_LEN,
    segments_per_episode: int = 3,
    rng_seed: int = 0,
    progress=None,
) -> SegmentSet:
    rng = np.random.default_rng(rng_seed)
    seg_obs, seg_act, seg_rew, seg_term, seg_src, seg_seed, seg_start = [], [], [], [], [], [], []
    for pi, (name, policy) in enumerate(policies):
        for e in range(episodes_per_policy):
            seed = COLLECTION_SEED_BASE + 1000 * pi + e
            obs, acts, rews, terminated = run_episode_record(policy, seed)
            n = len(acts)
            if n < segment_len:
                continue
            # Always keep the final window (episode endings matter most), plus random earlier ones.
            starts = {n - segment_len}
            for _ in range(segments_per_episode * 3):
                if len(starts) >= segments_per_episode:
                    break
                cand = int(rng.integers(0, n - segment_len + 1))
                if all(abs(cand - s) >= segment_len // 2 for s in starts):
                    starts.add(cand)
            for st in sorted(starts):
                seg_obs.append(obs[st : st + segment_len + 1])
                seg_act.append(acts[st : st + segment_len])
                seg_rew.append(rews[st : st + segment_len])
                seg_term.append(bool(terminated and st + segment_len == n))
                seg_src.append(pi)
                seg_seed.append(seed)
                seg_start.append(st)
            if progress:
                progress(name, e + 1, episodes_per_policy)
    return SegmentSet(
        obs=np.stack(seg_obs),
        actions=np.stack(seg_act),
        rewards=np.stack(seg_rew),
        terminal=np.array(seg_term),
        source=np.array(seg_src, np.int64),
        episode_seed=np.array(seg_seed, np.int64),
        start=np.array(seg_start, np.int64),
        sources=[n for n, _ in policies],
    )


def oracle_pairs(
    returns: np.ndarray, indices: np.ndarray, n_pairs: int, *, beta: float, rng: np.random.Generator
):
    """Random pairs within ``indices`` labelled by a Bradley–Terry simulated human.

    Returns (i, j, y_noisy, y_true): y = 1 means segment i is preferred.
    """
    i = rng.choice(indices, size=n_pairs)
    j = rng.choice(indices, size=n_pairs)
    keep = i != j
    i, j = i[keep], j[keep]
    diff = returns[i] - returns[j]
    p = 0.5 * (1.0 + np.tanh(0.5 * beta * diff))  # sigmoid(beta * diff), overflow-free
    y = (rng.random(i.size) < p).astype(np.float32)
    y_true = (diff > 0).astype(np.float32) + 0.5 * (diff == 0)
    return i, j, y, y_true


def create_dataset(
    policies: list[tuple[str, Policy]],
    *,
    episodes_per_policy: int,
    name: str = "prefs",
    rng_seed: int = 0,
    progress=None,
) -> str:
    seg = collect_segments(
        policies, episodes_per_policy=episodes_per_policy, rng_seed=rng_seed, progress=progress
    )
    dataset_id = new_id(name, prefix="ds")
    seg.save(
        datasets_dir() / dataset_id,
        {
            "dataset_id": dataset_id,
            "created_at": utc_now(),
            "segment_len": int(seg.actions.shape[1]),
            "episodes_per_policy": episodes_per_policy,
            "collection_seed_base": COLLECTION_SEED_BASE,
            "rng_seed": rng_seed,
            "segment_return": {
                "mean": float(seg.returns.mean()),
                "std": float(seg.returns.std()),
                "min": float(seg.returns.min()),
                "max": float(seg.returns.max()),
            },
            "segments_per_source": {n: int((seg.source == k).sum()) for k, n in enumerate(seg.sources)},
        },
    )
    return dataset_id


def dataset_path(dataset_id: str) -> Path:
    return safe_child(datasets_dir(), dataset_id)


def add_human_label(dataset_id: str, i: int, j: int, choice: str) -> dict:
    """Record a human preference: choice is 'a' (segment i), 'b' (segment j) or 'tie'."""
    if choice not in ("a", "b", "tie"):
        raise ValueError("choice must be 'a', 'b' or 'tie'")
    meta = read_json(dataset_path(dataset_id) / "meta.json")
    n = int(meta["n_segments"])
    if not (0 <= i < n and 0 <= j < n) or i == j:
        raise ValueError("invalid segment indices")
    key = (min(i, j), max(i, j))
    if any((min(h["i"], h["j"]), max(h["i"], h["j"])) == key for h in human_labels(dataset_id)):
        raise DuplicateLabel("this pair has already been labelled")
    entry = {"i": int(i), "j": int(j), "choice": choice, "time": utc_now()}
    append_jsonl(dataset_path(dataset_id) / "human_labels.jsonl", entry)
    return entry


def human_labels(dataset_id: str) -> list[dict]:
    return read_jsonl(dataset_path(dataset_id) / "human_labels.jsonl")


def list_datasets() -> list[dict]:
    out = []
    for d in sorted(datasets_dir().iterdir(), reverse=True) if datasets_dir().exists() else []:
        meta = read_json(d / "meta.json", default=None)
        if meta:
            meta["human_labels"] = len(read_jsonl(d / "human_labels.jsonl"))
            out.append(meta)
    return out


def _segment_json(seg: SegmentSet, index: int) -> dict:
    from lunarlab.env import scene_for_seed

    scene = scene_for_seed(int(seg.episode_seed[index]))  # terrain depends only on the reset seed
    return {
        "index": index,
        "episode_seed": int(seg.episode_seed[index]),
        "start": int(seg.start[index]),
        "obs": np.round(seg.obs[index], 5).tolist(),
        "actions": seg.actions[index].tolist(),
        "terminal": bool(seg.terminal[index]),
        "scene": {k: scene[k] for k in ("terrain", "helipad", "world", "obs_to_world")},
    }


def segment_payload(dataset_id: str, index: int) -> dict:
    """One segment as JSON (for the human-labelling UI). The source policy and the segment's
    return are deliberately not included: the labeller judges the flight itself."""
    seg = SegmentSet.load(dataset_path(dataset_id))
    if not 0 <= index < len(seg):
        raise IndexError(index)
    return _segment_json(seg, index)


def random_pair(dataset_id: str, rng: np.random.Generator | None = None) -> dict:
    """Two different segments for a human to compare (sources and returns hidden).

    Both come from the dataset's training episodes, so a label given here can be used to fit a
    reward model without touching validation data."""
    seg = SegmentSet.load(dataset_path(dataset_id))
    split = split_by_episode(seg)
    rng = rng or np.random.default_rng()
    i, j = (int(x) for x in rng.choice(split.train, size=2, replace=False))
    return {"dataset_id": dataset_id, "i": i, "j": j, "a": _segment_json(seg, i), "b": _segment_json(seg, j)}


def label_and_reveal(dataset_id: str, i: int, j: int, choice: str) -> dict:
    """Record a human label, then reveal what the environment's own reward said about the pair."""
    entry = add_human_label(dataset_id, i, j, choice)
    seg = SegmentSet.load(dataset_path(dataset_id))
    ri, rj = float(seg.returns[i]), float(seg.returns[j])
    better = "a" if ri > rj else "b" if rj > ri else "tie"
    return {
        "entry": entry,
        "returns": {"a": ri, "b": rj},
        "sources": {"a": seg.sources[int(seg.source[i])], "b": seg.sources[int(seg.source[j])]},
        "reward_prefers": better,
        "agrees": choice == better,
        "n_labels": len(human_labels(dataset_id)),
    }
