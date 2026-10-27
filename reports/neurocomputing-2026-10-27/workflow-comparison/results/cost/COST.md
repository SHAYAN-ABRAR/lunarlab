# Execution cost on the clean control (C0)

Each workflow evaluated the same 100 test episodes once per run; the workflows differ in the checks they perform. 5 runs per workflow in randomized blocks; fresh process each; one thread. Wall time includes interpreter start-up and imports. MB = 10^6 bytes.

| Workflow | Wall time median [95% CI of median] (min-max), s | Self peak working set median (min-max), MB | Sampled process-tree peak median, MB |
|---|---|---|---|
| W1 | 20.94 [10.76, 21.55] (10.76-21.55) | 288 (287-288) | 293 |
| W2 | 21.00 [20.76, 21.23] (20.76-21.23) | 289 (288-289) | 294 |
| W3 | 21.67 [13.48, 22.63] (13.48-22.63) | 293 (293-294) | 307 |
