# Readiness after the validator repairs (current record)

Written 1 November 2026. This is a record of evidence, not a rating, and it estimates no acceptance. The
manuscript is a **working draft, not submission-ready**: the archive deposit and the author's declarations
are outstanding (see "Author decisions").

**Journal answer, 30 October 2026** (inquiry 261027-019124, from Elsevier's Senior Journal Manager for
Neurocomputing):

- OSP submissions use the article type "Software publication".
- There is no publication fee if Subscription is chosen upon acceptance.
- Open access is optional and carries an APC.
- There is no OSP-specific template.

Fee-free eligibility is therefore no longer an open question; the route is the subscription option. The reply
did not address several points, and nothing about them is assumed here:

- page or word limits;
- when an archive DOI must exist;
- review timelines;
- whether presentations are required;
- separate submission, page or colour charges (not itemized).

| Revision | Role |
|---|---|
| `c9b9384` | The library revision the manuscript describes (merged into `main` as `98be27a`, pull request #2; CI run 40755305285 passed) |
| `954607b` | Validator revision: the follow-up comparison set and the repaired package validator. No library change since `c9b9384` |
| Later commits on `research/neurocomputing-final-validation` | The manuscript corrections; the archive candidate's source revision; the validation records. Each is named in `PROGRESS_LOG.md` and in the archive's `REVISIONS.md` |

## What the verification found, and what was done

| Finding (29 October, `received/`) | Repair | Verified by |
|---|---|---|
| All three comparison programs crashed on `psutil.Process().memory_info()` (`NoSuchProcess`) in a sandbox that hides the process | A versioned follow-up set: the hashed programs with unavailable memory recorded as null and a reason, never zero (`comparison-v2/`, derived and diffed). The hashed programs are unchanged | `tests/test_followup_comparison.py`. Run directly on Windows, all 42 pairs agree exactly with the historical results |
| The validator raised `AttributeError` on `checks=None` and wrote no report | Failures recorded per step, the report always written, absent, invalid, foreign or wrongly typed output failing, reused output refused | `tests/test_validator_failures.py`, including the reviewer's crashed output: 42 named failures, no exception |
| A permitted cross-platform difference of the clean control was labelled a false alarm | An assessment that separates exact agreement, a verified platform-dependent numerical difference, and failures. The literal label is kept beside it | Tests: the reviewer's diagnostic Linux output gives two platform-dependent differences on a verified Linux platform, and fails on the recording platform. Same-platform differences, changed faults and failed checks stay blocking |

## Evidence status

Labels: **executed** (run in this work), **CI**, **inspected**, **historical**, **diagnostic** (a reviewer's
modified run), **pending**.

| Item | Status |
|---|---|
| Follow-up comparison on Windows, from the working tree | **Executed:** 42 of 42 exact agreement |
| New regression tests | **Executed** on Windows (full suite: 690 passed). **CI** on Linux: see `PROGRESS_LOG.md` |
| Historical evidence unchanged | **Executed:** 2,359 of 2,359 protected files unchanged, combined digest `7366ba1b…`. The dated folders of 27 and 28 October gained only superseding notes (`integrity/`) |
| Fresh-extraction validation of the archive candidate on Windows | **Pending** at the revision that holds this file; its record is added later on this branch (`validation/`) |
| The full validator on Linux | **Pending.** No Linux machine with the fixture policies was available: they are not in Git, and no WSL or container runtime is installed. The reviewer's Linux results are **diagnostic** only |
| Linux replay of all 38 LunarLander policies | **Not done.** Nine have been replayed on Linux in CI (**historical**) |

## Limitations that remain

- **Users:** no independent person has installed, run or reported on LunarLab.
- **Platforms:**
  - Windows is covered locally and in CI; Linux by CI tests and by nine historical LunarLander replays.
  - macOS is untested.
  - The full validator has not run on Linux.
- **Provenance:**
  - The LunarLander policies were trained from a modified working tree based on `32823f3`, as their records
    state.
  - The reward-definition record does not cover imported modules, module-level data or library versions.
- **Byte identity:** figure bytes can differ under other Matplotlib or font versions, so plotted values are
  compared separately.
- **Not distributed:** the scheduled CartPole checkpoints are inventoried, not distributed.
- **Fixture C1:** its permitted difference depends on the replaying machine differing from its recorded
  Linux platform (`comparison-v2/README.md`).

## Ranked lists

**Author decisions** (ranked by how much they block submission):

1. **Archive:** choose the licences (`archive/LICENSING_PROPOSAL.md`), approve the contents, then create,
   preview and publish the Zenodo record (`archive/DEPOSIT_INSTRUCTIONS.md`). Cite its DOI.
2. **AI declaration:** complete the "AUTHOR TO CONFIRM" items of
   `paper/neurocomputing/AI_Disclosure_For_Submission.tex` from `AI_USE_INVENTORY.md`, and restore it.
   Complete the OpenAI model identifiers. Add the review sentence only when it is true.
3. **CRediT:** state the human roles (`paper/neurocomputing/CREDIT_CHECKLIST.md`). Nothing is pre-ticked.
4. **Final approval:** review and approve the manuscript wording, the highlights (optional) and the final
   materials. Then remove the working-draft footer.
5. **Merge:** decide whether to merge `research/neurocomputing-final-validation`.

**Technical items** (none blocks a decision; ranked by value):

1. Run the validator on Linux with the archive candidate, as its `START_HERE.md` shows.
2. Extend the Linux replay to all 38 LunarLander policies.
3. Record a trajectory in audit artifacts, so that `audit-artifact verify` can also run S8.
4. Build the PDF locally if a permitted TeX distribution is installed.

**Smallest useful next step:** the author's licence decision (item 1), which unblocks the deposit.
