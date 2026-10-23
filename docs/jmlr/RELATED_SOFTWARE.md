# Related software and defensible contribution

The comparison concerns documented capabilities, not a universal ranking. Evidence was checked against primary documentation and papers on 18–19 October 2026. LunarLab uses SB3 rather than replacing it.

| Project | Established capability relevant here | What LunarLab adds or integrates | Important limitation of the comparison |
|---|---|---|---|
| Stable-Baselines3 | Tested RL algorithms, Monitor, separate evaluation environments, EvalCallback, checkpoint and replay-buffer APIs | Named reward accounting with task diagnostics, seed/protocol checks and protected final-test artifacts in one workflow | These features can be composed by an SB3 user; evaluation safety is not absent from SB3 |
| RL Baselines3 Zoo | Configured experiments, tuned agents, Optuna, evaluation, videos and rliable-based plotting | A reward-design-oriented record linking term definitions, checkpoint identity and task outcomes | Zoo offers broader algorithm/environment recipes; no runtime comparison to Zoo was performed |
| CleanRL | Inspectable single-file algorithms, seeding, logs, tracking and benchmark utilities | A reusable audit/process layer and local experiment interface | Different architecture and goals; does not establish LunarLab algorithm superiority |
| rliable | IQM, bootstrap intervals, improvement probability and performance profiles | Connects analysis to stored per-policy evaluations and task-specific diagnostics | LunarLab implements related statistics locally; its episode-pooled profile is not the same as every rliable multi-task analysis |
| imitation | Reward replacement while retaining original rewards, preference learning, reward ensembles | Integrates analogous reward separation with the LunarLab selection/freeze/diagnostic workflow | Original-versus-learned reward accounting is established prior art; simulated task-reward preferences are not a new reward-learning method |
| AI Safety Gridworlds | Benchmarks separating reward and performance to expose specification failures | A richer LunarLander experiment/provenance and replay workflow | The benchmark environments, goals and validity criteria differ; no direct performance comparison is claimed |

A fair novelty statement is: “LunarLab integrates existing RL and evaluation techniques into an auditable reward-design workflow with explicit artifact identity and task diagnostics.” An unsupported statement is: “LunarLab is the first software to separate original and training rewards.”

## Primary sources

- SB3 paper: https://jmlr.org/papers/v22/20-1364.html
- SB3 evaluation advice: https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html
- SB3 callbacks: https://stable-baselines3.readthedocs.io/en/master/guide/callbacks.html
- SB3 monitoring/evaluation: https://stable-baselines3.readthedocs.io/en/master/common/evaluation.html
- RL Zoo: https://rl-baselines3-zoo.readthedocs.io/en/master/ ; plotting: https://rl-baselines3-zoo.readthedocs.io/en/master/guide/plot.html
- CleanRL paper: https://jmlr.org/papers/v23/21-1342.html ; documentation: https://docs.cleanrl.dev/
- rliable: https://github.com/google-research/rliable ; paper: https://arxiv.org/abs/2108.13264
- imitation original-reward preservation: https://imitation.readthedocs.io/en/latest/_api/imitation.rewards.reward_wrapper.html
- imitation paper: https://arxiv.org/abs/2211.11972
- AI Safety Gridworlds: https://arxiv.org/abs/1711.09883

See `COMPARISON_EVIDENCE.md` for code pointers and `BENCHMARK_PROTOCOL.md` for the only measured cross-implementation comparison, against SB3 on matched workloads.
