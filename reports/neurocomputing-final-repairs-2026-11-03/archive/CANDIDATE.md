# The archive candidate of 3 November 2026

A new local candidate for the optional public archive, built after the repairs. **It has not been uploaded,
deposited or published; no DOI exists or is reserved.** It stays outside Git, on the author's machine, in
`D:\LunarLab-final-repairs-2026-11-03\`, with its ZIP beside it. Its own documents are copied in
[`candidate-c0d9e5d/`](candidate-c0d9e5d/), including its `SHA256SUMS`, which identifies every file of a later
download. The candidate of 1 November (`a38d07f`), the one the Linux audit used, is unchanged and stays a
separate record (`../../neurocomputing-final-validation-2026-11-01/archive/CANDIDATE.md`).

| | |
|---|---|
| Source revision | `c0d9e5d0823167584a7bff37de9661c35a58228c` (library code identical to `c9b9384`; validator of `298562e`; the manuscript of build 41667322790) |
| Files | 2,696, of which 2,695 are listed in `SHA256SUMS` |
| Size | 147,906,253 bytes unzipped |
| `SHA256SUMS` digest | `815d98393c052ced3a8a3c9938abaca0de76a099d68a61236f35e3c22e1dfc14` |
| ZIP | `LunarLab-archive-candidate-2026-11-03-c0d9e5d.zip`, 2,696 entries, 82,988,733 bytes, CRC test passed |
| ZIP SHA-256 | `8e4889ced6d817ac01db91c391bfefa4c0d33b1aa4f439e7df37146a6105610f` |
| ZIP MD5 (the checksum Zenodo lists) | `2b91a65833acbefb4d3cbd7c01ed7450` |
| Licence map | [`licence-map-c0d9e5d.json`](licence-map-c0d9e5d.json): 2,696 of 2,696 files mapped (2,694 from `inventory.json`, plus `inventory.json` and `SHA256SUMS`), none unmapped. It is a proposal, not a determination of rights |

## How it was built

```bash
python tools/build_source_archive.py --rev c0d9e5d --out <work>/source-archive-c0d9e5d
python reports/neurocomputing-final-validation-2026-11-01/archive/build_archive_candidate.py \
    <work>/LunarLab-archive-candidate-2026-11-03-c0d9e5d --commit c0d9e5d \
    --evidence D:/LunarLab-neurocomputing-evidence-2026-10-27 \
    --historical <the a38d07f candidate>/lunarlander-study \
    --source-archive <work>/source-archive-c0d9e5d \
    --described-source-archive <the a38d07f candidate>/software/c9b9384
```

**The source archive of `c0d9e5d`:** 2,082 files, SHA-256 `c6cbdf69…0648` (`source-archive-c0d9e5d.log`). It was
built without `--verify`, because that step creates a virtual environment, whose launcher Windows Application
Control now blocks on this machine. CI's source-archive job on Linux builds, installs and tests the same
revision (`../ci/`).

**Digest checks during the build:** the builder checked every copied file against the digest a committed
record gives it. That covered the 36 frozen checkpoints, the 108 files of the 18 exported artifacts, the 14
fixture policies, the two historical files, and the 156 inventoried scheduled checkpoints, which were checked
against the study's original output. `build-candidate-c0d9e5d.log` has the facts it printed.

**Compared with the candidate of 1 November:** the historical bytes are the same: the 38-policy bundle, its
source archive, the checkpoints, the artifacts and the fixture policies. The rest differs:

- `source/` is the newer revision;
- `software/` holds the source archive of `c0d9e5d`;
- `START_HERE.md` has the narrowed dependency text, the `--fresh-target` note and the Linux limitations;
- `REVISIONS.md` adds `954607b`, `a38d07f`, `05ca17f` and `298562e`;
- `LICENSES.md` separates the software, the third-party files, the source archives, and the records, models
  and text.

Because of these differences its inventory, `SHA256SUMS` and ZIP digests are all new. None of the earlier
candidate's digests applies to it.

## Validation

From a fresh extraction of the ZIP on Windows: see [`../validation/README.md`](../validation/README.md).
