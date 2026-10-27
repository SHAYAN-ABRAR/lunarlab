# CartPole reward-design audit: prespecified protocol

Written 27 October 2026, before any training for this study. The machine-readable protocol is
`protocol.json`, and its canonical SHA-256 is recorded in every run. `protocol-pilot.json` describes the
separately labelled pilot. `PROTOCOL.sha256` holds the file digests and the time they were fixed.

## Purpose and scope

This study gives the generic audit layer (`lunarlab.audit`) a second, controlled use on a task other than
LunarLander. It asks whether the workflow detects a reward design that conflicts with task completion. The
workflow links each design's reward components, the checkpoint chosen on original-reward validation, and
that checkpoint's held-out outcomes. The study does not show that the layer applies to every task, and it
is not a reward-shaping benchmark. The flawed design is deliberately adversarial, not a defect discovered
in practice.

## Environment (Gymnasium 1.4.0, `CartPole-v1`, default arguments)

- Original reward: +1 on every step, the terminating step included (`sutton_barto_reward=False`). The
  original return therefore equals the episode length.
- Termination: the pole angle leaves ±12° (0.2094 rad) or the cart position leaves ±2.4.
- Truncation: the time limit of 500 steps (`max_episode_steps=500`). A step that both terminates and reaches
  the limit counts as a termination.
- Success: an episode that reaches the time limit without terminating, adapter outcome
  `balanced_to_time_limit`. Unlike in LunarLander, a time-limit ending is success here. The success rate is
  called the horizon-completion rate.

## Reward designs (frozen)

All three train on `training reward = 1.0 x original reward + term`, with the learner's discount γ = 0.98.

