# Evaluation protocol

Implemented in `lunarlab/evaluation.py`, `lunarlab/outcomes.py`, `lunarlab/stats.py`, `lunarlab/compare.py`.
The protocol (`EvalProtocol` in `lunarlab/config.py`, id `lunarlab-eval-v1`) is stored with every run and
every evaluation result, together with its hash.

## Conditions

- A fresh `LunarLander-v3`, `continuous=False`, default physics, 1,000-step limit.
- **Original reward only.** The only wrapper is the observation-only telemetry wrapper in `apply=False` mode.
  The evaluation loop additionally checks that the reward it received sums to the recorded original return,
  and refuses to report otherwise.
- **Deterministic policy** (argmax action) by default; recorded with each result.
- Observations are not normalized, so no statistics need freezing.

## Seeds

| Use | Seeds |
|---|---|
| Training workers | `1,000,000 + 1000·seed + 100·segment + rank` (recorded per segment) |
| Validation (checkpoint selection) | 10,000 – 10,009 |
| Final test | 20,000 – 20,099 (100 episodes) |
| Shared demonstration seed | 20,000 (labelled as a test seed in replays) |

All compared policies use the same validation and test seeds.

## Checkpoint selection and final-test freezing

- Validation runs at the start of training and every `validation_every` transitions (STANDARD: 50k). The
  **validation-selected checkpoint** maximises the mean **original** return on validation seeds. Shaped
  reward never selects checkpoints.
- The first test evaluation of a run **freezes** its selected checkpoint (file name, SHA-256 and config hash
  are recorded in `metadata.json → frozen_for_test`). Later test evaluations are flagged as repeats, and
  evaluating a *different* checkpoint on the test seeds is refused.
- Development sweeps compare on the validation split only.

## Outcome definitions

`env_outcome`, what the environment decided on the final step:

