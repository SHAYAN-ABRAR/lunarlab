# `lunarlab.hover`

Source: [`lunarlab/hover.py`](../../lunarlab/hover.py)

The hover predicate shared by the hover-bonus reward and the hover detector.

There is **one** predicate implementation and **two independent parameter sets**:

* ``HoverBonusConfig.eligibility`` (part of a reward configuration) decides when
  the flawed hover-bonus preset pays its bonus.
* ``EvalProtocol.hover_detector`` (part of the evaluation protocol) measures
  hovering for *every* agent, whatever reward it was trained on. Editing a
  reward configuration never changes the detector.

Thresholds are in the environment's observation units (see ``lunarlab.env``).
They are design choices, not validated optimal values.

### class `HoverThresholds`(BaseModel)

A region of state space that counts as hovering: airborne within a height band, nearly still and upright.

| Field | Type | Default | Description |
|---|---|---|---|
| `min_height` | `float` | `0.25` | Lower bound on observation y (normalized). |
| `max_height` | `float` | `1.0` | Upper bound on observation y (normalized). |
| `max_abs_angle_rad` | `float` | `0.2` | Maximum \|angle\| in radians. |
| `max_abs_vx` | `float` | `0.1` | Maximum \|vx\| (scaled units). |
| `max_abs_vy` | `float` | `0.1` | Maximum \|vy\| (scaled units). |
| `max_abs_angular_velocity` | `float | None` | `0.2` | Maximum \|angular velocity\| (scaled units); null disables the check. |


### `hover_state(obs: 'np.ndarray', t: 'HoverThresholds') -> 'bool'`

True when ``obs`` is an airborne, slow, level state inside the height band.

Boundaries are inclusive: a value exactly at a threshold counts as inside.

## Constants

- `DEFAULT_BONUS_ELIGIBILITY` = `HoverThresholds(min_height=0.25, max_height=1.0, max_abs_angle_rad=0.2, max_abs_vx=0.1, max_abs_vy=0.1, max_abs_angular_…`
- `DEFAULT_DETECTOR` = `HoverThresholds(min_height=0.1, max_height=1.6, max_abs_angle_rad=0.35, max_abs_vx=0.1, max_abs_vy=0.1, max_abs_angular_…`
