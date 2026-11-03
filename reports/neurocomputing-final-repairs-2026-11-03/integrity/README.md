# Integrity of the historical evidence, 3 November 2026

**Executed.** `inventory-2026-11-03.json` was written on the author's machine, with the dated evidence
folders excluded, and compared with the inventory taken on 27 October before any change:

```bash
python tools/evidence_inventory.py --out inventory-2026-11-03.json \
    --compare reports/neurocomputing-2026-10-27/integrity/inventory-before.json \
    --exclude reports/neurocomputing-2026-10-27 --exclude reports/neurocomputing-review-repairs-2026-10-28 \
    --exclude reports/neurocomputing-final-validation-2026-11-01 \
    --exclude reports/neurocomputing-final-repairs-2026-11-03 \
    --external "study-bundle-2026-10-24=<the repaired 38-policy bundle folder>" \
    --external "package-supplementary=<the 27 October handoff package's supplementary folder>"
```

| Result | Value |
|---|---|
| Protected files | 2,359 of 2,359 unchanged; none added, removed or changed |
| Combined digest | `7366ba1b6c19ce4e24ebe1bffb5122444dddef05debe6394eb1ed307876a5d9e`, equal to the inventory of 27 October |
| Areas | runs 1,123; demo/api 382; the repaired bundle 335; reports 327; data 143; paper/jmlr-mloss 20; examples/artifacts 12; docs/results 9; the handoff supplementary files 6; docs/media 2 |

**The dated evidence folders** (`git diff --stat 05ca17f` at this work's records commit):

- `reports/neurocomputing-2026-10-27/` and `reports/neurocomputing-review-repairs-2026-10-28/`: unchanged.
- `reports/neurocomputing-final-validation-2026-11-01/`:
  - `README.md`, `READINESS.md` and `archive/CANDIDATE.md` each gained a dated superseding note at the top,
    and nothing else changed in them.
  - The archive drafts and tools in `archive/` were revised in place, as the audit asked: the licensing
    proposal, the Zenodo metadata (the combined JSON draft replaced by two route-specific ones), the deposit
    instructions, the builder and the licence map.
  - Its validation, comparison, CI, received, integrity and manuscript records are untouched, and so are the
    `a38d07f` candidate's record and licence map.
- **The frozen comparison:** its protocol, fixtures, programs, runner, hash list and Windows results are
  untouched. `protocol/HASHES.sha256` verifies 79 of 79, as part of the 624 dependency checks.
- **The 38-policy bundle:** read from a new extraction of its digest-checked ZIP and never written to. The
  bundle folder of 24 October is part of the inventory above.