| Outcome | Condition | Env reward |
|---|---|---|
| `at_rest` | Box2D put the lander to sleep (environment's own success) | +100 |
| `crash` | lander body touched the ground and the lander was still awake | −100 |
| `out_of_bounds` | \|x\| ≥ 1 without body contact | −100 |
| `timeout` | truncated by the 1,000-step limit | — |
| `unknown` | terminated for no identifiable reason (reported, never guessed) | — |

`at_rest` does not check *where* the lander rests. **Strict pad landing** additionally requires:

1. `env_outcome == at_rest`;
2. no body contact at any time (`game_over` is sticky within an episode);
3. leg ground contact reported at least once during the episode;
4. both leg bodies horizontally between the helipad flags (x read from `env.unwrapped.helipad_x1/x2`);
5. final |angle| ≤ 0.35 rad.

**Leg naming.** Gymnasium documents observation 6 as the *left* leg and 7 as the *right* leg, but the
first leg body (whose flag is observation 6) is created on the **+x** side (screen right). LunarLab keeps the
documented indices and notes the physical side in its labels; the 3-D replay lights the matching foot.

**Contact-flag quirk (gymnasium 1.4.0).** The environment keeps one boolean per leg: `BeginContact` sets it,
`EndContact` clears it. When a leg slides across the joint between two terrain edge fixtures, the new contact
begins before the old one ends, so the flag reads 0 while the leg is still on the ground. With Gymnasium's
heuristic controller, several clean landings (seed 20011, for example) end asleep on the pad with both flags at 0. Requiring final-frame
contact would misclassify them, so condition 3 asks only that contact was seen. A sleeping lander without
body contact must be resting on its legs. The final-frame flags are still reported (`both_legs_contact`).

Reference point (Gymnasium's hand-coded heuristic, 100 test seeds): environment success 93%, return ≥ 200
92%, strict pad landing 73%. The remaining 19 rest upright with a leg outside the flags. A score threshold
and a landing outcome measure different things, so both are always shown.

## Hover detector

Independent of any reward preset and identical for every agent (protocol thresholds, not the reward's):
airborne, 0.1 ≤ y ≤ 1.6, |angle| ≤ 0.35 rad, |vx| ≤ 0.1, |vy| ≤ 0.1. Reported per episode: hover steps,
hover fraction, longest streak. A **sustained hover** is a streak ≥ 100 steps (2 s of simulated time).
Editing a reward's eligibility thresholds never changes the detector.

## Reported metrics (per evaluation)

Mean, standard deviation, median and **95% percentile-bootstrap interval of the mean** original return
(5,000 resamples, fixed seed), plus rates with **95% Wilson intervals** for: return ≥ 200, environment
success, strict pad landing, landed off pad, crash, out of bounds, time limit, body contact and sustained
hover. Also episode length, action counts per type, and main- and side-engine fractions. As context only, it
reports what the run's training reward *would* have paid on these episodes (rescored, never fed back).

## Two kinds of variability

- **Across evaluation episodes** of one policy: the bootstrap and Wilson intervals above.
- **Across independently trained policies:** one value per training seed, shown individually. With fewer
  than 5 seeds, across-seed summaries are labelled *descriptive only*. Episodes from different seeds are never
  pooled as if they came from many independent training runs.

## Aggregate statistics across training seeds

Following Agarwal et al., *Deep Reinforcement Learning at the Edge of the Statistical Precipice* (NeurIPS
2021), the Compare page and `docs/RESULTS.md` summarize a group of independently trained policies with:

- **IQM** (interquartile mean) of the per-policy mean original returns, computed exactly like rliable
  (`scipy.stats.trim_mean(x, 0.25)`: drop `int(0.25 n)` policies from each end, average the rest);
- **95% percentile-bootstrap intervals over policies** (5,000 resamples of training seeds), for the IQM, the
  mean and the pad-landing rate. Policies are the resampled unit, because training seeds are what differs
  between independent experiments; evaluation episodes are not resampled here;
- **probability of improvement** P(X > Y): the Mann–Whitney statistic over all pairs of policies
  (ties count ½), against the first group shown (the PPO original-reward baseline), with a bootstrap interval
  that resamples both groups. An interval that contains 0.5 means the data cannot order the two groups;
- **performance profiles**: the fraction of test episodes whose original return exceeds τ, for every τ on a
  shared grid, pooling a group's policies, with a 95% band from resampling policies.

With 3–5 policies per group, these intervals are wide. That is the honest result.

## Robustness (separate, labelled evaluations)

`python -m lunarlab robustness --experiment-id <id>` flies each run's **frozen** checkpoint (the one the
final test used) on the **first 50 final-test seeds** under physics it never trained on, with the original
reward:

| Condition | Change |
|---|---|
| `wind-5` | `enable_wind=True, wind_power=5, turbulence_power=0.5` |
| `wind-10` | `enable_wind=True, wind_power=10, turbulence_power=1.0` |
| `wind-15` | `enable_wind=True, wind_power=15, turbulence_power=1.5` (Gymnasium's default wind strength) |
| `gravity-11.5` | `gravity=-11.5` (default −10) |

The terrain and the initial push depend only on the episode seed, so each condition replays the same 50
episodes as the calm test. Results are stored as `evaluations/robustness-<condition>-….json` with split
`robustness:<condition>`; they never replace or change the final-test result, and nothing is selected or
tuned on them. Training and every primary evaluation keep the default physics (`make_env` accepts only these
four keys as overrides).

## Algorithm comparison (PPO vs DQN)

DQN runs use the same environment, reward wrapper, evaluation protocol and validation-based checkpoint
selection, with RL Baselines3 Zoo's LunarLander hyperparameters and Zoo's **100,000-transition** budget
(PPO: 1,000,000). The budgets differ on purpose (see ARCHITECTURE.md); comparisons flag this, so read
PPO-vs-DQN results as "each algorithm with its reference settings", not "equal experience".

## Reward-exploitation rule

The diagnostic asks: *is the agent earning more training reward without doing the actual landing task
better?* On the evaluation episodes of the selected checkpoint, a run is flagged **possible reward
exploitation** only when **all** hold:

1. its additional terms pay out (mean rescored training return − mean original return > 1.0);
2. behavioural evidence of what they pay for: sustained-hover rate ≥ 0.3, **or** mean hover fraction ≥ 0.25,
   **or** time-limit rate ≥ 0.3;
3. pad landing is not better than the original-reward baseline (same protocol), or ≤ 0.5 if no baseline is
   evaluated.

A gap between shaped and original return alone is **not** evidence; any bonus creates one. SMOKE runs are
always reported as *insufficient data*. Training-time trends (first vs last 20% of training episodes) are
shown as context only.

## Recordings

Recordings are single episodes on chosen seeds, evaluated under the same conditions. The UI shows each
recording's seed and split. Consult the outcome rates before treating any clip as typical.
`python -m lunarlab record-showcase --experiment-id <id> --references` records one policy per group (training
seed 0 by default) and the heuristic/random references on the same episode seeds, for side-by-side replays.
Keyboard flights (Fly It Yourself) are recorded the same way, with policy kind `human`, on seeds from
40,000–49,999 unless the player chooses one.
