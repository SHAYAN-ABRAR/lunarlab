# Audit-workflow comparison, follow-up run (version 2): outcome matrix

Run `b4aeb4cc832d46e78c3d0a8e70d5d903`, 2026-11-03T16:06:53Z to 2026-11-03T16:13:17Z, on Windows-11-10.0.26300-SP0, Python 3.12.13, torch 2.14.1, numpy 2.5.4, Box2D 2.3.10, gymnasium 1.4.0, stable-baselines3 2.9.0.

Inputs: verified against `protocol/HASHES.sha256` and `HASHES-v2.sha256`.

Each cell: raw verdict (exit status, episodes) · the frozen runner's literal-rule outcome · the follow-up assessment. Outcome definitions: `protocol/PROTOCOL.md`; assessment rules: `assessment.py`.

| Case | Targeted check | W1 conventional SB3 | W2 SB3 reference | W3 LunarLab |
|---|---|---|---|---|
| C0-clean | none | unchecked (exit 4, 100 episodes) · unsupported · **exact-agreement** | accepted (exit 0, 100 episodes) · correct · **exact-agreement** | accepted (exit 0, 100 episodes) · correct · **exact-agreement** |
| C1-numerical-difference | S10 | unchecked (exit 4, 100 episodes) · unsupported · **exact-agreement** | accepted-numerical-difference (exit 3, 100 episodes) · correct · **exact-agreement** | accepted-numerical-difference (exit 3, 100 episodes) · correct · **exact-agreement** |
| F01-checkpoint-swapped | S1 | unchecked (exit 4, 100 episodes) · unsupported · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** |
| F02-recorded-digest-corrupted | S1 | unchecked (exit 4, 100 episodes) · unsupported · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** |
| F03-protocol-mismatch | S3 | unchecked (exit 4, 100 episodes) · unsupported · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** |
| F04-dependency-missing | S2 | unchecked (exit 4, 100 episodes) · unsupported · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** |
| F05-dependency-changed | S2 | unchecked (exit 4, 100 episodes) · unsupported · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** |
| F06-coercible-seed | S4 | unchecked (exit 4, 100 episodes) · unsupported · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** |
| F07-overlapping-seeds | S4 | unchecked (exit 4, 100 episodes) · unsupported · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** |
| F08-nonfinite-parameter | S5 | unchecked (exit 4, 100 episodes) · unsupported · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** |
| F09-original-channel-absent | S6 | unchecked (exit 4, 100 episodes) · unsupported · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** |
| F10-inconsistent-totals | S7 | unchecked (exit 4, 100 episodes) · unsupported · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** |
| F11-potential-at-truncation | S8 | unchecked (exit 4, 100 episodes) · unsupported · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** |
| F12-outcome-schema-mismatch | S9 | unchecked (exit 4, 100 episodes) · unsupported · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** | rejected-before-execution (exit 1, 0 episodes) · rejected · **exact-agreement** |

**Assessment: passed.** 42 of 42 pairs present; classes: exact-agreement 42.

- W2 and W3 report the same S1-S10 statuses: yes (14 cases; disagreeing or missing: none).
- W2 and W3 reject all 12 faults before execution: yes (not so: none).
- W1 is unchecked in every case: yes (otherwise: none).

Memory telemetry (optional): measured in 42 of 42 results.
