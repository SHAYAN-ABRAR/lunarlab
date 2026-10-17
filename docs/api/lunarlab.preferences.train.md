# `lunarlab.preferences.train`

Source: [`lunarlab/preferences/train.py`](../../lunarlab/preferences/train.py)

Train a reward model from pairwise preferences (Bradley–Terry / logistic loss).

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

### class `PairSet`

Labelled pairs ready for fitting. y = 1 means segment i is preferred (0.5 = tie).

`PairSet(train_i: 'np.ndarray', train_j: 'np.ndarray', train_y: 'np.ndarray', val_i: 'np.ndarray', val_j: 'np.ndarray', val_y: 'np.ndarray', val_y_true: 'np.ndarray', human_val_i: 'np.ndarray', human_val_j: 'np.ndarray', human_val_y: 'np.ndarray', n_human_train: 'int', n_human_excluded: 'int') -> None`


### `assemble_pairs(seg: 'SegmentSet', split: 'EpisodeSplit', *, n_pairs: 'int', beta: 'float', rng: 'np.random.Generator', labels: 'list[dict] | None' = None) -> 'PairSet'`

Simulated pairs inside each side of the split, plus human labels by where they fall.

Every training pair has both segments in training episodes; every validation pair has both in
validation episodes. This is the invariant the regression tests check.

### `evaluate_model(model, seg: 'SegmentSet', feats: 'np.ndarray', split: 'EpisodeSplit', pairs: 'PairSet') -> 'dict'`

Validation metrics, computed on validation episodes only.

### `fit_network(X, pairs: 'tuple[np.ndarray, np.ndarray, np.ndarray]', val_pairs: 'tuple[np.ndarray, np.ndarray, np.ndarray]', *, seed: 'int', hidden: 'int' = 64, epochs: 'int' = 80, lr: 'float' = 0.001, patience: 'int' = 12)`

Fit one tanh MLP on (i, j, y) pairs with early stopping on the validation loss.

``X`` is a float tensor (segments, steps, features). Returns (network, history, best_epoch,
best_val_loss).

### `network_weights(net) -> 'list[tuple[np.ndarray, np.ndarray]]'`

### `normalization(feats: 'np.ndarray', train_idx: 'np.ndarray') -> 'tuple[np.ndarray, np.ndarray]'`

Feature mean/std from training segments only (one-hot action columns left unscaled).

### `pair_accuracy(model: 'RewardModel', feats: 'np.ndarray', i: 'np.ndarray', j: 'np.ndarray', y: 'np.ndarray') -> 'float | None'`

Fraction of non-tie pairs ordered like ``y`` by the model's summed reward.

### `train_reward_model(dataset_id: 'str', *, n_pairs: 'int', threads: 'int' = 2, **kwargs) -> 'dict'`

Fit and register a reward model. ``threads`` caps torch's intra-op threads while fitting:
the model is tiny, and the default (all cores) is much slower on a machine already busy
training policies.

## Constants

- `SPLIT_SEED` = `0`
- `VAL_FRACTION` = `0.2`
