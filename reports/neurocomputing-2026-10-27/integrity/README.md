# Integrity of the historical evidence

`tools/evidence_inventory.py` hashes every protected file, before and after the work. The protected areas
are:

- the historical runs and the data home;
- earlier reports, the published results and media, and the demo snapshot;
- the three example packages;
- the JMLR manuscript directory;
- two directories outside the repository: the repaired 38-policy study bundle
  (`LunarLab-learned-reward-repair-2026-10-24/study-artifacts`, 335 files) and the handoff package's
  supplementary folder (6 files).

This folder is new work and is excluded from the inventory.

```bash
python tools/evidence_inventory.py --out inventory-after.json --compare inventory-before.json \
  --exclude reports/neurocomputing-2026-10-27 \
  --external study-bundle-2026-10-24=<bundle>/study-artifacts --external package-supplementary=<package>/supplementary
```

| Inventory | Taken (UTC) | Files | Combined digest |
|---|---|---|---|
| `inventory-before.json` | 2026-10-27 15:34, before any change | 2,359 | `7366ba1b6c19ce4e24ebe1bffb5122444dddef05debe6394eb1ed307876a5d9e` |
| `inventory-after.json` | 2026-10-28 13:33, after the last code and evidence change | 2,359 | `7366ba1b6c19ce4e24ebe1bffb5122444dddef05debe6394eb1ed307876a5d9e` |

`comparison.txt` records the result: 2,359 of 2,359 protected files unchanged, with none added, removed or
changed. The comparison was also run at 17:26 UTC on 27 October, before the figure and manuscript commits,
with the same result.
