"""Train a reward model from pairwise preferences (Bradley–Terry / logistic loss).

For a pair (A, B) the model predicts P(A preferred) = sigmoid(sum_t r(A_t) - sum_t r(B_t)),
the standard setup of Christiano et al. (2017).

Train/validation isolation is by **whole episode** (``split_by_episode``, the dataset's fixed
split): simulated pairs are drawn inside each side, and human labels are used for training only
when both segments come from training episodes. Labels with both segments in validation episodes
are reported as a separate metric; labels that straddle the split are never used.

Reported quality, on validation episodes:
* accuracy against the simulated human's (noisy) labels and against the noise-free ordering;
* accuracy against human labels, when people labelled validation pairs;
* correlation of the model's per-step reward with the true per-step environment reward;
* correlation of summed segment rewards with true segment returns.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from lunarlab.preferences.data import (
    SPLIT_SEED,
    VAL_FRACTION,
    EpisodeSplit,
    SegmentSet,
    dataset_path,
    human_labels,
    label_value,
    oracle_pairs,
    partition_labels,
    split_by_episode,
)
from lunarlab.preferences.model import RewardModel, batch_features, model_path
from lunarlab.storage import atomic_write_json, new_id, sha256_file, utc_now


def _segment_features(seg: SegmentSet) -> np.ndarray:
    return batch_features(seg.obs[:, :-1], seg.actions, seg.obs[:, 1:])  # (N, L, 20)


@dataclass
class PairSet:
    """Labelled pairs ready for fitting. y = 1 means segment i is preferred (0.5 = tie)."""

    train_i: np.ndarray
    train_j: np.ndarray
    train_y: np.ndarray
    val_i: np.ndarray
    val_j: np.ndarray
    val_y: np.ndarray
    val_y_true: np.ndarray
    human_val_i: np.ndarray
    human_val_j: np.ndarray
    human_val_y: np.ndarray
    n_human_train: int
    n_human_excluded: int


def assemble_pairs(
    seg: SegmentSet,
    split: EpisodeSplit,
    *,
    n_pairs: int,
    beta: float,
    rng: np.random.Generator,
    labels: list[dict] | None = None,
) -> PairSet:
    """Simulated pairs inside each side of the split, plus human labels by where they fall.

    Every training pair has both segments in training episodes; every validation pair has both in
    validation episodes. This is the invariant the regression tests check.
    """
    returns = seg.returns
    n_train_pairs = int(round(n_pairs * (1 - split.val_fraction)))
    ti, tj, ty, _ = oracle_pairs(returns, split.train, n_train_pairs, beta=beta, rng=rng)
    vi, vj, vy, vy_true = oracle_pairs(
        returns, split.val, max(200, n_pairs - n_train_pairs), beta=beta, rng=rng
    )
    parts = partition_labels(labels or [], split)

    def arrays(rows: list[dict]):
        return (
            np.array([int(r["i"]) for r in rows], np.int64),
            np.array([int(r["j"]) for r in rows], np.int64),
            np.array([label_value(r["choice"]) for r in rows], np.float32),
        )

    hi, hj, hy = arrays(parts["train"])
    hvi, hvj, hvy = arrays(parts["val"])
    return PairSet(
        train_i=np.concatenate([ti, hi]),
        train_j=np.concatenate([tj, hj]),
        train_y=np.concatenate([ty, hy]).astype(np.float32),
        val_i=vi,
        val_j=vj,
        val_y=vy,
        val_y_true=vy_true,
        human_val_i=hvi,
        human_val_j=hvj,
        human_val_y=hvy,
        n_human_train=len(parts["train"]),
        n_human_excluded=len(parts["excluded"]),
    )


def normalization(feats: np.ndarray, train_idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Feature mean/std from training segments only (one-hot action columns left unscaled)."""
    steps = feats[train_idx].reshape(-1, feats.shape[-1])
    mu = steps.mean(axis=0)
    sigma = steps.std(axis=0) + 1e-6
    sigma[8:12] = 1.0
    mu[8:12] = 0.0
    return mu.astype(np.float32), sigma.astype(np.float32)


