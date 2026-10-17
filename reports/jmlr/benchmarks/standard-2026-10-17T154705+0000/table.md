Measured 2026-10-17T15:47:05+00:00 on 13th Gen Intel(R) Core(TM) i7-13620H (Windows-11-10.0.26300-SP0), Python 3.12.13, lunarlab 0.1.0 (source 28dd935c9253, uncommitted changes). PPO, 102,400 transitions per run, 3 repetitions per configuration, torch threads 1, CPU only. Mean ± SD over repetitions.

| Configuration | Training-loop time (s) | Loop throughput (transitions/s) | Loop time vs A | Validation (s, env steps) | Checkpoints (s) | CPU utilisation | Peak memory (MB) | Artifacts (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A · plain SB3 (Monitor only) | 48.8 ± 0.2 | 2,097 ± 8 | 1.00× | 0.0 (0) | 0.00 | 0.96 | 310 | 0.15 |
| B · + LunarLab reward accounting | 50.7 ± 0.3 | 2,019 ± 13 | 1.04× | 0.0 (0) | 0.00 | 0.95 | 311 | 0.15 |
| C · full LunarLab pipeline | 50.9 ± 1.2 | 2,013 ± 48 | 1.04× | 8.4 (18,780) | 0.09 | 0.94 | 323 | 1.06 |

Training-loop time excludes C's validation episodes and checkpoint writes (reported in their own columns). Artifacts: A and B save one SB3 model file; C keeps its whole run directory (checkpoints, episode CSV, metrics, events, status, validation results).
