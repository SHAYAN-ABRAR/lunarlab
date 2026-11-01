# CI of the validator revision `954607b`

Run [41345065489](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/41345065489), pushed on 1 November
2026, concluded **success** in all six jobs. The logs are the job logs as GitHub served them, with line endings
normalized to LF.

| Job | Result | Log |
|---|---|---|
| Python, Linux: lint and tests | 686 passed, 4 Windows-only skips; combined statement and branch coverage 86% (10,155 statements, 1,158 missed; 2,596 branches) | `python-lint-tests.log` |
| Windows, Python 3.12 | 293 targeted tests passed; reproducibility smoke test and artifact re-evaluation | `windows-py3.12.log` |
| Windows, Python 3.13 | 293 targeted tests passed | `windows-py3.13.log` |
| Source archive | Built twice byte for byte; installed fresh; 194 release tests passed | `source-archive.log` |
| Frontend | Typecheck, lint, build | `frontend.log` |
| Browser end-to-end | 15 flows passed | `browser-e2e.log` |

The Linux run includes the new `tests/test_followup_comparison.py` and `tests/test_validator_failures.py`. It is
CI evidence for the follow-up set's tests and the validator's failure handling. It is **not** a run of the
full validator on a package: the fixture policies and checkpoints are not in Git.

The same push also ran two other workflows, both successful:

- the manuscript build, run [41345065455](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/41345065455);
- the Linux learned-reward replay, run [41345065461](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/41345065461).
