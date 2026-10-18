# Capability comparison with related software: the evidence

Documentation of the other projects was read on 2026-10-17 (the `master`/`latest` documentation online; LunarLab
itself uses Stable-Baselines3 2.9.0). Every cell cites its source. For LunarLab the source is code and a test
that exercises it.

**Legend.** ● supported directly · ◐ possible through configuration, an extension or custom code · ○ not
documented in the sources reviewed (this is *not* a claim that the feature is absent) · — outside the tool's
scope (for example, an analysis library that does not train agents).

| # | Capability | LunarLab | Stable-Baselines3 | RL Baselines3 Zoo | CleanRL | rliable | imitation |
|---|---|---|---|---|---|---|---|
| 1 | Reward decomposed into named terms, per transition | ● [L1] | ◐ [S1] | ◐ [Z1] | ◐ [C1] | — | ◐ [I1] |
| 2 | Original and training (shaped) return recorded separately | ● [L2] | ◐ [S2] | ◐ [Z1] | ◐ [C1] | — | ● for learned rewards [I1] |
| 3 | Reward-exploitation diagnostics (preset-independent detector, documented rule) | ● [L3] | ○ | ○ | ○ | — | ○ |
| 4 | Disjoint validation/test seeds; selection on validation only | ● [L4] | ◐ [S3] | ◐ [S3][Z2] | ○ | — | ○ |
| 5 | Tested checkpoint frozen as an immutable, digest-checked copy | ● [L5] | ○ [S4] | ○ | ○ | — | ○ |
| 6 | Policy loading without unpickling (weights only) | ● [L6] | ◐ [S5] | ○ | ◐ [C2] | — | ○ |
| 7 | Checkpoint-based continuation of an interrupted run (optimizer, DQN replay buffer, counters; not bit-identical to an uninterrupted run) | ● [L7] | ◐ [S4][S5] | ○ | ◐ [C2] | — | ○ |
| 8 | Configuration identity (content hash of everything that defines a run) | ● [L8] | ◐ [S6] | ○ | ◐ [C3] | — | ○ |
| 9 | Per-step trajectory inspection (reward terms, policy internals) | ● [L9] | ◐ video [S7] | ◐ video [Z3] | ◐ video [C3] | — | ○ |
| 10 | Counterfactual re-scoring of recorded trajectories under other rewards | ● [L10] | ○ | ○ | ○ | — | ○ |
| 11 | Statistics across training seeds (IQM, bootstrap CIs, P(improvement), profiles) | ● [L11] | ○ | ◐ [Z4] | ○ | ● [R1] | ○ |
| 12 | One command regenerates tables and figures from stored evaluations | ● [L12] | ○ | ◐ [Z4] | ◐ [C4] | ◐ [R1] | ○ |
| 13 | Reward terms configurable without code changes | ● [L13] | ◐ [S1] | ◐ [Z1] | ◐ [C1] | — | ◐ [I1] |
| 14 | Hyperparameter tuning | ● validation only [L14] | ○ | ● [Z5] | ◐ [C5] | — | ○ |
| 15 | Learning a reward from preferences | ● simulated + human labels [L15] | — | — | — | — | ● [I2] |
| 16 | Runtime and memory measured against the underlying library | ● [L16] | — | ○ | ○ | — | ○ |
| 17 | Documentation | local Markdown, API reference, tutorial [L17] | hosted site [S8] | hosted site [Z6] | hosted site [C6] | README + notebook [R1] | hosted site [I3] |

## LunarLab evidence

- **[L1]** `lunarlab/rewards/terms.py::compute_terms`; per-step `info["lunarlab"]` and recorded steps in
  `lunarlab/rewards/wrapper.py`; tests `tests/test_rewards.py`, `tests/test_audit_core.py` (any task through
  `lunarlab.audit`).
- **[L2]** episode summary `original_return` / `training_return` and per-term returns
  (`rewards/accounting.py`); evaluation always uses the original reward and cross-checks it
  (`evaluation.run_episode`); `reproduce-smoke` check "training episodes record original and shaped returns
  separately".