def fit_network(
    X,
    pairs: tuple[np.ndarray, np.ndarray, np.ndarray],
    val_pairs: tuple[np.ndarray, np.ndarray, np.ndarray],
    *,
    seed: int,
    hidden: int = 64,
    epochs: int = 80,
    lr: float = 1e-3,
    patience: int = 12,
):
    """Fit one tanh MLP on (i, j, y) pairs with early stopping on the validation loss.

    ``X`` is a float tensor (segments, steps, features). Returns (network, history, best_epoch,
    best_val_loss)."""
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    net = nn.Sequential(
        nn.Linear(X.shape[-1], hidden), nn.Tanh(), nn.Linear(hidden, hidden), nn.Tanh(), nn.Linear(hidden, 1)
    )
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-5)
    bce = nn.BCEWithLogitsLoss()

    def logits(i, j):
        return net(X[i]).squeeze(-1).sum(-1) - net(X[j]).squeeze(-1).sum(-1)

    ti, tj, ty = (torch.as_tensor(a) for a in pairs)
    vi, vj, vy = (torch.as_tensor(a) for a in val_pairs)
    best = (float("inf"), None, 0)
    history = []
    gen = torch.Generator().manual_seed(seed)
    for epoch in range(epochs):
        net.train()
        order = torch.randperm(len(ti), generator=gen)
        for k in range(0, len(order), 128):
            b = order[k : k + 128]
            loss = bce(logits(ti[b], tj[b]), ty[b])
            opt.zero_grad()
            loss.backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            vloss = float(bce(logits(vi, vj), vy))
            tloss = float(bce(logits(ti, tj), ty))
        history.append({"epoch": epoch + 1, "train_loss": tloss, "val_loss": vloss})
        if vloss < best[0] - 1e-4:
            best = (vloss, {k: v.clone() for k, v in net.state_dict().items()}, epoch + 1)
        elif epoch + 1 - best[2] >= patience:
            break  # early stopping on validation loss
    net.load_state_dict(best[1])
    net.eval()
    return net, history, best[2], best[0]


def network_weights(net) -> list[tuple[np.ndarray, np.ndarray]]:
    import torch.nn as nn

    layers = [m for m in net if isinstance(m, nn.Linear)]
    return [(m.weight.detach().numpy().T.copy(), m.bias.detach().numpy().copy()) for m in layers]


def pair_accuracy(
    model: RewardModel, feats: np.ndarray, i: np.ndarray, j: np.ndarray, y: np.ndarray
) -> float | None:
    """Fraction of non-tie pairs ordered like ``y`` by the model's summed reward."""
    keep = y != 0.5
    if not keep.any():
        return None
    ri = model.batch(feats[i[keep]]).sum(-1)
    rj = model.batch(feats[j[keep]]).sum(-1)
    return float(((ri > rj).astype(np.float32) == y[keep]).mean())


def train_reward_model(dataset_id: str, *, n_pairs: int, threads: int = 2, **kwargs) -> dict:
    """Fit and register a reward model. ``threads`` caps torch's intra-op threads while fitting:
    the model is tiny, and the default (all cores) is much slower on a machine already busy
    training policies."""
    import torch

    previous = torch.get_num_threads()
    torch.set_num_threads(max(1, threads))
    try:
        return _train_reward_model(dataset_id, n_pairs=n_pairs, **kwargs)
    finally:
        torch.set_num_threads(previous)


def _train_reward_model(
    dataset_id: str,
    *,
    n_pairs: int,
    beta: float = 0.05,
    seed: int = 0,
    hidden: int = 64,
    epochs: int = 80,
    lr: float = 1e-3,
    val_fraction: float = VAL_FRACTION,
    split_seed: int = SPLIT_SEED,
    include_human: bool = False,
    name: str | None = None,
    members: int = 1,
) -> dict:
    import torch

    rng = np.random.default_rng(seed)
    seg = SegmentSet.load(dataset_path(dataset_id))
    split = split_by_episode(seg, val_fraction=val_fraction, seed=split_seed)
    feats = _segment_features(seg)
    pairs = assemble_pairs(
        seg,
        split,
        n_pairs=n_pairs,
        beta=beta,
        rng=rng,
        labels=human_labels(dataset_id) if include_human else None,
    )
    mu, sigma = normalization(feats, split.train)
    X = torch.tensor((feats - mu) / sigma, dtype=torch.float32)  # (N, L, 20)
    if members > 1:
        return _register_ensemble(
            dataset_id,
            seg,
            feats,
            split,
            pairs,
            X,
            mu,
            sigma,
            members=members,
            seed=seed,
            n_pairs=n_pairs,
            beta=beta,
            hidden=hidden,
            epochs=epochs,
            lr=lr,
            name=name,
        )
    net, history, best_epoch, best_val = fit_network(
        X,
        (pairs.train_i, pairs.train_j, pairs.train_y),
        (pairs.val_i, pairs.val_j, pairs.val_y),
        seed=seed,
        hidden=hidden,
        epochs=epochs,
        lr=lr,
    )
    with torch.no_grad():
        step_r_train = net(X[split.train]).squeeze(-1).numpy()
    model = RewardModel(
        mu=mu,
        sigma=sigma,
        weights=network_weights(net),
        out_mean=float(step_r_train.mean()),
        out_std=float(step_r_train.std() + 1e-8),
    )
    metrics = evaluate_model(model, seg, feats, split, pairs)
    metrics |= {"best_epoch": best_epoch, "val_loss": best_val}

    model_id = new_id(name or f"rm-{n_pairs}pairs", prefix="rm")
    d = model_path(model_id)
    path = model.save(d)
    meta = {
        "model_id": model_id,
        "created_at": utc_now(),
        "dataset_id": dataset_id,
        "n_pairs_requested": n_pairs,
        "n_train_pairs": int(len(pairs.train_i)),
        "n_val_pairs": int(len(pairs.val_i)),
        "n_human_labels": pairs.n_human_train,
        "n_human_val_labels": int(len(pairs.human_val_i)),
        "n_human_excluded": pairs.n_human_excluded,
        "n_train_segments": int(split.train.size),
        "n_val_segments": int(split.val.size),
        "split": split.describe(),
        "label_model": f"Bradley–Terry simulated human, beta={beta}, on original segment return",
        "beta": beta,
        "seed": seed,
        "architecture": f"MLP 20-{hidden}-{hidden}-1 tanh on (obs, one-hot action, next obs)",
        "output_normalisation": {"mean": model.out_mean, "std": model.out_std},
        "metrics": metrics,
        "history": history,
        "sha256": sha256_file(path),
    }
    atomic_write_json(d / "meta.json", meta)
    return meta


