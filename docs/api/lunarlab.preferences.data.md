# `lunarlab.preferences.data`

Source: [`lunarlab/preferences/data.py`](../../lunarlab/preferences/data.py)

Trajectory segments and preference labels.

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

### class `DuplicateLabel`(ValueError)

The pair (in either order) has already been labelled.

`DuplicateLabel(...)`


### class `EpisodeSplit`

Segment indices of the training and validation episodes (sorted, disjoint).

`EpisodeSplit(train: 'np.ndarray', val: 'np.ndarray', train_episodes: 'int', val_episodes: 'int', seed: 'int', val_fraction: 'float') -> None`

- method `describe(self) -> 'dict'`

### class `SegmentSet`

SegmentSet(obs: 'np.ndarray', actions: 'np.ndarray', rewards: 'np.ndarray', terminal: 'np.ndarray', source: 'np.ndarray', episode_seed: 'np.ndarray', start: 'np.ndarray', sources: 'list[str]')

`SegmentSet(obs: 'np.ndarray', actions: 'np.ndarray', rewards: 'np.ndarray', terminal: 'np.ndarray', source: 'np.ndarray', episode_seed: 'np.ndarray', start: 'np.ndarray', sources: 'list[str]') -> None`

- method `load(cls, directory: 'Path') -> 'SegmentSet'`
- property `returns`
- method `save(self, directory: 'Path', meta: 'dict') -> 'None'`

### `add_human_label(dataset_id: 'str', i: 'int', j: 'int', choice: 'str') -> 'dict'`

Record a human preference: choice is 'a' (segment i), 'b' (segment j) or 'tie'.

### `collect_segments(policies: 'list[tuple[str, Policy]]', *, episodes_per_policy: 'int', segment_len: 'int' = 40, segments_per_episode: 'int' = 3, rng_seed: 'int' = 0, progress=None) -> 'SegmentSet'`

### `create_dataset(policies: 'list[tuple[str, Policy]]', *, episodes_per_policy: 'int', name: 'str' = 'prefs', rng_seed: 'int' = 0, progress=None) -> 'str'`

### `dataset_path(dataset_id: 'str') -> 'Path'`

### `datasets_dir() -> 'Path'`

### `episode_ids(seg: 'SegmentSet') -> 'np.ndarray'`

One integer per segment identifying its episode (policy source + episode seed).

### `human_labels(dataset_id: 'str') -> 'list[dict]'`

### `label_and_reveal(dataset_id: 'str', i: 'int', j: 'int', choice: 'str') -> 'dict'`

Record a human label, then reveal what the environment's own reward said about the pair.

### `label_value(choice: 'str') -> 'float'`

### `list_datasets() -> 'list[dict]'`

### `oracle_pairs(returns: 'np.ndarray', indices: 'np.ndarray', n_pairs: 'int', *, beta: 'float', rng: 'np.random.Generator')`

Random pairs within ``indices`` labelled by a Bradley–Terry simulated human.

Returns (i, j, y_noisy, y_true): y = 1 means segment i is preferred.

### `partition_labels(labels: 'list[dict]', split: 'EpisodeSplit') -> 'dict[str, list[dict]]'`

Sort labelled pairs by where their segments lie: both in training episodes ('train'),
both in validation episodes ('val'), or one on each side ('excluded': never used).

### `random_pair(dataset_id: 'str', rng: 'np.random.Generator | None' = None) -> 'dict'`

Two different segments for a human to compare (sources and returns hidden).

Both come from the dataset's training episodes, so a label given here can be used to fit a
reward model without touching validation data.

### `run_episode_record(policy: 'Policy', seed: 'int') -> 'tuple[np.ndarray, np.ndarray, np.ndarray, bool]'`

### `segment_payload(dataset_id: 'str', index: 'int') -> 'dict'`

One segment as JSON (for the human-labelling UI). The source policy and the segment's
return are deliberately not included: the labeller judges the flight itself.

### `split_by_episode(seg: 'SegmentSet', *, val_fraction: 'float' = 0.2, seed: 'int' = 0) -> 'EpisodeSplit'`

Hold out whole episodes for validation (deterministic for a given dataset and seed).

## Constants

- `COLLECTION_SEED_BASE` = `30000`
- `SEGMENT_LEN` = `40`
- `SPLIT_SEED` = `0`
- `VAL_FRACTION` = `0.2`
