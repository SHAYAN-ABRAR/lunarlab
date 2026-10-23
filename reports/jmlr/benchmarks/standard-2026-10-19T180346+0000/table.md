Measured 2026-10-19T18:03:46+00:00 on 13th Gen Intel(R) Core(TM) i7-13620H (Windows-11-10.0.26300-SP0), Python 3.12.13, lunarlab 0.1.0 (source 67440c664f65, uncommitted changes). PPO, 102,400 transitions per run, 3 repetitions per configuration, torch threads 1, CPU only. Mean ± SD over repetitions.

| Configuration | Training-loop time (s) | Loop throughput (transitions/s) | Loop time vs A | Validation (s, env steps) | Checkpoints (s) | CPU utilisation | Peak memory (MB) | Artifacts (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A · plain SB3 (Monitor only) | 47.5 ± 0.5 | 2,158 ± 22 | 1.00× | 0.0 (0) | 0.00 | 0.96 | 310 | 0.15 |
| B · + LunarLab reward accounting | 48.4 ± 0.7 | 2,115 ± 29 | 1.02× | 0.0 (0) | 0.00 | 0.96 | 310 | 0.15 |
| C · full LunarLab pipeline | 50.0 ± 1.4 | 2,051 ± 55 | 1.05× | 7.9 (18,780) | 0.08 | 0.94 | 314 | 1.06 |

Training-loop time excludes C's validation episodes and checkpoint writes (reported in their own columns). Artifacts: A and B save one SB3 model file; C keeps its whole run directory (checkpoints, episode CSV, metrics, events, status, validation results).