def _register_ensemble(
    dataset_id,
    seg,
    feats,
    split,
    pairs,
    X,
    mu,
    sigma,
    *,
    members,
    seed,
    n_pairs,
    beta,
    hidden,
    epochs,
    lr,
    name,
):
    """Same data and split as a single model, fitted as an ensemble on bootstrap resamples."""
    from lunarlab.preferences.active import fit_ensemble

    ens = fit_ensemble(
        X,
        feats,
        split.train,
        mu,
        sigma,
        (pairs.train_i, pairs.train_j, pairs.train_y),
        (pairs.val_i, pairs.val_j, pairs.val_y),
        members=members,
        seed=seed,
        epochs=epochs,
        hidden=hidden,
        lr=lr,
    )
    metrics = evaluate_model(ens, seg, feats, split, pairs)
    model_id = new_id(name or f"rm-{n_pairs}pairs-x{members}", prefix="rm")
    d = model_path(model_id)
    path = ens.save(d)
    meta = {
        "model_id": model_id,
        "created_at": utc_now(),
        "kind": "ensemble",
        "members": members,
        "dataset_id": dataset_id,
        "n_pairs_requested": n_pairs,
        "n_train_pairs": int(len(pairs.train_i)),
        "n_val_pairs": int(len(pairs.val_i)),
        "n_human_labels": pairs.n_human_train,
        "n_human_val_labels": int(len(pairs.human_val_i)),
        "n_human_excluded": pairs.n_human_excluded,
        "n_train_segments": int(split.train.size),
        "n_val_segments": int(split.val.size),
        "split": split.describe(),
        "label_model": f"Bradley–Terry simulated human, beta={beta}, on original segment return",
        "beta": beta,
        "seed": seed,
        "architecture": f"{members} x MLP 20-{hidden}-{hidden}-1 tanh, bootstrap resamples; reward = mean of members",
        "metrics": metrics,
        "sha256": sha256_file(path),
    }
    atomic_write_json(d / "meta.json", meta)
    return meta


def evaluate_model(model, seg: SegmentSet, feats: np.ndarray, split: EpisodeSplit, pairs: PairSet) -> dict:
    """Validation metrics, computed on validation episodes only."""
    step_r_val = model.batch(feats[split.val])  # (n_val, L)
    true_r_val = seg.rewards[split.val]
    acc_labels = pair_accuracy(model, feats, pairs.val_i, pairs.val_j, pairs.val_y)
    return {
        "val_accuracy_vs_labels": acc_labels,
        "val_accuracy_vs_true_order": pair_accuracy(model, feats, pairs.val_i, pairs.val_j, pairs.val_y_true),
        "val_accuracy_vs_human": pair_accuracy(
            model, feats, pairs.human_val_i, pairs.human_val_j, pairs.human_val_y
        ),
        "label_noise_agreement": float((pairs.val_y == pairs.val_y_true)[pairs.val_y_true != 0.5].mean()),
        "step_reward_correlation": float(np.corrcoef(step_r_val.ravel(), true_r_val.ravel())[0, 1]),
        "segment_return_correlation": float(np.corrcoef(step_r_val.sum(1), true_r_val.sum(1))[0, 1]),
    }
