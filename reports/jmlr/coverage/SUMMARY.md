# Code coverage

Measured with coverage.py (statement and branch coverage, worker subprocesses included) over the whole `lunarlab` package; nothing is omitted except `if TYPE_CHECKING:` blocks and `__main__` guards. Reproduce with the commands in `tools/coverage_summary.py`. The HTML report is regenerated locally (`reports/jmlr/coverage/html/`, not stored in git).

| | Statements | Missed | Branches | Partial | Coverage (statements + branches) |
|---|---:|---:|---:|---:|---:|
| **Now** | 8,908 | 1,269 | 2,206 | 339 | **82.9 %** |
| Before this work (`baseline/`) | 8,060 | 1,750 | 2,062 | 304 | 75.2 % |

## Scientific core

| Module | Now | Before |
|---|---:|---:|
| `lunarlab/rewards/terms.py` | 94.7 % | 94.7 % |
| `lunarlab/rewards/accounting.py` | 100.0 % | 100.0 % |
| `lunarlab/rewards/wrapper.py` | 97.7 % | 97.7 % |
| `lunarlab/rewards/config.py` | 91.2 % | 91.2 % |
| `lunarlab/audit/core.py` | 97.7 % | new |
| `lunarlab/audit/adapters.py` | 91.7 % | new |
| `lunarlab/audit/evaluate.py` | 96.6 % | new |
| `lunarlab/training.py` | 91.1 % | 91.1 % |
| `lunarlab/continuation.py` | 88.4 % | 79.2 % |
| `lunarlab/freeze.py` | 84.1 % | 84.1 % |
| `lunarlab/outcomes.py` | 93.4 % | 92.9 % |
| `lunarlab/hover.py` | 100.0 % | 100.0 % |
| `lunarlab/config.py` | 96.4 % | 96.4 % |
| `lunarlab/evaluation.py` | 92.0 % | 90.9 % |
| `lunarlab/stats.py` | 100.0 % | 100.0 % |
| `lunarlab/rl_stats.py` | 96.9 % | 96.9 % |
| `lunarlab/results.py` | 88.0 % | 64.4 % |
| `lunarlab/reproduce.py` | 97.7 % | new |
| `lunarlab/runs.py` | 80.1 % | 80.1 % |
| `lunarlab/storage.py` | 90.7 % | 90.7 % |
| `lunarlab/lineage.py` | 73.3 % | 73.3 % |
| `lunarlab/demo.py` | 86.3 % | 86.3 % |
| `lunarlab/sysinfo.py` | 66.7 % | 63.4 % |

## All other modules

| Module | Now | Before |
|---|---:|---:|
| `lunarlab/__init__.py` | 100.0 % | 100.0 % |
| `lunarlab/__main__.py` | 100.0 % | 100.0 % |
| `lunarlab/audit/__init__.py` | 100.0 % | new |
| `lunarlab/benchmark.py` | 95.3 % | 0.0 % |
| `lunarlab/cli.py` | 58.1 % | 34.0 % |
| `lunarlab/compare.py` | 87.2 % | 85.9 % |
| `lunarlab/db.py` | 95.6 % | 95.6 % |
| `lunarlab/doctor.py` | 80.7 % | 0.0 % |
| `lunarlab/env.py` | 93.4 % | 93.4 % |
| `lunarlab/experiments.py` | 91.0 % | 89.7 % |
| `lunarlab/jobs.py` | 65.4 % | 65.4 % |
| `lunarlab/locks.py` | 80.3 % | 80.3 % |
| `lunarlab/overhead.py` | 93.1 % | new |
| `lunarlab/parallel.py` | 15.9 % | 15.9 % |
| `lunarlab/physics.py` | 100.0 % | 100.0 % |
| `lunarlab/play.py` | 84.8 % | 84.8 % |
| `lunarlab/policies.py` | 97.5 % | 97.5 % |
| `lunarlab/preferences/__init__.py` | 100.0 % | 100.0 % |
| `lunarlab/preferences/active.py` | 75.9 % | 75.9 % |
| `lunarlab/preferences/data.py` | 92.9 % | 92.9 % |
| `lunarlab/preferences/model.py` | 94.0 % | 94.0 % |
| `lunarlab/preferences/train.py` | 92.3 % | 92.3 % |
| `lunarlab/procs.py` | 85.9 % | 85.9 % |
| `lunarlab/reclassify.py` | 98.1 % | 0.0 % |
| `lunarlab/recording.py` | 87.3 % | 87.3 % |
| `lunarlab/report.py` | 89.9 % | 89.9 % |
| `lunarlab/rescoring.py` | 91.2 % | 91.2 % |
| `lunarlab/rewards/__init__.py` | 100.0 % | 100.0 % |
| `lunarlab/rewards/analysis.py` | 84.4 % | 84.4 % |
| `lunarlab/robustness.py` | 100.0 % | 100.0 % |
| `lunarlab/server/__init__.py` | 100.0 % | 100.0 % |
| `lunarlab/server/api.py` | 69.0 % | 69.0 % |
| `lunarlab/server/main.py` | 44.9 % | 44.9 % |
| `lunarlab/server/schemas.py` | 100.0 % | 100.0 % |
| `lunarlab/tuning.py` | 89.6 % | 89.6 % |

## What remains below 70 %, and why

- `lunarlab/cli.py` (58.1 %): command handlers; the tutorial, documentation and CLI tests run the common commands end to end, while orchestration commands (tuning, RLHF studies, showcase recording, demo export) are tested through the functions they call.
- `lunarlab/jobs.py` (65.4 %): the job supervisor's process management and crash recovery across operating-system processes.
- `lunarlab/parallel.py` (15.9 %): running several experiment runs in parallel worker processes.
- `lunarlab/server/api.py` (69.0 %): HTTP endpoints of the web interface; the 15 browser flows exercise them, but in a separate server process that this measurement does not include.
- `lunarlab/server/main.py` (44.9 %): server start-up, static file serving and shutdown (same note as the API).
- `lunarlab/sysinfo.py` (66.7 %): platform-specific branches (for example Linux CPU detection) that do not run on Windows.

Coverage measures which lines ran, not whether their results are right; the scientific core is additionally checked by exact-value, property-based and end-to-end tests.
