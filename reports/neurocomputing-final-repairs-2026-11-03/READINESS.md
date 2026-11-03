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
| Later commits of `research/neurocomputing-final-repairs` | The manuscript and documentation corrections, then the records of this work (`PROGRESS_LOG.md`) |

## What the audit established, and what was done

| Audit finding (assistant-executed) | Done here | Status |
|---|---|---|
| Both `uv pip install` commands wrote `venv-pip-install.log`; the lock install's log was overwritten | Distinct logs and exit statuses for every setup command (`venv-create`, `venv-install-lock`, `venv-install-source`). Historical logs are unchanged, and the overwritten one is not reconstructed | **Repaired, tested:** both logs survive with distinct sentinel output; a failed install stops and names its log |
| One DQN policy (`…-aefc`): `aggregate-disagreement` on Linux, 224.07 recorded vs 230.25 and 230.45 | Reproduced on Windows from a new extraction and empty data home: `exact`, 100 of 100 episodes, with default and with one thread. A trace of seeds 20068, 20011 and 20033 was recorded and re-flown identically | **Disclosed** in the manuscript and kept **blocking**. Its cause is not identified. **Pending:** the Linux `--compare` (`dqn-diagnostic/`) |
| The all-38 Linux replay stage: integrity 38 of 38, 37 permitted numerical differences, one disagreement; its parent run was interrupted | Reported as a diagnostic with its runtime, separately from the nine historical Linux replays | Disclosed. **Pending:** an uninterrupted Linux validator run with all 38 replays |
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
| DQN trace on Linux | **Pending** |
| Validator repair | **Executed:** the tests (`298562e`) |
| New archive candidate and its fresh-extraction validation on Windows | **Pending** at the time of this commit; recorded in the next one |
| Manuscript | **Pending** at the time of this commit: the CI build and the page-by-page inspection |
| The full validator on Linux, uninterrupted, with all 38 replays | **Pending:** no Linux machine with the bundle is available here, and CI cannot reach the bundle |

## Author decisions (ranked by how much they block submission)

1. **AI declaration:** complete its AUTHOR TO CONFIRM items (`paper/neurocomputing/AI_USE_INVENTORY.md`):
   - the OpenAI products and models;
   - any other use;
   - whether references were selected or edited;
   - the review-and-responsibility sentence, only if true.
2. **CRediT roles** (`paper/neurocomputing/CREDIT_CHECKLIST.md`): nothing is ticked; a proposal is there.
3. **Licences** for the models, records and manuscript text, in the repository and any deposit
   (`../neurocomputing-final-validation-2026-11-01/archive/LICENSING_PROPOSAL.md`).
4. **Availability of the local-only material:** 29 LunarLander policies, the CartPole checkpoints and
   artifacts, and the fixture policies. Either deposit them (optional; `DEPOSIT_INSTRUCTIONS.md`) or keep the
   statement that they are not yet public.
5. **Approval:** of the manuscript wording, the highlights (`paper/neurocomputing/highlights.txt`), the
   cover-letter draft, the biography (not drafted) and the final files; then remove the working-draft
   footer. `check_manuscript.py --final` must pass.
6. **Merge:** whether to merge `research/neurocomputing-final-repairs`.
