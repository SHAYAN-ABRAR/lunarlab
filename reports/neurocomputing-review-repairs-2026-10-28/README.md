# Repairs after the review of the Neurocomputing revision, 28 October 2026

A review of the research-strengthening revision (`reports/neurocomputing-2026-10-27/`, merged into `main` as
`d5881cb`) found:

- **Missing run records:** distributions built from Git omitted the CartPole study's run records.
- **Two validation defects:** overflowing episode totals, and malformed recorded episodes.
- **Overstated claims** in the manuscript.

This folder holds the reproduction of each finding, the repair and its verification. The branch is
`research/neurocomputing-review-repairs`, which has not been merged. Nothing was trained.

| Path | What it holds |
|---|---|
| [PROGRESS_LOG.md](PROGRESS_LOG.md) | The dated log (UTC): base state, each finding and repair, the commands run |
| [recovery/](recovery/INVENTORY.md) | The missing CartPole records. `recover_cartpole_records.py` and its inventory: 72 of 72 expected files recovered, each matching every recorded digest. `verify_cartpole_study.py` and `verification/` re-derive the analysis and check all 18 runs from the records |
| [defects/](defects/) | `reproduce_defects.py` and its output before (`before-fix-d1f69c6.json`) and after (`after-fix-working-tree.json`) the two validation fixes |
| [regression/](regression/) | The comparison's W3 program rerun on the 14 fixtures with the repaired code: verdicts unchanged |
| [ci/](ci/) | CI of the repaired code revision `c9b9384` (run 40712412847): log, coverage, reproducibility reports, source-archive digest |
| [validation/](validation/README.md) | The repaired revision's source archive built on Windows (byte-identical to CI's), and the fresh-extraction validation of the review package (every step passed) |
| [package/](package/) | `build_review_package.py` and `seal_package.py`: how the review package is assembled and sealed |
| [manuscript/](manuscript/VISUAL_REVIEW.md) | Manuscript builds 4 and 5 after the review: logs and the page-by-page review |
| [integrity/](integrity/) | The comparison of the 2,359 protected historical files with the inventory taken before any change on 27 October |
| [READINESS.md](READINESS.md) | What was repaired and verified, what remains unverified, and what blocks submission |
| [DEPOSIT.md](DEPOSIT.md) | The local deposit candidate: contents, digests, licences and citation fields. Nothing is published |

The claim-by-claim map for the corrected manuscript is
[paper/neurocomputing/EVIDENCE.md](../../paper/neurocomputing/EVIDENCE.md).
