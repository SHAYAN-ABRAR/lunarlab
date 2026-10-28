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

**What this run did not cover:** the suite collects the commands documented in Markdown files when it starts,
at about 17:13:00 UTC. The new sections 5 to 9 of `docs/REPRODUCING.md` were written at 17:13:44, so this run
did not test them.

**First CI test of those sections:** CI run 40691885283 on `b92879e` tested them first and failed in every job
that runs the documentation tests. One new command was split over two lines with a trailing backslash, which
the documentation test cannot parse (`tests/test_docs.py::test_documented_command_parses[docs/REPRODUCING.md:73]`).

**Fix:** the command is now on one line, and the documentation and metadata tests pass locally (126 passed).
