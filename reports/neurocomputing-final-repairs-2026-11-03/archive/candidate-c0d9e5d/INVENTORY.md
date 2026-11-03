# Inventory

`inventory.json` lists every file of this candidate with its size, SHA-256 and the part it belongs to,
except itself and `SHA256SUMS`, which lists every other file. The counts below also leave out this file.

| Part | Files | MB | Contents |
|---|---:|---:|---|
| `source/` | 2,523 | 81.2 | The repository at the archive revision: code, tests, documentation, manuscript source, study records, protocols, comparison programs and results, figure scripts and plotted values |
| `software/` | 6 | 26.6 | Deterministic source archives (pip-installable) |
| `outside-git/` | 14 | 2.0 | Comparison-fixture policies, at their repository paths |
| `cartpole-study-output/` | 145 | 11.4 | CartPole frozen checkpoints, exported artifacts, inventory of undistributed checkpoints |
| `lunarlander-study/` | 2 | 25.5 | Historical 38-policy LunarLander bundle and its repair-time source archive |
| `(top level)` | 3 | 0.0 | This candidate's own documents |
| **Total** | **2,693** | **146.8** | |

## Scientific dependencies and the records that name them

| Record (under `source/`) | What it names, by SHA-256 |
|---|---|
| `reports/neurocomputing-2026-10-27/cartpole-study/records/*/study.json`, `reports/neurocomputing-2026-10-27/cartpole-study/results/results.json`, `pilot-results/results.json` | The 72 CartPole run records and the analysis inputs |
| `reports/neurocomputing-2026-10-27/cartpole-study/records/frozen-checkpoints.sha256` | The 36 frozen checkpoints in `cartpole-study-output/` |
| `reports/neurocomputing-2026-10-27/cartpole-study/records/*/artifacts/*/manifest.json` | The files of the 18 exported artifacts |
| `reports/neurocomputing-2026-10-27/cartpole-study/records/*/runs/*/run.json` | Every scheduled checkpoint; the 156 not distributed are listed in `cartpole-study-output/INTERMEDIATE_CHECKPOINTS.json` |
| `reports/neurocomputing-2026-10-27/workflow-comparison/protocol/HASHES.sha256` | The comparison protocol, the 14 fixtures (policies in `outside-git/`), the three programs and the runner (79 entries) |
| `reports/neurocomputing-final-validation-2026-11-01/comparison-v2/HASHES-v2.sha256` | The follow-up programs, runner and assessment |
| `paper/neurocomputing/figures/MANIFEST.json` | The figure inputs |
| `examples/learned-reward-artifacts/SHA256SUMS` | The six learned-reward packages and their reward models |
| `reports/neurocomputing-final-validation-2026-11-01/archive/historical-bundle.sha256` | `lunarlander-study/`: the bundle and its source archive |
| `reports/jmlr/learned-reward-repair-2026-10-24/study-artifacts/SHA256SUMS` | The 333 listed members of the bundle (its `DEPENDENCIES.md`, `INVENTORY.md` and `inventory.json` are committed beside it) |
