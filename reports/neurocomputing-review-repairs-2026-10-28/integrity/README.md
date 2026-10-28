# Integrity of the historical evidence after the repairs

## Protected historical files (the 27 October inventory)

The same command and external directories as before any change on 27 October:

```bash
python tools/evidence_inventory.py --out inventory-after-repairs.json \
  --compare ../../neurocomputing-2026-10-27/integrity/inventory-before.json \
  --exclude reports/neurocomputing-2026-10-27 --exclude reports/neurocomputing-review-repairs-2026-10-28 \
  --external study-bundle-2026-10-24=<bundle>/study-artifacts --external package-supplementary=<package>/supplementary
```

`comparison.txt`, taken at 17:18 UTC on 28 October, reports 2,359 of 2,359 protected files unchanged, with
none added, removed or changed. The combined digest is
`7366ba1b6c19ce4e24ebe1bffb5122444dddef05debe6394eb1ed307876a5d9e`, identical to the inventory taken before any
change.

## The 27 October evidence folder

`evidence-2026-10-27-changes-since-d5881cb.txt` lists every change to `reports/neurocomputing-2026-10-27/` since
it was merged into `main`.

- **Added (72):** the CartPole run records under `cartpole-study/records/{main,pilot}/runs/`. Each matches
  every digest recorded for it (`../recovery/INVENTORY.md`).
- **Modified (5), all documentation:**
  - `PROGRESS_LOG.md` and `READINESS.md`: dated correction notes added; the earlier text is unchanged;
  - `README.md`: a pointer to these repairs, and the merged status;
  - `workflow-comparison/README.md` and `FINDINGS.md`: "independent" replaced by "separately implemented".
- **Unchanged:** every protocol, hash list, raw output, result, record and figure input.
