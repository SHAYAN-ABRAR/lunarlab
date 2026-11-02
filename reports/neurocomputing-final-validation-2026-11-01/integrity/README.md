# Integrity of the historical evidence, 1 November 2026

`inventory-2026-11-01.json` was written on the author's machine, with the dated evidence folders excluded:

```bash
python tools/evidence_inventory.py --out inventory-2026-11-01.json \
    --compare reports/neurocomputing-2026-10-27/integrity/inventory-before.json \
    --exclude reports/neurocomputing-2026-10-27 --exclude reports/neurocomputing-review-repairs-2026-10-28 \
    --exclude reports/neurocomputing-final-validation-2026-11-01 \
    --external "study-bundle-2026-10-24=<the repaired 38-policy bundle folder>" \
    --external "package-supplementary=<the 27 October handoff package's supplementary folder>"
```

| Result | Value |
|---|---|
| Protected files | 2,359 of 2,359 unchanged; none added or removed |
| Combined digest | `7366ba1b6c19ce4e24ebe1bffb5122444dddef05debe6394eb1ed307876a5d9e`, equal to the inventory taken on 27 October before any change |
| Areas | runs 1,123; demo/api 382; the repaired bundle 335; reports 327; data 143; paper/jmlr-mloss 20; examples/artifacts 12; docs/results 9; the handoff supplementary files 6; docs/media 2 |

**The dated evidence folders** (`git diff --stat 98be27a 954607b`):

- `reports/neurocomputing-2026-10-27/`: two files, each gaining one dated superseding note (`READINESS.md`,
  `ARCHIVE.md`).
- `reports/neurocomputing-review-repairs-2026-10-28/`: two files, likewise (`READINESS.md`, `README.md`).
- In both: 37 lines added, none changed or removed.
- **The frozen comparison:** its protocol, fixtures, programs, runner, hash list and Windows results are
  untouched. `protocol/HASHES.sha256` verifies 79 of 79, and the historical `results/summary.json` has the
  digest that `comparison-v2/run_comparison_v2.py` pins.
