# Readiness after the Linux audit (current record)

Written 3 November 2026. This is a record of evidence, not a rating, and it estimates no acceptance or review
time. The manuscript is a **working draft, not submission-ready**: the author's declarations, licence choices
and approval are outstanding, and some trained policies are not yet public (see "Author decisions").

## The journal's answers (correspondence with the author, summarized)

| Question | Answer | When |
|---|---|---|
| Article type | "Software publication" | 30 October |
| Fees | No publication fee under Subscription; open access optional, with an APC | 30 October |
| Template | No OSP-specific template | 30 October |
| Data availability | The GitHub link can be cited under "Data Availability"; the repository should remain accessible to the handling editor during review | Reported 3 November |
| Length | No word or page restriction | Reported 3 November |
| Review | Written peer review and revisions, without a mandatory interview | Reported 3 November |

The earlier blockers on fee-free eligibility, page limits and interviews are **removed**. JMLR's four-page
rule does not apply to this paper. A DOI is **not** required solely because the earlier plan wanted one:
Zenodo stays optional, as the way to make the local-only material downloadable. A repository link does not
publish files that are not in the repository. No further inquiry about these points is needed. No review time
is promised, and none is inferred from journal-wide figures.

## Revision identities

| Revision | Role |
|---|---|
| `c9b9384` | The library the manuscript describes (merged as `98be27a`, pull request #2) |
| `954607b` | The earlier validator revision (follow-up comparison set, failure handling), merged through pull request #3 as `05ca17f` on 2 November 2026 (CI 41471828824: six jobs passed) |
| `a38d07f` | The source of the archive candidate audited on Linux |
| `f9615d1` | The final commit of the earlier review branch |
| `298562e` | This work's validator revision: separate setup logs, `--fresh-target`, the manuscript check's `--draft` mode. No library change |
| `db8f937` | The manuscript, licensing and archive-draft corrections, and the first records |
| `c0d9e5d` | Two overflowing lines fixed: the source of the new archive candidate and of the final manuscript build (41667322790); CI 41667323177 passed all six jobs |
| `f9c2906` | The validation, CI and manuscript records. The author merged it into `main` through pull request #4 as `d575925` (2026-11-03 16:53:43 UTC; CI on the pull request, 41675942076, passed) |
| `26da5c7` and later | The second round, after the author turned off Windows Application Control. These commits are on the branch, after the merge, and need a new pull request (`PROGRESS_LOG.md`) |

## What the audit established, and what was done

| Audit finding (assistant-executed) | Done here | Status |
|---|---|---|
| Both `uv pip install` commands wrote `venv-pip-install.log`; the lock install's log was overwritten | Distinct logs and exit statuses for every setup command (`venv-create`, `venv-install-lock`, `venv-install-source`). Historical logs are unchanged, and the overwritten one is not reconstructed | **Repaired, tested:** both logs survive with distinct sentinel output; a failed install stops and names its log |
| One DQN policy (`…-aefc`): `aggregate-disagreement` on Linux, 224.07 recorded vs 230.25 and 230.45 | Reproduced on Windows from a new extraction and empty data home: `exact`, 100 of 100 episodes, with default and with one thread. A trace of seeds 20068, 20011 and 20033 was recorded and re-flown identically | **Disclosed** in the manuscript and kept **blocking**. Its cause is not identified. No further Linux run is planned: the author's decision of 3 November (`dqn-diagnostic/`) |
| The all-38 Linux replay stage: integrity 38 of 38, 37 permitted numerical differences, one disagreement; its parent run was interrupted | Reported as a diagnostic with its runtime, separately from the nine historical Linux replays | Disclosed. No further Linux run is planned (the author's decision, 3 November) |
| The unmodified comparison crashed in 36 of 42 pairs (`NoSuchProcess`); the follow-up set agreed in 40 pairs and reported two permitted differences | Reported with the correct counts (not "all 42") | Disclosed |
| The manuscript claimed that every named file is present | Narrowed: 192 named CartPole checkpoints = 36 distributed + 156 inventoried with digests | Corrected in `main.tex`, `EVIDENCE.md`, the validator's docstring and the candidate's `START_HERE.md` |
| Stale "not merged"; byte identity of figures; licence scope; data availability | Corrected, as the brief listed (`../../paper/neurocomputing/EVIDENCE.md`) | Corrected |
| `THIRD_PARTY_NOTICES.md` said no third-party source is copied | The notice and its generator list `elsarticle.cls` and `elsarticle-num.bst` under the LPPL 1.3 or later; a test checks the listing and the headers | **Repaired** |
| The licence map left out `inventory.json` and `SHA256SUMS`; a container was labelled MIT | The map covers every file and labels source archives as mixed. The proposal says that rebuilding changes the digests | **Repaired** (`../neurocomputing-final-validation-2026-11-01/archive/`) |
| The Zenodo draft mixed the REST and `.zenodo.json` formats, with `_status` and an invalid licence; the instructions said files can never change | Route-specific drafts with no licence, date or marker. The 45-day file-edit rule is quoted; the project's own rule is to make a new version | **Repaired**; licences still the author's decision |

## Evidence status

Labels: **executed** (run in this work), **CI**, **inspected**, **historical**, **assistant-executed** (the
received audit), **diagnostic**, **pending**.

| Item | Status |
|---|---|
| Linux validation of the `a38d07f` candidate | **Assistant-executed** (`received/`): complete runs A (exit 0) and C one-thread (exit 1, on the unmodified comparison); the all-38 replay stage as a diagnostic with an interrupted parent |
| DQN policy on Windows | **Executed:** `exact` twice; the trace is recorded |
| DQN trace on Linux | Not run, and not planned (the author's decision, 3 November). The Windows trace is kept |
| Validator repair | **Executed:** the regression tests (`298562e`). In real runs every setup log survives: `target-install-lock` and `target-install-source` in the `--fresh-target` run, and `venv-create`, `venv-install-lock` and `venv-install-source` in the `--fresh-venv` run. While the launcher was blocked, `--fresh-venv` stopped at `install-lock` and named that step and its log (`validation/`) |
| Tests | **Executed** on Windows: the full suite, 708 passed, both on the base interpreter with a target install and in the project's own `.venv` (`tests/`). **CI** on `c0d9e5d` (run 41667323177) and on `f9c2906` (41673748117): all six jobs passed; Linux 704 passed and 4 Windows-only skips; Windows 294 on each Python; 195 release tests; 15 browser flows |
| New archive candidate (`c0d9e5d`) | **Executed:** built locally (`archive/CANDIDATE.md`). ZIP 82,988,733 bytes, SHA-256 `8e4889ce…610f`, MD5 `2b91a658…`. Its licence map covers 2,696 of 2,696 files. Not deposited |
| Its fresh-extraction validation on Windows | **Executed twice, every step passed both times** (`validation/`): once with `--fresh-target`, and once with the documented `--fresh-venv`, each from a new extraction. 2,695 checksums; 624 dependency checks; values 4 of 4 and bytes 20 of 20; bundle 333; 3,800 episodes recomputed; **38 of 38 replays exact**, including the policy that disagrees on Linux; 18 of 18 CartPole artifacts exact; comparison 42 of 42 in exact agreement, with both the follow-up and the unmodified programs |
| Negative checks | **Executed:** a damaged copy gives named checksum and dependency failures, a written report and exit 1; the follow-up runner refuses its inputs and runs nothing; the blocked `--fresh-venv` gives a written report, the failed step's log and exit 1 |
| Historical evidence | **Executed:** 2,359 of 2,359 protected files unchanged, combined digest `7366ba1b…` (`integrity/`) |
| Manuscript | **CI** builds 41666276641 (`db8f937`: two lines past the margin) and 41667322790 (`c0d9e5d`: fixed). Every page **inspected**: 22 pages, all fonts embedded, no overfull box. **Executed** locally with Tectonic (XeTeX) once Application Control was off: 22 pages, but four lines run 1 to 12 pt past the margin, so the pdfTeX build stays the reference (`manuscript/VISUAL_REVIEW.md`) |
| The full validator on Linux, uninterrupted, with all 38 replays | Not run, and not planned (the author's decision, 3 November). The Linux evidence is the received assistant-executed audit's, as recorded |

## Limitations that remain

- **The DQN cross-platform disagreement:** `…-aefc` does not reproduce its recorded aggregate on Linux
  (224.07 recorded; 230.45 and 230.25 in three Linux executions; 8 of 100 outcomes changed). It is exact on
  Windows. Its cause is not identified, and no further Linux run is planned. It stays disclosed,
  and blocking under the replay gate. The other 37 Linux classifications do not establish equivalence.
- **Linux runs are not fully repeatable:** two Linux executions of that policy differ on one episode (seed
  20065).
- **The full validator on Linux:** it has not completed an uninterrupted run with all 38 replays. The audit's
  all-38 stage was a diagnostic with an interrupted parent.
- **Provenance:** the LunarLander policies were trained from a modified working tree based on `32823f3`,
  which is not reconstructed. The reward-definition record does not cover imported modules, module-level data
  or library versions.
- **Users:** no independent person has installed, run or reported on LunarLab. The audits are
  assistant-executed.
- **Scope:** two environments, designed faults, five seeds per design. The comparison measures neither
  researcher time nor usability.
- **This machine:** on 3 November (found at 14:56 UTC), Windows Application Control blocked virtual-environment
  launchers and the TeX engine, until the author turned it off later that day. Nothing was bypassed. The
  blocked steps were then rerun: the `--fresh-venv` validation, the source archive's `--verify`, and a local
  Tectonic build.

## Author decisions (ranked by how much they block submission)

**Settled by the author on 3 November 2026:**

- **AI declaration:** the tools are named by model and developer, Anthropic's Opus 5.5 and OpenAI's GPT-6;
  GPT-6 is as the author gave it. The text is cut to the policy's minimum (two sentences before the
  references, one in the Methods, one clause in Figure 1's caption), and the review sentence is the
  author's statement (`paper/neurocomputing/AI_USE_INVENTORY.md`).
- **CRediT:** sole author, with twelve roles; Funding acquisition and Supervision are not claimed. AIUB's
  faculty are thanked for ideas (`paper/neurocomputing/CREDIT_CHECKLIST.md`).

**Still open:**

1. **Licences** for the models, records and manuscript text, in the repository and any deposit. This is the
   last AUTHOR TO CONFIRM item (`../neurocomputing-final-validation-2026-11-01/archive/LICENSING_PROPOSAL.md`).
2. **Availability of the local-only material:** 29 LunarLander policies, the CartPole checkpoints and
   artifacts, and the fixture policies. Either deposit them (optional; `DEPOSIT_INSTRUCTIONS.md`) or keep the
   statement that they are not yet public.
3. **Approval:** of the manuscript wording, including the AI declaration; of the highlights
   (`paper/neurocomputing/highlights.txt`), the cover-letter draft, the biography (not drafted) and the final
   files. Then remove the working-draft footer, so that `check_manuscript.py --final` passes.
4. **Merge:** the author merged pull requests #4 (up to `f9c2906`, as `d575925`) and #5 (up to `7e5a916`, as
   `4b4751c`). The commit with the AI wording and the CRediT roles came after them and needs a new pull request.

## Technical items (ranked by value; none blocks an author decision)

1. Record a trajectory in audit artifacts, so that `audit-artifact verify` can also run S8.
2. Optionally, make the five paragraphs that overrun under XeTeX reflow there too, if the submission system
   compiles with XeLaTeX. With pdfLaTeX, nothing is needed.

**Not planned:** further Linux runs, meaning the DQN trace comparison and an uninterrupted validator run with
all 38 replays. The author decided on 3 November not to pursue them. The audit's Linux findings, including the
disagreement, stay disclosed as received. The local candidate (`c0d9e5d`) still carries the earlier
"not yet run" wording in its manuscript source; the rebuild that the licence decision requires will carry the
current wording.

## Public-availability work that needs the author's authorization

- Any deposit (Zenodo or another archive), DOI reservation, upload or release. None was made.
- Merging `research/neurocomputing-final-repairs` into `main`, or tagging a release.
- Licence statements for the models, records and text, in the repository or a deposit.
- Submission to the journal, and any contact with it or with others.
