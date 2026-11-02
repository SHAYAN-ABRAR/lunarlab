# Received: independent package verification of 29 October 2026

This is external material, kept as received and treated as data. The author supplied it on 1 November 2026 as
`LunarLab_Independent_Verification_2026-10-29.zip`.

| | |
|---|---|
| Bytes | 798,996 |
| SHA-256 | `433eb116b1513f7e869ac339fcb1c96ab88591424ac4037dcd382aa14395ce51` |
| ZIP CRC test | passed (345 entries) |
| Its own `SHA256SUMS` | 344 of 344 entries match, after extraction into a new, empty directory |

It verified the review package `LunarLab-neurocomputing-review-repairs-2026-10-28-e94ec5d.zip`
(SHA-256 `0a3bc304…34dbe6`). Its own notes describe it as "an assistant-executed independent review", not as
an external human researcher's use.

## What is copied here

The files below are copied byte for byte. Each matches the digest that the received `SHA256SUMS` (also copied)
records for it. The rest of the ZIP is not in Git: the PDF it reviewed, the per-artifact replay reports and the
remaining raw logs. The whole ZIP is in the review ZIP of 1 November.

| File | Label |
|---|---|
| `LunarLab_Independent_Package_Review_2026-10-29.txt` | The reviewer's report |
| `LunarLab_Portability_Repair_Note.txt` | The reviewer's repair requests (followed in `../../comparison-v2/` and `tools/validate_review_package.py`) |
| `validator.log`, `validation/comparison/` | **Unmodified run** of the package's validator in the reviewer's Linux sandbox. Every program crashed on `psutil.NoSuchProcess` (stderr of the three C0 programs included), and the validator then raised `AttributeError` |
| `basic-validator.log`, `basic-validation/validation.json` | The validator without `--commands`: passed |
| `comparison-diagnostic/` | **Diagnostic result:** the reviewer's modified copy, in which `peak_rss()` returns null when memory is unavailable. It is not an unmodified reproduction of the hashed programs. All 42 pairs completed; the two C0 rows of W2 and W3 replayed as `accepted-numerical-difference`, and the frozen runner labelled them false alarms |
| `diagnostic-comparison-summary.json`, `independent-verification.json`, `cartpole-linux-summary.json`, `pdf-review.json` | The reviewer's summaries. The CartPole replays are the reviewer's Linux results (18 policies, 1,560 episodes), not runs of this work |

## How it was used

- **Telemetry:** the first finding is repaired in a separate program set; the hashed programs are unchanged
  (`../../comparison-v2/`).
- **Validator:** the second is repaired in `tools/validate_review_package.py`.
  `tests/test_validator_failures.py` feeds the reviewer's crashed `summary.json` and stderr to it: 42 named
  failures, a written report, no exception.
- **Platform label:** for the third, `tests/test_followup_comparison.py` assesses the diagnostic
  `summary.json`. On a verified Linux platform the two C0 rows are platform-dependent numerical differences,
  kept visible beside their literal "false alarm" label. On the recording platform, the same rows fail.
- **Not claimed:** none of the reviewer's Linux results is claimed as a run of this work.
