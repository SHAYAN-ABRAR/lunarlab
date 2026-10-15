# Rewards

All formulas below are implemented once, in `lunarlab/rewards/terms.py`, and used by training, evaluation
telemetry and the Reward Stress Test alike.

## Observations and actions

`LunarLander-v3` with `continuous=False`, default physics (gravity −10, wind off), 1,000-step time limit
(`TimeLimit` from `gym.make`). The policy receives exactly eight values:

| # | Value | Units | Meaning (gymnasium 1.4.0 source) |
|---|---|---|---|
| 0 | x | normalized | `(x − W/2)/(W/2)`, W = 20 world units; 0 = pad centre, \|x\| ≥ 1 ends the episode |
| 1 | y | normalized | `(y − (pad_y + LEG_DOWN/SCALE)) / (H/2)`, H = 13.33; ≈0 legs on pad, ≈1.4 at spawn |
| 2 | vx | scaled | `vx_world · (W/2)/FPS` = 0.2 × world units/s |
| 3 | vy | scaled | `vy_world · (H/2)/FPS` ≈ 0.133 × world units/s |
| 4 | angle | rad | body angle, not normalized (UI also shows degrees) |
| 5 | angular velocity | scaled | `20·ω/FPS` = 0.4 × rad/s |
| 6, 7 | leg contact | 0/1 | see the contact-flag quirk in [EVALUATION.md](EVALUATION.md) |

Actions: `0` do nothing · `1` fire left orientation engine · `2` fire main engine · `3` fire right
orientation engine.

## The original reward (authoritative, never modified)

On ordinary steps the environment pays the **change** of its internal shaping score

```
shaping(s) = −100·√(x²+y²) − 100·√(vx²+vy²) − 100·|angle| + 10·left_contact + 10·right_contact
reward     = shaping(s′) − shaping(s) − 0.30·[main engine fired] − 0.03·[side engine fired]
```

On the final step the environment **replaces** the whole step reward: −100 if the lander body touched the
ground or |x| ≥ 1, +100 if Box2D put the lander to sleep. (If both happen on the same step, the env's code
order makes it +100.) LunarLab's Flight Replay shows this decomposition per step; it is reconstructed from
observations and checked against the env's actual reward in tests (residual < 10⁻³, float32 rounding).

## Additional terms and the invariant

```
training_reward = original_reward + Σ enabled additional terms
```

`LunarLabRewardWrapper` (in `lunarlab/rewards/wrapper.py`) receives the original reward, computes the terms
from `(s, a, s′, terminated, truncated)`, and returns the sum during training (`apply=True`) or the original
reward unchanged during evaluation (`apply=False`, terms recorded only). Tests check the invariant on every
transition of every preset.

## The four presets

### A. Original baseline

`training_reward = original_reward`. No additional terms.

### B. Time-penalty ablation

`training_reward = original_reward − c` on every transition (default `c = 0.01`, terminal step included).

This is an **ablation**, not a promised improvement. A per-step cost changes the objective toward shorter
episodes. At 0.01 a full 1,000-step episode costs 10, small next to the −100 crash penalty, but larger costs
can make crashing early optimal.

### C. Intentionally flawed hover bonus

`training_reward = original_reward + b · 1[eligible(s′)]`, default `b = 1.0`, paid on the state *reached* by
the step. Eligibility (all must hold; design choices, not validated optima):

| Condition | Default |
|---|---|
| airborne | neither leg flag in contact |
| height band | 0.25 ≤ y ≤ 1.0 |
| tilt | \|angle\| ≤ 0.2 rad (11.5°) |
| speed | \|vx\| ≤ 0.1 and \|vy\| ≤ 0.1 (scaled) |
| spin (optional) | \|angular velocity\| ≤ 0.2 (scaled) |

**Why it is flawed:** it pays for staying in a desirable *intermediate* state. Landing ends the episode and
the bonus with it; hovering until the time limit keeps collecting it.

**Discounted reasoning, not "bonus × 1,000".** PPO maximises the discounted return with γ = 0.999 (an
effective horizon of ≈1,000 steps). Under stated assumptions (the Reward Studio calculator,
`lunarlab/rewards/analysis.py`), with hovering from step 100, a 50% main-engine duty at −0.30 per firing:

- naive undiscounted bonus: 900;
- discounted bonus net of fuel until the 1,000-step limit: ≈457;
- what a critic perceives if it expects hovering to continue past the limit: ≈769, because SB3 bootstraps
  `γ·V(s_T)` on truncation;
