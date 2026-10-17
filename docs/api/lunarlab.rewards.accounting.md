# `lunarlab.rewards.accounting`

Source: [`lunarlab/rewards/accounting.py`](../../lunarlab/rewards/accounting.py)

Per-episode accounting of original and training rewards.

The accumulator is reset at every ``reset()`` so no state can leak from one
episode into the next. Discounted sums use the convention G = sum_t gamma^t r_t
with t = 0 for the first transition after reset.

### class `EpisodeAccumulator`

EpisodeAccumulator(gamma: 'float', detector: 'HoverThresholds', length: 'int' = 0, original_return: 'float' = 0.0, training_return: 'float' = 0.0, discounted_original: 'float' = 0.0, discounted_training: 'float' = 0.0, term_returns: 'dict[str, float]' = <factory>, term_discounted: 'dict[str, float]' = <factory>, action_counts: 'list[int]' = <factory>, hover_steps: 'int' = 0, longest_hover_streak: 'int' = 0, bonus_eligible_steps: 'int' = 0, leg_contact_steps: 'int' = 0, both_legs_contact_steps: 'int' = 0, _streak: 'int' = 0, _discount: 'float' = 1.0)

`EpisodeAccumulator(gamma: 'float', detector: 'HoverThresholds', length: 'int' = 0, original_return: 'float' = 0.0, training_return: 'float' = 0.0, discounted_original: 'float' = 0.0, discounted_training: 'float' = 0.0, term_returns: 'dict[str, float]' = <factory>, term_discounted: 'dict[str, float]' = <factory>, action_counts: 'list[int]' = <factory>, hover_steps: 'int' = 0, longest_hover_streak: 'int' = 0, bonus_eligible_steps: 'int' = 0, leg_contact_steps: 'int' = 0, both_legs_contact_steps: 'int' = 0, _streak: 'int' = 0, _discount: 'float' = 1.0) -> None`

- method `add(self, *, original: 'float', terms: 'dict[str, float]', training: 'float', action: 'int', next_obs: 'np.ndarray') -> 'bool'`: Record one transition. Returns whether ``next_obs`` is a hover state (detector).
- method `reset(self) -> 'None'`: Start a new episode: every sum and counter back to zero.
- method `summary(self) -> 'dict'`: Returns (original, training and per term; undiscounted and discounted), action counts, hover

## Constants

- `ACTION_KEYS` = `('noop', 'left', 'main', 'right')`
- `TERM_KEYS` = `('time_penalty', 'hover_bonus', 'potential_shaping', 'learned_reward')`
