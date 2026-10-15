_Generated 2026-10-15T20:50:40+00:00 by `python -m lunarlab results` from stored final-test evaluations (100 held-out episode seeds per policy, frozen validation-selected checkpoints, original reward)._

### Aggregate per group

P(improvement) is against **Original baseline**: the probability that a randomly chosen policy of the group scores higher than a randomly chosen reference policy. Intervals: 95% bootstrap over policies.

| Group | Policies | IQM [95% CI] | Mean [95% CI] | Pad landing | Env. success | Crash | Time limit | P(improvement) [95% CI] |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Original baseline | 5 | 268.6 [255, 272] | 265.8 [258, 271] | 98% | 99% | 1% | 0% | reference |
| Time-penalty ablation | 5 | 265.3 [247, 269] | 260.4 [249, 268] | 94% | 98% | 2% | 0% | 0.32 [0.00, 0.72] |
| Flawed hover bonus | 5 | -33.1 [-54, 16] | -23.5 [-48, 8] | 0% | 12% | 7% | 80% | 0.00 [0.00, 0.00] |
| Potential-based shaping | 5 | 262.3 [238, 274] | 258.6 [242, 271] | 94% | 95% | 1% | 4% | 0.36 [0.00, 0.76] |
| Learned reward 300 pairs | 3 | -165.2 [-342, 151] | -165.2 [-342, 151] | 12% | 23% | 38% | 0% | 0.00 [0.00, 0.00] |
| Learned reward 3000 pairs | 3 | 200.2 [183, 222] | 200.2 [183, 222] | 54% | 81% | 17% | 1% | 0.00 [0.00, 0.00] |
| DQN · Original baseline | 3 | 211.0 [155, 270] | 211.0 [155, 270] | 54% | 77% | 11% | 11% | 0.20 [0.00, 0.67] |
| DQN · Time-penalty ablation | 3 | 177.2 [117, 207] | 177.2 [117, 207] | 31% | 62% | 8% | 28% | 0.00 [0.00, 0.00] |
| DQN · Flawed hover bonus | 3 | 109.6 [7, 224] | 109.6 [7, 224] | 41% | 60% | 22% | 14% | 0.00 [0.00, 0.00] |
| DQN · Potential-based shaping | 3 | 207.2 [150, 245] | 207.2 [150, 245] | 61% | 75% | 20% | 5% | 0.00 [0.00, 0.00] |

### Robustness (mean original return over policies · strict pad-landing rate)

| Group | calm | wind-5 | wind-10 | wind-15 | gravity-11.5 |
|---|---:|---:|---:|---:|---:|
| Original baseline | 266 · 98% | 229 · 72% | 173 · 47% | 93 · 22% | 253 · 93% |
| Time-penalty ablation | 260 · 94% | 225 · 72% | 159 · 41% | 90 · 22% | 241 · 88% |
| Flawed hover bonus | -24 · 0% | -28 · 0% | -46 · 0% | -68 · 0% | -41 · 0% |
| Potential-based shaping | 259 · 94% | 231 · 76% | 180 · 52% | 105 · 24% | 248 · 91% |
| Learned reward 300 pairs | -165 · 12% | -202 · 9% | -245 · 4% | -270 · 1% | -170 · 11% |
| Learned reward 3000 pairs | 200 · 54% | 193 · 44% | 130 · 28% | 51 · 11% | 184 · 45% |
| DQN · Original baseline | 211 · 54% | 202 · 57% | 154 · 41% | 61 · 23% | 182 · 49% |
| DQN · Time-penalty ablation | 177 · 31% | 174 · 33% | 97 · 31% | -26 · 18% | 173 · 35% |
| DQN · Flawed hover bonus | 110 · 41% | 105 · 33% | 77 · 29% | 11 · 15% | 119 · 41% |
| DQN · Potential-based shaping | 207 · 61% | 174 · 47% | 110 · 27% | 36 · 14% | 167 · 48% |

Conditions: `calm` = Calm (default physics, final test); `wind-5` = Light wind (5, turbulence 0.5); `wind-10` = Moderate wind (10, turbulence 1.0); `wind-15` = Strong wind (15, turbulence 1.5); `gravity-11.5` = Heavy gravity (-11.5 instead of -10).