- **[L3]** `lunarlab/hover.py` (detector independent of the reward preset), `docs/EVALUATION.md` (reward-exploitation
  rule), `tests/test_diagnostics.py`; published result: hover-bonus policies landed in 0 of 500 test episodes.
- **[L4]** `config.EvalProtocol.problems` (duplicates, overlap, ranges), `tests/test_protocol.py`; checkpoint
  selection on validation seeds only (`training` callback); `audit.seed_split_problems` for other tasks.
- **[L5]** `lunarlab/freeze.py`, `tests/test_freeze.py`; `reproduce-smoke` checks the tested digest equals the frozen,
  read-only copy.
- **[L6]** `policies.load_policy_weights` (`load_from_zip_file(..., load_data=False)` + `load_state_dict`).
- **[L7]** PPO resume contract and DQN continuation bundle (`continuation.py`), `tests/test_dqn_continuation.py`.
- **[L8]** `RunConfig.config_hash`, `RewardConfig.content_hash`, `EvalProtocol.protocol_hash`; pinned historical
  hashes in `tests/test_protocol.py`.
- **[L9]** `recording.py` (per-step telemetry, PPO action probabilities, DQN Q-values), Flight Replay page.
- **[L10]** `rescoring.py`, Reward Stress Test page, `tests/test_video_rescoring.py`.
- **[L11]** `rl_stats.py` (IQM, stratified-by-group bootstrap over training runs, probability of improvement,
  performance profiles), `tests/test_outcomes_stats_storage.py`, `tests/test_properties.py`.
- **[L12]** `python -m lunarlab results` and `report`.
- **[L13]** `RewardConfig` schema (`rewards/config.py`), `reward export` / `--reward-config` YAML.
- **[L14]** `tuning.py` (Optuna on validation episodes only), `tests/test_tuning.py`.
- **[L15]** `preferences/` (Bradley–Terry ensemble, simulated and human labels, active selection).
- **[L16]** `python -m lunarlab overhead-benchmark`; results in [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md).
- **[L17]** `README.md`, `docs/TUTORIAL.md`, `docs/DEVELOPER.md`, `docs/api/`, `docs/*.md`; no hosted documentation site.

## Sources for the other projects

- **[S1]** SB3 `Monitor(env, filename=None, allow_early_resets=True, reset_keywords=(), info_keywords=(), …)`:
  `info_keywords` logs "extra information to log, from the information return of env.step()". A reward
  decomposition needs a user-written Gymnasium wrapper.
  https://stable-baselines3.readthedocs.io/en/master/common/monitor.html
- **[S2]** SB3 `evaluate_policy`: wrappers "that modify rewards or episode lengths … will affect the evaluation
  results"; wrapping with `Monitor` "before anything else" avoids it.
  https://stable-baselines3.readthedocs.io/en/master/common/evaluation.html
- **[S3]** SB3 `EvalCallback`: evaluates on a separate `eval_env`, keeps the best model by `mean_reward`
  (`best_model_save_path`, `n_eval_episodes=5` by default). Seed separation is left to the user.
  https://stable-baselines3.readthedocs.io/en/master/guide/callbacks.html
- **[S4]** SB3 `CheckpointCallback` saves the model periodically; replay buffer and `VecNormalize` statistics only
  when `save_replay_buffer` / `save_vecnormalize` are set ("False by default"). No freezing or digest semantics
  are documented. Same page as [S3].
- **[S5]** SB3 `BaseAlgorithm.set_parameters(load_path_or_dict, exact_match=True, device='auto')` loads parameters
  in place; `load` "re-creates the model from scratch"; `OffPolicyAlgorithm.save_replay_buffer(path)` "Save the
  replay buffer as a pickle file". The save format stores class parameters as JSON with complex objects
  "serialized with cloudpickle".
  https://stable-baselines3.readthedocs.io/en/master/modules/base.html ·
  https://stable-baselines3.readthedocs.io/en/master/guide/save_format.html
- **[S6]** SB3 save format: the zip holds `data` (class parameters), `_stable_baselines3_version` and
  `system_info.txt`. Same page as [S5].
