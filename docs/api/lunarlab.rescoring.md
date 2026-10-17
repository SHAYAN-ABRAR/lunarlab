# `lunarlab.rescoring`

Source: [`lunarlab/rescoring.py`](../../lunarlab/rescoring.py)

Reward Stress Test: re-score one saved trajectory under candidate reward configs.

This is **re-scoring a fixed trajectory**. The flight is not re-simulated and no
policy is trained. It shows how each reward design would *score* behaviour that
already happened, and which parts of the flight each term pays for. It is not
a prediction of what PPO would learn under that reward, and it is not causal
evidence that a reward produces any behaviour.

The original reward of each step is taken from the recording. The additional
terms are recomputed with :func:`lunarlab.rewards.terms.compute_terms`, the same
function used during training.

### `rescore(telemetry: 'dict', configs: 'list[RewardConfig]', *, gamma: 'float', detector: 'HoverThresholds', max_points: 'int' = 400) -> 'dict[str, Any]'`

Re-score a recorded trajectory under other reward configurations.

The original reward of each step comes from the recording; every term is recomputed with the same pure
functions used in training. Returns, per configuration, cumulative series, totals (undiscounted and discounted)
and per-phase sums.

## Constants

- `PHASES` = `('hover', 'airborne', 'ground_contact', 'final_step')`
- `PHASE_LABELS` = `{'hover': 'Hovering (detector: airborne, slow, level, in band)', 'airborne': 'Airborne, not hovering', 'ground_contact':…`
