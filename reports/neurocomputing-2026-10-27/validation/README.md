# Local validation, 27 October 2026

The full Python test suite, run on the author's Windows machine in an isolated, empty data home:

```bash
H=$(mktemp -d); LUNARLAB_HOME="$H" .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --cov \
  --cov-report=json:reports/neurocomputing-2026-10-27/validation/coverage-windows.json \
  --junitxml=reports/neurocomputing-2026-10-27/validation/pytest-windows.xml
```

| Item | Value |
|---|---|
| Source | commit `21ceb66`, with documentation, figure and manuscript edits uncommitted (no change under `lunarlab/`, `tests/`, `examples/` or `tools/`) |
| Platform | Windows 11, Intel i7-13620H, Python 3.12.13, the locked dependencies of `requirements.lock` |
| Started | 2026-10-27 23:13:00 +06:00 |
| Result | 571 passed, 0 failed, 0 errors, 0 skipped, 664.8 s (exit status 0) |
| Coverage | 86.01% combined: 8,877 of 10,018 statements and 1,914 of 2,528 branches |

- `pytest-windows.log`: the console output.
- `pytest-windows.xml`: the JUnit report, with the machine's host name replaced by `redacted`.
- `coverage-windows.json`: the coverage report.

Public CI on Linux reports 567 passed and four skips for the same tests. The four are Windows-only tests, which
run here. The manuscript cites the public CI run, not this one.
