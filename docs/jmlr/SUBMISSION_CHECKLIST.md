# Submission decision checklist

Current assessment: **hold submission**. Base source `67440c6`; revised files are local, uncommitted work. Dates: 18–19 October 2026; follow-up on the original machine 19–20 October 2026 (see `READINESS_REPORT.md`). Requirements are grounded in `REQUIREMENTS_MATRIX.md`.

## Required manuscript and cover-letter materials

- [x] MLOSS framing, public software URL and MIT license identified.
- [x] Revised LaTeX and compiled PDF supplied in official JMLR style; build details in `paper/jmlr-mloss/BUILD.md`.
- [ ] Supply author email, affiliation and full postal address.
- [ ] Confirm author consent to this specific submission; disclose prior overlapping publications and concurrent submissions.
- [ ] Supply funding and competing-interest declarations covering the journal's requested period; do not assume “none.”
- [ ] Confirm conflict-free action-editor and reviewer suggestions; provisional candidates are in the cover-letter notes.
- [ ] Supply a truthful dated community-evidence statement. Current absence of evidence remains a major substantive weakness.
- [ ] Identify the exact source version that will be reviewed, including the applied local changes; replace draft metadata only with actual values. *The manuscript marks this with "[final source revision and public archive of the 38-policy bundle]".*
- [ ] Rebuild and visually check after filling author details; verify four description pages, abstract ≤200 words, five keywords, short title ≤50 characters, and upload size <5 MB.

## High-priority scientific and software readiness

- [x] Preserve source provenance and distinguish self-report from executed tests and published CI.
- [x] Recompute summary-level main results and benchmark timing ratios.
- [x] Verify three distributed artifact payloads and execute their re-evaluations locally.
- [x] Correct exactness, trace-causality, overhead, continuation and generic-scope language.
- [x] Patch benchmark memory sampling and reproduction reporting locally; retain historical measurements unchanged.
- [x] Supply for review the raw final-test records, configurations, manifests and selected checkpoint bytes for the claimed study; no new training is needed. *All 38 policies exported and verified on the original machine, 19 October 2026 (`reports/jmlr/original-machine-2026-10-19/study-artifacts/`).*
- [ ] Publish that bundle (for example a DOI archive) and replace the manuscript's marker with its location. Author decision; nothing has been uploaded.
- [ ] Obtain independent research-use or reproduction evidence, retaining failures and maintenance responses. *A ready-to-use exercise and report form are in the review-return package; nobody has been invited.*
- [ ] Run the revised source through supported-platform CI and fresh-source installation before assigning a release identity. *Done locally on Windows 11 (full suite, browser tests, fresh source-archive install); Linux and CI need a push and remain outstanding.* *24 October 2026: CI run 40015498622 passed all six jobs on `4116599` (Linux, Windows Python 3.12 and 3.13, source archive, frontend, browser). CI has not yet run on the learned-reward dependency fix.*
- [x] Rerun the modest overhead benchmark with corrected memory scope if claiming comparable training memory; otherwise retain the explicit historical caveat. *Run `standard-2026-10-19T180346+0000`; the manuscript now uses it.*
- [x] Record actual local and CI validation results; do not equate an interrupted or restricted-runtime test with a pass. *Local results recorded in `reports/jmlr/original-machine-2026-10-19/VALIDATION.md`; CI results for the revised source do not exist yet.*

## Optional improvements, not journal mandates

- [ ] Archive the reviewed release with a DOI.
- [ ] Host the existing API/tutorial documentation for convenient reading.
- [ ] Add an environment adapter justified by a real research use case.
- [ ] Run extra seeds or matched-budget algorithms only if making corresponding new scientific claims.

## Authorization boundary

This package does not authorize a commit, push, merge, tag, release, submission, repository-setting change or outreach. Preparation commands in `RELEASE_PREPARATION.md` stop before those actions. After eventual acceptance, follow JMLR's source/archive naming and licensing paperwork using the accepted version.
