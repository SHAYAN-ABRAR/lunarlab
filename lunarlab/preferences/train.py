"""Train a reward model from pairwise preferences (Bradley–Terry / logistic loss).

For a pair (A, B) the model predicts P(A preferred) = sigmoid(sum_t r(A_t) - sum_t r(B_t)),
the standard setup of Christiano et al. (2017). Segments are split into train/validation
sets *before* pairing, so validation pairs only contain unseen segments.

Reported quality, on validation segments:
* accuracy against the simulated human's (noisy) labels and against the noise-free ordering;
* correlation of the model's per-step reward with the true per-step environment reward;
* correlation of summed segment rewards with true segment returns.
"""

from __future__ import annotations

import numpy as np

from lunarlab.preferences.data import SegmentSet, dataset_path, human_labels, oracle_pairs
from lunarlab.preferences.model import RewardModel, batch_features, model_path
from lunarlab.storage import atomic_write_json, new_id, sha256_file, utc_now


def _segment_features(seg: SegmentSet) -> np.ndarray:
    return batch_features(seg.obs[:, :-1], seg.actions, seg.obs[:, 1:])  # (N, L, 20)


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
    val_fraction: float = 0.2,
    include_human: bool = False,
    name: str | None = None,
) -> dict:
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    seg = SegmentSet.load(dataset_path(dataset_id))
    feats = _segment_features(seg)
    returns = seg.returns
    perm = rng.permutation(len(seg))
    n_val = max(2, int(round(val_fraction * len(seg))))
    val_idx, train_idx = np.sort(perm[:n_val]), np.sort(perm[n_val:])
    n_train_pairs = int(round(n_pairs * (1 - val_fraction)))
    ti, tj, ty, ty_true = oracle_pairs(returns, train_idx, n_train_pairs, beta=beta, rng=rng)
    vi, vj, vy, vy_true = oracle_pairs(
        returns, val_idx, max(200, n_pairs - n_train_pairs), beta=beta, rng=rng
    )

    n_human = 0
    if include_human:
        labels = human_labels(dataset_id)
        if labels:
            hi = np.array([h["i"] for h in labels])
            hj = np.array([h["j"] for h in labels])
            hy = np.array(
                [1.0 if h["choice"] == "a" else 0.0 if h["choice"] == "b" else 0.5 for h in labels],
                np.float32,
            )
            ti, tj, ty = np.concatenate([ti, hi]), np.concatenate([tj, hj]), np.concatenate([ty, hy])
            n_human = len(labels)

    train_steps = feats[train_idx].reshape(-1, feats.shape[-1])
    mu = train_steps.mean(axis=0)
    sigma = train_steps.std(axis=0) + 1e-6
    sigma[8:12] = 1.0  # one-hot action columns stay as they are
    mu[8:12] = 0.0
    X = torch.tensor((feats - mu) / sigma, dtype=torch.float32)  # (N, L, 20)

    net = nn.Sequential(
        nn.Linear(X.shape[-1], hidden), nn.Tanh(), nn.Linear(hidden, hidden), nn.Tanh(), nn.Linear(hidden, 1)
    )
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-5)
    bce = nn.BCEWithLogitsLoss()

    def logits(i, j):
        return net(X[i]).squeeze(-1).sum(-1) - net(X[j]).squeeze(-1).sum(-1)

    ti_t, tj_t, ty_t = torch.tensor(ti), torch.tensor(tj), torch.tensor(ty)
    vi_t, vj_t, vy_t = torch.tensor(vi), torch.tensor(vj), torch.tensor(vy)
    best = (float("inf"), None, 0)
    history = []
    batch = 128
    for epoch in range(epochs):
        net.train()
        order = torch.randperm(len(ti_t))
        for k in range(0, len(order), batch):
            b = order[k : k + batch]
            loss = bce(logits(ti_t[b], tj_t[b]), ty_t[b])
            opt.zero_grad()
            loss.backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            vloss = float(bce(logits(vi_t, vj_t), vy_t))
            tloss = float(bce(logits(ti_t, tj_t), ty_t))
        history.append({"epoch": epoch + 1, "train_loss": tloss, "val_loss": vloss})
        if vloss < best[0] - 1e-4:
            best = (vloss, {k: v.clone() for k, v in net.state_dict().items()}, epoch + 1)
        elif epoch + 1 - best[2] >= 12:
            break  # early stopping on validation loss
    net.load_state_dict(best[1])
    net.eval()

    with torch.no_grad():
        val_logits = logits(vi_t, vj_t).numpy()
        step_r_val = net(X[val_idx]).squeeze(-1).numpy()  # (n_val, L)
        step_r_train = net(X[train_idx]).squeeze(-1).numpy()
    pred = (val_logits > 0).astype(np.float32)
    true_r_val = seg.rewards[val_idx]
    metrics = {
        "val_accuracy_vs_labels": float((pred == vy).mean()),
        "val_accuracy_vs_true_order": float((pred == vy_true)[vy_true != 0.5].mean()),
        "label_noise_agreement": float((vy == vy_true)[vy_true != 0.5].mean()),
        "step_reward_correlation": float(np.corrcoef(step_r_val.ravel(), true_r_val.ravel())[0, 1]),
        "segment_return_correlation": float(np.corrcoef(step_r_val.sum(1), true_r_val.sum(1))[0, 1]),
        "best_epoch": best[2],
        "val_loss": best[0],
    }

    layers = [m for m in net if isinstance(m, nn.Linear)]
    weights = [(m.weight.detach().numpy().T.copy(), m.bias.detach().numpy().copy()) for m in layers]
    out_mean = float(step_r_train.mean())
    out_std = float(step_r_train.std() + 1e-8)
    model = RewardModel(
        mu=mu.astype(np.float32),
        sigma=sigma.astype(np.float32),
        weights=weights,
        out_mean=out_mean,
        out_std=out_std,
    )

    model_id = new_id(name or f"rm-{n_pairs}pairs", prefix="rm")
    d = model_path(model_id)
    path = model.save(d)
    meta = {
        "model_id": model_id,
        "created_at": utc_now(),
        "dataset_id": dataset_id,
        "n_pairs_requested": n_pairs,
        "n_train_pairs": int(len(ti)),
        "n_val_pairs": int(len(vi)),
        "n_human_labels": n_human,
        "n_train_segments": int(len(train_idx)),
        "n_val_segments": int(len(val_idx)),
        "label_model": f"Bradley–Terry simulated human, beta={beta}, on original segment return",
        "beta": beta,
        "seed": seed,
        "architecture": f"MLP 20-{hidden}-{hidden}-1 tanh on (obs, one-hot action, next obs)",
        "output_normalisation": {"mean": out_mean, "std": out_std},
        "metrics": metrics,
        "history": history,
        "sha256": sha256_file(path),
    }
    atomic_write_json(d / "meta.json", meta)
    return meta