### Every policy

| Group | Seed | Run | Checkpoint (transitions) | Mean [95% CI over episodes] | Pad | Success | Crash | Time limit | Hover fraction |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| Original baseline | 0 | `20261015-223113-baseline-s0-standard-c5af` | 1,003,520 | 265.9 [257, 274] | 96% | 97% | 3% | 0% | 0.001 |
| Original baseline | 1 | `20261015-223115-baseline-s1-standard-3b80` | 1,003,520 | 273.0 [269, 277] | 100% | 100% | 0% | 0% | 0.001 |
| Original baseline | 2 | `20261015-223115-baseline-s2-standard-5b5d` | 1,003,520 | 250.1 [242, 257] | 94% | 98% | 2% | 0% | 0.001 |
| Original baseline | 3 | `20261015-223115-baseline-s3-standard-7b0f` | 950,272 | 268.3 [262, 274] | 99% | 99% | 1% | 0% | 0.001 |
| Original baseline | 4 | `20261015-223115-baseline-s4-standard-f7f6` | 1,003,520 | 271.5 [267, 276] | 99% | 100% | 0% | 0% | 0.001 |
| Time-penalty ablation | 0 | `20261015-223115-time-penalty-s0-standard-2582` | 1,003,520 | 267.0 [263, 271] | 100% | 100% | 0% | 0% | 0.001 |
| Time-penalty ablation | 1 | `20261015-223115-time-penalty-s1-standard-6fc9` | 1,003,520 | 262.5 [257, 268] | 94% | 99% | 0% | 1% | 0.001 |
| Time-penalty ablation | 2 | `20261015-223115-time-penalty-s2-standard-9f88` | 950,272 | 269.7 [265, 274] | 100% | 100% | 0% | 0% | 0.001 |
| Time-penalty ablation | 3 | `20261015-223115-time-penalty-s3-standard-f398` | 1,003,520 | 236.5 [223, 249] | 75% | 91% | 8% | 1% | 0.001 |
| Time-penalty ablation | 4 | `20261015-223115-time-penalty-s4-standard-828d` | 1,003,520 | 266.5 [261, 272] | 99% | 99% | 1% | 0% | 0.001 |
| Flawed hover bonus | 0 | `20261015-223115-hover-bonus-s0-standard-3376` | 200,704 | -21.2 [-25, -17] | 0% | 0% | 0% | 100% | 0.734 |
| Flawed hover bonus | 1 | `20261015-223115-hover-bonus-s1-standard-9a39` | 53,248 | -30.3 [-35, -25] | 0% | 1% | 1% | 98% | 0.679 |
| Flawed hover bonus | 2 | `20261015-223115-hover-bonus-s2-standard-d887` | 102,400 | -47.8 [-58, -38] | 0% | 3% | 0% | 91% | 0.675 |
| Flawed hover bonus | 3 | `20261015-223115-hover-bonus-s3-standard-c5ba` | 151,552 | 38.6 [17, 60] | 0% | 57% | 32% | 11% | 0.316 |
| Flawed hover bonus | 4 | `20261015-223115-hover-bonus-s4-standard-cc47` | 950,272 | -57.0 [-61, -53] | 0% | 0% | 0% | 100% | 0.866 |
| Potential-based shaping | 0 | `20261015-223115-potential-s0-standard-0162` | 1,003,520 | 261.7 [255, 267] | 96% | 97% | 0% | 3% | 0.001 |
| Potential-based shaping | 1 | `20261015-223115-potential-s1-standard-9f70` | 802,816 | 228.9 [216, 241] | 81% | 82% | 7% | 11% | 0.001 |
| Potential-based shaping | 2 | `20261015-223115-potential-s2-standard-7f75` | 1,003,520 | 256.9 [249, 264] | 94% | 94% | 0% | 6% | 0.001 |
| Potential-based shaping | 3 | `20261015-223115-potential-s3-standard-91e6` | 1,003,520 | 277.2 [273, 281] | 100% | 100% | 0% | 0% | 0.001 |
| Potential-based shaping | 4 | `20261015-223115-potential-s4-standard-0b22` | 950,272 | 268.2 [264, 272] | 99% | 100% | 0% | 0% | 0.001 |
| Learned reward 300 pairs | 0 | `20261015-235939-custom-s0-standard-0274` | 1,003,520 | 151.0 [124, 177] | 35% | 68% | 28% | 0% | 0.001 |
| Learned reward 300 pairs | 1 | `20261015-235939-custom-s1-standard-b692` | 53,248 | -304.5 [-345, -265] | 1% | 1% | 45% | 0% | 0.002 |
| Learned reward 300 pairs | 2 | `20261015-235940-custom-s2-standard-a299` | 151,552 | -342.2 [-390, -296] | 0% | 0% | 41% | 0% | 0.008 |
| Learned reward 3000 pairs | 0 | `20261015-235940-custom-s0-standard-d28b` | 450,560 | 196.3 [175, 216] | 66% | 84% | 15% | 1% | 0.002 |
| Learned reward 3000 pairs | 1 | `20261015-235940-custom-s1-standard-ce26` | 1,003,520 | 221.6 [202, 239] | 54% | 86% | 11% | 2% | 0.001 |
| Learned reward 3000 pairs | 2 | `20261015-235940-custom-s2-standard-dbc1` | 651,264 | 182.8 [160, 204] | 42% | 74% | 25% | 1% | 0.001 |
| DQN · Original baseline | 0 | `20261015-224317-dqn-baseline-s0-custom-2fe1` | 90,000 | 155.4 [128, 182] | 29% | 58% | 28% | 13% | 0.002 |
| DQN · Original baseline | 1 | `20261015-224318-dqn-baseline-s1-custom-1fa1` | 20,000 | 207.6 [195, 220] | 35% | 77% | 3% | 20% | 0.019 |
| DQN · Original baseline | 2 | `20261015-224318-dqn-baseline-s2-custom-f083` | 90,000 | 270.1 [262, 277] | 97% | 97% | 3% | 0% | 0.014 |
| DQN · Time-penalty ablation | 0 | `20261015-224318-dqn-time-penalty-s0-custom-c4a9` | 50,000 | 116.8 [101, 131] | 3% | 25% | 3% | 70% | 0.173 |
| DQN · Time-penalty ablation | 1 | `20261015-224318-dqn-time-penalty-s1-custom-dc89` | 70,000 | 207.3 [187, 226] | 49% | 77% | 15% | 7% | 0.003 |
| DQN · Time-penalty ablation | 2 | `20261015-224318-dqn-time-penalty-s2-custom-9494` | 100,000 | 207.5 [184, 227] | 42% | 83% | 6% | 8% | 0.051 |
| DQN · Flawed hover bonus | 0 | `20261015-224318-dqn-hover-bonus-s0-custom-aefc` | 50,000 | 224.1 [213, 234] | 84% | 95% | 1% | 4% | 0.151 |
| DQN · Flawed hover bonus | 1 | `20261015-224318-dqn-hover-bonus-s1-custom-e122` | 60,000 | 97.2 [62, 130] | 24% | 43% | 24% | 31% | 0.188 |
| DQN · Flawed hover bonus | 2 | `20261015-224318-dqn-hover-bonus-s2-custom-9c0f` | 100,000 | 7.4 [-31, 47] | 14% | 41% | 40% | 6% | 0.047 |
| DQN · Potential-based shaping | 0 | `20261015-224318-dqn-potential-s0-custom-ee4b` | 30,000 | 227.2 [209, 244] | 63% | 81% | 14% | 5% | 0.002 |
| DQN · Potential-based shaping | 1 | `20261015-224318-dqn-potential-s1-custom-5487` | 90,000 | 244.9 [235, 253] | 90% | 94% | 4% | 2% | 0.059 |
| DQN · Potential-based shaping | 2 | `20261015-224318-dqn-potential-s2-custom-5b10` | 80,000 | 149.7 [128, 171] | 29% | 51% | 41% | 8% | 0.046 |

Comparability notes: Different algorithms (DQN, PPO): read this as an algorithm comparison; their settings and budgets differ by design.
