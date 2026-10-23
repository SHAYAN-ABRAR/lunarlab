# Follow-up validation on the original machine

Dates: 19–20 October 2026 (measurements on 19 October UTC). Machine: the Windows 11 computer that holds the
original LunarLab data home and recorded every published result. Hardware: Intel i7-13620H, 10 physical / 16
logical cores, 16.8 GB, Windows 11 build 26300. Python 3.12.13 in the `requirements.lock` environment (every
applicable pin matches; the 19 unmatched pins are Linux-only CUDA/Triton wheels). Node 26.3.0, npm 11.16.0,
Microsoft Edge for Playwright.

**Source:** base `67440c664f658ccd589f7198ee2182d5820ca7c1` with the independent review's `lunarlab-review.patch`
applied unchanged (`git apply --check`, then `git apply`; all 28 resulting text files equal the review's
replacement files), its review records copied to `reports/jmlr/independent-review-2026-10-19/`, and the
follow-up changes listed at the end. Nothing was committed, pushed, tagged, released, uploaded or submitted, and
no one was contacted.

**Historical evidence:** never written. SHA-256 scans of `runs/`, `data/`, `reports/`, `docs/results/`,
`docs/media/`, `demo/api/` and `examples/artifacts/` before and after every step that read them found no removed
or changed file. Besides the review's own records, copied from its package as it instructs, the only additions
are the new benchmark run and this folder.

## Results

