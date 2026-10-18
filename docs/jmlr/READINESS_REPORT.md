# JMLR-MLOSS readiness report

**Software:** LunarLab 0.1.0 · **Repository state:** the first readiness pass is on `main` at `2c41b42`
(pushed 2026-10-18; CI run [39069730331](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/39069730331): all
six jobs passed). The **correction pass** described first below is on branch `research/jmlr-mloss-corrections`,
from `2c41b42`, **uncommitted** — nothing was committed, pushed, merged, released or submitted. **Machine:**
Windows 11, Intel i7-13620H, 16 GB, Python 3.12.13 (and 3.13.12), CPU only.

Companion documents: [REQUIREMENTS_MATRIX.md](REQUIREMENTS_MATRIX.md) · [REPRODUCIBILITY.md](REPRODUCIBILITY.md) ·
[BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md) · [SCIENTIFIC_REVIEW.md](SCIENTIFIC_REVIEW.md) ·
[COMMUNITY_EVIDENCE.md](COMMUNITY_EVIDENCE.md) · [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md) ·
[RELATED_SOFTWARE.md](RELATED_SOFTWARE.md) · [COMPARISON_EVIDENCE.md](COMPARISON_EVIDENCE.md) ·
[EXTENDING_LUNARLAB.md](EXTENDING_LUNARLAB.md) · [INITIAL_AUDIT.md](INITIAL_AUDIT.md) · manuscript
[../../paper/jmlr-mloss/](../../paper/jmlr-mloss/BUILD.md) · independent users [../REPRODUCING.md](../REPRODUCING.md).

# Correction pass (2026-10-18)

## A. Problems confirmed

| Problem reported | Reproduced? | Cause | Kind | Fixed | Remaining |
|---|---|---|---|---|---|
| Linux CI: 0/100 episodes of each supplied artifact bit-identical | yes (CI reports of run 39069730331) | numerical divergence; experiments point to the simulator's compiled float code (Box2D builds), amplified by the closed loop: correctly rounded Python trigonometry changes nothing, other BLAS kernels change network outputs but no action, a one-ulp simulator perturbation produces the same pattern | scientific limitation | characterised; per-episode diagnostics, four separate properties, statuses and exit codes; Windows reference traces and a Linux trace comparison in CI | direct Linux confirmation of the first diverging step runs at the next CI run |
| CI hid the Linux reproduction outcome (`|| true`) | yes | reporting problem | reporting | every exit code recorded; job summary; fails on integrity errors, same-platform differences, significant aggregate changes; test forbids masking | the corrected workflow has not run on GitHub |
| "Interrupted runs resume exactly" (manuscript, JMLR docs, README "full training state") | yes | overstated wording; the code's own contract already said "not bit-identical" | reporting | wording corrected everywhere to the implemented contract (levels 1–2 yes, 3 partly, 4 no) | — |
| Readiness documents described the pre-push state | yes | documents written before the push | reporting | matrix, checklist, reproducibility, progress and this report updated with commit IDs, run ID and dates | — |
| Benchmark run on a dirty tree; "4 % overhead" without scope | yes | provenance and reporting | reporting | standard benchmark repeated on a clean checkout of `2c41b42`; loop overhead (0–4 % accounting, 4–6 % pipeline) and full wall clock (1.22–1.23×, validation included) reported separately | other machines, DQN, comprehensive profile not run |
| Low coverage of `parallel.py`, `server/main.py`, `cli.py`, `jobs.py`, `api.py`, `sysinfo.py` | yes | `parallel.py` untested; server start-up and shutdown never run in tests; browser flows run the backend unmeasured | code (tests) and measurement | integration tests: parallel runner, served backend lifecycle, supervisor termination/crash/shutdown, CLI and HTTP errors, provenance without git; Playwright backends now shut down gracefully (measurable) | coverage 85.8 %, not close to 100 % |
| — found by those tests | — | after a worker crash the run kept claiming "running" and refused a resume for up to 60 s | code defect | `jobs.py` marks such a run interrupted (as a backend restart already did); regression test | — |
| — found by those tests | — | the CLI printed tracebacks for invalid or unknown ids and missing artifact folders; `test-status` reported "0 completed tests" for an unknown run | code defect | ids validated before any command (exit 2); unknown ids, missing folders: clear error (exit 1/2); regression tests | — |
| — found before the push of `2c41b42` | — | revision archives built on Windows contained CRLF text | code defect | fixed and pushed (`2c41b42`); CI's Linux archive is byte-identical to the Windows build | — |
| Manuscript never compiled; figure text below 9 pt; four-page limit unverified | yes | no LaTeX engine | missing tooling | built with an isolated Tectonic; figures redrawn at print size with an automatic ≥ 9 pt check; table overflow fixed; text tightened to four pages | pdflatex build not run; author fields |
| Novelty and scope | partly | "applies the accounting to any Gymnasium environment" too broad | reporting | manuscript states what the adapter layer demonstrates and what stays LunarLander-specific | — |
| Release provenance | — | no release, no tag | missing human action | release candidate 0.1.0 verified consistent; exact commands in the checklist | tagging and publishing (maintainer) |
| Active user community | — | none exists | missing human action | independent-reproduction guide; evidence-collection guidance; report forms aligned with statuses | real users (authors) |

