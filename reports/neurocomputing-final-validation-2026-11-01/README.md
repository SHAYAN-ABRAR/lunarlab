# Validator repairs, archive preparation and manuscript handoff, 1 November 2026

An independent package verification of 29 October 2026 found three portability faults:

- the comparison programs crashed on unavailable memory telemetry;
- the package validator crashed on the resulting rows and wrote no report;
- a permitted cross-platform difference of the clean control was labelled a false alarm.

This folder holds the repairs and their verification. The prespecified comparison of 27 October is
**unchanged**: its protocol, fixtures, programs, hash list and Windows results. The branch is
`research/neurocomputing-final-validation`, which has not been merged. Nothing was trained.

| Path | What it holds |
|---|---|
| [PROGRESS_LOG.md](PROGRESS_LOG.md) | The dated log (UTC): starting state, findings, every step and command |
| [received/](received/independent-verification-2026-10-29/RECEIVED.md) | The labelled subset of the received verification, checked against its own digests |
| [comparison-v2/](comparison-v2/README.md) | The versioned follow-up programs, runner and assessment, the diff from the hashed originals, their hash list (fixed before any run), and the directly executed Windows run |
| [archive/](archive/CANDIDATE.md) | The archive-candidate builder and the candidate's record (`CANDIDATE.md`, its own documents and `SHA256SUMS`); the historical bundle's digests; the licensing proposal and file-to-licence map; the Zenodo metadata and deposit instructions. Nothing was deposited |
| [validation/](validation/README.md) | The fresh-extraction validation of the archive candidate on Windows (every step passed), the negative checks on a damaged copy, and the pending Linux run |
| [ci/](ci/) | The CI runs of `954607b` and `a38d07f`: logs and counts |
| [manuscript/](manuscript/VISUAL_REVIEW.md) | The four manuscript builds: logs, digests and the page-by-page review |
| [integrity/](integrity/README.md) | The historical evidence compared with the inventory of 27 October: 2,359 of 2,359 unchanged |
| [tests/](tests/) | The local full test suite at `a38d07f` |
| [package/](package/) | `build_review_zip.py`, which assembles and seals the review ZIP |
| [READINESS.md](READINESS.md) | What was repaired and verified, what is pending, and the author's decisions |

The validator is [`tools/validate_review_package.py`](../../tools/validate_review_package.py). Its regression
tests are [`tests/test_validator_failures.py`](../../tests/test_validator_failures.py) and
[`tests/test_followup_comparison.py`](../../tests/test_followup_comparison.py).
