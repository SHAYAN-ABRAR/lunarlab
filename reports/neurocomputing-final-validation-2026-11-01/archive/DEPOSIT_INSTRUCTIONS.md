# Depositing the archive candidate on Zenodo (instructions; nothing has been done)

Prepared 1 November 2026; revised 3 November 2026. No deposit, draft, upload or DOI reservation has been made.
Every step below is the author's to take, and each publishes or reserves something. **The deposit is
optional:** the journal confirmed that the GitHub link can be cited under data availability. A deposit is the
way to make the local-only policies, checkpoints and records downloadable and durable.

**Editing after publication (Zenodo's help pages, read on 3 November 2026):** "Once published, you can edit
the metadata of the record at any time but you can only edit the files within 45 days." Larger changes need a
new version. **This project's practice is stricter:** once a record is cited, its files are not changed;
any change becomes a new version, with new digests.

## 1. Decide

- **Licences:** choose them (`LICENSING_PROPOSAL.md`), and decide whether the manuscript text and the
  received review material belong in the deposit.
- **Route:** the web form (several licences per record), the legacy REST API (one licence identifier) or
  the GitHub integration (`ZENODO_METADATA.md`).
- **Metadata:** review `ZENODO_METADATA.md`, and add an ORCID iD only if there is one.
- **Rebuild:** the licence decision changes `LICENSES.md`, so rebuild the candidate from the chosen revision.
  `REV` is a commit of this repository, and `OUT` must be a new directory. On a machine where application
  control blocks virtual-environment launchers, build the source archive without `--verify` and rely on CI's
  source-archive job for the install and release tests:

  ```bash
  python tools/build_source_archive.py --rev REV --out SA --verify
  python reports/neurocomputing-final-validation-2026-11-01/archive/build_archive_candidate.py OUT --commit REV \
      --evidence <original output folder> --historical <bundle folder> --source-archive SA \
      --described-source-archive <c9b9384 source archive folder>
  ```

  The scientific files stay byte for byte as they are; `inventory.json`, `SHA256SUMS` and the ZIP digests
  change. Validate the rebuilt candidate from a fresh extraction (`START_HERE.md`) before depositing it.

## 2. Package and record the digests

Zenodo does not keep folder structure for files uploaded one by one, so upload the candidate as one ZIP. Also
upload `START_HERE.md` separately, so that the record's page shows it. That is two files, well within Zenodo's
stated limits of 100 files and 50 GB per record. Record the ZIP's size and SHA-256, and also its MD5, because
Zenodo lists MD5 checksums:

```bash
sha256sum LunarLab-archive-candidate-<rev>.zip; md5sum LunarLab-archive-candidate-<rev>.zip
```

Use the digests of the candidate actually deposited, from its record in
`reports/neurocomputing-final-repairs-2026-11-03/archive/` or a later one. Never reuse an earlier candidate's
digests.

## 3. Create a draft

1. Signed in at <https://zenodo.org>, start a new upload. This creates a private draft.
2. Upload the ZIP and `START_HERE.md`.
3. Enter the fields of `ZENODO_METADATA.md`, including the licences the author chose. Check that the
   pre-selected licence is the one wanted.
4. Save the draft.

**DOI reservation (optional):** the draft can reserve a DOI before publication, so that the manuscript can cite
it. A reserved DOI does not resolve until the record is published, and it is lost if the draft is deleted. It
is not a published archive, and the manuscript must not describe the data as deposited until it is published.

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
