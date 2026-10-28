# Local deposit candidate

Status on 28 October 2026: a complete deposit candidate exists on the author's machine.

- **Not done:** it has not been uploaded, published or registered, and it has no DOI or other persistent
  identifier.
- **The author's decisions:** whether and where to deposit, the licences of the records and model files, and
  the final metadata.

| | |
|---|---|
| Location | `D:\LunarLab-deposit-candidate-2026-10-28\` (on the author's machine) |
| Built by | `deposit/build_deposit_candidate.py 83176fb …`, the evidence taken by `git archive` from commit `83176fb` |
| Files | 961 (960 listed in its `SHA256SUMS`, all verified after building), 95.4 MB |
| Digest of its `SHA256SUMS` | `3d17fa3304a261e3a5dcf655a8a44c8752beaf73447d3bb6597c283f61676020` |
| Its README | `deposit/DEPOSIT_README.md` (copied to the candidate as `README.md`) |

## Contents

| Path in the candidate | What | Integrity |
|---|---|---|
| `software/` | The deterministic source archive of `c9b9384`, the described revision, with its manifest | `3427d9a9…cdf5eac60`: Linux CI and Windows builds are byte-identical |
| `evidence/reports/neurocomputing-2026-10-27/` | The research-strengthening evidence, including the 72 CartPole run records | As committed at `83176fb` |
| `evidence/reports/neurocomputing-review-repairs-2026-10-28/` | This folder as committed at `83176fb` | As committed |
| `cartpole-study-output/` | The CartPole study runner's complete output: 192 checkpoint files (scheduled and frozen), the 18 exported artifacts, the indexes, ledgers and logs | The 36 frozen checkpoints were checked against `frozen-checkpoints.sha256`; every file is in `SHA256SUMS` |
| `comparison-fixture-policies/` | The 14 fixture policies, at their fixture paths | Checked against the comparison's `HASHES.sha256` |
| `lunarlander-study/` | The historical 38-policy export and its source archive, unchanged | Digests in the review package's `historical-unchanged/README.md` |
| `LICENSE`, `THIRD_PARTY_NOTICES.md`, `CITATION.cff` | Licence and citation files | |

## Licences and metadata

- **Software:** MIT.
- **Records and trained model files:** not yet licensed. The candidate's README proposes CC BY 4.0 as one
  option, for the author to decide.
- **Citation fields:** proposed in the candidate's README. These cover title, creator and affiliation,
  version and software revision, keywords and related identifiers. An ORCID identifier, if there is one, is
  for the author to add.
- **Identifiers:** no DOI or other identifier was requested or invented.

## What a deposit would change

1. **CITATION.cff:** add the record's identifier.
2. **Manuscript:** replace the availability statement's "not yet deposited" sentence with the record's
   citation, and add the record to `paper/neurocomputing/references.bib`.
3. **Release:** tag a release only from `main` after the review branches are merged, and rebuild the source
   archive from that commit.

None of these steps has been taken.
