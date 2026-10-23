# Published study summaries: regeneration and raw-episode recomputation

Date: 2026-10-19. Machine: the original Windows 11 data home. Nothing in `runs/` or `docs/results/` was
written; a before/after SHA-256 integrity scan of 1,875 protected files (runs, data, reports,
docs/results, docs/media, demo/api, examples/artifacts) found 0 added, 0 removed and 0 changed files.

## 1. Regeneration with the shipped command

```
python -m lunarlab results --experiment-ids exp-20261015-223113-reward-shaping-study-7f93,exp-20261015-224317-dqn-comparison-e3d2,exp-20261015-235939-rlhf-study-d449 --out regenerated-results
```

Exit 0. Output: `regenerated-results/` (results.json, tables.md, five figures). Compared with
`docs/results/results.json` (SHA-256 `35dcd0f9e134dfebd00035b3f724e23f84dbeab1db357247bd2bde65b2d50d49`)
key by key, ignoring only generation metadata (`generated_at`, `created_at`, `provenance`,
`source_revision`, `git`, `code`, `generated_with`):

| Kind of difference | Count |
|---|---:|
| Published value changed | **0** |
| Published field missing from the regeneration | **0** |
| Field the current code adds (absent from the published file) | 267 |

The 267 added fields are 38 × 7 per-policy fields written by the newer analysis code
(`checkpoint_sha256`, `outcome_classifier_version`, `derived_v2` and four classifier-v2 rate keys,
which are `null` for these classifier-v1 evaluations) plus one top-level `generated_by` record. They
add information; they do not alter any published number.

- All five figures (`headline`, `learned_reward`, `learning_curves`, `performance_profiles`,
  `robustness` PNG) are **byte-identical** to `docs/results/`.
- `tables.md` differs only in the generation timestamp and in the longer caveat paragraph that the
  current code prints under the P(improvement) table (Mann–Whitney wording; a collapsed interval is
  not a zero probability; an interval containing 0.5 does not show equality). No table value differs.

## 2. Independent recomputation from raw final-test episodes

```
python tools/compare_study_summaries.py --artifacts <study-artifact bundle> --regenerated regenerated-results --out study_summary_comparison.json
```

The tool reads the 38 exported `evaluation.json` files (byte-identical copies of the recorded
final-test evaluations, written by `tools/export_study_artifacts.py`) and recomputes, with NumPy and
without LunarLab code, each policy's episode count, mean original return, strict pad-landing rate and
time-limit rate, and each group's interquartile mean of per-policy means. It also performs the key-by-key
comparison of section 1. Exit 0.

**Result: 38 of 38 policies and 3,800 of 3,800 episodes; every per-policy value and all ten group
IQMs match the published summary** (absolute tolerance 1e-9 for means, exact equality for counts and
rates). Bootstrap intervals were not recomputed here; the reviewer's `iqm_ci_verification.json`
recomputes them from the per-policy summaries.

| Group | Policies | IQM from raw episodes | Published IQM |
|---|---:|---:|---:|
| Original baseline | 5 | 268.5609 | 268.5609 |
| Time-penalty ablation | 5 | 265.3267 | 265.3267 |
| Flawed hover bonus | 5 | -33.1273 | -33.1273 |
| Potential-based shaping | 5 | 262.2668 | 262.2668 |
| Learned reward 300 pairs | 3 | -165.2468 | -165.2468 |
| Learned reward 3000 pairs | 3 | 200.1949 | 200.1949 |
| DQN — Original baseline | 3 | 211.0054 | 211.0054 |
| DQN — Time-penalty ablation | 3 | 177.1857 | 177.1857 |
| DQN — Flawed hover bonus | 3 | 109.5520 | 109.5520 |
| DQN — Potential-based shaping | 3 | 207.2477 | 207.2477 |

Full record: `study_summary_comparison.json`.

## Scope

This confirms that the published summaries are a faithful aggregation of the recorded final-test
episodes and that the shipped analysis command reproduces them. It does not re-run any policy; it
says nothing about whether the recorded episodes would be reproduced on another machine (see the
re-evaluation reports for that).
