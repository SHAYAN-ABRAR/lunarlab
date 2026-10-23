# Reproduction reports from continuous integration

Unmodified copies of the reproduction artifacts that GitHub Actions uploads (it keeps them for 30 days), so the
cross-platform evidence cited in `docs/jmlr/REPRODUCIBILITY.md` and in the manuscript stays available. Digests:
`SHA256SUMS`.

| Folder | Run | Revision | Date | CI artifact | Contents |
|---|---|---|---|---|---|
| `run-39069730331-2c41b42/linux` | [39069730331](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/39069730331) | `2c41b42` | 2026-10-18 | `reproducibility-linux` | report schema 1: the first 20 differing episodes per artifact; its "largest return difference" is the maximum over the original and the training return |
| `run-39069730331-2c41b42/windows-py3.12`, `-py3.13` | same | `2c41b42` | 2026-10-18 | `reproducibility-windows-py3.12`, `-py3.13` | schema 1, 300/300 episodes bit-identical |
| `run-39144191758-4fd30db/linux` | [39144191758](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/39144191758) | `4fd30db` | 2026-10-18 | `reproducibility-linux` | schema 2 (every episode, statuses, paired tests), trace comparison against the Windows reference traces, CI summary, exit codes |
| `run-39144191758-4fd30db/windows-py3.12`, `-py3.13` | same | `4fd30db` | 2026-10-18 | `reproducibility-windows-py3.12`, `-py3.13` | schema 2 (`exact`, 300/300), trace comparison, CI summary, exit codes (written by PowerShell, CRLF) |
| `run-40015498622-4116599/linux` | [40015498622](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/40015498622) | `4116599` | 2026-10-23 | `reproducibility-linux` | `numerical-difference` (exit 3) for all three artifacts, integrity intact; trace comparisons, CI summary, exit codes, smoke report |
| `run-40015498622-4116599/windows-py3.12`, `-py3.13` | same | `4116599` | 2026-10-23 | `reproducibility-windows-py3.12`, `-py3.13` | `exact` (exit 0, 300/300) on both Python versions; trace comparisons, CI summary, exit codes |
| `run-40015498622-4116599/` (files) | same | `4116599` | 2026-10-23 | `coverage-linux`, job logs | `coverage-linux.json` (85.68% combined statement and branch coverage on Linux), the complete job log of all six jobs (`ci-run-40015498622.log`) and the run record (`run.json`); its own `SHA256SUMS` |
