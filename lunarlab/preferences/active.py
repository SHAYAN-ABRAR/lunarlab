"""Active preference learning: a reward-model ensemble chooses which pairs to label next.

Strategies:

* ``random``: pairs of training segments drawn uniformly (the baseline);
* ``disagreement``: among a pool of random candidate pairs, the ones where the ensemble members
  disagree most about P(A preferred), measured as the standard deviation of the members'
  Bradley–Terry probabilities (Christiano et al., 2017, query selection by ensemble variance).

Pairs are unordered and never repeated: a pair that has been labelled is excluded from every later
selection. Only training episodes are used (``split_by_episode``), so labels never touch validation.

``run_active_learning`` simulates the whole loop with the Bradley–Terry labeller, deterministically per
pair (the same pair always gets the same answer whichever strategy asks), so strategies are compared on
equal terms. The human-labelling UI uses ``next_pair`` with an ensemble fitted on the labels so far.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from lunarlab.preferences.data import (
    SegmentSet,
    dataset_path,
    human_labels,
    label_value,
    oracle_pairs,
    partition_labels,
    split_by_episode,
)
from lunarlab.preferences.model import RewardEnsemble, RewardModel, model_path
from lunarlab.preferences.train import (
    _segment_features,
    fit_network,
    network_weights,
    normalization,
)
from lunarlab.storage import atomic_write_json, new_id, read_json, sha256_file, utc_now

STRATEGIES = ("random", "disagreement")
DEFAULT_MEMBERS = 5
DEFAULT_CANDIDATES = 2000


def pair_key(i: int, j: int) -> tuple[int, int]:
    return (int(i), int(j)) if i < j else (int(j), int(i))


def oracle_label(returns: np.ndarray, i: int, j: int, *, beta: float, seed: int) -> float:
    """Simulated human for one pair, deterministic per unordered pair: 1.0 if segment i is preferred."""
    a, b = pair_key(i, j)
    u = np.random.default_rng([seed, a, b]).random()
    prefers_a = u < 0.5 * (1.0 + np.tanh(0.5 * beta * (returns[a] - returns[b])))
    return float(prefers_a == (int(i) == a))


def candidate_pairs(
    pool: np.ndarray, exclude: set[tuple[int, int]], n: int, rng: np.random.Generator
) -> np.ndarray:
    """Up to ``n`` distinct unordered pairs from ``pool``, none of them in ``exclude``."""
    out: list[tuple[int, int]] = []
    seen = set(exclude)
    max_pairs = len(pool) * (len(pool) - 1) // 2
    attempts = 0
    while len(out) < n and len(seen) < max_pairs and attempts < 50 * max(n, 1):
        attempts += 1
        i, j = (int(x) for x in rng.choice(pool, size=2, replace=False))
        k = pair_key(i, j)
        if k not in seen:
            seen.add(k)
            out.append((i, j))
    return np.array(out, dtype=np.int64).reshape(-1, 2)


def fit_ensemble(
    X,
    feats: np.ndarray,
    train_idx: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
    pairs: tuple[np.ndarray, np.ndarray, np.ndarray],
    val_pairs: tuple[np.ndarray, np.ndarray, np.ndarray],
    *,
    members: int = DEFAULT_MEMBERS,
    seed: int = 0,
    epochs: int = 60,
    hidden: int = 64,
    lr: float = 1e-3,
    bootstrap: bool = True,
) -> RewardEnsemble:
    """Fit ``members`` networks, each on a bootstrap resample of the labelled pairs."""
    import torch

    rng = np.random.default_rng([seed, 4242])
    ti, tj, ty = pairs
    out = []
    for k in range(members):
        idx = rng.integers(0, len(ti), len(ti)) if bootstrap and members > 1 else np.arange(len(ti))
        net, _, _, _ = fit_network(
            X,
            (ti[idx], tj[idx], ty[idx]),
            val_pairs,
            seed=seed * 1000 + k,
            hidden=hidden,
            epochs=epochs,
            lr=lr,
        )
        with torch.no_grad():
            step = net(X[train_idx]).squeeze(-1).numpy()
        out.append(
            RewardModel(
                mu=mu,
                sigma=sigma,
                weights=network_weights(net),
                out_mean=float(step.mean()),
                out_std=float(step.std() + 1e-8),
            )
        )
    return RewardEnsemble(members=out)


def disagreement(ensemble: RewardEnsemble, feats: np.ndarray, pairs: np.ndarray) -> np.ndarray:
    """Standard deviation across members of P(first segment preferred), one value per pair."""
    if len(pairs) == 0:
        return np.zeros(0)
    seg_ids, inverse = np.unique(pairs.reshape(-1), return_inverse=True)
    returns = ensemble.member_raw(feats[seg_ids]).sum(-1)  # (members, unique segments)
    inv = inverse.reshape(-1, 2)
    diff = returns[:, inv[:, 0]] - returns[:, inv[:, 1]]
    prob = 0.5 * (1.0 + np.tanh(0.5 * diff))
    return prob.std(axis=0)


def ensemble_accuracy(ensemble: RewardEnsemble, feats: np.ndarray, i, j, y) -> float | None:
    keep = y != 0.5
    if not keep.any():
        return None
    ri = ensemble.batch(feats[i[keep]]).sum(-1)
    rj = ensemble.batch(feats[j[keep]]).sum(-1)
    return float(((ri > rj).astype(np.float32) == y[keep]).mean())


def _register(ensemble: RewardEnsemble, name: str, meta: dict[str, Any]) -> dict[str, Any]:
    model_id = new_id(name, prefix="rm")
    d = model_path(model_id)
    path = ensemble.save(d)
    meta = {"model_id": model_id, "created_at": utc_now(), "members": len(ensemble.members), **meta}
    meta["sha256"] = sha256_file(path)
    atomic_write_json(d / "meta.json", meta)
    return meta


def run_active_learning(
    dataset_id: str,
    *,
    strategy: str,
    budget: int = 1000,
    initial: int = 100,
    batch: int = 100,
    members: int = DEFAULT_MEMBERS,
    candidates: int = DEFAULT_CANDIDATES,
    seed: int = 0,
    beta: float = 0.05,
    epochs: int = 60,
    register: bool = False,
    progress=None,
) -> dict[str, Any]:
    """Simulated labelling loop. Returns the learning curve (validation metrics after each round)."""
    import torch

    previous = torch.get_num_threads()
    torch.set_num_threads(2)  # tiny networks: more threads only contend with other work
    try:
        return _run_active_learning(
            dataset_id,
            strategy=strategy,
            budget=budget,
            initial=initial,
            batch=batch,
            members=members,
            candidates=candidates,
            seed=seed,
            beta=beta,
            epochs=epochs,
            register=register,
            progress=progress,
        )
    finally:
        torch.set_num_threads(previous)


def _run_active_learning(
    dataset_id: str,
    *,
    strategy: str,
    budget: int,
    initial: int,
    batch: int,
    members: int,
    candidates: int,
    seed: int,
    beta: float,
    epochs: int,
    register: bool,
    progress,
) -> dict[str, Any]:
    import torch

    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {', '.join(STRATEGIES)}")
    if not 0 < initial <= budget:
        raise ValueError("need 0 < initial <= budget")
    seg = SegmentSet.load(dataset_path(dataset_id))
    split = split_by_episode(seg)
    feats = _segment_features(seg)
    returns = seg.returns
    mu, sigma = normalization(feats, split.train)
    X = torch.tensor((feats - mu) / sigma, dtype=torch.float32)
    # One fixed validation set for every strategy and round: comparable learning curves.
    vi, vj, vy, vy_true = oracle_pairs(
        returns, split.val, 600, beta=beta, rng=np.random.default_rng([seed, 991])
    )
    rng = np.random.default_rng([seed, 17])
    li: list[int] = []
    lj: list[int] = []
    ly: list[float] = []
    keys: set[tuple[int, int]] = set()

    def add(chosen: np.ndarray) -> None:
        for i, j in chosen:
            li.append(int(i))
            lj.append(int(j))
            ly.append(oracle_label(returns, int(i), int(j), beta=beta, seed=seed))
            keys.add(pair_key(i, j))

    add(candidate_pairs(split.train, keys, initial, rng))
    history: list[dict[str, Any]] = []
    while True:
        pairs = (np.array(li), np.array(lj), np.array(ly, np.float32))
        ens = fit_ensemble(
            X, feats, split.train, mu, sigma, pairs, (vi, vj, vy), members=members, seed=seed, epochs=epochs
        )
        step_val = ens.batch(feats[split.val])
        point = {
            "labels": len(li),
            "val_accuracy_vs_true_order": ensemble_accuracy(ens, feats, vi, vj, vy_true),
            "val_accuracy_vs_labels": ensemble_accuracy(ens, feats, vi, vj, vy),
            "segment_return_correlation": float(
                np.corrcoef(step_val.sum(1), seg.rewards[split.val].sum(1))[0, 1]
            ),
        }
        history.append(point)
        if progress:
            progress(point)
        if len(li) >= budget:
            break
        n = min(batch, budget - len(li))
        cand = candidate_pairs(
            split.train, keys, max(candidates, n) if strategy == "disagreement" else n, rng
        )
        if len(cand) == 0:
            break
        if strategy == "disagreement":
            chosen = cand[np.argsort(-disagreement(ens, feats, cand), kind="stable")[:n]]
        else:
            chosen = cand[:n]
        add(chosen)
    assert len(keys) == len(li), "a pair was labelled twice"
    out: dict[str, Any] = {
        "dataset_id": dataset_id,
        "strategy": strategy,
        "seed": seed,
        "budget": budget,
        "initial": initial,
        "batch": batch,
        "members": members,
        "candidates": candidates,
        "beta": beta,
        "split": split.describe(),
        "history": history,
    }
    if register:
        out["model"] = _register(
            ens,
            f"rm-active-{strategy}-{len(li)}",
            {
                "dataset_id": dataset_id,
                "kind": "ensemble",
                "strategy": strategy,
                "n_train_pairs": len(li),
                "n_human_labels": 0,
                "split": split.describe(),
                "label_model": f"Bradley–Terry simulated human, beta={beta}, on original segment return",
                "metrics": history[-1],
                "history": history,
            },
        )
    return out


# --------------------------------------------------------------------------- #
# Human labelling: pair selection, progress, the labelling ensemble
# --------------------------------------------------------------------------- #


def _labelling_file(dataset_id: str):
    return dataset_path(dataset_id) / "labelling.json"


def labelled_keys(dataset_id: str) -> set[tuple[int, int]]:
    return {pair_key(h["i"], h["j"]) for h in human_labels(dataset_id)}


def labelling_progress(dataset_id: str) -> dict[str, Any]:
    seg = SegmentSet.load(dataset_path(dataset_id))
    split = split_by_episode(seg)
    labels = human_labels(dataset_id)
    parts = partition_labels(labels, split)
    state = read_json(_labelling_file(dataset_id), default=None)
    n_train = split.train.size
    return {
        "labels": len(labels),
        "usable_for_training": len(parts["train"]),
        "in_validation_episodes": len(parts["val"]),
        "excluded": len(parts["excluded"]),
        "training_segments": int(n_train),
        "possible_pairs": int(n_train * (n_train - 1) // 2),
        "ensemble": state,
        "since_ensemble": len(labels) - (state or {}).get("n_human_labels_total", 0) if state else None,
        "strategies": {"random": True, "disagreement": bool(state)},
    }


def train_labelling_ensemble(
    dataset_id: str,
    *,
    simulated_pairs: int = 0,
    members: int = DEFAULT_MEMBERS,
    seed: int = 0,
    beta: float = 0.05,
) -> dict[str, Any]:
    """Fit an ensemble on the human labels from training episodes (plus, optionally, simulated pairs)
    and make it the dataset's labelling ensemble, used by the disagreement strategy."""
    import torch

    seg = SegmentSet.load(dataset_path(dataset_id))
    split = split_by_episode(seg)
    labels = human_labels(dataset_id)
    usable = partition_labels(labels, split)["train"]
    rng = np.random.default_rng([seed, 23])
    si, sj, sy, _ = (
        oracle_pairs(seg.returns, split.train, simulated_pairs, beta=beta, rng=rng)
        if simulated_pairs
        else (
            np.zeros(0, np.int64),
            np.zeros(0, np.int64),
            np.zeros(0, np.float32),
            None,
        )
    )
    ti = np.concatenate([np.array([h["i"] for h in usable], np.int64), si])
    tj = np.concatenate([np.array([h["j"] for h in usable], np.int64), sj])
    ty = np.concatenate([np.array([label_value(h["choice"]) for h in usable], np.float32), sy]).astype(
        np.float32
    )
    if len(ti) < 10:
        raise ValueError(
            f"need at least 10 labelled pairs from training episodes (have {len(ti)}); label more, or add simulated pairs"
        )
    feats = _segment_features(seg)
    mu, sigma = normalization(feats, split.train)
    X = torch.tensor((feats - mu) / sigma, dtype=torch.float32)
    vi, vj, vy, vy_true = oracle_pairs(
        seg.returns, split.val, 400, beta=beta, rng=np.random.default_rng([seed, 991])
    )
    previous = torch.get_num_threads()
    torch.set_num_threads(2)
    try:
        ens = fit_ensemble(
            X, feats, split.train, mu, sigma, (ti, tj, ty), (vi, vj, vy), members=members, seed=seed
        )
    finally:
        torch.set_num_threads(previous)
    meta = _register(
        ens,
        "rm-labelling",
        {
            "dataset_id": dataset_id,
            "kind": "labelling ensemble",
            "n_train_pairs": int(len(ti)),
            "n_human_labels": len(usable),
            "n_simulated_pairs": int(len(si)),
            "split": split.describe(),
            "metrics": {
                "val_accuracy_vs_true_order": ensemble_accuracy(ens, feats, vi, vj, vy_true),
                "val_accuracy_vs_labels": ensemble_accuracy(ens, feats, vi, vj, vy),
            },
        },
    )
    state = {
        "model_id": meta["model_id"],
        "created_at": meta["created_at"],
        "members": members,
        "n_human_labels": len(usable),
        "n_human_labels_total": len(labels),
        "n_simulated_pairs": int(len(si)),
        "metrics": meta["metrics"],
    }
    atomic_write_json(_labelling_file(dataset_id), state)
    return state


