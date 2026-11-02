# Audit-workflow comparison: outcome matrix

14 prespecified cases (2 controls, 12 faults), each run once by each workflow. Outcome definitions are in `protocol/PROTOCOL.md`. Raw output for each pair is under `raw/<workflow>/<case>/`.

| Case | Targeted check | W1 conventional SB3 | W2 SB3 reference | W3 LunarLab |
|---|---|---|---|---|
| C0-clean | none | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) |
| C1-numerical-difference | S10 | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) |
| F01-checkpoint-swapped | S1 | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) |
| F02-recorded-digest-corrupted | S1 | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) |
| F03-protocol-mismatch | S3 | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) |
| F04-dependency-missing | S2 | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) |
| F05-dependency-changed | S2 | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) |
| F06-coercible-seed | S4 | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) |
| F07-overlapping-seeds | S4 | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) |
| F08-nonfinite-parameter | S5 | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) |
| F09-original-channel-absent | S6 | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) |
| F10-inconsistent-totals | S7 | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) |
| F11-potential-at-truncation | S8 | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) |
| F12-outcome-schema-mismatch | S9 | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) | crashed (exit 1, ? episodes) |
