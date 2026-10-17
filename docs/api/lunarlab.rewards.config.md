# `lunarlab.rewards.config`

Source: [`lunarlab/rewards/config.py`](../../lunarlab/rewards/config.py)

Reward configuration schema and the four named presets.

A reward configuration is pure data validated by a fixed schema. There is no
expression language and nothing from the editor is ever evaluated as code.

    training_reward = original_weight * original_reward + sum(enabled additional terms)

``original_weight`` is 1 for every preset: the original environment reward is
included unchanged. Only the learned-reward (RLHF) experiments set it to 0, so
the agent optimises a reward model and never sees the environment's reward.
The additional terms are:

* ``time_penalty``      -cost on every transition
* ``hover_bonus``       +bonus when the *resulting* state satisfies the eligibility predicate
* ``potential_shaping`` alpha * (gamma * Phi(s') - Phi(s)), with Phi(terminal) = 0
* ``learned_reward``    scale * r_model(s, a, s') from a reward model trained on preferences

``gamma`` for potential shaping is *not* part of the reward config: it is
always the PPO discount of the run that uses the config, so the two cannot
drift apart.

### class `HoverBonusConfig`(_Strict)

A bonus whenever the resulting state satisfies the eligibility predicate.

It does not telescope, so it changes which policy is optimal: the deliberately flawed preset.

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | `bool` | `False` |  |
| `bonus_per_step` | `float` | `1.0` | Added when the resulting state is eligible. |
| `eligibility` | `HoverThresholds` | `factory` |  |


### class `LearnedRewardConfig`(_Strict)

A reward model learned from preferences (``lunarlab.preferences``), scaled. With ``original_weight = 0``
the agent never sees the environment's reward.

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | `bool` | `False` |  |
| `model_id` | `str | None` | `None` |  |
| `scale` | `float` | `1.0` | Multiplies the normalised model output. |


### class `PotentialConfig`(_Strict)

Potential-based shaping alpha * (gamma * Phi(s') - Phi(s)) with Phi(terminal) = 0; gamma is the run's discount.

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | `bool` | `False` |  |
| `alpha` | `float` | `10.0` | Scale of the shaping term. |
| `weights` | `PotentialWeights` | `factory` |  |


### class `PotentialWeights`(_Strict)

Weights of the bounded potential Phi(s) = -sum_i w_i * tanh|feature_i| (see ``rewards.terms.potential``).

| Field | Type | Default | Description |
|---|---|---|---|
| `x` | `float` | `1.0` | Weight on tanh(\|x\|). |
| `y` | `float` | `0.5` | Weight on tanh(\|y\|). |
| `speed` | `float` | `1.0` | Weight on tanh(hypot(vx, vy)). |
| `angle` | `float` | `0.5` | Weight on tanh(\|angle\|). |
| `angular_velocity` | `float` | `0.25` | Weight on tanh(\|angular velocity\|). |


### class `RewardConfig`(_Strict)

A complete reward definition: training reward = original_weight * original reward + the enabled terms.

Validated strictly (unknown keys are refused, values bounded); :meth:`content_hash` identifies it in every run
and evaluation.

| Field | Type | Default | Description |
|---|---|---|---|
| `schema_version` | `Literal[1]` | `1` |  |
| `name` | `str` | `required` |  |
| `preset` | `Literal['baseline', 'time-penalty', 'hover-bonus', 'potential', 'custom']` | `'custom'` |  |
| `description` | `str` | `''` |  |
| `time_penalty` | `TimePenaltyConfig` | `factory` |  |
| `hover_bonus` | `HoverBonusConfig` | `factory` |  |
| `potential` | `PotentialConfig` | `factory` |  |
| `original_weight` | `float` | `1.0` | Weight of the original environment reward. |
| `learned` | `LearnedRewardConfig` | `factory` |  |

- method `active_terms(self) -> 'list[str]'`: Names of the enabled additional terms.
- method `content_hash(self) -> 'str'`: Hash of the reward function itself. Two configs with equal hashes are the same reward.
- method `is_original(self) -> 'bool'`: True when the training reward equals the original reward (no additional term, weight 1).
- method `reward_payload(self) -> 'dict'`: Only the fields that change the reward function (not name/description).
- method `warnings(self) -> 'list[str]'`: Design warnings shown in the Reward Studio (not validation errors).

### class `TimePenaltyConfig`(_Strict)

A constant cost on every transition (the time-penalty ablation).

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | `bool` | `False` |  |
| `cost_per_step` | `float` | `0.01` | Subtracted on every transition. |


### `all_presets() -> 'list[RewardConfig]'`

The four named presets: baseline, time penalty, flawed hover bonus, potential-based shaping.

### `preset(name: 'str') -> 'RewardConfig'`

Return a fresh copy of a named preset.

## Constants

- `DEFAULT_BONUS_ELIGIBILITY` = `HoverThresholds(min_height=0.25, max_height=1.0, max_abs_angle_rad=0.2, max_abs_vx=0.1, max_abs_vy=0.1, max_abs_angular_…`
- `PRESET_NAMES` = `('baseline', 'time-penalty', 'hover-bonus', 'potential')`
- `TERM_KEYS` = `('time_penalty', 'hover_bonus', 'potential_shaping', 'learned_reward')`
