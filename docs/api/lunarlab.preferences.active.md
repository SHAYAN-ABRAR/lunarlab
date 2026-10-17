# `lunarlab.preferences.active`

Source: [`lunarlab/preferences/active.py`](../../lunarlab/preferences/active.py)

Active preference learning: a reward-model ensemble chooses which pairs to label next.

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

### `candidate_pairs(pool: 'np.ndarray', exclude: 'set[tuple[int, int]]', n: 'int', rng: 'np.random.Generator') -> 'np.ndarray'`

Up to ``n`` distinct unordered pairs from ``pool``, none of them in ``exclude``.

### `disagreement(ensemble: 'RewardEnsemble', feats: 'np.ndarray', pairs: 'np.ndarray') -> 'np.ndarray'`

Standard deviation across members of P(first segment preferred), one value per pair.

### `ensemble_accuracy(ensemble: 'RewardEnsemble', feats: 'np.ndarray', i, j, y) -> 'float | None'`

### `fit_ensemble(X, feats: 'np.ndarray', train_idx: 'np.ndarray', mu: 'np.ndarray', sigma: 'np.ndarray', pairs: 'tuple[np.ndarray, np.ndarray, np.ndarray]', val_pairs: 'tuple[np.ndarray, np.ndarray, np.ndarray]', *, members: 'int' = 5, seed: 'int' = 0, epochs: 'int' = 60, hidden: 'int' = 64, lr: 'float' = 0.001, bootstrap: 'bool' = True) -> 'RewardEnsemble'`

Fit ``members`` networks, each on a bootstrap resample of the labelled pairs.

### `labelled_keys(dataset_id: 'str') -> 'set[tuple[int, int]]'`

### `labelling_progress(dataset_id: 'str') -> 'dict[str, Any]'`

### `list_active_studies(dataset_id: 'str') -> 'list[dict[str, Any]]'`

### `next_pair(dataset_id: 'str', strategy: 'str' = 'random', rng: 'np.random.Generator | None' = None) -> 'dict[str, Any]'`

The next pair for a person to label: never one they have labelled already, always from training
episodes. ``disagreement`` needs the dataset's labelling ensemble.

### `oracle_label(returns: 'np.ndarray', i: 'int', j: 'int', *, beta: 'float', seed: 'int') -> 'float'`

Simulated human for one pair, deterministic per unordered pair: 1.0 if segment i is preferred.

### `pair_key(i: 'int', j: 'int') -> 'tuple[int, int]'`

### `run_active_learning(dataset_id: 'str', *, strategy: 'str', budget: 'int' = 1000, initial: 'int' = 100, batch: 'int' = 100, members: 'int' = 5, candidates: 'int' = 2000, seed: 'int' = 0, beta: 'float' = 0.05, epochs: 'int' = 60, register: 'bool' = False, progress=None) -> 'dict[str, Any]'`

Simulated labelling loop. Returns the learning curve (validation metrics after each round).

### `run_active_study(dataset_id: 'str', *, strategies: 'list[str]', seeds: 'list[int]', echo=<built-in function print>, **kwargs) -> 'dict[str, Any]'`

Every strategy with every seed (each seed shares its initial labels across strategies).

### `studies_dir(dataset_id: 'str')`

### `summarize_curves(runs: 'list[dict[str, Any]]') -> 'dict[str, list[dict[str, Any]]]'`

Per strategy and label count: mean, min and max over seeds of the validation accuracy.

### `train_labelling_ensemble(dataset_id: 'str', *, simulated_pairs: 'int' = 0, members: 'int' = 5, seed: 'int' = 0, beta: 'float' = 0.05) -> 'dict[str, Any]'`

Fit an ensemble on the human labels from training episodes (plus, optionally, simulated pairs)
and make it the dataset's labelling ensemble, used by the disagreement strategy.

## Constants

- `DEFAULT_CANDIDATES` = `2000`
- `DEFAULT_MEMBERS` = `5`
- `STRATEGIES` = `('random', 'disagreement')`
