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

## Training under varied physics

A run can train with per-episode randomized physics (`train --physics randomized`, `suite --physics both`, or
*Training physics* in the Training Console). Before every training episode, `lunarlab/physics.py` draws:
wind on with probability `wind_probability` (default 0.8); if on, wind power uniform in `wind_power`
(default 0–10) and turbulence uniform in `turbulence_power` (default 0–1); gravity uniform in `gravity`
(default −11 to −9). The draw is seeded from the worker's episode seed, so a run is reproducible, and it is
logged per episode (`wind`, `wind_power`, `turbulence_power`, `gravity` columns of `episodes.csv`).

What stays the same for every run, fixed or randomized: validation (checkpoint selection) and the final test
fly **default physics**, and the robustness conditions above evaluate the frozen checkpoint. With the default
ranges, `wind-5`, `wind-10` and the calm test lie inside the training distribution, while `wind-15` and
`gravity-11.5` lie outside it. Compare & Diagnose pairs fixed and randomized groups of the same algorithm,
reward and discount and shows both across the calm test and every robustness condition, each difference with
a 95% bootstrap interval that resamples each side's policies (coloured only when it excludes zero).

## Automatic tuning and the test set

Tuning (`python -m lunarlab tune`, or *Automatic Tuning* in the UI) uses **validation only**. Every trial is
a normal run trained with the sampled settings, the same training seed as every other trial of the study
(common random numbers), and validated every `validation_every` transitions on the protocol's 10 validation
seeds with default physics and the original reward. Each validation is reported to Optuna; after the warm-up
(`warmup_transitions`, and `startup_trials` complete trials), a median pruner may stop a trial whose
validation return is below the median of earlier trials at the same point. A trial's value is its best
validation return, the criterion that also selects a run's checkpoint.

Trial runs carry `tuning: {study_id, trial}` in their metadata and are **refused** by the final-test
evaluation. `tune-apply` (or *Normal runs from best*) creates fresh, unmarked runs from the best settings with
new training seeds and a normal budget; only those are trained to completion and evaluated on the test seeds.
Selecting the maximum of many noisy validation scores flatters the winner, which is exactly why its test
result has to come from these fresh runs.

## Algorithm comparison (PPO vs DQN)

DQN runs use the same environment, reward wrapper, evaluation protocol and validation-based checkpoint
selection, with RL Baselines3 Zoo's LunarLander hyperparameters. Compare & Diagnose says which of two kinds of
comparison a selection is:

- **Each algorithm at its reference setup** (the published DQN experiment): Zoo's **100,000-transition**
  budget for DQN, 1,000,000 for PPO. Read it as "each algorithm with its reference settings", not "equal
  experience".
- **Matched budgets** (`suite --algos ppo,dqn`, or several algorithms in the Training Console's experiment
  form): one experiment, the same rewards and training seeds for both algorithms, and the budget rounded up to
  a multiple of every algorithm's rollout, so every run trains on exactly the same number of transitions
  (300,000 requested → 303,104; 1,000,000 → 1,003,520).

Learning curves can be read against **transitions** (sample efficiency) or **wall-clock time** (cost on this
machine): the Compare page switches the axis, and `results` draws both for every reward trained by several
algorithms at one budget (`algorithm_comparison.png`). Wall-clock time runs from the start of each training
segment's loop, validation passes and checkpoint saves included; pauses between the segments of a resumed run
are not counted. It depends on the machine and on how many runs trained at the same time, so it compares
speed only between runs trained under the same conditions. Every training segment records how many runs its
launcher trained at once (`parallel_slots`: `--parallel N`, or the app's training lane), and Compare lists
every difference between the selected runs (machine, runs in parallel, device, threads) under the time axis.
In `results`, a group's time curve stops when its first seed finished, so its mean is never carried by the
slowest seeds alone. Every group has several independently trained policies (training seeds), and all
statistics are computed over them as described above.

### Discount-factor ablation

PPO's reference discount factor is 0.999 and DQN's is 0.99, so the reference-setup comparison changes the
algorithm and γ at once. `suite --algos ppo,dqn --gammas 0.99,0.999` trains the 2 × 2 design: both
algorithms at both discount factors, with the same rewards, seeds, budget and evaluation, and every other
setting at its reference value. For every reward and training physics with such a contrast, Compare &
Diagnose, `compare` and `results` report:

- each algorithm × γ cell: the mean over training seeds of every policy's final-test mean original return,
  with a 95% bootstrap interval over seeds, and the pad-landing rate;
- the effect of γ within each algorithm, against that algorithm's reference γ;
- PPO − DQN at each matched γ and, for contrast, at their reference settings (where both differ);
- for each difference, a 95% interval that resamples each cell's seeds independently, and P(first higher).

A difference counts as evidence only when its interval excludes zero (the Compare page colours only those).
The cells come from groups that differ in γ alone; when budgets, other hyperparameters or protocols differ
between cells, or a cell has fewer than five seeds, the table says so.

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
Recordings of trained policies also store, for every step, what the network computed on the observation it
acted on (row *k* holds the decision that produced frame *k*): PPO's action probabilities, their entropy and
the critic's value V(s); DQN's Q-values. They are computed separately from choosing the action, so recorded
actions are unchanged (with deterministic evaluation the action is the most probable / highest-valued one,
which the tests check). Values are stored rounded (probabilities to 5 decimals, Q-values and V(s) to 4), so a
near-tie can show two equal values; the chosen action is always one of the largest. In a smooth deterministic
descent PPO's entropy is often close to uniform (ln 4 ≈ 1.39): the policy is nearly indifferent there and
decisive where it matters. As a check, for the potential-shaping seed-0 policy the entropy these diagnostics
compute, averaged over states visited with *sampled* actions (10 episodes), is 0.721, against 0.724 logged by
SB3 in its last update; averaged over deterministic flights it is 1.16. V(s) estimates the discounted *training*-reward return, so for a shaped reward it is on
the shaped scale. Recordings made before this existed have no such fields; Flight Replay says so.
`python -m lunarlab record-showcase --experiment-id <id> --references` records one policy per group (training
seed 0 by default) and the heuristic/random references on the same episode seeds, for side-by-side replays.
Keyboard flights (Fly It Yourself) are recorded the same way, with policy kind `human`, on seeds from
40,000–49,999 unless the player chooses one.
