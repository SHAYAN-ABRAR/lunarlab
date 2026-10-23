# Comparison evidence map

Read with `RELATED_SOFTWARE.md`; external functionality is based on the linked primary documentation, not inferred from the absence of a marketing bullet.

| LunarLab claim | Direct implementation | Relevant test or example | Scope |
|---|---|---|---|
| Named reward decomposition | `rewards/terms.py`, `rewards/wrapper.py`, `rewards/accounting.py` | `tests/test_rewards.py`, `tests/test_properties.py` | Computes each transition; stores episode totals by default; step traces optional |
| Separate evaluation channels | `evaluation.py`, `rewards/wrapper.py` | `tests/test_evaluation.py`, `examples/artifacts/*/evaluation.json` | Original task reward and re-scored training reward |
| Seed/protocol validation | `config.py::EvalProtocol`, `audit/core.py` | `tests/test_protocol.py`, `tests/test_audit_core.py` | Does not prevent investigator reuse of test insights |
| Protected test checkpoint | `freeze.py`, `storage.py` | `tests/test_freeze.py` | Immutable-copy/digest contract, not an external adversarial security guarantee |
| Restricted policy loading | `policies.py::load_policy_weights` | `tests/test_training.py` | Skips SB3 saved Python configuration objects with `load_data=False`; do not broadly claim “no unpickling” |
| Stateful continuation | `training.py`, `continuation.py` | `tests/test_dqn_continuation.py` | Restores learning state; simulator/RNG continuation is not bit-identical |
| Provenance | `config.py`, `sysinfo.py`, `lineage.py` | `tests/test_provenance.py` | Some historical runs predate stronger provenance; source ZIP itself is independently pinned |
| Reward-independent hover diagnostics | `hover.py`, `outcomes.py` | `tests/test_diagnostics.py` | Preset-independent implementation, not a universally validated detector |
| Replay and re-scoring | `recording.py`, `rescoring.py` | `tests/test_video_rescoring.py` | Re-scoring the same trajectory is not estimating the policy that would learn under a new reward |
| Statistics | `rl_stats.py` | `tests/test_properties.py`, `tests/test_outcomes_stats_storage.py` | Training-run bootstrap; finite-seed uncertainty, fixed test-seed conditioning |
| Generic auditing API | `audit/` | CartPole example and `tests/test_audit_core.py` | Does not generalize the whole application |
| Benchmark | `overhead.py`, stored raw JSONL | `tests/test_overhead.py` | Runtime comparable under measured settings; historical C memory includes recording |

The comparison supports an integrated-software contribution. No claim of first implementation, superior RL algorithms, universal reward-hacking detection, or unique statistical methods is justified by these sources.
