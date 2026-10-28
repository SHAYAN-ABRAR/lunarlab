# Audit-workflow comparison, 27 October 2026

| Path | What |
|---|---|
| `protocol/` | `PROTOCOL.md`, `specification.json` and `fault_inventory.json`. `HASHES.sha256` fixed these, the fixtures and every script before any workflow ran on the main fixtures |
| `workflows/` | W1 (conventional SB3), W2 (independent SB3 reference implementation) and W3 (LunarLab) |
| `build_fixtures.py`, `fixtures/` | The 14 neutral cases built from the CartPole study's frozen `upright-potential-s50` policy, with `oracle.json`. The `policy.zip` files are kept outside Git; their SHA-256 is in `protocol/HASHES.sha256` |
| `run_comparison.py`, `results/` | `MATRIX.md`, `summary.json`, and the raw stdout, stderr and exit status of every pair under `raw/<workflow>/<case>/` |
| `measure_cost.py`, `results/cost/` | The randomized execution-cost runs on the clean control |
| `count_code.py`, `results/code_size.json` | Counted custom lines of each workflow |
| `FINDINGS.md` | Results, interpretation and limits |

To reproduce: rebuild the fixtures from the study run (`python build_fixtures.py RUN_DIR fixtures`), check
them against `protocol/HASHES.sha256`, then run `run_comparison.py fixtures results` and
`measure_cost.py fixtures/C0-clean results/cost`.
