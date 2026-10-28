# Validation records of the repairs

## Source archive of the described revision `c9b9384`

`python tools/build_source_archive.py --rev c9b9384 --out OUT --verify` was run on the author's Windows laptop
(`source-archive-c9b9384-windows.log`, with temporary paths shown as `<temp>`).

- **Archive:** 1,112 files, 12.0 MB, SHA-256 `3427d9a91de84606ffd19e52cc8c2c28eba68559cfd62ed278a33afcdf5eac60`.
- **Byte identity:** this equals the archive built by CI run 40712412847 on Linux
  (`../ci/run-40712412847-c9b9384/source-archive/SHA256SUMS`).
- **Fresh install:** the archive installed into a fresh environment and passed 14 of 14 smoke checks and 194
  release tests.

## Fresh-extraction validation of the review package (`package-validation-82518c6/`)

The review package was built from commit `82518c6` with `../package/build_review_package.py`, sealed with
`../package/seal_package.py`, zipped, and extracted into a new directory. The package's own copy of the
validator was then run from that extraction:

```bash
python <extraction>/source/tools/validate_review_package.py <extraction> <validation-run> --fresh-venv --commands
```

It ran from 17:51 to 18:04 UTC on 28 October 2026 and passed every step (`validation.json`, `console.txt`).

| Step | Result |
|---|---|
| Fresh environment | A new virtual environment with uv, installed from the package's `requirements.lock` and the package source (`logs/venv-*.log`) |
| Checksums | 1,439 of 1,439 files match `SHA256SUMS`; no file is unlisted |
| Scientific dependencies | 423 checks, 0 problems. Covered: the study indexes (72), the analysis inputs (54), the CartPole protocol (4), the frozen checkpoints (36), the exported-artifact files (108), the comparison fixtures and programs (79), the figure inputs (10) and the learned-reward packages (60) |
| CartPole records | The analysis reproduces from the run records: main and pilot `results.json` equal, `RESULTS.md` byte-identical. 18 of 18 runs pass the record checks, and the 36 frozen checkpoints match (`study-verification/`) |
| Figures | Rebuilt in the working copy. The plotted values are identical in 4 of 4 `.values.json` files, the historical figure re-derives its values, and 20 of 20 output files are byte-identical on this machine and toolchain. `check_manuscript.py --final` passes |
| Published replays | `ppo-hover-bonus-s0` and the learned-reward package `…-0274` both replay `exact`, each from an empty data home that stayed empty (`reports/`) |
| CartPole artifacts | All 18 exported artifacts verify (exit 0) and replay `exact` |
| Workflow comparison | Rerun from its fixtures, it reproduces the recorded verdict, outcome, exit status, episode count and S1-S10 statuses in all 42 workflow-case pairs (`comparison/`) |

Paths are replaced by `<fresh-extraction>`, `<validation-run>`, `<temp>` and `uv`. Not run: the documented
CartPole smoke study, because it trains 384 transitions and this task trained nothing. CI's Linux replay job
runs it on every push.

An earlier run on the package built from `500e360` passed every step except the dependency check. That step
reported two false positives (the hash lists' header lines), now fixed in the validator. A run before that,
from `83176fb`, found the line-ending fault in the package builder (`../PROGRESS_LOG.md`).
