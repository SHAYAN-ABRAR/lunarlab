# The archive candidate of 1 November 2026

A local candidate for the public archive. **It has not been uploaded, deposited or published; no DOI exists
or is reserved.** It stays outside Git, on the author's machine:

- `D:\LunarLab-final-validation-2026-11-01\LunarLab-archive-candidate-2026-11-01-a38d07f\`
- and its ZIP beside it.

Its own documents are copied in [`candidate-a38d07f/`](candidate-a38d07f/), and so is its `SHA256SUMS`.
That list identifies every file of a later download.

| | |
|---|---|
| Source revision | `a38d07f59f99dee53676b061955d25e8caef3e72` (library code identical to `c9b9384`) |
| Files | 2,180, of which 2,179 are listed in `SHA256SUMS` |
| Size | 137,583,056 bytes unzipped |
| `SHA256SUMS` digest | `ab0a6471e3d66b403965bdbdfb74919247eb1bb84ce20fe4e058a5d28fde849d` |
| ZIP | `LunarLab-archive-candidate-2026-11-01-a38d07f.zip`, 2,180 entries, 80,659,343 bytes, CRC test passed |
| ZIP SHA-256 | `8a02752eed0a86d862fa0365e2cc2ae60a66fe8768293d07c4a57dc7fc7f9cd7` |
| ZIP MD5 (the checksum Zenodo lists) | `f323c1b0417ba3a216a338caa5a369ea` |
| Licence map | [`licence-map-a38d07f.json`](licence-map-a38d07f.json): every file mapped, none unmapped. It is a proposal ([`LICENSING_PROPOSAL.md`](LICENSING_PROPOSAL.md)) |

## How it was built

```bash
python tools/build_source_archive.py --rev a38d07f --out <work>/source-archive-a38d07f --verify
python reports/neurocomputing-final-validation-2026-11-01/archive/build_archive_candidate.py \
    <work>/LunarLab-archive-candidate-2026-11-01-a38d07f --commit a38d07f \
    --evidence <the CartPole study's original output folder> \
    --historical <folder holding LunarLab_38_Policy_Study.zip and lunarlab-0.1.0-444a4c5-src.tar.gz> \
    --source-archive <work>/source-archive-a38d07f \
    --described-source-archive <the c9b9384 source archive built on 28 October>
```

**The source archive of `a38d07f`:** 1,569 files, SHA-256 `2bd398e5…8867b`. It installed into a fresh
environment and passed 194 of 194 release tests on the author's Windows laptop.

**Digest checks during the build:** the builder checked every copied file against the digest a committed
record gives it:

- the 36 frozen checkpoints;
- the 108 files of the 18 exported artifacts;
- the 14 fixture policies;
- the two historical files;
- the 156 inventoried scheduled checkpoints, against the study's original output.

## Contents (from its `INVENTORY.md`)

| Part | What |
|---|---|
| `source/` | `git archive a38d07f`: the complete repository tree, including `demo/api/` and the manuscript source |
| `software/a38d07f/`, `software/c9b9384/` | Deterministic source archives of the archive revision and of the described library revision |
| `outside-git/` | The 14 comparison-fixture policies |
| `cartpole-study-output/` | 36 frozen checkpoints and 18 exported artifacts, and `INTERMEDIATE_CHECKPOINTS.json` (156 scheduled checkpoints not distributed, 22.5 MB, of which 36 have the bytes of a distributed frozen checkpoint) |
| `lunarlander-study/` | `LunarLab_38_Policy_Study.zip` (SHA-256 `da53a1db…`) and `lunarlab-0.1.0-444a4c5-src.tar.gz` (`d097631d…`), byte for byte |

**Compared with the candidate of 28 October** (`D:\LunarLab-deposit-candidate-2026-10-28\`, unchanged):

- the layout is a package that the validator checks from a fresh extraction;
- the scheduled CartPole checkpoints are inventoried instead of distributed, as the brief asked;
- added: `START_HERE.md`, the revision table, the file and dependency inventory, the licence note and the
  source archive of the archive revision;
- the historical bytes are the same.

The validation of its fresh extraction is in [`../validation/`](../validation/).