| Design | Term | Formula, units, coefficients |
|---|---|---|
| `original` | none | The original reward alone |
| `upright-potential` | `upright_potential`, α = 1.0 (the adapter's existing term) | F = α(γΦ(s') − Φ(s)), with Φ(s) = −\|θ\|/θmax, θ the pole angle in radians and θmax = 12° = 0.2094 rad. Φ is dimensionless, in [−1, 0], and 0 when upright. Φ(s') = 0 when s' is a true termination; a truncation uses the real s' |
| `failure-bonus` | `failure_bonus`, bonus = 1000.0 (new, deliberately flawed) | +1000 reward units on the transition that ends the episode by a true termination, including one that also reaches the time limit. Zero otherwise, so a time-limit truncation alone earns nothing |

Rationale for the flawed design: in CartPole-v1 only failure produces a true termination, so the bonus
pays for failing. The coefficient 1000 exceeds the largest possible original return (500). Any failing
episode therefore earns a higher training return than any successful one, so the conflict with task
completion holds at every horizon.

### Hand calculations (independent of the code)

Undiscounted, for an episode of T steps:

- If it fails (terminates) at step T: original return T, failure-bonus training return T + 1000 ≥ 1001.
- If it reaches the limit: original return 500, failure-bonus training return 500.

Discounted at γ = 0.98, the failure-bonus objective from the start of an episode that fails after T
steps is G(T) = (1 − 0.98^T)/0.02 + 1000 · 0.98^(T−1):

- G(10) = 9.146 + 833.7 = 842.8
- G(50) = 31.79 + 371.6 = 403.4
- G(100) = 43.37 + 135.3 = 178.6
- A policy that keeps balancing earns at most 1/(1 − 0.98) = 50 (PPO bootstraps the value at truncation).

So the flawed design's optimum is to fail as early as the dynamics allow. The original design's optimum
is to balance to the limit. The potential term's discounted sum over an episode telescopes to
α(γ^T Φ(s_T) − Φ(s_0)). Φ(s_T) is 0 at a termination, and |Φ(s_0)| ≤ 0.24, since the initial angle is in
±0.05 rad. The term therefore changes the discounted return of a whole episode by less than 0.25. That is
a property of the sum; it does not establish that learning with a finite budget is unaffected.

The pilot checks these payments on recorded episodes. The study's tests check them too
(`tests/test_audit_study.py::test_the_failure_bonus_pays_exactly_on_true_termination`).

## Learner (identical for every design)

PPO from Stable-Baselines3 2.9.0, `MlpPolicy` (two 64-unit tanh layers each for the policy and the value
network, SB3 defaults). The settings are RL Baselines3 Zoo's tuned CartPole-v1 entry
(`hyperparams/ppo.yml` at commit `eec15dc22e1ec7167064aae0c1218eefccaf0ff4`, copied as `rl-zoo-ppo.yml`):

- 8 environments in a `DummyVecEnv`, 32 steps each per rollout, so 256 transitions per rollout
- minibatch 256, 20 epochs
- GAE λ 0.8, γ 0.98, entropy coefficient 0
- learning rate and clip range decaying linearly from 1e-3 and 0.2

PyTorch runs on the CPU with one thread.

- **Budget:** 100,000 configured transitions per policy, rounded up to whole rollouts, so 100,096 actual
  (391 rollouts).
- **Checkpoint evaluation:** after every 40 rollouts (10,240 transitions) and at the end, giving 10
  candidates per run. The untrained initial policy is not a candidate.

## Seeds

- **Training (learner) seeds:** 50, 51, 52, 53, 54, the same five for every design, so a seed-paired
  comparison is possible. `PPO(seed=s)` seeds Python, NumPy, PyTorch and the action space.
- **Training environments:** the first reset of environment i uses 1,000,000 + 1000·s + i, set after the
  model is built. Later episodes reset unseeded and continue each environment's random stream. Every run
  records the effective first-reset seeds and refuses to finish if they differ from these.
- **Validation:** 110000–110019, 20 episodes per checkpoint, deterministic actions.
- **Test:** 210000–210099, 100 episodes per selected policy, deterministic actions.

The three sets are disjoint, which the protocol validator checks.

## Selection, freezing and testing

- **Selection:** the highest mean original return over the 20 validation episodes. Ties go to the earliest
  checkpoint. The rule is the same for every design and uses the original reward only.
- **Freezing:** the selected checkpoint and the final checkpoint are copied to content-addressed read-only
  files and their digests verified.
- **Test order:** the test seeds are opened only after all 15 runs are trained and every frozen digest has
  been verified.

The final-checkpoint test is a prespecified secondary analysis. It is reported separately and never used
for selection.

## Analysis (prespecified)

- **Unit:** the trained policy, five per design. A policy's statistics are over its 100 test episodes.
  The 500 episodes of a design are not 500 independent training replications. All statistics condition on
  the fixed test seeds.
- **Primary measures per policy:** mean original return, and the horizon-completion rate.
- **Reported separately:** each design's training return on the same episodes, as its own reward would
  score them. It is on a different scale and is never compared directly with original return.
- **Per design:**
  - all five policy values;
  - their mean, with a 95% percentile bootstrap interval over policies (10,000 resamples, seed 0);
  - the integer-boundary 25% trimmed mean, which for five values removes the lowest and highest and
    averages the middle three. It is labelled as such, not as rliable's fractional-weight IQM.
- **Effect sizes:** each shaped design minus `original`, as the mean of the five seed-paired differences
  with a 95% bootstrap interval, and as the difference of means with an unpaired bootstrap interval. With
  five runs these intervals are wide and are read as such.
- **Exclusions:** none planned. A run that fails technically is retained with its error and reason.
  Unfavourable seeds are not rerun. Every prespecified condition is reported.

## Compute

- **Main study:** 15 × 100,096 = 1,501,440 training transitions.
- **Pilot:** 3 × 20,480 = 61,440 transitions, with learner seed 90 and its own seeds: validation
  310000–310019, test 410000–410019. It never touches the main validation or test seeds.
- **Total:** 1,562,880 of the authorised 2,000,000 new transitions. Elapsed time is logged against the
  six-hour cap.

## Pilot

The pilot runs all three designs at 20,480 transitions to check the pipeline, the recorded seeds, the
failure-bonus payments against the hand calculation and the timing. Its results are labelled as a pilot
and are not part of the study's results. The protocol was not changed after the pilot. Any change would
be recorded here with its reason before the main runs.
