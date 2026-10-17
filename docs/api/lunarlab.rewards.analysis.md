# `lunarlab.rewards.analysis`

Source: [`lunarlab/rewards/analysis.py`](../../lunarlab/rewards/analysis.py)

Back-of-envelope discounted-return reasoning for reward designs.

These are calculators with explicit, editable assumptions. They illustrate why
a design *might* create an incentive; they do not predict what PPO will learn.
PPO's finite-sample behaviour also depends on exploration, the critic's
accuracy, entropy regularisation and the training budget.

### `geometric_sum(per_step: 'float', gamma: 'float', n_steps: 'int') -> 'float'`

sum_{t=0}^{n-1} gamma^t * per_step.

### `hover_incentive(*, bonus: 'float', gamma: 'float', horizon: 'int' = 1000, hover_start: 'int' = 100, main_engine_duty: 'float' = 0.5, landing_step: 'int' = 300, landing_original_return: 'float' = 220.0) -> 'dict'`

Compare 'hover until the time limit' with 'land' under stated assumptions.

Assumptions (all editable):
* hovering starts at ``hover_start`` and is eligible every step afterwards;
* holding altitude needs the main engine a fraction ``main_engine_duty`` of
  steps, each costing 0.30 of *original* reward (the env's own fuel cost);
* a landing policy finishes at ``landing_step`` with original return
  ``landing_original_return``.
The original-reward shaping drift while hovering is ignored.

### `perpetual_value(per_step: 'float', gamma: 'float') -> 'float'`

sum_{t=0}^{inf} gamma^t * per_step (finite only for gamma < 1).

### `potential_telescoping(*, alpha: 'float', gamma: 'float', phi_start: 'float', phi_end: 'float', steps: 'int', terminated: 'bool') -> 'float'`

Closed form of sum_t gamma^t * F_t over one episode.

terminated: gamma^T * 0 - alpha*Phi(s0)       = -alpha * phi_start
truncated:  gamma^T * alpha*Phi(s_T) - alpha*Phi(s0)

### `time_penalty_effect(*, cost: 'float', gamma: 'float', steps: 'int') -> 'dict'`

Undiscounted and discounted total of a per-step cost over ``steps`` steps (to compare with the -100
crash penalty).

## Constants

- `BUILTIN_MAIN_ENGINE_COST` = `0.3`
