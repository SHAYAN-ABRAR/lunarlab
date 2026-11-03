# The DQN policy that disagrees on Linux: reproduction and trace (3 November 2026)

**Policy:** `dqn-flawed-hover-bonus/20261015-224318-dqn-hover-bonus-s0-custom-aefc`, one of the 38 historical
LunarLander packages (`LunarLab_38_Policy_Study.zip`, SHA-256 `da53a1db…`; not in Git). Its historical
checkpoint, configuration and evaluation are unchanged: they were read from a new extraction of the bundle, and
every replay checked their digests first. Nothing was retrained, and no threshold, record or classification
was changed.

## What the Linux audit found (received, assistant-executed)

Summarized in [`linux-reports-summary.json`](linux-reports-summary.json), derived from the received reports in
`../received/linux-audit-2026-11-03/`, which are unchanged.

| Execution (Linux 6.18.57, Python 3.12.14, torch 2.14.1+cpu) | Mean original return (recorded 224.0699) | Paired difference [95% interval]; unadjusted p | Status |
|---|---|---|---|
| Default threads (run B; its parent validation was interrupted) | 230.2469 | 6.18 [1.30, 12.62]; 0.0089 | `aggregate-disagreement` (exit 1) |
| One thread, this policy alone | 230.2469 | 6.18 [1.30, 12.62]; 0.0089 | `aggregate-disagreement` |
| One thread, the all-38 diagnostic (its parent was interrupted) | 230.4473 | 6.38 [1.58, 12.77]; 0.0033 | `aggregate-disagreement` |

- **Integrity:** passed in all three.
- **Episodes:** all 100 differ numerically, though the median absolute return difference is only 0.03 to 0.04.
- **Outcome changes:** 8 of 100, the same eight in each execution: 6 pad landings gained and 2 lost (84% → 88%).
  They include seed 20068 (a recorded crash, −27.59, that became a pad landing, 200.09) and seeds 20011 and
  20033 (recorded timeouts, 106.85 and 104.08, that became pad landings, 232.76 and 220.27).
- **Executions:** the two at 230.2469 agree on all 100 episodes. The all-38 execution differs from them only
  on seed 20065, so the Linux replays are not fully repeatable between executions.
- **Gate:** the significance is that of the existing within-policy screen (Holm across that policy's metrics).
  A higher return is still a disagreement, and it stays blocking.

## Executed here, on the recording platform (Windows 11, Python 3.12.13, torch 2.14.1)

The environment is a fresh install of the locked dependencies (`environment.json`). It used the uv-managed
CPython 3.12.13 run directly, with `PYTHONPATH` set to the install and no user site-packages. A virtual
environment could not be used because Windows Application Control now blocks uv's launcher; that launcher was
not run or unblocked. The library is the `c9b9384` source archive, whose library code equals the current
revision's. Each command had its own new, empty `LUNARLAB_HOME`.

| Command | Result | Files |
|---|---|---|
| `python -m lunarlab reproduce-artifact --artifact ART --report reports/windows-reproduce-default-threads.json` (OMP/MKL threads unset) | `exact`: 100 of 100 episodes; mean 224.06994853107503; integrity passed; exit 0; 17 s | `reports/`, `logs/` |
| The same with `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1` | `exact`, 100 of 100 | `reports/windows-reproduce-one-thread.json` |
| `python -m lunarlab trace-artifact --artifact ART --seeds 20068,20011,20033 --out traces/windows-reference-2026-11-03.npz` | Traces recorded: 529 steps, return −27.5891; 1,000 steps, 106.8464; 1,000 steps, 104.0810 (the recorded crash and two timeouts) | `traces/` (`.npz` and its `.json`) |
| `python -m lunarlab trace-artifact --artifact ART --compare traces/windows-reference-2026-11-03.npz --report reports/windows-trace-self-compare-2026-11-03.json` | `IDENTICAL`, exit 0: re-flown on the recording machine, no output, action or observation difference | `reports/` |

**Why these three seeds:** they had the largest Linux return differences, and each changed outcome. They are
not a random sample, and they estimate nothing about how often divergence occurs.

## Pending: the Linux comparison

Not run: no Linux machine with the historical bundle is available here. GitHub's Linux CI cannot run it
either, because the bundle is not public. On Linux, from a fresh install of the candidate's locked CPU
dependencies (`requirements-ci.lock` with `--torch-backend cpu`) and a new, empty `LUNARLAB_HOME`:

```bash
python -m lunarlab trace-artifact \
    --artifact <bundle>/study-artifacts/dqn-flawed-hover-bonus/20261015-224318-dqn-hover-bonus-s0-custom-aefc \
    --compare traces/windows-reference-2026-11-03.npz \
    --report linux-trace-comparison-<date>.json
```

Exit status 0 means identical; 3 means differences were located (reported, not failed); 1 means the closed loop
differs although neither policy inference nor simulator dynamics does. The report separates three things:

- the first difference in the network's outputs, and any greedy-action flips, on the recorded observations
  (policy inference);
- the first open-loop observation difference under the recorded actions (simulator dynamics);
- the step where the closed loop parts, and the resulting returns (the aggregate outcome).

Read it with these limits:

- An early, tiny state difference that grows would fit a simulator-numerics mechanism, as in the nine
  historical trace comparisons. It would not prove that Box2D or a compiler causes every platform difference.
- No exact cross-platform fix is promised.
- The disagreement stays disclosed, and blocking under the existing gate, whatever the trace shows.
