# CartPole reward-design audit, 27 October 2026

This is a second, controlled use of the task-independent audit layer (`lunarlab.audit`). It is separate
from the historical LunarLander study and does not add to its 38 policies or 3,800 episodes.

| Path | What |
|---|---|
| `protocol/` | `PROTOCOL.md`, `protocol.json`, the pilot's `protocol-pilot.json` and the RL Zoo settings they use. `PROTOCOL.sha256` fixed them at 16:08:41 UTC, before any training |
| `records/pilot/` | The labelled pilot: seed 90, 20,480 transitions per design, its own validation and test seeds. It includes the hand-calculation check of the failure bonus on 20 recorded episodes |
| `records/main/` | The 15 main runs (`runs/<design>-s<seed>/`). Each holds `run.json` (seeds, budget, every checkpoint's validation episodes, selection, frozen digests, reward provenance), `test-selected.json` and `test-final.json` (all 100 test episodes), and `protocol.json`. Also here: `study.json`, `compute.jsonl` (the compute ledger), `run.log`, and every exported artifact's `manifest.json` |
| `records/frozen-checkpoints.sha256` | SHA-256 of every frozen checkpoint. The checkpoint files themselves are kept outside Git and are delivered in the review package |
| `analyze.py`, `results/`, `pilot-results/` | The prespecified analysis and its output (`results.json`, `RESULTS.md`) |

To reproduce from the source tree:

```sh
python examples/cartpole_study.py --protocol reports/neurocomputing-2026-10-27/cartpole-study/protocol/protocol.json --out OUT --workers 5
python reports/neurocomputing-2026-10-27/cartpole-study/analyze.py OUT OUT/analysis
python -m lunarlab audit-artifact reproduce --artifact OUT/artifacts/failure-bonus-s50
```

Compute on the recording machine (Windows 11, Intel i7-13620H, one PyTorch thread per process, 5
processes): about 7 minutes for the 15 main runs, and 35 seconds for the pilot. Training transitions:
1,501,440 for the main runs and 61,440 for the pilot.
