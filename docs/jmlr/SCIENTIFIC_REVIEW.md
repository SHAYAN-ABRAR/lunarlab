# Scientific validity review of the published results and claims

Reviewed on 2026-10-17/18 against the stored records (read-only), and again on 2026-10-18 after CI ran the
readiness branch on Linux (correction pass). No result was recomputed into the published files; one sentence
of `docs/RESULTS.md` was reworded in the first pass, and four claims about the software were corrected in the
second (below).

## Checks

| Check | Finding | Evidence |
|---|---|---|
| Reward accounting | The identity `training = w·original + Σ terms` holds per transition and per episode; evaluation always uses the original reward and cross-checks it. | `tests/test_rewards.py`, `tests/test_properties.py`, `reproduce-smoke` |
| Checkpoint selection | Selected on 10 validation seeds by mean original return; never on test seeds. | `training` callback, `freeze.py` |
| Evaluation seed overlap | Validation 10,000–10,009, test 20,000–20,099, training workers ≥ 1,000,000, preference data 30,000–48,019: disjoint (checked in the stored preference dataset). | `INITIAL_AUDIT.md` |
| Training seed independence | Each run's worker seeds derive from its seed (base + 1000·seed + 100·segment + rank); runs of a group differ only in seed. | `config.RunConfig.worker_seeds`, run metadata |
| Protocol identity | All 44 runs share a valid protocol; configuration and protocol hashes pinned in tests. | `tests/test_protocol.py` |
| Failure categories | Outcome classifier v2 re-examination of 11,500 published episodes relabelled none. | `docs/results/outcome_reclassification_v2.md` |
| Confidence intervals and resampling units | Group IQM/mean intervals bootstrap over training runs; per-policy intervals over episodes; group pad-landing rates carry no pooled episode interval. Correct units. | `lunarlab/rl_stats.py`, `docs/EVALUATION.md` |
| Statistical comparisons | Probability of improvement (Mann–Whitney) with bootstrap intervals over runs; degenerate [0, 0] intervals explained as complete separation, not zero probability. | `README.md`, `docs/RESULTS.md` |
| Budget matching | PPO (1 M) and DQN (100 k) were compared at different reference budgets; every statement says so, and the matched-budget study is listed as not yet run. | `README.md` |
| Algorithm configuration differences | DQN uses RL Zoo's tuned LunarLander settings, PPO LunarLab's defaults; stated. | `config.DQNConfig` |
| Reward-exploitation labels | Hover-bonus policies: 0 of 500 test landings, 80 % at the time limit; the supplied seed-0 policy hovers 73 % of steps and its training reward (678.9) far exceeds its original return (−21.2). Consistent with the documented rule. | `examples/artifacts/ppo-hover-bonus-s0/`, `docs/EVALUATION.md` |
| Preference-data provenance | 380 episodes from the study's policies on collection seeds, stored with the dataset and its split; reward models validated on held-out episodes. | `data/preferences/…/meta.json` (local) |
| Robustness evaluation | Frozen checkpoints under wind, turbulence and gravity never seen in training, on test seeds not used for any selection. | `lunarlab/robustness.py` |
| Exploratory vs confirmatory | The 20 shaping runs and 12 DQN runs were created before any test result existed. The learned-reward study was created about a minute after the first shaping test results; its design was fixed by one command and its data uses disjoint seeds, so there is no evidence of test-set influence, but the timing is recorded here. | `INITIAL_AUDIT.md` |

## Claims

