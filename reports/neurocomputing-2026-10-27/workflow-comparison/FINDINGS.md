# Audit-workflow comparison: findings

Run on 27 October 2026 (16:35–16:42 UTC; cost measurement afterwards) from committed source `5c7a62a`, on
the main fixtures fixed by `protocol/HASHES.sha256` at 16:35:26 UTC. The machine was a Windows 11 laptop
with an Intel i7-13620H, Python 3.12.13, Stable-Baselines3 2.9.0, PyTorch 2.14.1 (CPU), Gymnasium 1.4.0
and NumPy 2.5.4. The only uncommitted file at the start was the log of the start time itself. The data home
stayed empty.

## Outcomes (`results/MATRIX.md`, raw output in `results/raw/`)

| | W1 conventional SB3 | W2 SB3 reference | W3 LunarLab |
|---|---|---|---|
| Clean control C0 | ran 100 episodes; no checks (unsupported), no false alarm | accepted, replay exact | accepted, replay exact |
| Numerical-difference control C1 | ran 100 episodes; no comparison (unsupported) | `numerical-difference` (exit 3), not labelled corruption | `numerical-difference` (exit 3), not labelled corruption |
| 12 faults (F01–F12) | 0 of 12 detected: all unsupported, and 100 episodes evaluated in each case without a warning | 12 of 12 rejected through the targeted check, before any episode | 12 of 12 rejected through the targeted check, before any episode |
| False alarms on controls | 0 | 0 | 0 |

W2 and W3 report identical status vectors (S1–S10) on all 14 cases. Because W2 shares no code with LunarLab
and was written from the specification, the agreement cross-checks W3's checks against an independent
implementation of the same specification. Both were written by the same developer with AI assistance, so
this is not evidence from an independent team.

W1 is the conventional SB3 evaluation. SB3's tools act during training (`EvalCallback`, best-model saving),
evaluate a policy (`evaluate_policy`, `Monitor`) or check an environment's API (`check_env`). They do not
verify recorded evidence. W1 therefore evaluated a swapped checkpoint, corrupted digest records, a mismatched
protocol, a changed reward dependency, a float seed and overlapping seeds without notice. Its returns (500
on every case) could not reveal any of these faults, because the swapped final checkpoint also balances to
the limit. `PPO.load(print_system_info=True)` did report the saved and the current system information, but
nothing compares it with a recorded evaluation. These are capabilities SB3 does not attempt; they are not
errors in SB3.

## What this shows and what it does not

- The specification's checks can be implemented on SB3 with custom code: W2 needs 277 counted lines.
  LunarLab supplies them as library functions, so mapping this neutral format onto them took 152 lines (W3).
  Within LunarLab's own artifact format the same checks run as one command
  (`lunarlab audit-artifact reproduce`). The integration, not any single check, is what LunarLab adds. A
  competent SB3 user who writes the checks obtains the same verdicts.
- The fault set is designed: 12 single-property faults of the kinds that motivate the workflow. The
  results say nothing about how often such faults occur, nor about faults outside the set.
- One task (CartPole), one policy and one recorded trajectory. The neutral format, the specification, W2 and
  W3 were all written by the developer of LunarLab.
- A digest check (S1, S2) establishes that bytes are the recorded ones, not that the recorded scientific
  labels are right. S6–S9 check the records' internal consistency against the declared definitions.

## Execution cost (`results/cost/COST.md`, `cost.json`)

| Workflow | Wall time, median (min–max), s | Self peak working set, median, MB | Sampled process-tree peak, median, MB |
|---|---|---|---|
| W1 | 20.94 (10.76–21.55) | 288 | 293 |
| W2 | 21.00 (20.76–21.23) | 289 | 294 |
| W3 | 21.67 (13.48–22.63) | 293 | 307 |

- **Variation:** each run evaluated the same 100 CartPole episodes (500 steps each), and the replay
  dominates. Wall times were bimodal over time: in blocks 1–2, W1 and W3 ran in 10.8–14.4 s, while the other
  runs took 20.8–22.6 s. That variation in machine state exceeds the 0.06–0.7 s differences between medians.
  With five runs these data do not support a precise cost difference.
- **Memory:** W3's process tree was larger (307 MB versus 293–294 MB) partly because of the `git`
  subprocesses its provenance record runs.
- **Rejected faults:** both W2 and W3 refused a faulty case in about 1.4 s without executing the policy,
  whereas W1 spent 16–20 s evaluating it.

## Custom code (`results/code_size.json`)

Counted lines are non-blank, non-comment and non-docstring lines, counted with `tokenize`: W1 65, W2 277,
W3 152. This indicates the setup a user writes for this format. It does not measure researcher time, and
no installation time, task completion time or user satisfaction was measured.
