# LunarLab and related software

The likely reviewer question is: *Stable-Baselines3 already trains, evaluates, records and loads models — what does
LunarLab add?* This page answers it with evidence. The capability matrix, with a source for every cell, is in
[COMPARISON_EVIDENCE.md](COMPARISON_EVIDENCE.md); measured runtime and memory are in
[BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md).

## What LunarLab is built on (not competitors)

- **Gymnasium** provides `LunarLander-v3` and `CartPole-v1`; LunarLab never modifies the environments' dynamics or
  rewards, it wraps them.
- **Stable-Baselines3 2.9.0** provides PPO and DQN. LunarLab constructs SB3's own `PPO`/`DQN` classes
  (`training.build_model`) and adds no learning algorithm of its own.
- **RL Baselines3 Zoo**: LunarLab's DQN settings are RL Zoo's tuned `LunarLander-v3` entry (`config.DQNConfig`).
- **rliable / Agarwal et al. (2021)**: LunarLab's interquartile mean, bootstrap intervals over training runs,
  probability of improvement and performance profiles follow that paper (`rl_stats.py` is an independent
  implementation for one task with a handful of runs; it does not depend on the `rliable` package).
- **Optuna** drives LunarLab's hyperparameter tuning, on validation episodes only.

## Related tools

| Tool | What it is for | Relation to LunarLab |
|---|---|---|
| Stable-Baselines3 | reliable implementations of RL algorithms, with callbacks (`EvalCallback`, `CheckpointCallback`), `Monitor`, `evaluate_policy`, save/load | LunarLab's dependency. SB3 evaluates whatever reward the wrapper stack returns unless `Monitor` sits below reward wrappers [S2]; keeping the original and shaped rewards apart, freezing the tested checkpoint and DQN continuation with the replay buffer and algorithm state are left to the user [S3–S5]. |
| RL Baselines3 Zoo | a training framework for SB3 with tuned hyperparameters, Optuna tuning, plots (partly rliable-based), videos | Overlaps on tuning and plotting. Reward shaping is possible through `env_wrapper`, with no documented original-versus-shaped logging [Z1]. |
| CleanRL | single-file reference implementations, TensorBoard/W&B tracking, benchmark utility | A different design goal (readable implementations to copy and edit). Resuming is a recipe that saves the agent's weights only [C2]. |
| rliable | statistically sound aggregate metrics with stratified bootstrap intervals across tasks | LunarLab reports the same family of statistics for one task across training seeds; rliable is the general library [R1]. |
| imitation | imitation learning and reward learning, including preference comparisons | Its `RewardVecEnvWrapper` keeps the original reward under `original_env_rew` [I1]; LunarLab's learned-reward studies are a small, LunarLander-specific counterpart with simulated and human labels [I2]. |
| AI Safety Gridworlds (DeepMind) | environments in which agents maximise a visible reward but are scored by a hidden performance function | The same distinction — what the agent is trained on versus what it is judged by — built into environment design; LunarLab applies it as instrumentation around an existing environment and reward. |
| Experiment trackers (TensorBoard, Weights & Biases, MLflow) | logging, dashboards, artifact storage | General-purpose infrastructure; LunarLab keeps its records as local files and needs no service or account. |

## What LunarLab adds, with evidence

LunarLab is an **auditing and experimentation layer** around SB3 for reward-design studies. Its distinguishing
contribution is the integration of the following into one tested workflow (cell references are to
[COMPARISON_EVIDENCE.md](COMPARISON_EVIDENCE.md)):

1. **Transition-level reward accounting**: the identity `training = w·original + Σ terms` is applied and
   recorded on every transition, with original, training and per-term returns kept apart, and evaluation is
   always on the original reward (rows 1–2, 13). The same accounting is available for other Gymnasium tasks
   through a small adapter interface (`lunarlab.audit`), tested to reproduce the LunarLander pipeline exactly.
2. **Reward-exploitation diagnostics**: a detector independent of the reward preset and a documented rule; the
   published study measures a flawed hover bonus being exploited (0 of 500 test landings) (row 3).
3. **An evaluation protocol that cannot leak**: validated, disjoint validation and test seeds; selection on
   validation only; the tested checkpoint frozen as an immutable, digest-checked copy; runs influenced by an
   already-seen test labelled exploratory (rows 4–5).
4. **Checkpoint-based continuation and provenance**: PPO and DQN runs resume from safe boundaries with optimizer
   state and (for DQN) the replay buffer and algorithm state, though not bit-identically to an uninterrupted run; every run records configuration, reward and protocol hashes, seeds, versions and source revisions
   (rows 6–8).
5. **Inspection and counterfactuals**: per-step telemetry with policy internals, and re-scoring of recorded
   flights under other reward designs (rows 9–10).
6. **Statistics across training seeds** and one-command regeneration of the published tables and figures
   (rows 11–12).
7. **Reproduction tooling for third parties**: `reproduce-smoke`, and supplied artifacts that re-evaluate
   bit-identically on the machine that produced them (see [REPRODUCIBILITY.md](REPRODUCIBILITY.md)).

The measured cost of the instrumentation is small compared with plain SB3 (row 16; numbers in
[BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md)).

## What LunarLab does not claim

- No new learning algorithm, and no claim of being faster than SB3 (it adds a small overhead to it).
- No claim to be the first tool with any single capability above; several exist elsewhere in some form, as the
  matrix shows. The contribution is their integration and verification for reward-design audits.
- No claim that auditing prevents reward hacking: LunarLab measures and exposes it.
- Generality is demonstrated only partially: the full pipeline is specific to `LunarLander-v3`; the adapter layer
  runs on `CartPole-v1` as a demonstration ([EXTENDING_LUNARLAB.md](EXTENDING_LUNARLAB.md)).
- No claim about real-world rocket control: everything is a 2-D simulation benchmark.
