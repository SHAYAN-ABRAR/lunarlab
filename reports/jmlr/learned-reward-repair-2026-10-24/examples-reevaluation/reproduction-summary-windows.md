## Artifact reproduction on windows-py3.12

| Artifact | Status | Exit | Integrity | Exact summary fields | Outcomes agree | Median / max abs original-return diff | Mean return (recorded -> here) | Pad landing | Aggregates |
|---|---|---:|---|---:|---:|---:|---:|---:|---|
| dqn-baseline-s0 | **exact** | 0 | ok | 100/100 | 100% | 0 / 0 | 155.36 -> 155.36 | 29% -> 29% | no significant difference |
| ppo-baseline-s0 | **exact** | 0 | ok | 100/100 | 100% | 0 / 0 | 265.86 -> 265.86 | 96% -> 96% | no significant difference |
| ppo-hover-bonus-s0 | **exact** | 0 | ok | 100/100 | 100% | 0 / 0 | -21.25 -> -21.25 | 0% -> 0% | no significant difference |

Exact matches concern five selected episode-summary fields, not complete trajectories. Non-significant differences do not establish equivalence; no equivalence margins were specified.

### Where the trajectories part (against the recorded Windows traces)

| Artifact | Seed | Source | First output difference | Action flips | First open-loop obs. difference (size) | Closed loop parts at | abs return diff |
|---|---:|---|---:|---:|---:|---:|---:|
| 20261015-224317-dqn-baseline-s0-custom-2fe1 | 20000 | none | - | 0 | - (-) | - | 0 |
| 20261015-224317-dqn-baseline-s0-custom-2fe1 | 20001 | none | - | 0 | - (-) | - | 0 |
| 20261015-224317-dqn-baseline-s0-custom-2fe1 | 20002 | none | - | 0 | - (-) | - | 0 |
| 20261015-223113-baseline-s0-standard-c5af | 20000 | none | - | 0 | - (-) | - | 0 |
| 20261015-223113-baseline-s0-standard-c5af | 20001 | none | - | 0 | - (-) | - | 0 |
| 20261015-223113-baseline-s0-standard-c5af | 20002 | none | - | 0 | - (-) | - | 0 |
| 20261015-223115-hover-bonus-s0-standard-3376 | 20000 | none | - | 0 | - (-) | - | 0 |
| 20261015-223115-hover-bonus-s0-standard-3376 | 20001 | none | - | 0 | - (-) | - | 0 |
| 20261015-223115-hover-bonus-s0-standard-3376 | 20002 | none | - | 0 | - (-) | - | 0 |

**Problems:** none
