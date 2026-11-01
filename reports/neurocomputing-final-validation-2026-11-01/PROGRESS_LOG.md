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
