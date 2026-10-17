# `lunarlab.preferences.model`

Source: [`lunarlab/preferences/model.py`](../../lunarlab/preferences/model.py)

Reward-model inference (NumPy) and the on-disk model registry.

Weights are stored as plain arrays in ``model.npz`` and loaded with
``allow_pickle=False``: loading a reward model cannot execute code. A model
directory is written once and never modified, so its id identifies the reward
function exactly (its SHA-256 is also recorded).

### class `RewardEnsemble`

Several reward networks trained on bootstrap resamples of the same labels.

The reward is the mean of the members' normalized outputs (Christiano et al., 2017); how much the
members disagree about a pair is what active preference learning queries first.

`RewardEnsemble(members: 'list[RewardModel]', model_id: 'str' = '') -> None`

- method `batch(self, x: 'np.ndarray') -> 'np.ndarray'`
- method `member_raw(self, x: 'np.ndarray') -> 'np.ndarray'`: (members, ...) raw outputs: the per-step logits each member was trained with.
- method `save(self, directory: 'Path') -> 'Path'`

### class `RewardModel`

r(s, a, s') = ((MLP((φ - mu) / sigma)) - out_mean) / out_std, a tanh MLP.

`RewardModel(mu: 'np.ndarray', sigma: 'np.ndarray', weights: 'list[tuple[np.ndarray, np.ndarray]]', out_mean: 'float', out_std: 'float', model_id: 'str' = '') -> None`

- method `batch(self, x: 'np.ndarray') -> 'np.ndarray'`
- method `raw(self, x: 'np.ndarray') -> 'np.ndarray'`
- method `save(self, directory: 'Path') -> 'Path'`

### `batch_features(obs: 'np.ndarray', actions: 'np.ndarray', next_obs: 'np.ndarray') -> 'np.ndarray'`

obs, next_obs: (..., 8); actions: (...) ints → (..., 20).

### `features(obs: 'np.ndarray', action: 'int', next_obs: 'np.ndarray') -> 'np.ndarray'`

### `list_models() -> 'list[dict]'`

### `load_model_file(path: 'Path', model_id: 'str' = '') -> 'RewardModel | RewardEnsemble'`

### `model_path(model_id: 'str') -> 'Path'`

### `models_dir() -> 'Path'`

## Constants

- `FEATURE_DIM` = `20`
- `MODEL_ID_RE` = `re.compile('^[A-Za-z0-9][A-Za-z0-9_\\-]{0,95}$')`
