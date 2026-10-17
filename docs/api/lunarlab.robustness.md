# `lunarlab.robustness`

Source: [`lunarlab/robustness.py`](../../lunarlab/robustness.py)

Robustness: how do trained policies cope with conditions they never trained on?

Every run trains in calm default physics. Here its frozen, validation-selected
checkpoint flies the *same* final-test episode seeds (identical terrain and
initial push) under changed physics: wind and turbulence (Gymnasium's own wind
model) or stronger gravity. The original reward is used, as everywhere.

These are separate, clearly named evaluations ("robustness:<condition>"). They
never replace or modify the calm final-test result, and nothing is tuned on them.

### `evaluate_robustness(run_id: 'str', condition: 'str', *, episodes: 'int' = 50) -> 'dict[str, Any]'`

Evaluate a run's final-test checkpoint (the frozen bytes once frozen) under one robustness condition it
never trained on (wind, turbulence, heavier gravity), on the first ``episodes`` test seeds, and save the result.

### `latest_robustness(run_id: 'str') -> 'dict[str, dict]'`

Most recent summary per condition for one run.

## Constants

- `CONDITIONS` = `{'wind-5': {'label': 'Light wind (5, turbulence 0.5)', 'env': {'enable_wind': True, 'wind_power': 5.0, 'turbulence_power…`
- `DEFAULT_EPISODES` = `50`
