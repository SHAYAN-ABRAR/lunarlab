# Archive and release preparation

Status on 28 October 2026: nothing has been deposited, so there is no DOI. No release has been tagged or
published, and the review branch is not merged. Each of these steps publishes something, so each is the
author's decision. The brief authorized only pushing the review branch.

## What Neurocomputing asks

From the captured guide (`docs/neurocomputing/README.md`):

- **Research data:** under Option C, deposit the research data in a relevant data repository, and cite and link
  it in the article. If that is not possible, state why the data cannot be shared. Research data includes
  "software, code, models".
- **Supplementary files:** these alone do not meet the rule.
- **Software citations:** a persistent identifier is preferred, and a DOI is preferred among them, but neither
  is mandated. If there is none, the URL of the software is "the best identifier available".

## Deposit candidate

| Item | Contents | Size | Integrity record |
|---|---|---|---|
| Source archive of the reviewed revision | `python tools/build_source_archive.py --rev <final commit> --verify` writes `dist/lunarlab-0.1.0-src.tar.gz`, its manifest and `SHA256SUMS`. The archive is deterministic: the same commit always gives the same bytes | about 9 MB (the `444a4c5` archive is 9,068,129 bytes) | The manifest's SHA-256 digests. The archive includes `reports/`, so it carries this evidence folder; it excludes `paper/` and `demo/api/` by design |
| Historical 38-policy study | `LunarLab_38_Policy_Study.zip` (335 files, with the learned-reward models) and `lunarlab-0.1.0-444a4c5-src.tar.gz` | 16,407,948 and 9,068,129 bytes | The bundle's `SHA256SUMS`. It is unchanged by this work and was checked in `integrity/` |
| CartPole study checkpoints | The 36 frozen checkpoints (selected and final, main and pilot), optionally with all 210 scheduled checkpoints, which allow the selection to be redone | 5.2 MB frozen; 30.2 MB for all 210 | `cartpole-study/records/frozen-checkpoints.sha256`. All 36 matched on 28 October |
| Comparison fixtures | The 14 cases' `policy.zip` files | small | `workflow-comparison/protocol/HASHES.sha256`. All 14 matched on 28 October |

The six learned-reward packages (2.3 MB) and the three example packages are already in the repository. No
model bundle beyond these was added to Git.

## Citation metadata for the deposit form

These are proposals only; no record exists.

**Software record**

- **Title, version and revision:** LunarLab, version 0.1.0, the final reviewed commit.
- **Creator:** Shayan Abrar, American International University-Bangladesh (AIUB).
- **Licence:** MIT.
- **Keywords:** those in `CITATION.cff`.
- **Related identifiers:** the repository URL, and the article once it has one.

**Dataset record (optional)**

- **Title:** "LunarLab reward-design audit artifacts", covering the LunarLander 38-policy study and the
  CartPole study.
- **Licence:** the author's choice. For example, CC BY 4.0 for the records and MIT for the code-derived model
  files.

**Still to be supplied by the author:** an ORCID identifier, if there is one, and the choice of repository.
Examples are Zenodo or OSF for the archives, and Software Heritage for the code.

## After a deposit (the author's steps)

1. **Citation file:** add the DOI to `CITATION.cff` (`identifiers`), and record it in the README.
2. **Manuscript:** replace the availability statement and its "not yet deposited" sentence with the record's
   citation, add the record to `references.bib`, and run `python paper/neurocomputing/check_manuscript.py
   --final`.
3. **Release:** tag a release only from a commit on `main` after the review branch is merged, and build its
   source archive from that commit.

## Not done

- **No deposit:** no upload, deposit or DOI request.
- **No release:** no tag and no release.
- **Branch:** no merge into `main`, no force-push and no history rewrite.
- **Contacts:** no contact with the journal, Elsevier or anyone else.
