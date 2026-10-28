# Evidence for the Neurocomputing revision, 27 and 28 October 2026

This folder holds the new evidence behind `paper/neurocomputing/main.tex`.

- **Branch:** the review branch `research/neurocomputing-audit-evidence`. It has not been merged or released.
- **Software evaluated:** revision `30bd3f6`, the last commit on the branch that changed library code.
- **What was added:** protocols were fixed before the runs they govern, with raw records, analyses, CI logs and
  the manuscript's build logs.
- **What was not changed:** the historical evidence. The 38-policy study, its runs and data home, earlier
  reports, published results, example packages and the JMLR manuscript are unchanged; see `integrity/`.

| Path | What it holds | Used in the paper |
|---|---|---|
| [PROGRESS_LOG.md](PROGRESS_LOG.md) | Dated log of the work in UTC. Includes the base state, corrections of mistimed entries, and the compute tally against the brief's caps | — |
| [integrity/](integrity/) | SHA-256 inventories of the 2,359 protected files before and after the work, and their comparison | Sec. 5.2 ("all 38 study exports retain…") |
| [contracts/](contracts/README.md) | Runtime reproductions of the seed, finite-value, seeding and reward-identity defects, on the unmodified `932cf1c` and on the fixed tree. The old-API probe fails 16 of 17 checks before the fix and passes 17 of 17 after it | Sec. 2.2, 2.3, 5.1 |
| [cartpole-study/](cartpole-study/README.md) | The prespecified CartPole study: protocol hashed before training, pilot, 15 main runs, compute ledger, analysis and results | Sec. 4.2, Fig. 4 |
| [workflow-comparison/](workflow-comparison/README.md) | The prespecified W1/W2/W3 audit-workflow comparison: protocol, specification and fault inventory hashed before the run, the three programs, fixtures, every program's raw output and exit status, cost and code size, and the findings | Sec. 4.1, Fig. 3 |
| [linux-replay/run-40545198707-dea292c/](linux-replay/run-40545198707-dea292c/) | Linux replay of the six learned-reward packages from an empty data home (CI): each package's reproduction report, exit codes, negative cases, platform and the generic example | Sec. 5.2, Fig. A.1 |
| [ci/run-40694880778-30bd3f6/](ci/run-40694880778-30bd3f6/) | The CI run the paper cites, on the last code revision: job log, Linux coverage, reproducibility reports from Linux and Windows 3.12 and 3.13, and the source archive's manifest and digest | Sec. 5.1, 5.2 |
| [ci/run-40546091715-11145b3/](ci/run-40546091715-11145b3/) | The same records for the previous code revision `11145b3` | — |
| [validation/](validation/README.md) | The local Windows run of the full test suite: 571 passed, and what it did not cover | — |
| [manuscript/](manuscript/VISUAL_REVIEW.md) | Diffs of `main.tex` and `references.bib` against the imported package, each CI build's logs, and the page-by-page review of each build | — |
| [READINESS.md](READINESS.md) | Readiness assessment: what was done, verified, not verified and still blocking | — |
| [ARCHIVE.md](ARCHIVE.md) | What a public archive deposit would need, and the release steps that remain the author's | Code and data availability |

The claim-by-claim map from the manuscript to these files is
[paper/neurocomputing/EVIDENCE.md](../../paper/neurocomputing/EVIDENCE.md).

## Kept outside Git

These are listed by digest here and are delivered in the review package.

- **CartPole checkpoints:** the frozen checkpoints of the study are listed in
  `cartpole-study/records/frozen-checkpoints.sha256` (36 files).
- **Comparison fixtures:** the policies of the comparison fixtures are listed in
  `workflow-comparison/protocol/HASHES.sha256`.
- **Manuscript builds:** each build's PDF and page images are listed in its `SHA256SUMS`.
- **CI outputs:** the source tarball of `30bd3f6` that CI built is listed by digest in
  `ci/run-40694880778-30bd3f6/source-archive/SHA256SUMS`. It is kept outside Git together with CI's HTML
  coverage report.
- **Historical bundle:** the repaired 38-policy bundle (`LunarLab_38_Policy_Study.zip`) and its source archive.
  These are historical and unchanged.

## Checking the evidence

```bash
python tools/evidence_inventory.py --out after.json --compare reports/neurocomputing-2026-10-27/integrity/inventory-before.json --exclude reports/neurocomputing-2026-10-27
python reports/neurocomputing-2026-10-27/cartpole-study/analyze.py reports/neurocomputing-2026-10-27/cartpole-study/records/main OUT   # = results/, byte for byte
python paper/neurocomputing/figures/build_figures.py                               # redraw the figures from these files
python paper/neurocomputing/check_manuscript.py --final
```

- **Inventory comparison:** the inventory needs the original data home. Pass the historical bundle with
  `--external` to include it.
- **Comparison programs:** they are rerun from the fixtures, following `workflow-comparison/README.md`.
