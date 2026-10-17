# `lunarlab.compare`

Source: [`lunarlab/compare.py`](../../lunarlab/compare.py)

Comparison of runs and the reward-hacking diagnostic.

Two different kinds of variability are kept apart:

* **across evaluation episodes** of one trained policy (bootstrap CI in each
  evaluation result), and
* **across independently trained policies** (one value per training seed).
  With only a few seeds every seed is shown, and across-seed summaries are
  descriptive only. Episodes from different seeds are never pooled as if they
  were independent training runs.

Reward-exploitation flag (documented rule, see docs/EVALUATION.md). On the
evaluation episodes of the selected checkpoint, a run is flagged
"possible reward exploitation" only when **all** hold:

1. its additional reward terms pay out on those episodes
   (mean rescored training return - mean original return > ``MIN_TERM_GAIN``);
2. there is behavioural evidence of what the terms pay for: sustained-hover rate
   >= 0.3, or mean hover fraction >= 0.25, or time-limit rate >= 0.3;
3. task performance is not better than the original-reward baseline: pad-landing
   rate <= the baseline's (same protocol), or <= 0.5 if no baseline is evaluated.

A positive gap between shaped and original return alone is **not** evidence of
reward hacking; it is expected whenever bonuses are added.

### `compare_runs(run_ids: 'list[str]', split: 'str' = 'test') -> 'dict[str, Any]'`

### `compatibility(summaries: 'list[dict]') -> 'dict[str, Any]'`

Which properties differ across the selected runs.

### `display_name(reward_name: 'str', algo: 'str', variant: 'str' = '') -> 'str'`

### `elapsed_seconds(df: 'pd.DataFrame') -> 'pd.Series'`

Wall-clock training time at each episode, accumulated over the run's segments.

``wall_time_s`` restarts with every segment (resume); each segment is offset by the time the kept part
of the earlier segments took. Includes validation passes; depends on the machine and on how many runs
shared it.

### `evidence_level(profile: 'str', completed: 'bool', test_eval: 'dict | None', trained_transitions: 'int' = 0) -> 'str'`

### `experiment_run_ids(experiment_id: 'str') -> 'list[str]'`

### `exploitation_assessment(ev: 'dict | None', baseline_pad_rate: 'float | None') -> 'dict[str, Any]'`

### `gamma_ablation(groups: 'list[dict]', summaries: 'list[dict]') -> 'list[dict]'`

The discount factor's effect, kept apart from the algorithm's.

PPO and DQN at their reference settings differ in two ways at once: the algorithm and its discount
factor (0.999 vs 0.99). For every reward design and training physics trained at more than one
discount factor, or with both algorithms at the same one, this lists each algorithm x gamma cell
(the final score of every training seed), the effect of gamma within each algorithm (against its
reference gamma, or the lowest gamma trained) and PPO - DQN at each matched gamma. Differences are
in mean original return over training seeds; intervals resample each cell's seeds.

### `group_by_reward(summaries: 'list[dict]', split: 'str' = 'test') -> 'list[dict]'`

One group per reward function. Each seed is listed; across-seed stats are descriptive.

### `load_episodes(run_id: 'str') -> 'pd.DataFrame'`

Training episodes with rows from abandoned branches removed.

When a run is resumed from a checkpoint at transition S, episodes that an
earlier segment logged after S were never part of the continued run.

### `path_for(run_id: 'str') -> 'Path'`

### `physics_comparison(groups: 'list[dict]', summaries: 'list[dict]') -> 'list[dict]'`

Fixed vs randomized training physics, for every algorithm/reward/discount that has both,
across the calm final test and the robustness conditions (frozen checkpoints, original reward).
Each difference of means over policies has a 95% interval that resamples each side's policies.

### `robust_statistics(groups: 'list[dict]') -> 'dict'`

IQM, bootstrap intervals over training seeds, P(improvement) vs the first group, performance
profiles. Only groups with at least one evaluated run are included.

### `robustness_table(groups: 'list[dict]', summaries: 'list[dict]') -> 'dict'`

Per group and condition: per-seed results and the across-seed mean (calm = final test).

### `run_summary(run_id: 'str') -> 'dict[str, Any]'`

### `training_curve(run_id: 'str', window: 'int' = 100, max_points: 'int' = 400) -> 'dict[str, Any]'`

### `training_trend(run_id: 'str') -> 'dict[str, Any] | None'`

Change in training vs original return between the first and last 20% of episodes.

### `variant_key(cfg) -> 'str'`

### `variant_suffix(cfg) -> 'str'`

What sets a run apart from its algorithm's reference setup: a non-reference discount factor
and/or randomized training physics ('' for the reference setup).

### `wall_clock_notes(summaries: 'list[dict]') -> 'list[str]'`

Differences between runs that change wall-clock training time without changing what was learned.
Elapsed-time curves compare speed fairly only when there are none.

## Constants

- `EXPLOIT_HOVER_FRACTION` = `0.25`
- `EXPLOIT_HOVER_RATE` = `0.3`
- `EXPLOIT_TIMEOUT_RATE` = `0.3`
- `MIN_TERM_GAIN` = `1.0`
- `NO_BASELINE_PAD_CEILING` = `0.5`
- `REFERENCE_GAMMA` = `{'ppo': 0.999, 'dqn': 0.99}`