def next_pair(
    dataset_id: str, strategy: str = "random", rng: np.random.Generator | None = None
) -> dict[str, Any]:
    """The next pair for a person to label: never one they have labelled already, always from training
    episodes. ``disagreement`` needs the dataset's labelling ensemble."""
    from lunarlab.preferences.model import load_reward_model

    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {', '.join(STRATEGIES)}")
    seg = SegmentSet.load(dataset_path(dataset_id))
    split = split_by_episode(seg)
    rng = rng or np.random.default_rng()
    exclude = labelled_keys(dataset_id)
    if strategy == "random":
        cand = candidate_pairs(split.train, exclude, 1, rng)
        if not len(cand):
            raise LookupError("every pair of training segments has been labelled")
        return {"i": int(cand[0, 0]), "j": int(cand[0, 1]), "strategy": "random", "score": None}
    state = read_json(_labelling_file(dataset_id), default=None)
    if not state:
        raise LookupError("no labelling ensemble yet: fit one from your labels first")
    ens = load_reward_model(state["model_id"])
    if not isinstance(ens, RewardEnsemble):
        raise LookupError("the labelling model is not an ensemble")
    cand = candidate_pairs(split.train, exclude, DEFAULT_CANDIDATES, rng)
    if not len(cand):
        raise LookupError("every pair of training segments has been labelled")
    scores = disagreement(ens, _segment_features(seg), cand)
    k = int(np.argmax(scores))
    return {
        "i": int(cand[k, 0]),
        "j": int(cand[k, 1]),
        "strategy": "disagreement",
        "score": float(scores[k]),
        "candidates": int(len(cand)),
        "median_score": float(np.median(scores)),
    }


