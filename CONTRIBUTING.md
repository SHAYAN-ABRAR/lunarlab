# Contributing to LunarLab

Thank you for considering a contribution. Bug reports, reproducibility reports (including "it matched exactly"),
documentation fixes, reward terms, diagnostics and task adapters are all welcome. By contributing you agree that
your contribution is released under the project's MIT License.

## Ways to contribute

- **Report a bug** or **propose a feature** with the issue forms.
- **Report a reproduction** of a documented result: the reproducibility form, or without a GitHub account
  [docs/jmlr/REPRODUCTION_REPORT_TEMPLATE.md](docs/jmlr/REPRODUCTION_REPORT_TEMPLATE.md).
- **Extend LunarLab**: reward terms, diagnostics and environment adapters are described in
  [docs/jmlr/EXTENDING_LUNARLAB.md](docs/jmlr/EXTENDING_LUNARLAB.md); the codebase in
  [docs/DEVELOPER.md](docs/DEVELOPER.md).

## Development setup

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1     # venv from requirements.lock, UI build, self-check
.venv\Scripts\python.exe -m lunarlab --version
```

Linux (CPU-only, the configuration CI uses):

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-ci.lock --torch-backend cpu
uv pip install --python .venv/bin/python --no-deps -e .
```

The lock files include the development tools (pytest, pytest-cov, hypothesis, ruff). After changing
`requirements.in`, regenerate both locks with the commands at the top of that file and check that no unrelated
pin moved.

## Checks to run before a pull request

```powershell
.venv\Scripts\python.exe -m pytest -q                              # all tests (about 5 minutes)
.venv\Scripts\python.exe -m pytest -q -m "not slow"               # quick subset while developing
.venv\Scripts\python.exe -m pytest --cov                           # with statement and branch coverage
.venv\Scripts\python.exe -m ruff check lunarlab tests tools examples
.venv\Scripts\python.exe -m ruff format --check lunarlab tests tools examples
.venv\Scripts\python.exe tools\spdx_headers.py                     # every source file carries the license header
.venv\Scripts\python.exe tools\gen_api_docs.py --check             # the API reference matches the code
cd frontend; npm ci; npm run typecheck; npm run lint; npm run build; npx playwright test
```

CI runs the Python tests on Linux and the Windows-specific tests and scripts on Windows; a pull request must pass
both.

## Conventions

- **Tests for every behaviour change.** Tests run in a temporary `LUNARLAB_HOME` (`tests/conftest.py`); never point
  a test at real experiment data.
- **Experiment evidence is never modified.** Code must not rewrite stored runs, evaluations, checkpoints or
  recordings. Derived results go to new files that record the digests of their sources.
- **Reward terms are pure functions** of one transition, shared by training, evaluation and re-scoring; the
  identity `training = original_weight × original + Σ terms` must keep holding.
- **Configuration hashes of existing runs must not change.** `tests/test_protocol.py` pins published hashes; a new
  configuration field must be excluded from the hash when it has its default value.
- **Documented commands must run.** `tests/test_docs.py` parses every command in the documentation, and
  `tests/test_tutorial.py` executes the tutorial.
- **License headers.** New source files start with the two SPDX lines (`python tools/spdx_headers.py --fix`).
- **Windows and Linux.** Use `pathlib`, avoid shell-specific behaviour, and keep PowerShell 5.1 and 7 compatible.
- **No mandatory network service, account or proprietary dependency** in the core workflow.

## Review

A maintainer reviews every pull request. Expect questions about tests, provenance and backwards compatibility
before style. Changes that would alter a published result, a configuration hash or a stored format are discussed
in an issue first.

## Releases (maintainers)

1. Change the version in `lunarlab/__init__.py`, `CITATION.cff` and `frontend/package.json` (a test checks they
   agree), and update `README.md`.
2. Regenerate `THIRD_PARTY_NOTICES.md` and `docs/api/`, run all checks, commit, then tag.
3. `python tools/build_source_archive.py --rev <tag> --verify` builds the deterministic source archive, installs it
   into a fresh environment and runs its release tests; publish the archive and `SHA256SUMS` with the release.

## Conduct

Be respectful and constructive. Harassment or personal attacks are not tolerated; maintainers may remove such
contributions.