| Claim pattern | Status in the documents |
|---|---|
| "Potential-based shaping is better" | Not claimed. README and RESULTS: no clear evidence of improvement; equivalence not established either. |
| "PPO is better than DQN" | Not claimed. Budgets differ and are stated; the matched study is listed as not run. |
| "RLHF solved the task" | Not claimed. With 3,000 simulated labels PPO learned to land in 54 % of test episodes; with 300 labels two of three runs exploited the learned reward. The original reward still enters through the simulated labeller and checkpoint selection, and this is stated. |
| "The method generalizes" | Not claimed for the results. The software's adapter layer is demonstrated on CartPole only, as an example. |
| "The platform guarantees reproducibility" | Not claimed. Bit-identity holds within a platform (development machine and CI Windows machines, Python 3.12 and 3.13: 300/300 episodes); on Linux 0/300 episodes were bit-identical while mean returns moved by at most 1.51 and pad-landing rates were identical. Integrity, within-platform, cross-platform and conclusion stability are reported separately (`REPRODUCIBILITY.md`). |
| "Interrupted runs resume exactly" | **Was claimed** in the manuscript and in `RELATED_SOFTWARE.md`, `COMPARISON_EVIDENCE.md`, `REQUIREMENTS_MATRIX.md` and the README ("full training state"). **Corrected:** continuation restores the algorithm state (networks, optimizer, counters; for DQN the replay buffer, target-network phase and exploration) at a safe boundary; environments restart and random-number streams are not restored, so it is not bit-identical to uninterrupted training — as the code's own contract (`training.py`) already stated. |
| "The instrumentation adds about 4 % to training time" | **Was stated without its scope.** Corrected: about 0–4 % of the *training loop* (two runs, one on a clean checkout); a complete run takes 1.22–1.23 times as long as plain SB3 because of the validation episodes the protocol requires, reported separately (`BENCHMARK_PROTOCOL.md`). |
| "The adapter layer applies the accounting to any Gymnasium environment" | **Was too broad** (manuscript). Corrected: it applies to other Gymnasium environments through a small adapter, demonstrated on CartPole-v1 only; training, the evaluation protocol and checkpointing remain LunarLander-specific. |
| "The tool prevents reward hacking" | Not claimed. LunarLab measures and exposes exploitation. |
| Real-world rocket control | Explicitly disclaimed (2-D simulation benchmark). |

**Reworded:** `docs/RESULTS.md` said a single 3 M-transition baseline run was "no better than the 1M runs beyond
noise". One run cannot establish that, so it now says the run is "within the spread of the five 1M runs. One run
cannot show whether the longer budget helps." No number changed.

No verifiable error in the published results was found, so no corrected analysis was needed.

## Missing experiments, ranked by how much they would strengthen the submission

All commands exist and were smoke-tested; none of these was run here (compute rules), and none of their results
exists. Times are for the development laptop (i7-13620H, CPU).

1. **Cross-platform attribution and independent reproductions.** Linux and a second Windows machine have now
   re-evaluated the artifacts in CI (run 39069730331). Still missing: the per-step trace comparison on Linux that
   locates the first diverging step and separates simulator from inference differences (it runs in CI once the
   corrections are pushed: `python -m lunarlab trace-artifact --artifact examples/artifacts/<name> --compare
   reports/jmlr/reproducibility/traces/<name>-windows.npz`), and reproductions on machines not controlled by the
   author.
2. **More training seeds for the shaping comparison** (5 → 10 per group) to narrow the probability-of-improvement
   intervals: `python -m lunarlab suite --presets baseline,time-penalty,potential --seeds 5,6,7,8,9 --profile standard --parallel 5 --yes`
   — 15 runs × 1 M transitions, about 1–1.5 h with five in parallel.
3. **Matched-budget PPO vs DQN, crossed with the discount factor** (already designed; see `docs/RESULTS.md`,
   "Studies built but not yet run"): 40 runs of 303,104 transitions, roughly 4–7 h with six in parallel.
4. **A second task with a deliberately flawed term** (for example a CartPole state bonus through
   `lunarlab.audit`), to test whether the audit exposes exploitation beyond LunarLander: minutes per run; needs a
   preregistered protocol (seeds, budget, criterion) before running.
5. **Comprehensive overhead benchmark** (1 M transitions, 5 repetitions; and DQN):
   `python -m lunarlab overhead-benchmark --profile comprehensive --yes` — 15 PPO runs, about 2–3 h.
