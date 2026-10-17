# JMLR-MLOSS readiness report

**Software:** LunarLab 0.1.0 · **Branch:** `research/jmlr-mloss-readiness` from `28dd935` (uncommitted; nothing
pushed, released or submitted) · **Dates:** 2026-10-17/18 · **Machine:** Windows 11, Intel i7-13620H, 16 GB,
Python 3.12.13 (and 3.13.12 for the version check), CPU only.

Companion documents: [INITIAL_AUDIT.md](INITIAL_AUDIT.md) · [REQUIREMENTS_MATRIX.md](REQUIREMENTS_MATRIX.md) ·
[REPRODUCIBILITY.md](REPRODUCIBILITY.md) · [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md) ·
[RELATED_SOFTWARE.md](RELATED_SOFTWARE.md) · [COMPARISON_EVIDENCE.md](COMPARISON_EVIDENCE.md) ·
[EXTENDING_LUNARLAB.md](EXTENDING_LUNARLAB.md) · [COMMUNITY_EVIDENCE.md](COMMUNITY_EVIDENCE.md) ·
[SCIENTIFIC_REVIEW.md](SCIENTIFIC_REVIEW.md) · [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md) ·
manuscript workspace [../../paper/jmlr-mloss/](../../paper/jmlr-mloss/BUILD.md).

## A. Implementation summary

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

## B. Technical quality

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

## C. Scientific contribution

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

## D. Publication suitability

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

## E. Historical artifact protection

| | |
|---|---|
| Inventory | SHA-256 of every file under `runs/`, `data/`, `reports/`, `docs/results/`, `docs/media/`, `demo/api/`, taken 2026-10-17T15:19Z before any change: 1,667 files, combined digest `651c5e2b170cdcd2da13fda67d744cb5023454ca2e24de19fd3eaec492085e04` (`reports/jmlr/artifacts/integrity_baseline.json`) |
| Final comparison | 1,667 files, **0 added, 0 removed, 0 changed**, combined digest identical (`reports/jmlr/artifacts/integrity_comparison.json`); the new deliverables under `reports/jmlr/` are listed separately |
| Published results and model files | **unchanged.** Runs, checkpoints, evaluations, recordings, the published tables and figures and the demo snapshot were only read. `examples/artifacts/` holds byte-identical *copies* of three tested checkpoints, configurations and evaluations (digests recorded and tested) |
| Documents | `docs/RESULTS.md` (narrative): one sentence reworded, no number changed |
| Isolation | every test, smoke run, benchmark and reproduction used a temporary `LUNARLAB_HOME`; the start/stop script check used an isolated home |

## F. Final recommendation

**2. MOSTLY READY — SPECIFIC TECHNICAL BLOCKERS REMAIN.**

The software side is close: licensing, packaging, release tooling, reproducibility, benchmarking, comparison,
documentation and tests are in place and verified on Windows. The specific technical items left are: (1) run the
branch on Linux in CI (requires a push; the "runs on all supported platforms" condition is unverified until
then); (2) build the manuscript PDF and check the four-page limit (requires LaTeX); (3) coverage of
82.9 % is well short of the "close to 100 %" the MLOSS guidelines expect, mainly in application code.
Beyond these, a submission is **not** possible yet without the authors' manuscript information and, decisively,
real evidence of an active user community, which currently does not exist. No acceptance probability is
estimated.