## B. Files changed in the correction pass

- **Reproduction diagnostics:** `lunarlab/reproduce.py` (per-episode rows and summary, paired conclusion tests,
  platform comparison, statuses and exit codes, new integrity checks), `lunarlab/divergence.py` (new: per-step
  traces, inference vs dynamics attribution), `lunarlab/cli.py` (`trace-artifact`; exit codes; id validation and
  clear errors), `tools/reproduction_summary.py` (new: CI summary and gate), `tools/reproducibility_experiments.py`
  (new: the controlled experiments), `.github/workflows/ci.yml` (no masked exit codes; trace comparison; summaries).
- **Supervisor fix:** `lunarlab/jobs.py` (crashed worker leaves the run interrupted).
- **Manuscript:** `paper/jmlr-mloss/main.tex` (claims corrected, four pages), `EVIDENCE.md`, `BUILD.md`;
  figures redrawn (`tools/paper_figures.py`: print-size check; `figures/`, `reports/jmlr/figures/`); unused
  overhead figure removed from the manuscript folder.
- **Tests:** `tests/test_reproduction_report.py`, `test_server_lifecycle.py`, `test_parallel_and_supervisor.py`,
  `test_cli_and_http_errors.py` (new); additions in `test_project_metadata.py`; `test_tutorial.py` (exit code 3).
- **Browser tests:** `frontend/e2e/teardown.ts` (new), `frontend/playwright.config.ts` (graceful backend shutdown).
- **Documentation:** `README.md`, `PROGRESS.md`, `docs/REPRODUCING.md` (new), `docs/MIGRATION.md` and the JMLR
  documents (`READINESS_REPORT`, `REQUIREMENTS_MATRIX`, `SUBMISSION_CHECKLIST`, `REPRODUCIBILITY`,
  `SCIENTIFIC_REVIEW`, `BENCHMARK_PROTOCOL`, `COMMUNITY_EVIDENCE`, `RELATED_SOFTWARE`, `COMPARISON_EVIDENCE`,
  `REPRODUCTION_REPORT_TEMPLATE`), the reproducibility issue form, `docs/api/` (regenerated).
- **New measurements (no existing file changed):** `reports/jmlr/benchmarks/standard-2026-10-18T132206+0000/`,
  `reports/jmlr/reproducibility/` (traces, experiments); regenerated: `reports/jmlr/coverage/`.

## C. Test results