# --------------------------------------------------------------------------- #
# Simulated studies: strategies x seeds, saved with the dataset
# --------------------------------------------------------------------------- #


def studies_dir(dataset_id: str):
    p = dataset_path(dataset_id) / "active"
    p.mkdir(parents=True, exist_ok=True)
    return p


def summarize_curves(runs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Per strategy and label count: mean, min and max over seeds of the validation accuracy."""
    out: dict[str, list[dict[str, Any]]] = {}
    for strategy in sorted({r["strategy"] for r in runs}):
        by_labels: dict[int, list[float]] = {}
        for r in runs:
            if r["strategy"] != strategy:
                continue
            for h in r["history"]:
                if h["val_accuracy_vs_true_order"] is not None:
                    by_labels.setdefault(h["labels"], []).append(h["val_accuracy_vs_true_order"])
        out[strategy] = [
            {
                "labels": n,
                "mean": float(np.mean(v)),
                "min": float(np.min(v)),
                "max": float(np.max(v)),
                "n_seeds": len(v),
            }
            for n, v in sorted(by_labels.items())
        ]
    return out


def run_active_study(
    dataset_id: str,
    *,
    strategies: list[str],
    seeds: list[int],
    echo=print,
    **kwargs,
) -> dict[str, Any]:
    """Every strategy with every seed (each seed shares its initial labels across strategies)."""
    runs = []
    for seed in seeds:
        for strategy in strategies:
            r = run_active_learning(dataset_id, strategy=strategy, seed=seed, **kwargs)
            last = r["history"][-1]
            echo(
                f"{strategy:<13} seed {seed}: {last['labels']} labels -> accuracy vs true order "
                f"{last['val_accuracy_vs_true_order']:.3f}"
            )
            runs.append(r)
    study_id = new_id("active", prefix="al")
    study = {
        "study_id": study_id,
        "created_at": utc_now(),
        "dataset_id": dataset_id,
        "strategies": strategies,
        "seeds": seeds,
        "params": {k: v for k, v in kwargs.items() if k not in ("progress",)},
        "summary": summarize_curves(runs),
        "runs": runs,
    }
    atomic_write_json(studies_dir(dataset_id) / f"{study_id}.json", study)
    return study


def list_active_studies(dataset_id: str) -> list[dict[str, Any]]:
    out = []
    for f in sorted(studies_dir(dataset_id).glob("al-*.json"), reverse=True):
        s = read_json(f, default=None)
        if s:
            out.append(
                {
                    k: s[k]
                    for k in (
                        "study_id",
                        "created_at",
                        "dataset_id",
                        "strategies",
                        "seeds",
                        "params",
                        "summary",
                    )
                }
            )
    return out