- a landing worth 220 at step 300 is worth ≈163–220 discounted.

So the reward favours hovering on paper. Whether PPO **finds** that behaviour depends on exploration (the
eligible band must be visited), the critic and the budget. It is an empirical question, and LunarLab is
built to measure it rather than assume it. If hovering does not emerge, keep that result, inspect the
diagnostics, and if needed run an explicit development sweep (`python -m lunarlab sweep`). Sweeps select on
validation episodes only and keep every trial; the environment is never changed to manufacture an outcome.

### D. Potential-based shaping

```
F(s, s′) = α · (γ · Φ(s′) − Φ(s)),     γ = the PPO discount of the run (0.999)
Φ(s)     = −( wx·tanh|x| + wy·tanh|y| + wv·tanh(√(vx²+vy²)) + wa·tanh|angle| + ww·tanh|ω| )
Φ(s′)    = 0 when s′ is a true terminal state (absorbing)
```

Defaults: α = 10, wx = 1.0, wy = 0.5, wv = 1.0, wa = 0.5, ww = 0.25. Φ is bounded in [−3.25, 0], so the
whole-episode shaping contribution is at most α·3.25 = 32.5, modest beside the original reward's ±100
terminal and its own dense shaping of ~100–200. The weights favour being centred, slow and upright, and
roughly mirror the components the original reward already values, without changing what is optimal.

Why it is "safe" in theory (Ng, Harada & Russell, 1999): the discounted sum over a terminated episode
telescopes to `−α·Φ(s₀)`, which depends only on the start state, so optimal policies are unchanged. Tested
in `tests/test_rewards.py` for several γ, for both termination and truncation.

What it does **not** promise: faster learning, better finite-budget PPO results, or a better undiscounted
leaderboard score. Breaking any of these voids the theorem: replacing γΦ(s′) with Φ(s′), clipping F,
adding terminal bonuses, or using a different γ from PPO.

A visible consequence: because Φ ≤ 0 and Φ(terminal) = 0, the final transition of a crash pays
`F = −α·Φ(s) > 0`. That step cancels the potential collected so far; the episode as a whole is not rewarded
for crashing. The Stress Test shows this as the "final step" phase.

### E. Learned reward (RLHF in miniature)

Not a preset: reward configurations created by `python -m lunarlab rlhf-study` (or by hand) with
`original_weight: 0` and `learned: {enabled: true, model_id: <id>, scale: 1}`. PPO then optimizes only
`scale × r̂(s, a, s′)`, the output of a reward model fitted to pairwise preferences between 40-step flight
segments (see ARCHITECTURE.md). The general invariant is

```
training_reward = original_weight × original_reward + Σ additional terms
```

with `original_weight = 1` for every preset (their content hashes are unchanged by this field). Evaluation is
unaffected: it always reports the original reward. The model's per-step output is normalized to zero mean and
unit standard deviation on the training segments, so its scale is arbitrary; only its ordering of
trajectories was trained. Nothing constrains its sign on states the dataset never covered, which is exactly
where an optimizing policy can find unintended reward.

## Termination vs truncation

- **terminated** (crash, out of bounds, at rest): the episode really ended. SB3 does not bootstrap and
  Φ(s′) = 0.
- **truncated** (1,000-step limit): the episode was cut. SB3 adds `γ·V(terminal_observation)` to the last
  reward, and LunarLab uses the real final observation for Φ(s′). The telescoped sum is then
  `α(γ^T·Φ(s_T) − Φ(s₀))`; the residual `γ^T·Φ(s_T)` is consistent with the bootstrap.
- SB3 vector environments auto-reset: the observation returned after `done` is the **next** episode's
  first observation, and the true final one is `info["terminal_observation"]`. LunarLab computes all terms
  inside the wrapper, before the reset, so they cannot be confused. This is tested.

## Why shaped scores are not comparable

Each reward preset defines a different objective on a different scale. A potential-shaped return of 230 and
a hover-bonus return of 700 say nothing about which agent lands better. Compare agents only through
**evaluation with the original reward** on the same seeds. LunarLab plots training (shaped) and original
returns separately, and SB3's own `ep_rew_mean` is the shaped return because `Monitor` wraps the reward
wrapper.

## Reward-configuration safety

Configurations are data validated by a strict schema (`lunarlab/rewards/config.py`): unknown fields are
rejected and numbers are bounded. No expression from the editor is ever evaluated. Saving creates an
immutable revision, and every run snapshots its exact reward into `config.yaml` together with a content hash.