| Gate | Command | Result |
|---|---|---|
| Study-artifact export | `python tools/export_study_artifacts.py --out <new folder>` (calls `python -m lunarlab export-artifact --run-id <id> --out <folder>` for every run in `docs/results/results.json`) | 38 of 38 exported (exit 0 each) and verified. Each exported checkpoint, configuration and recorded final evaluation is byte-identical to its file in `runs/` and to the digest in `artifact.json`. Each checkpoint is the one its legacy freeze record names, by name and SHA-256. Each evaluation is the one `results.json` summarises (file, checkpoint, protocol hash, episode count, mean return, landing and time-limit rates). Run metadata, status, checkpoint manifest and event log copied unchanged; `episodes.csv` for the 15 learning-curve runs, matching the figure's source digests. No export refused. `study-artifacts/` |
| Published summaries | `python -m lunarlab results --experiment-ids <the three studies> --out <new folder>`; `python tools/compare_study_summaries.py` | Regeneration exit 0: 0 published values changed, 0 fields missing, 267 fields added by newer code (38 × 7 per-policy fields, one metadata record). All five figures byte-identical. Recomputed from the 3,800 raw episodes: 38/38 policies and 10/10 group IQMs match. `STUDY_SUMMARY_COMPARISON.md` |
| Python suite, run 1 | `pytest -q --cov` (as CI) on the patched source | **485 passed, 0 failed, 0 skipped**, 963 s; 85.80% combined statement and branch coverage (8,158/9,216 statements, 1,705/2,280 branches). `test_summary_run1.json` |
| Python suite, final | the same, after the follow-up's documentation edits and new test file | **489 passed, 0 failed, 0 skipped**, 614 s; coverage identical (the four new tests in `test_study_tools.py` exercise a tool outside the measured package). Wall time differs from run 1 mainly in one study test (564 s then, 111 s now); no test or outcome changed. `test_summary_final.json` |
| Reviewer sandbox failures | the review's seven failures (process adoption, supervised resume, process discovery, the three-worker benchmark, parallel workers, termination recovery, server lifecycle) and nine skips (five need a git checkout, four are Windows-only) | All 16 pass here. Diagnosis from the review's own log (`logs/revised_tests.log`): in that sandbox `psutil.Process()` raised `NoSuchProcess` for the calling process's own PID (benchmark worker, `overhead.py` line 90, before any training and outside the patched lines). A live 120-second child was likewise reported as terminated. The sandbox's `/proc` does not show its own processes, so every psutil-based ownership check fails or times out there. The same tests passed in GitHub's Linux CI at the base revision, and the patch does not touch process management. The review's test log was also recorded on an earlier draft of its documentation: its parametrised documentation tests cite different line numbers (495 tests there, 485 here) |
| Focused regressions | in both runs | `test_overhead` 3/3 (memory sampled before optional recording), `test_reproduction_report` 13/13 (compared fields, separate return maxima, no equivalence claim), freeze, continuation and integrity (`test_freeze` 8, `test_continuation_validation` 11, `test_dqn_continuation` 7, `test_reproduce` 9, `test_provenance` 3), CLI and HTTP failure paths 17/17, executable tutorial 2/2 (every command in `docs/TUTORIAL.md` in a fresh home) |
| Static gates | `ruff check`, `ruff format --check`, `tools/gen_api_docs.py --check`, `tools/spdx_headers.py`, `paper/jmlr-mloss/check_manuscript.py` | All pass; the manuscript checker lists four author-input markers |
| Frontend | `npm ls`, `npm run typecheck`, `npm run lint`, `npm run build` | All exit 0; the 100 installed packages match `package-lock.json` exactly |
| Browser tests | `npx playwright test` (Edge, real backends in disposable homes) | **15 passed** in 1.4 min. The backend logged one asyncio `ConnectionResetError` (WinError 10054) from the Windows proactor when the browser closed a connection; no test was affected |
| Recording-platform re-evaluation | `reproduce-artifact` and `trace-artifact --compare` for the three packages, then `tools/reproduction_summary.py` | Three of three `exact`, exit 0: 300/300 episodes match on the five compared fields, and the means equal the records (265.8558, −21.2456, 155.3644). All nine reference traces are identical. `reevaluation/` |
| Smoke reproduction | `reproduce-smoke --training-determinism` | exit 0 |
| Standard benchmark | `python -m lunarlab overhead-benchmark --profile standard` | New run `reports/jmlr/benchmarks/standard-2026-10-19T180346+0000/` with `source_state.json`. Loop ratios 1.021 and 1.053, workflow ratio 1.221; peaks 310/310/314 MB, all sampled before optional recording. `benchmark_recomputation.json`, `docs/jmlr/BENCHMARK_PROTOCOL.md` |
| Historical integrity claims | re-hash against the manifests | Committed 1,667-file manifest: 1,667 byte-identical. The correction pass's "1,699 identical" was a miscount of 1,708, and all 1,708 are still identical. A first-pass 1,699-entry scan's 32 deliverables: 4 unchanged, 16 line endings only, 2 PDFs re-rendered before the first commit, 10 figures regenerated in `4fd30db`. `integrity_claims_check.json` |
| Fresh source-archive install | `python tools/build_source_archive.py --working-tree --out <folder> --verify` | Working-tree archive, labelled `working-tree 67440c664f65 (uncommitted changes included)`: 425 files, 8.6 MB. Installed into a fresh environment from `requirements.lock`: `--version`, `doctor` 10 ok / 0 warnings / 0 failures, `reproduce-smoke` 14/14, **189 release tests passed** (the archive omits `paper/`, so its documentation tests differ from CI's 199 at the base). The archive contains this file, so its digest and log are kept in the review-return package (`source/`) |
| Manuscript | Tectonic 0.17.0 with the unmodified pinned style | Four description pages plus one reference page; no overfull boxes or unresolved references; every page inspected. A clipped figure title was fixed (`paper/jmlr-mloss/BUILD.md`) |

## Not done here

- No Linux run and no CI run of the revised source: WSL is not installed, and CI needs a push, which is the
  author's decision.
- No pdflatex build. Tectonic reproduced the review's pdflatex pagination on the unchanged source.
- The 38 exported packages were checked, not re-evaluated.
- No independent user was contacted. An exercise kit is prepared in the review-return package.
- Author fields, declarations, final revision and the bundle's public location are left to the author.

## Follow-up changes to the source

New: `tools/export_study_artifacts.py`, `tools/compare_study_summaries.py`, `tests/test_study_tools.py`, this
folder, the benchmark run folder. Changed: `README.md`, `PROGRESS.md` (the 1,699 correction),
`docs/jmlr/{BENCHMARK_PROTOCOL, READINESS_REPORT, RELEASE_PREPARATION, REPRODUCIBILITY, SUBMISSION_CHECKLIST}.md`,
`paper/jmlr-mloss/{main.tex, BUILD.md, EVIDENCE.md, COVER_LETTER_TEMPLATE.md, build_audit_figure.py}`, the
regenerated `figures/final_test_audit.{pdf,png}`, and lint fixes so the review's files pass the repository's
ruff gates. Three patched files, `lunarlab/reproduce.py`, `tests/test_reproduction_report.py` and
`tools/reproduction_summary.py`, were reformatted only: their syntax trees are identical to the review's. The
review's two new scripts were reformatted and given explicit UTF-8 I/O and `zip(strict=True)`; their outputs
were proved unchanged (identical figure PDF, identical verifier JSON).
