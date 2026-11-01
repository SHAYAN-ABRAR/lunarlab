# Progress log: validator repairs, archive preparation and manuscript handoff

Times are UTC. Machine: the author's Windows 11 laptop (Intel i7-13620H), Python 3.12.13 in the repository's
`.venv`. Nothing was trained.

## 2026-11-01

### Starting state

- 15:03 Recorded the starting state:
  - **Branch:** `research/neurocomputing-review-repairs` at `e94ec5d65dbfa7c13bbfd056489fef87d766561f`, with
    a clean working tree and no stashes.
  - **Main:** `origin/main` is `98be27ac20b7b35bc82c8ec806edeffe2eee4efb`, the merge of pull request #2.
    Its tree equals that of `e94ec5d`.
  - **CI:** run 40755305285 on `98be27a` concluded `success` (checked with `gh run view`).
- 15:03 Created `research/neurocomputing-final-validation` from `origin/main`, with no upstream. No branch was
  reset or overwritten.
- 15:04 Evidence available:
  - **Earlier review ZIP:** `LunarLab-neurocomputing-review-repairs-2026-10-28-e94ec5d.zip`, SHA-256
    `0a3bc304…34dbe6`.
  - **Deposit candidate:** the local candidate of 28 October (`D:\LunarLab-deposit-candidate-2026-10-28\`,
    built from `83176fb`).
  - **Original CartPole output:** 192 checkpoint files and 18 artifacts.
  - **Historical 38-policy bundle:** SHA-256 `da53a1db…bd13532`.
  - **The received independent verification ZIP.**

### The received verification

- 15:05 Extracted `LunarLab_Independent_Verification_2026-10-29.zip` (798,996 bytes, SHA-256 `433eb116…ce51`)
  into a new, empty directory after refusing unsafe names. The CRC test passed, and its `SHA256SUMS` matched
  344 of 344. A labelled subset is in `received/`. It reports three faults; each is visible in its unmodified
  logs:
  - **A, telemetry:** each comparison program crashed in `peak_rss()` with `psutil.NoSuchProcess`, so all 42
    pairs crashed (`validation/comparison/raw/*/C0-clean/stderr.txt`).
  - **B, validator:** `tools/validate_review_package.py` then raised `AttributeError: 'NoneType' object has
    no attribute 'items'` in `key()`, and no `validation.json` was written (`validator.log`).
  - **C, literal labels:** in the reviewer's diagnostic copy, with null telemetry, W2 and W3 replayed C0 as
    `accepted-numerical-difference` with S1-S10 passing. The runner labelled this "false alarm" because it
    compares one literal verdict (`comparison-diagnostic/`).

### The follow-up program set and the validator

- 15:10-15:30 Wrote the follow-up comparison set (`comparison-v2/`), leaving the hashed originals unchanged:
  - **Programs:** `derive_v2_programs.py` derives the three version-2 programs from the hashed originals by
    listed replacements. It verifies the originals against `protocol/HASHES.sha256` first.
  - **Assessment:** `assessment.py` classes each pair as exact agreement, a verified platform-dependent
    numerical difference of the clean control, or a failure, and adds the set-level checks.
  - **Runner:** `run_comparison_v2.py` verifies every input first and records crashes and malformed output.
  - **Validator:** rewrote `tools/validate_review_package.py`. Each step's failure is recorded, and the report
    is always written. A reused output directory is refused. The bundle and checkpoint-inventory checks were
    added, with the LunarLander recomputation, the optional 38-policy replays and the optional unmodified
    comparison.
- 15:30 New tests: `tests/test_followup_comparison.py` (63) and `tests/test_validator_failures.py` (26,
  passing together with the 3 existing `tests/test_review_package.py` tests). Two use the reviewer's actual
  outputs: the crashed run gives 42 named failures and no exception. In the diagnostic run, the two C0 rows
  are platform-dependent differences on a verified Linux platform and failures on the recording platform.
- 15:32:17 Fixed `comparison-v2/HASHES-v2.sha256`, before any version-2 program ran on the fixtures.
- 15:34:16-15:40:33 **Directly executed** the follow-up runner on the real fixtures, from the working tree
  (`comparison-v2/results-windows-2026-11-01/`):
  - **Inputs:** verified against both hash lists.
  - **Pairs:** 42 of 42 agree exactly with the historical Windows results.
  - **Set-level checks:** W2 and W3 report identical statuses in all 14 cases, both reject the 12 faults
    before execution, and W1 is unchecked throughout.
  - **Telemetry:** measured in all 42 results.

### Documentation

- 15:41 Recorded the journal's answer of 30 October 2026 (case 261027-019124) with dated notes:
  - **Where:** `docs/neurocomputing/README.md` and the README. The historical readiness and archive notes of
    27 and 28 October got superseding notes; their text is unchanged.
  - **Answered:** the article type is "Software publication"; there is no publication fee under Subscription;
    open access is optional and carries an APC; there is no OSP-specific template.
  - **Not answered:** limits, DOI timing, review times and presentations.
- 15:43 Fetched Elsevier's generative-AI policy again: unchanged since 26 October ("Policy updated June
  2026"). From the session transcript's metadata (no conversation text), compiled
  `paper/neurocomputing/AI_USE_INVENTORY.md`:
  - **Tool:** Claude Code versions 2.1.283, 2.1.299 and 2.1.312, model `claude-opus-5-5`, with 622
    repository edits.
  - **Code:** it wrote 82 of the 94 files of the first commit.
  - **Runs:** it launched the LunarLander study runs (15 October) and the CartPole study runs (27 October).
  - **Training state:** the 38 LunarLander runs record revision `32823f3` with `dirty: true`, so they were
    trained from a modified working tree.
- 15:47 Rewrote the declaration draft `AI_Disclosure_For_Submission.tex`, with "AUTHOR TO CONFIRM" items and
  no claim of human review. `check_manuscript.py --final` now fails while a restored input still holds such an
  item; this was tested both ways. Added `CREDIT_CHECKLIST.md`, with nothing ticked, and with Funding
  acquisition and Supervision excluded.
- 15:49 Full local test suite: 690 passed, none skipped or failed.

### The validator revision and its CI

- 20:06 Committed **`954607b83853d3fbd1018b5992158f1c924ff0d5`** (the validator revision), with the
  author's identity and no co-author lines. Pushed `research/neurocomputing-final-validation` to `origin`
  with a normal push. Before the commit, these passed locally: Ruff lint and format on the CI's paths, the
  licence headers, and the generated API reference.
- 20:07-20:33 CI of `954607b`; every job of all three runs succeeded (`ci/run-41345065489-954607b/`):
  - **CI run 41345065489:**
    - Linux: 686 passed, 4 Windows-only skips, 86% combined coverage;
    - Windows Python 3.12 and 3.13: 293 tests each;
    - source archive: 194 release tests;
    - browser: 15 flows.
  - **Manuscript build 41345065455** and **Linux learned-reward replay 41345065461:** both succeeded.

### Manuscript and archive documents

- 20:08-20:20 Bounded manuscript corrections in `paper/neurocomputing/main.tex`:
  - **Footer:** every page now reads "Working draft, not submitted".
  - **Header:** the header comment records the journal's answer.
  - **Comparison section:** it says its replay labels belong to the recording platform.
  - **Limitation sentence:** it says one developer produced the specification and programs with AI tools.
  - **Section 5.2:** it names its three kinds of evidence as integrity, exact reproduction and outcome
    agreement.
  - **Section 5.3:** it describes the package validator and the follow-up set, and gives an accurate account
    of the AI work (versions 2.1.283, 2.1.299, 2.1.312).
  - **Availability statement:** it separates the described library revision (merged as `98be27a`), the
    validator revision (`954607b`, not merged), the LunarLander training state (`32823f3`, modified working
    tree) and export (`4116599`), and the other experiments' source states. It names the archive candidate,
    not deposited.

  `EVIDENCE.md` and `BUILD.md` follow these changes. `check_manuscript.py --final` passes; the abstract is
  unchanged (180 words).
- 20:12-20:20 Wrote the licensing proposal and `archive/licence_map.py`, `archive/ZENODO_METADATA.md`,
  `zenodo-metadata.json` (licence left for the author), `archive/DEPOSIT_INSTRUCTIONS.md` and
  `READINESS.md`. Nothing was uploaded, reserved or published.
- 20:13 Dry run of `archive/build_archive_candidate.py` from `954607b` (2,164 files, 136.7 MB). The validator's
  steps without `--commands` passed on it:
  - **Checksums:** 2,163 listed, nothing unlisted or malformed.
  - **Dependencies:** 624 checks with no problem. They include 192 checkpoints named by the run records
    (36 distributed, 156 inventoried) and the follow-up programs (7).
  - **Bundle:** 333 members checked; 38 packages, 6 with reward models.
  - **LunarLander statistics:** 38 policies and 3,800 episodes recomputed, all matching.
  - **Figures:** plotted values identical in 4 of 4, bytes identical in 20 of 20.
  - **CartPole records:** passed.

  This was a development check, not the recorded validation.
- 20:16 Integrity (`integrity/`): 2,359 of 2,359 protected historical files unchanged, combined digest
  `7366ba1b…`. The dated folders gained only four superseding notes (37 added lines).
- 20:14-20:38 Dry run of the validator **with** `--commands` on the dry-run candidate. Every step passed:
  - **Replays:** both published replays `exact`, with their data homes left empty.
  - **CartPole artifacts:** 18 of 18 `exact`.
  - **Comparison through the validator:** 42 of 42 exact agreement, all three set-level checks passed.

  This was a development check.

### Manuscript builds and the archive revision

- 20:24 Committed `28c811a` (the manuscript corrections and archive documents) and pushed it.
- 20:25-20:31 Manuscript build 41346694714 of `28c811a`: every one of its 20 pages read
  (`manuscript/VISUAL_REVIEW.md`). There were two faults:
  - the "Appendix A" heading stood alone at the foot of page 18;
  - a duplicate link anchor (`figure.1`), already present in the October builds.
- 20:26 `d840f50`: the appendix starts on a new page, and its figures have their own anchors.
  - Build 41347005235: 21 pages; pages 1-17 byte-identical to the previous renders; pages 18-21 read.
  - Remaining blemish: the last two lines of reference [12] on page 21.
- 20:29 `ea219fc`: enlarged the page before the references. Build 41347218412: the last line of reference [3]
  collided with the working-draft footer.
- 20:30 `a38d07f`: withdrew the enlargement. The tree equals `d840f50`'s.
  - Build 41347412905: 21 pages, all 34 fonts embedded, no overfull box, no duplicate anchor, PDF SHA-256
    `ebd27ba8…`.
  - All 21 page renders are byte-identical to those of build 41347005235.
  - **`a38d07f` is the archive revision.**
- 20:31-20:36 Built the source archive of `a38d07f`: 1,569 files, SHA-256 `2bd398e5…8867b`. It installed
  into a fresh environment and passed 194 of 194 release tests.
- 20:36 Built the archive candidate from `a38d07f` (`archive/CANDIDATE.md`): 2,180 files, 137.6 MB,
  `SHA256SUMS` digest `ab0a6471…`.
- 20:37 Zipped it: 2,180 entries, 80,659,343 bytes, CRC test passed, SHA-256 `8a02752e…`, MD5 `f323c1b0…`.
  Extracted it into a new, empty directory.
- 20:38 Started the validator **from the fresh extraction**:
  - **Interpreter:** the base uv-managed Python 3.12, which has no LunarLab, torch or any project package.
    `VIRTUAL_ENV`, `PYTHONPATH` and `LUNARLAB_HOME` were unset.
  - **Options:** `--fresh-venv --commands --unmodified-comparison --lunarlander-replays all`.
- 20:39 Licence map of the candidate: all 2,178 inventoried files mapped, none unmapped
  (`archive/licence-map-a38d07f.json`). The archive revision was filled into the Zenodo metadata.
- 20:41-20:46 Negative checks on a deliberately damaged copy of the extraction (`validation/negative-damaged-copy/`):
  - **Damage:** one fixture policy removed, one byte of a CartPole policy inverted.
  - **Validator:** the report was written, with named checksum and dependency failures, and the run exited 1.
  - **Follow-up runner:** it refused before any program ran, and exited 2.
- 20:44-21:03 Full local test suite at `a38d07f`, run beside the validation: 690 passed
  (`tests/local-full-suite-a38d07f-windows.log`).
- 20:45-21:05 CI of `a38d07f`, run 41347412883: all six jobs passed (`ci/run-41347412883-a38d07f/`):
  - Linux: 686 passed, 4 skipped, 86% coverage;
  - Windows: 293 tests on each Python;
  - source archive: 194 release tests;
  - browser: 15 flows.

  The CI runs of `28c811a`, `d840f50` and `ea219fc` were cancelled when the next commit superseded them.

### The validation

- 21:32:42 The validation from the fresh extraction finished with exit status 0. Every step passed
  (`validation/`, 55 minutes):
  - **Checksums:** 2,179 of 2,179.
  - **Dependencies:** 624 checks with no problem.
  - **CartPole records:** the analysis and all 18 runs reproduced.
  - **Figures:** plotted values identical in 4 of 4, bytes in 20 of 20.
  - **Bundle and statistics:** 333 of 333 bundle members verified; the statistics of the 3,800 episodes
    recomputed, all matching.
  - **Replays:** 38 of 38 LunarLander packages `exact`, and both published replays `exact`, each from an
    empty data home that stayed empty.
  - **CartPole artifacts:** 18 of 18 verified and `exact`.
  - **Comparison:** 42 of 42 pairs in exact agreement, with the follow-up set and with the unmodified frozen
    runner and programs. W2 and W3 agreed in 14 of 14 cases, rejected all 12 faults before execution, and W1
    was unchecked.
  - **Not observed:** no platform-dependent difference, since this is the recording platform.
- 21:35 Recorded the environment the run used: `uv pip freeze` of its virtual environment. Its 65 packages
  equal the lock's pins. A minor validator defect was found: the two `uv pip install` steps share a log
  name. It is noted rather than fixed after the run.
