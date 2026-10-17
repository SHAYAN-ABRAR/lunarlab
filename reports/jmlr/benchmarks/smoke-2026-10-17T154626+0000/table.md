Measured 2026-10-17T15:46:26+00:00 on 13th Gen Intel(R) Core(TM) i7-13620H (Windows-11-10.0.26300-SP0), Python 3.12.13, lunarlab 0.1.0 (source 28dd935c9253, uncommitted changes). PPO, 8,192 transitions per run, 2 repetitions per configuration, torch threads 1, CPU only. Mean ± SD over repetitions.

| Configuration | Training-loop time (s) | Loop throughput (transitions/s) | Loop time vs A | Validation (s, env steps) | Checkpoints (s) | CPU utilisation | Peak memory (MB) | Artifacts (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A · plain SB3 (Monitor only) | 3.4 ± 0.0 | 2,410 ± 11 | 1.00× | 0.0 (0) | 0.00 | 0.97 | 310 | 0.15 |
| B · + LunarLab reward accounting | 3.7 ± 0.1 | 2,198 ± 72 | 1.10× | 0.0 (0) | 0.00 | 0.97 | 310 | 0.15 |
| C · full LunarLab pipeline | 4.1 ± 0.0 | 1,977 ± 18 | 1.22× | 0.9 (2,865) | 0.04 | 0.91 | 316 | 0.53 |

Training-loop time excludes C's validation episodes and checkpoint writes (reported in their own columns). Artifacts: A and B save one SB3 model file; C keeps its whole run directory (checkpoints, episode CSV, metrics, events, status, validation results).
