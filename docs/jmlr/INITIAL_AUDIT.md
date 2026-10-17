# Initial audit for a JMLR-MLOSS submission

**Inspected revision:** `28dd935c92532a046b902bfe4a5457b632a1b9f1` (`main`, identical to `origin/main`, clean
working tree), inspected on 2026-10-17. All work since then is on the branch `research/jmlr-mloss-readiness`.

**Machine:** Windows 11 (10.0.26300), Intel Core i7-13620H, 16 GB RAM; Python 3.12.13 (uv-managed virtual
environment), gymnasium 1.4.0, stable-baselines3 2.9.0, torch 2.14.1 (CPU build), Node.js 26.3.0.

**Method:** read the official JMLR pages (below), the source (16,103 lines of Python in `lunarlab/`, 4,459 lines of
tests, 44 frontend files), CI workflows, documentation and stored results; ran the test suite under coverage;
reproduced each finding with the command given. Experiment data was only read; a SHA-256 inventory of all 1,667
evidence files was taken first (`reports/jmlr/artifacts/integrity_baseline.json`, combined digest
`651c5e2b170cdcd2da13fda67d744cb5023454ca2e24de19fd3eaec492085e04`).

## Official sources

| Page | Retrieved | SHA-256 of the HTML read |
|---|---|---|
| https://www.jmlr.org/mloss/mloss-info.html | 2026-10-17 | `809ed0fd8dc0c3eb…` |
| https://www.jmlr.org/author-info.html | 2026-10-17 | `de4f2e6dee40e595…` |
| https://www.jmlr.org/format/format.html | 2026-10-17 | `1769895a037c6473…` |
| https://www.jmlr.org/mloss/ (list of published MLOSS papers) | 2026-10-17 | (read for context) |
| JMLR style repository `JmlrOrg/jmlr-style-file` | commit `f413f638b407af76074813f8f88a82a7a5a81e9d` | `jmlr2e.sty` `a430a875…`, `sample.tex` `19f56344…` |

The requirements extracted from them are in [REQUIREMENTS_MATRIX.md](REQUIREMENTS_MATRIX.md).

## Baseline measurements

| Measurement | Result | How to reproduce |
|---|---|---|
| Test suite | 270 passed (local, Windows); CI run 38960915205 at this revision passed on Linux (Python, frontend, browser end-to-end) and Windows | `python -m pytest -q` |
| Statement + branch coverage | **75.2 %** (8,060 statements, 1,750 missed; 2,062 branches, 304 partial); `doctor.py`, `benchmark.py`, `reclassify.py` 0 %, `parallel.py` 16 %, `cli.py` 34 %, `server/main.py` 45 % | `python -m pytest --cov` with the coverage settings in `pyproject.toml`; report in `reports/jmlr/coverage/baseline/` |
| Docstrings | 194 of 625 public functions and classes (31 %); every module has a module docstring | an AST count over every module of the package (per-module counts for the research API are now generated in `docs/api/README.md`) |
| Documented commands | 69 command lines in fenced code blocks; all parse with the CLI parser except one diagram line with an inline comment | `tests/test_docs.py` (added) |
| Repository activity | public since 2026-10-14; 0 stars, 0 forks, 0 watchers, 0 issues; 1 contributor (12 commits); issues enabled, discussions disabled; no license detected by GitHub | `gh api repos/SHAYAN-ABRAR/lunarlab` |

## Findings

Priorities: **P0** blocks a trustworthy submission or reproduction; **P1** is a major research-software weakness;
**P2** strengthens the submission; **P3** is polish.

