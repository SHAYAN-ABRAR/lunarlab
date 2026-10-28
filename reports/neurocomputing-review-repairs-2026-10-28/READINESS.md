# Readiness after the review repairs

Written 28 October 2026. This is a record of evidence, not a rating, and it estimates no acceptance. The
manuscript is **not submission-ready**; see "Author decisions" below.

| | |
|---|---|
| Branch | `research/neurocomputing-review-repairs`, pushed with a normal `git push`; not merged |
| Base | `d5881cb` (`main`: the merge of PR #1, whose CI run 40703107313 passed) |
| Implementation the paper describes | `c9b9384`, the last commit that changed library code. CI run 40712412847 passed all six jobs |
| Validated package state | `82518c6`: the review package's `source/`, validated from a fresh extraction |
| Final commit and its CI | Recorded in the review package's `SUMMARY.md` and at the end of `PROGRESS_LOG.md` |

## What the review found, and what was done

| Finding | Reproduced? | Repair | Verified by |
|---|---|---|---|
| The CartPole run records that `analyze.py` needs were missing from every Git-built distribution | Yes. `.gitignore` line 11 (`runs/`, unanchored) matched `cartpole-study/records/*/runs/`. Earlier claims that the analysis "reproduces from the committed records" had been tested against the working tree | The 72 records are committed byte for byte (`417b91a`), and the ignore rule is anchored to the data home | Each record matches the study index, the analysis inputs and the artifact manifests, and the original output (`recovery/`). From a fresh extraction, the analysis reproduces exactly, and all 18 runs pass the record checks (`recovery/verification/`) |
| Finite rewards could sum to infinite episode totals inside a "completed" audit | Yes (`defects/before-fix-d1f69c6.json`). Also found: a bare `OverflowError` for overflowing term sums, infinite re-scored totals, and a crash of the audit mean | Totals validated before the audit changes; no summary is emitted, `last_episode` is cleared, steps are refused until reset; `finite_mean` (`c9b9384`) | Six overflow tests with independent oracles; `defects/after-fix-working-tree.json`; CI |
| `check_recorded_episodes` raised `TypeError` on null returns | Yes. Booleans and text were reported only as "episodes [0]", and a null optional value passed | Explicit required and optional fields; refusal without conversion; failures named by episode and field; `integrity` and `record` check kinds; `MALFORMED-RECORD` in the CLI (`c9b9384`) | Eleven record tests, including the tampered-artifact path and the CLI. The comparison's W3 program reaches the same verdicts on all 14 fixtures (`regression/`) |
| Overstated manuscript claims (A–G) | Yes: each named text was present | The adapter scope; "separately implemented reference"; which command runs which checks; the finite-value contract; the validation observation; revision identities; provenance limits (`af8bc4d`, `a9e164d`) | `paper/neurocomputing/EVIDENCE.md`; every page of build 5 read (`manuscript/VISUAL_REVIEW.md`) |
| Package paths and dependency checking | Yes: `SUMMARY.md` named paths that did not exist as written, and a checksum manifest cannot show missing inputs | A repository-shaped package layout; `tools/validate_review_package.py` | From a fresh extraction of the package built from `82518c6`, every step passed (`validation/package-validation-82518c6/`): 1,439 of 1,439 checksums and 423 dependency checks; the CartPole analysis and 18-run record checks; plotted values identical; both published replays and all 18 CartPole artifacts `exact`; and all 42 comparison pairs reproduced |

Two more faults turned up while doing this work, and both were fixed:

- **Line endings:** the first package's plain `git archive` converted line endings on this machine. The
  validator found it.
- **Layout:** manuscript build 4 had margin overruns and a stale section title. The page reading found them.

## Status of the evidence

- **Historical evidence:** 2,359 of 2,359 protected files are unchanged (`integrity/`). The 27 October
  evidence folder gained only the 72 records and five documentation edits.
- **Results:** no reported result changed. The CartPole analysis, the plotted values and the comparison
  verdicts are identical. The repaired code changes only how invalid input is refused.
- **Training:** none was done for these repairs. The reruns were evaluation only.

## Still unverified

- **Independent use:** no independent person has installed, run or reported on LunarLab. The fresh-extraction
  validation ran on the author's Windows machine, in a fresh virtual environment, but on the same hardware.
- **Platforms:** Linux is covered by CI and Windows locally; macOS is untested, and 9 of the 38 policies have
  been replayed on Linux.
- **Byte identity:** PDF, SVG and PNG bytes can differ under other Matplotlib or font versions. The validator
  compares plotted values separately from bytes.
- **Provenance:** the record does not cover imported modules, module-level data or library versions, and two
  lambdas on one source line with equal captured values remain indistinguishable.
- **Documented smoke study:** its 384-transition training run (REPRODUCING.md step 7) was not run in this
  validation, because no training was to be done. CI's Linux replay job runs it on every push.

## Ranked lists

**Technical issues** (none blocks a decision; ranked by value):

1. Run the package validation on a second machine or operating system.
2. Extend the Linux replay to all 38 policies.
3. Record a trajectory in audit artifacts, so that `audit-artifact verify` can also run the
   potential-convention check (S8).
4. Build the PDF locally, if the TeX distribution is permitted by the operating system's security settings.
   It was not bypassed.

**Author decisions** (ranked by how much they block submission):

1. **OSP article type and fees:** fee-free eligibility and format are unresolved. Elsevier inquiry
   261027-019124 has only an automatic acknowledgment, and no new inquiry was sent.
2. **Archive deposit:** choose a repository and the licence for records and model files, then deposit to
   obtain an identifier. A local candidate is ready (`DEPOSIT.md`); nothing was published.
3. **AI declaration:** restore and finalize it in the manuscript, as Elsevier's policy requires
   (`paper/neurocomputing/AI_Disclosure_For_Submission.tex`).
4. **CRediT:** state the human CRediT roles. No roles were invented.
5. **Highlights and final materials:** approve the highlights (optional) and the final submission materials.
6. **Merge:** decide whether to merge `research/neurocomputing-review-repairs` into `main`.

**Smallest useful next step:** the author reviews and merges the repair branch, then decides on the deposit
(item 2), which needs no further experiment.
