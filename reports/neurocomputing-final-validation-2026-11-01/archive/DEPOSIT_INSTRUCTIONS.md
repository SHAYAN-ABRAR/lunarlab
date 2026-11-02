# Depositing the archive candidate on Zenodo (instructions; nothing has been done)

Prepared 1 November 2026. No deposit, draft, upload or DOI reservation has been made. Every step below is the
author's to take and publishes or reserves something. Publication on Zenodo is permanent: a published record's
files cannot be changed, only superseded by a new version.

## 1. Decide

- **Licences:** choose them (`LICENSING_PROPOSAL.md`), and decide whether the manuscript text and the
  received review material belong in the deposit.
- **Metadata:** review `ZENODO_METADATA.md`, and add an ORCID iD if there is one.
- **Rebuild if needed:** if anything changes, rebuild the candidate from the chosen revision. `REV` is a
  commit of this repository, and `out` must be a new directory:

  ```bash
  python tools/build_source_archive.py --rev REV --out SA --verify
  python reports/neurocomputing-final-validation-2026-11-01/archive/build_archive_candidate.py OUT --commit REV \
      --evidence <original output folder> --historical <bundle folder> --source-archive SA \
      --described-source-archive <c9b9384 source archive folder>
  ```

## 2. Package and record the digests

Zenodo does not keep folder structure for files uploaded one by one, so upload the candidate as one ZIP. Also
upload `START_HERE.md` separately, so that the record's page shows it. Record the ZIP's size and SHA-256, and
also its MD5, because Zenodo lists MD5 checksums:

```bash
sha256sum LunarLab-archive-candidate-<rev>.zip; md5sum LunarLab-archive-candidate-<rev>.zip
```

The candidate's ZIP digests and its validation are recorded in `../validation/` and `../READINESS.md` once
that validation has run; use those values for this step.

## 3. Create a draft

1. Signed in at <https://zenodo.org>, start a new upload. This creates a private draft.
2. Upload the ZIP and `START_HERE.md`.
3. Enter the fields of `ZENODO_METADATA.md`, including the licences the author chose. Check that the
   pre-selected licence is the one wanted.
4. Save the draft.

**DOI reservation (optional):** the draft can reserve a DOI before publication, so that the manuscript can cite
it. A reserved DOI does not resolve until the record is published. It is not a published archive, and the
manuscript must not describe the data as deposited until it is published.

## 4. Preview, then publish only after approval

Preview the draft and check the files, their sizes, the metadata and the licences. Publish only when the author
approves the contents and the licences.

## 5. Verify the published record

Once the record is published:

1. **Check the bytes:** download the ZIP from the published record. Check its SHA-256 against the recorded
   value, and its MD5 against both Zenodo's listing and the recorded value.
2. **Validate it:** extract it into a new, empty directory and run the validator as `START_HERE.md` shows.
   Keep the validation report.
3. **Cite it:** record the DOI in `CITATION.cff`, the manuscript's availability statement, `README.md` and
   `paper/neurocomputing/EVIDENCE.md`, then rebuild the manuscript.

Zenodo's stated limits (50 GB per record) are far above this candidate's size, which is about 140 MB unzipped.
