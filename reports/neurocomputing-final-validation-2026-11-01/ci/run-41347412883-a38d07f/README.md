# CI of the archive revision `a38d07f`

Run [41347412883](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/41347412883) concluded **success** in all
six jobs. The logs are the job logs as GitHub served them, with line endings normalized to LF.

| Job | Result |
|---|---|
| Python, Linux: lint and tests | 686 passed, 4 Windows-only skips; combined statement and branch coverage 86% (10,155 statements, 1,160 missed; 2,596 branches) |
| Windows, Python 3.12 and 3.13 | 293 targeted tests passed on each; reproducibility smoke test and artifact re-evaluation |
| Source archive | Built twice byte for byte; installed fresh; 194 release tests passed |
| Frontend | Typecheck, lint, build |
| Browser end-to-end | 15 flows passed |

The same push built the manuscript and replayed the learned-reward packages on Linux; both succeeded:

- the manuscript build is run [41347412905](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/41347412905), the
  final working draft, reviewed in `../../manuscript/VISUAL_REVIEW.md`;
- the replay is run [41347412861](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/41347412861).

The CI run on `28c811a` was cancelled by the next push (the workflow cancels superseded runs), and so was the
one on `d840f50`. The run on `ea219fc` was likewise superseded.