| | Where | Result |
|---|---|---|
| Python suite | development machine, Python 3.12, 2026-10-18 | **493 passed, 0 failed, 0 skipped** |
| Statement + branch coverage | same run | **85.8 %** (first pass 82.9 %, before the readiness work 75.2 %); per module in `reports/jmlr/coverage/SUMMARY.md` |
| Python suite incl. browser flows' backends | development machine | 86.3 % (supplementary: the backends of the 15 browser flows measured too) |
| Fast suite, Python 3.13 | development machine | 417 passed (76 slow tests deselected); `reproduce-smoke` 15/15 |
| Browser flows (Playwright, Edge) | development machine | 15 passed (Microsoft Edge); both backends shut down through `/api/shutdown` |
| Frontend typecheck, lint, build | development machine | `tsc`, `oxlint` and the production build clean |
| Lint and format | development machine | ruff check and format clean (also with the CI lock's ruff version) |
| Source archive | development machine | working-tree archive (318 files, 8.2 MB) installed into a fresh environment: `--version`, `doctor` 10/10, `reproduce-smoke` 14/14, 199 release tests passed |
| Reproducibility | development machine | `reproduce-smoke` 15/15; artifacts `exact` 300/300 (status report schema 2) |
| CI at `2c41b42` (before the corrections) | GitHub, run 39069730331 | all six jobs passed: Linux 445 passed, 4 skipped (Windows-only); Windows 3.12 and 3.13: 288 targeted tests each; source archive installed fresh (189 release tests); 15 browser flows |
| CI of the corrections | — | **not run** (nothing pushed) |

## D. Cross-platform reproducibility

| Artifact | Bit-identical (Windows dev / CI Windows / CI Linux) | Mean return recorded → Linux | Largest / sampled typical difference (Linux) | Pad landing recorded → Linux |
|---|---|---|---|---|
| PPO baseline | 100 / 100 / 0 of 100 | 265.8558 → 265.8615 | 0.277 / 0.0028 (seed 20000) | 96 % → 96 % |
| PPO hover bonus | 100 / 100 / 0 of 100 | −21.2456 → −20.7658 | 126 / 0.90 (seed 20000) | 0 % → 0 % |
| DQN baseline | 100 / 100 / 0 of 100 | 155.3644 → 156.8764 | 192 / 0.0009 (seed 20000) | 29 % → 29 % |

Outcome agreement on Linux was measured only for the 20 episodes per artifact the old report kept: all
environment outcomes and pad-landing classifications agreed, episode lengths in 55 of 60. The main scientific
conclusions are stable: the reward-exploitation result (0 % pad landing for the hover bonus) and every mean
return lie well inside the recorded intervals. Explanation and limitations: [REPRODUCIBILITY.md](REPRODUCIBILITY.md).

## E. Manuscript status

PDF built (Tectonic 0.17.0, XeTeX): **4 description pages, 2 reference pages, 118 KB**; no overfull lines, no
undefined citations or references; abstract 191 words, running title 38 characters, five keywords, 16
verified references. Figures redrawn at the printed size (6.0 in, all text ≥ 9 pt, checked automatically).
Corrected claims: continuation, reproducibility, overhead, adapter scope (see [SCIENTIFIC_REVIEW.md](SCIENTIFIC_REVIEW.md)).
Unresolved author fields (9 `\TODO` markers): author names, surnames, e-mail, affiliation and address, release tag,
acknowledgements with the funding and competing-interests declaration, submission date; the editor and paper ID
are JMLR's. About three lines are free on page 4 beyond the acknowledgements placeholder.

## F. Experimental integrity

SHA-256 of every file under `runs/`, `data/`, `reports/`, `docs/results/`, `docs/media/`, `demo/api/` and
`examples/artifacts/` was recorded before this pass (1,782 files). After it: 1,699 files byte-identical to the baseline (runs, data, published results and media, demo snapshot, supplied artifacts, earlier reports and benchmark runs); 0 removed; 21 added (the clean benchmark run and the reproducibility evidence); the coverage report and the figures regenerated. Trained policies,
evaluations, datasets, seeds and published results were only read; every test, experiment and benchmark used a
temporary home.

## G. Submission readiness

**MOSTLY READY — SPECIFIC TECHNICAL ISSUES REMAIN**

The software, its tests and its documentation are in submission shape, and every claim in the manuscript is backed by stored evidence. Specific technical issues remain: (1) the corrections of this pass have run only on Windows — the corrected CI workflow, including the Linux trace comparison that should confirm where Linux trajectories part, runs only after the branch is pushed; (2) coverage is 85.8 % (command-line orchestration 60 %), still short of the "close to 100 %" the MLOSS guidelines expect; (3) the PDF was built with XeTeX (Tectonic) and its page count is unconfirmed with pdflatex. Beyond these, submission needs what only people can provide: the authors' details, acknowledgements and declarations, an approved and tagged release, and, decisively, real evidence of an active user community, which does not exist today.

No acceptance probability is estimated.

# First readiness pass (2026-10-17/18, historical)

The sections below describe the first pass as it was reported before the push; numbers in them are those of
that time. Two statements there are superseded by the correction pass above: "resumes exactly" (C) — continuation
restores the algorithm state but is not bit-identical — and "this branch has not run on Linux" (B, D) — it ran in
CI on 2026-10-18.

### First pass — A. Implementation summary

**Verified gaps** (reproducible commands in [INITIAL_AUDIT.md](INITIAL_AUDIT.md)): no license file and no
per-file license notice (P0); no source package (P0); `optuna` missing from the package metadata, so an install
without the lock file broke tuning (P0); declared Python support broader than tested (P0); no coverage
measurement, no API reference (31 % docstrings), version in three places without `--version`, no contribution
guide or citation metadata, no reviewer-facing reproducibility command, no runtime/memory comparison, CI on one
Python version, UI-centred tutorials, a Linux install path that pulled proprietary CUDA packages (all P1);
generality not demonstrated, no property-based tests, no supplied artifacts, raster-only paper figures (P2).

**Implemented**

| Area | What | Files |
|---|---|---|
| Licensing | MIT `LICENSE`; SPDX notice in every source file (a tool and a test keep it so); third-party notices generated from the locks and PyPI/npm metadata; `CITATION.cff`; license fields consistent in Python and npm metadata | `LICENSE`, `tools/spdx_headers.py`, `tools/third_party_notices.py`, `THIRD_PARTY_NOTICES.md`, `CITATION.cff` |
| Packaging and version | single version (`lunarlab.__version__`, read by setuptools); `--version` and `version --json` with the source revision; `optuna` declared; `requires-python` = tested 3.12–3.13; PEP 639 license metadata; dev tools (pytest-cov, hypothesis) added to both locks without moving any existing pin | `pyproject.toml`, `lunarlab/cli.py`, `lunarlab/sysinfo.py`, `requirements*.lock` |
| Release | deterministic source archive (sorted members, normalised owners/times, git-identical text), manifest with per-file SHA-256, refuses VCS/platform/env files, `--verify` installs it into a fresh environment and runs its release tests | `tools/build_source_archive.py` |
| Reproducibility | `reproduce-smoke` (14 provenance checks, optional training-determinism check), `export-artifact`, `reproduce-artifact`; three published final tests supplied | `lunarlab/reproduce.py`, `examples/artifacts/` |
| Benchmark | equivalent-workload overhead benchmark against plain SB3 (time, CPU, memory, artifacts, checkpoint and recording cost), raw data, table and figures | `lunarlab/overhead.py`, `reports/jmlr/benchmarks/` |
| Generality | task-independent accounting wrapper, task adapters (LunarLander identical to the pipeline; CartPole), policy audits, seed-split validation | `lunarlab/audit/`, `examples/cartpole_audit.py` |
| Documentation | tutorial (executed by the tests), developer guide, generated API reference (Python, CLI, HTTP/OpenAPI) with 104 new docstrings, contributing guide, issue forms, PR checklist, JMLR readiness documents | `docs/TUTORIAL.md`, `docs/DEVELOPER.md`, `docs/api/`, `CONTRIBUTING.md`, `.github/`, `docs/jmlr/` |
| Figures and manuscript | figures from stored data with a manifest; manuscript scaffold in the official style, verified bibliography, evidence map, cover-letter template, style fetcher, source checker | `tools/paper_figures.py`, `reports/jmlr/figures/`, `paper/jmlr-mloss/` |
| CI | coverage report, docs/headers/manuscript checks, reproduction reports (Linux and Windows), source-archive job, Windows on Python 3.12 and 3.13 | `.github/workflows/ci.yml` |
| Fixes found on the way | `setup.ps1`-style help broken by the new license header (blank line now required, tested); argparse output made width-independent for the API reference; one over-strong sentence in `docs/RESULTS.md` reworded | `scripts/*.ps1`, `tools/gen_api_docs.py`, `docs/RESULTS.md` |

**Tests added** (179 new; 449 in total): release metadata and licensing
(`test_project_metadata.py`), documented commands parse (`test_docs.py`), the tutorial executed in order
(`test_tutorial.py`), reproducibility commands and tamper detection (`test_reproduce.py`), DQN continuation
refusals (`test_continuation_validation.py`), property-based invariants of shaping, accounting, statistics and
outcomes (`test_properties.py`), the audit layer incl. exact equivalence with the pipeline
(`test_audit_core.py`), the overhead benchmark (`test_overhead.py`), the source archive (`test_source_archive.py`),
reclassification and the planning benchmark (`test_reclassify_and_benchmark.py`), study-type result generation
(`test_results_studies.py`), PowerShell help (`test_windows.py`).

**Existing behaviour preserved:** all 270 earlier tests pass unchanged; published configuration hashes are pinned
and unchanged; the generic accounting reproduces `LunarLabRewardWrapper` exactly for all four presets; the
frontend changed only by license comments and the package's license field; the main pipeline's code paths
were not altered beyond docstrings, the version option and new commands; the demo snapshot is untouched.

### First pass — B. Technical quality

| Measure | Result |
|---|---|
| Statement + branch coverage | **82.9 %** (before: 75.2 %); reward, audit, training, continuation, freezing, outcome, evaluation and statistics modules 84–100 %, result export, run storage and provenance modules (`results`, `demo`, `runs`, `storage`, `lineage`, `sysinfo`) 67–91 %; per-module table and reasons for the remaining gaps in `reports/jmlr/coverage/SUMMARY.md` |
| Python tests | **449 passed** (Windows 11, Python 3.12); fast suite 376 passed on Python 3.13 |
| Browser end-to-end | **15 passed** (Playwright on two real backends: 10 earlier flows + 5 audit flows) |
| Lint, format, types | ruff check and format clean; `tsc` clean; `oxlint` clean; production build OK |
| Installation | `doctor` 10/10; source archive installed into a fresh environment, `reproduce-smoke` 14/14 and 188 release tests passed there |
| Platforms | Windows 11 verified locally (Python 3.12 and 3.13; scripts parse under 5.1; start/stop verified). Linux: the CI install path passed on GitHub at the audited revision, **this branch has not run on Linux**. macOS: not supported or tested |
| Reproducibility | smoke pipeline 15/15 (PPO and DQN, with the determinism check); trainings bit-identical within and across processes on this machine; 300/300 published final-test episodes bit-identical from the supplied artifacts |
| Benchmark | plain SB3 2,097 ± 8 transitions/s; with reward accounting 2,019 ± 13 (1.04×); full pipeline 2,013 ± 48 (1.04×) plus 8.4 s of validation; peak memory 310 / 311 / 323 MB (102,400 transitions, 3 repetitions) |

**Remaining technical limitations:** the extended CI and the Linux run of the new code are unverified until a
push; cross-platform bit-identity is not established (the CI reports will show it); coverage is well below "close
to 100 %" in application code (CLI handlers, server, job supervisor); 129 public objects of the research API still
lack docstrings and there is no hosted documentation site; the manuscript PDF was not built (no LaTeX).

### First pass — C. Scientific contribution

**What LunarLab demonstrably adds:** one tested workflow that records the original reward, every term and the
training reward on each transition; evaluates on the original reward with validated, disjoint seeds and
immutable final-test checkpoints; exposes exploitation with a reward-independent detector (measured: the flawed
hover bonus earns a training return of 746 while the original return is −50; 0 of 500 test landings); resumes
exactly (DQN replay buffer included); records provenance; and ships reproduction tooling. Evidence:
[COMPARISON_EVIDENCE.md](COMPARISON_EVIDENCE.md).

**What existing tools already do:** SB3 provides the algorithms, `Monitor`, `EvalCallback`, checkpointing and
replay-buffer saving on request; RL Zoo adds Optuna tuning, configurable wrappers and partly rliable-based plots;
CleanRL offers single-file implementations with tracking; rliable provides the statistics; imitation keeps the
original reward beside a learned one. Distinctions are stated only where the sources reviewed document no
equivalent, and absence is never claimed.

**Limits of the claims:** no new algorithm; the full pipeline is LunarLander-specific (adapter layer
demonstrated on CartPole only); the published study has 3–5 seeds per group and one budget; bit-identity holds on
the producing platform; LunarLab exposes reward hacking, it does not prevent it; it is a 2-D simulation benchmark.

**Additional experiments** (ranked, with commands and budgets, in [SCIENTIFIC_REVIEW.md](SCIENTIFIC_REVIEW.md)):
cross-platform reproduction of the artifacts; more seeds for the shaping comparison; the matched-budget PPO/DQN
× discount-factor study; a second task with a flawed term; the comprehensive overhead benchmark. None was run.

### First pass — D. Publication suitability

- **Mandatory conditions satisfied:** recognised open-source license; license stated in the package and every
  source file; source package free of extra files; public repository.
- **Mandatory conditions incomplete:** runs on all supported platforms (Linux run of this branch pending); the
  four-page description (scaffold, PDF not built); JMLR style PDF (not built); cover letter with version and
  community evidence; title-page author details; funding and competing-interests declaration.
- **Review criteria strongly supported:** comparison with run-time, memory and features; installation; tutorial;
  non-trivial examples; ease of contribution; design clarity; developer documentation; open-source platform;
  freedom from proprietary software.
- **Review criteria weakly supported:** novelty and breadth (integration, one main task); openness (no forum);
  API documentation (69 % docstrings, no website); testing (coverage 82.9 %, not close to 100 %); CI on all
  platforms with multiple dependency versions (extended, not yet run).
- **Human actions required:** review and commit; push and check CI; confirm the license holder and the license
  of data/docs; choose and tag a version; author list, affiliations, contact; overlap, consent, conflicts,
  funding statements; suggest action editors and reviewers; build the PDF; collect real community evidence.
- **Evidence still unavailable:** an active user community (none today); independent and cross-platform
  reproductions; the built manuscript and its page count.

### First pass — E. Historical artifact protection

| | |
|---|---|
| Inventory | SHA-256 of every file under `runs/`, `data/`, `reports/`, `docs/results/`, `docs/media/`, `demo/api/`, taken 2026-10-17T15:19Z before any change: 1,667 files, combined digest `651c5e2b170cdcd2da13fda67d744cb5023454ca2e24de19fd3eaec492085e04` (`reports/jmlr/artifacts/integrity_baseline.json`) |
| Final comparison | 1,667 files, **0 added, 0 removed, 0 changed**, combined digest identical (`reports/jmlr/artifacts/integrity_comparison.json`); the new deliverables under `reports/jmlr/` are listed separately |
| Published results and model files | **unchanged.** Runs, checkpoints, evaluations, recordings, the published tables and figures and the demo snapshot were only read. `examples/artifacts/` holds byte-identical *copies* of three tested checkpoints, configurations and evaluations (digests recorded and tested) |
| Documents | `docs/RESULTS.md` (narrative): one sentence reworded, no number changed |
| Isolation | every test, smoke run, benchmark and reproduction used a temporary `LUNARLAB_HOME`; the start/stop script check used an isolated home |

### First pass — F. Final recommendation

**2. MOSTLY READY — SPECIFIC TECHNICAL BLOCKERS REMAIN.**

The software side is close: licensing, packaging, release tooling, reproducibility, benchmarking, comparison,
documentation and tests are in place and verified on Windows. The specific technical items left are: (1) run the
branch on Linux in CI (requires a push; the "runs on all supported platforms" condition is unverified until
then); (2) build the manuscript PDF and check the four-page limit (requires LaTeX); (3) coverage of
82.9 % is well short of the "close to 100 %" the MLOSS guidelines expect, mainly in application code.
Beyond these, a submission is **not** possible yet without the authors' manuscript information and, decisively,
real evidence of an active user community, which currently does not exist. No acceptance probability is
estimated.