- **[S7]** SB3 "Record a Video" example: `VecVideoRecorder`, "Record an MP4 video".
  https://stable-baselines3.readthedocs.io/en/master/guide/examples.html · SB3 on reproducibility: "Completely
  reproducible results are not guaranteed across PyTorch releases or different platforms".
  https://stable-baselines3.readthedocs.io/en/master/guide/algos.html
- **[S8]** https://stable-baselines3.readthedocs.io/
- **[Z1]** RL Zoo configuration: `env_wrapper` takes dotted class paths with parameters; `monitor_kwargs` /
  `info_keywords` record extra episode data. No built-in reward-shaping wrapper or original-versus-shaped logging
  is documented. https://rl-baselines3-zoo.readthedocs.io/en/master/guide/config.html
- **[Z2]** RL Zoo provides training and evaluation scripts and evaluation during training.
  https://rl-baselines3-zoo.readthedocs.io/en/master/
- **[Z3]** RL Zoo "Record a Video of a Trained Agent".
  https://rl-baselines3-zoo.readthedocs.io/en/master/guide/enjoy.html
- **[Z4]** RL Zoo plot scripts "integrate some of rliable library features" (`--rliable`, `--iqm`, bootstrap
  intervals). https://rl-baselines3-zoo.readthedocs.io/en/master/guide/plot.html
- **[Z5]** RL Zoo: "We use Optuna for optimizing the hyperparameters" (TPE sampler, median and halving pruners).
  https://rl-baselines3-zoo.readthedocs.io/en/master/guide/tuning.html
- **[Z6]** https://rl-baselines3-zoo.readthedocs.io/
- **[C1]** CleanRL: "Every detail about an algorithm variant is put into a single standalone file"; it "is not
  meant to be imported". Reward changes are made by editing the script. https://docs.cleanrl.dev/
- **[C2]** CleanRL resume training is a recipe: `torch.save(agent.state_dict(), …)` uploaded to Weights & Biases
  and reloaded with `agent.load_state_dict`; optimizer state and replay buffers are not mentioned.
  https://docs.cleanrl.dev/advanced/resume-training/
- **[C3]** CleanRL feature list: TensorBoard logging, Weights & Biases experiment management, "Local
  Reproducibility via Seeding", gameplay video capture. https://docs.cleanrl.dev/ ·
  https://docs.cleanrl.dev/get-started/experiment-tracking/
- **[C4]** CleanRL benchmark utility. https://docs.cleanrl.dev/get-started/benchmark-utility/
- **[C5]** CleanRL hyperparameter tuning page. https://docs.cleanrl.dev/advanced/hyperparameter-tuning/
- **[C6]** https://docs.cleanrl.dev/
- **[R1]** rliable: "Library for reliable evaluation on RL and ML benchmarks, even with only a handful of seeds";
  stratified bootstrap confidence intervals, performance profiles, IQM, optimality gap, probability of
  improvement, plotting utilities. https://github.com/google-research/rliable
- **[I1]** imitation `RewardVecEnvWrapper` "Uses a provided reward_fn to replace the reward function returned by
  step()" and keeps "the previous reward given by the inner VecEnv in the returned info dict under the
  original_env_rew key"; `WrappedRewardCallback` logs the wrapped reward.
  https://imitation.readthedocs.io/en/latest/_api/imitation.rewards.reward_wrapper.html
- **[I2]** imitation preference comparisons: Bradley–Terry model over trajectory fragments, reward-network
  ensembles, a default gatherer with "synthetic preferences based on ground-truth rewards".
  https://imitation.readthedocs.io/en/latest/algorithms/preference_comparisons.html
- **[I3]** https://imitation.readthedocs.io/

## Measured comparison

Runtime and memory against the underlying library (row 16) are measured, not estimated: see
[BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md). LunarLab was not benchmarked against RL Zoo, CleanRL or imitation:
they train different code (CleanRL's own PPO, imitation's trainers), so a timing difference would not isolate
LunarLab's instrumentation.