| ID | Pri. | Finding | Evidence / reproduction |
|---|---|---|---|
| A1 | P0 | **No license file and no license notice in any source file.** The package metadata declared MIT (`license = { text = "MIT" }`), but the repository had no `LICENSE`, GitHub detected no license, and no source file mentioned one. MLOSS: the software "must adhere to a recognised open source license", and licensing must be "clearly stated in the source package and mentioned in each source file". | `git ls-files \| grep -i licen` (empty); `gh api repos/SHAYAN-ABRAR/lunarlab --jq .license` → `null` |
| A2 | P0 | **No source package.** Nothing builds a source archive without version-control files; after acceptance MLOSS requires "a single file containing an archive of the source code". | no `MANIFEST.in`, no build script; `dist/` absent |
| A3 | P0 | **A runtime dependency was missing from the package metadata.** `lunarlab/tuning.py` imports `optuna`, which was only in `requirements.in`. Installing the package from source without the lock produces an installation in which tuning and its tests fail to import. | `python -c "import importlib.metadata as m; print(m.requires('lunarlab'))"` (no optuna); `git grep "import optuna" lunarlab` |
| A4 | P0 | **Declared Python support did not match tested support.** `requires-python = ">=3.10,<3.14"`, README "Python 3.12 or 3.13", CI 3.12 only. MLOSS checklist: the code must run "on all your supported platforms". | `pyproject.toml`, `README.md`, `.github/workflows/ci.yml` |
| B1 | P1 | **No coverage measurement or report** (MLOSS: "report of code coverage of tests. It is expected that test coverage is close to 100%"). | no coverage tool in the locks or CI |
| B2 | P1 | **No API reference**; 31 % docstrings (MLOSS: "Full documentation of the API"; developer documentation should "provide an API reference"). | see baseline table |
| B3 | P1 | **Version declared in three places** (`pyproject.toml`, `lunarlab/__init__.py`, `frontend/package.json`); no `--version` option; the CLI reported no source revision. Runs recorded the revision, the CLI could not. | `grep -rn 0.1.0 pyproject.toml lunarlab/__init__.py frontend/package.json`; `python -m lunarlab --version` → error |
| B4 | P1 | **No contribution guide, issue templates or citation metadata**; discussions disabled (MLOSS: openness, "bug tracker, mailing list/forum", ease of contribution). | `ls CONTRIBUTING* CITATION* .github/ISSUE_TEMPLATE` (none) |
| B5 | P1 | **No reviewer-facing end-to-end reproducibility command or document.** The pieces are tested separately; there was no single portable command (without the web UI) that trains, checkpoints, reloads, evaluates, exports and verifies digests, nor a document with verified Windows and Linux commands. | — |
| B6 | P1 | **No runtime or memory comparison with the underlying implementation or related software** (MLOSS: "comparison to previous … related implementations, w.r.t. run-time, memory requirements, features"). The existing `benchmark` command measures throughput for planning only. | `lunarlab/benchmark.py` |
| B7 | P1 | **CI tests one Python version, without coverage**; the Windows job runs a selection of the tests (127 of 270 at the time). MLOSS: CI "ideally on all supported platforms and with multiple versions of potential dependencies". | `.github/workflows/ci.yml` |
| B8 | P1 | **Tutorials were UI-centred.** README "First run" walks through the web UI; there was no step-by-step research tutorial for the CLI and Python API (custom reward term, diagnosing exploitation, comparing runs, exporting results). | `README.md`, `docs/` |
| B9 | P1 | **Linux install path pulled proprietary packages by default.** On Linux, `requirements.lock` installs 19 CUDA/Triton packages through PyPI's default `torch` wheel; 10 declare a proprietary NVIDIA license on PyPI. LunarLab never needs them (CPU by default) and the CI lock is CPU-only, but the README's Linux instructions used `requirements.lock`. MLOSS: "freedom of the code (lack of dependence on proprietary software)". | `grep -E '^(nvidia\|cuda\|triton)' requirements.lock`; THIRD_PARTY_NOTICES.md |
| C1 | P2 | **Generalisability is not demonstrated.** The reward-accounting identity, original-versus-training separation, configuration hashing, seed handling, provenance and statistics are task-independent in design, but not exposed through a documented adapter; `EvalProtocol` deliberately accepts only `LunarLander-v3`; outcome classification, hover detection, action labels and the episode accumulator are LunarLander-specific. | `lunarlab/config.py` (`problems()`), `lunarlab/rewards/accounting.py`, `lunarlab/outcomes.py` |
| C2 | P2 | **No property-based tests** of the mathematical invariants (shaping telescopes to a potential difference; accounting identity; statistics bounds). | — |
| C3 | P2 | **No supplied artifact for independent reproduction.** `runs/` and `data/` are local (git-ignored); the repository holds derived results (`docs/results/`, `demo/api/`) but no checkpoint a third party could re-evaluate. | `.gitignore` |
| C4 | P2 | **Paper figures:** the existing figures (`docs/results/*.png`) are raster only and not linked to source artifact digests by a manifest. | `docs/results/` |
| D1 | P3 | Docstring gaps outside the research API (FastAPI route handlers, CLI command functions). | — |

## Scientific checks performed at this revision (no problem found)

- **Study timeline.** All 20 reward-shaping runs (seeds 0–4) and all 12 DQN runs were created before any final-test
  result existed (created 16:31 and 16:43 UTC on 2026-10-15; first test 17:58 UTC). No seeds were added after
  results were seen.
- **Preference data and test seeds.** The learned-reward study was created at 17:59 UTC, after the first
  reward-shaping test results, but its preference dataset uses episode seeds 30,000–48,019 (380 episodes), disjoint
  from the validation (10,000–10,009) and test (20,000–20,099) seeds. Verified from
  `data/preferences/ds-20261015-235812-rlhf-5029/segments.npz`.
- **Freeze integrity.** In all 43 frozen runs every training segment ended before the freeze, and the tested
  checkpoints are byte-identical to their recorded digests (re-checked from `metadata.json` and the files).
- **Statistical unit.** Group intervals (IQM, mean, probability of improvement) bootstrap over training runs
  (policies), not episodes; group pad-landing rates are reported without pooled episode intervals.
- **Previous reliability audit.** The corrections in [../AUDIT_FIXES.md](../AUDIT_FIXES.md) (DQN continuation,
  immutable final-test checkpoints, outcome classifier v2, protocol validation, provenance) are covered by tests
  that pass at this revision.

## Strengths to preserve

The transition-level identity `training = w·original + Σ terms` is checked on every step; evaluation always uses
the unmodified reward; validation and test seeds are disjoint and validated; final tests use immutable,
digest-checked checkpoints; DQN runs resume with their replay buffer; runs record configuration hashes, seeds,
versions and source revisions; 270 tests and 15 browser flows run in CI on Linux and Windows.

## Not solvable by code

Evidence of an active user community; the author list, affiliations and consent; the cover letter's
action-editor and reviewer suggestions, conflicts of interest and funding statement; building the manuscript PDF
(no LaTeX engine on this machine); redistributing the JMLR style file (its repository declares no license).
