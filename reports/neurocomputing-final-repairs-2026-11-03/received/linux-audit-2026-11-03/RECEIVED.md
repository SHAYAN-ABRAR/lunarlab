# Received: the Linux audit of 2 to 3 November 2026 (a labelled subset)

**Assistant-executed, not an independent researcher's reproduction.** The audit was run by ChatGPT (OpenAI) in
its own Linux sandbox, from the prompt of 2 November 2026, and supplied by the author on 3 November 2026 as
`LunarLab_Linux_Validation_2026-11-03.zip`. It is review material for the author, not evidence of outside use.

| | |
|---|---|
| ZIP | 9,980,079 bytes; SHA-256 `b55ad8f816d3657805816aef27029089e0ef92fbba98be76d0cb9985275ad958` (as the brief gave it) |
| Checked on 3 November 2026 | size and SHA-256 equal; every CRC passed; 1,546 entries, `REPORT.md` first; its `SHA256SUMS` verifies 1,545 of 1,545 entries, with no file unlisted |
| Audited inputs | `LunarLab-archive-candidate-2026-11-01-a38d07f.zip` (SHA-256 `8a02752e…`) and `LunarLab-final-validation-review-2026-11-02-f9615d1.zip` (`c39733ab…`) |
| Platform | Linux 6.18.57, glibc 2.39, Python 3.12.14, CPU torch 2.14.1+cpu, NumPy 2.5.4, Box2D 2.3.10, Gymnasium 1.4.0, Stable-Baselines3 2.9.0 (`REPORT.md`) |

This folder holds 25 of its files, unchanged. Each one except `SHA256SUMS` has the digest that the audit's
own `SHA256SUMS` (copied here whole) records, so the subset can be checked against the original package. The rest
of the ZIP (the raw logs of every run, the generated figures, the inspected inputs and the page renders) is in
the review package of 3 November 2026, not in Git.

What the files are:

- `REPORT.md`, `REPAIR_NOTE_FOR_CLAUDE.txt`: the audit's report and its repair note, which the work of
  3 November followed (`../../README.md`).
- `run-a/validation.json`: the complete default-thread run (exit 0; two published replays).
- `run-c-one-thread/validation.json`: the complete one-thread run with the unmodified comparison (exit 1:
  36 failed pairs, each with `psutil.NoSuchProcess`).
- `run-b/…aefc.json`, `.log`: the first, default-thread replay of the DQN policy that disagrees. Its parent
  run was interrupted and has no final report.
- `diagnostic-full-final/…aefc.json`: the same policy in the one-thread all-38 diagnostic, whose parent run was
  also interrupted before its final report.
- `diagnostics/single-thread-dqn/`: a separate one-thread replay of that policy.
- `diagnostics/*-context.json`, `thread-environment-probe.log`: the runs' thread settings and interruption
  context.
- `analysis-final/`: the audit's derived tables (replay statuses, group observations, telemetry, blocking
  rows).
- `evidence/`: the audit's own integrity checks of its inputs, and its note on which earlier outputs it lost.

| File | Bytes | SHA-256 |
|---|---:|---|
| `analysis-final/blocking-comparison-rows.json` | 70,296 | `a68c772c09395c379d8904434becd5515ebbec4de6efd75fdb77fc3b76e7805b` |
| `analysis-final/cartpole-field-comparison.json` | 20,153 | `6e6b8efb4d9cf33806467c5039e5b76368f9b9fbbcddfb082d86b7335bc5a885` |
| `analysis-final/memory-telemetry.csv` | 51,748 | `63dff8478ee8f973997d6f0386e5ecde439cdc36c0d014bc60d27ef8126ebafe` |
| `analysis-final/replay-group-observations.json` | 6,982 | `1103e30a1559b39b217a9c582dcdb1d84d117aef515b6c2478983d740bb88b16` |
| `analysis-final/replay-summary.csv` | 50,028 | `2b670eda29436185a141f3bc59bea1828425efd729f6c371a34b4b8792068541` |
| `analysis-final/replay-summary.json` | 121,897 | `04115544d0ee6c32f4e707d9f2653c30321c62a971db0d9b2cece82bddc4a5ef` |
| `analysis-final/run-summary.json` | 127,827 | `e395e3d1fa2ca4c5a5d16dc6a6a4f94e4cdc315ede40dfae78ba1b826932e836` |
| `diagnostic-full-final/reports/lunarlander-20261015-224318-dqn-hover-bonus-s0-custom-aefc.json` | 88,954 | `00a1f67e882fd9ee0b05b131cb2ee6076c83222a7f600edd47786dbc9e6432f7` |
| `diagnostics/c-one-thread-context.json` | 1,049 | `ffc1c87ff8ad020b1d01704d6f41ea6e099ff91054a2d414518ce25f870cdca4` |
| `diagnostics/full-final-context.json` | 889 | `79699afc65d866322165a7152b99fb872bddfeaae18a252b07c1a96f103a68b4` |
| `diagnostics/single-thread-all-context.json` | 908 | `b0aaa55d4dc7073e6a65189bea80f0cc25cfaf7733c2993d13e4e89eedecd38c` |
| `diagnostics/single-thread-dqn/console.txt` | 1,731 | `7d2f43036e7af0a4905bca1eb50f25d0f2cc140f9a0a6f3d6f91061cb184c3b7` |
| `diagnostics/single-thread-dqn/execution.json` | 1,086 | `65f5def67c8a853bbc728d659b320710730b2e2befb35862a2d66e0c7fdeb303` |
| `diagnostics/single-thread-dqn/replay.json` | 88,952 | `27fc11a45fc89a7f1b2f2b3c2a73d552855cd7cb27bd5ba24cf2a228bcb2f5d1` |
| `diagnostics/thread-environment-probe.log` | 158 | `8345a104b2083d039485be581e7d1d063e68e8c1cf628713afdfda9643fa4be8` |
| `evidence/integrity_final.json` | 1,183 | `5412c5c24aca1797b1d55258dce27a9c134e8ca86516fe79b9fe4b32cbdbf85c` |
| `evidence/integrity_initial.json` | 1,223 | `f2bd3da28ee12f6f8743319f2cdcebd606272cb750624337d8acc2c8c99d2419` |
| `evidence/session-continuity.json` | 991 | `d237f487d0c267ac63060b35dd541e07cc75cffa4b6cc80de28c8ab7bb9832df` |
| `REPAIR_NOTE_FOR_CLAUDE.txt` | 8,499 | `67edce1af1344381094e72b4dff1c751f0b0e1cd0727a254f85147e0b803a378` |
| `REPORT.md` | 45,407 | `cbfb3802281493003de001a2fbb531ad1e8ba7bc12562571e1880fd908fbda24` |
| `run-a/validation.json` | 19,348 | `16e192bcb192996ce1dddc068ed622235d6673fefac92d5bd263b06bbef57c62` |
| `run-b/logs/lunarlander-20261015-224318-dqn-hover-bonus-s0-custom-aefc.log` | 2,228 | `64dab5cb43308a55c73d2f4788c1d0c168a5b0269450f9ab3b8d2b2f4c408cb1` |
| `run-b/reports/lunarlander-20261015-224318-dqn-hover-bonus-s0-custom-aefc.json` | 88,954 | `d917eb6e38f9b4df6bee8aa99596f61e6de485fe854cb8962dffef2d517ac6db` |
| `run-c-one-thread/validation.json` | 96,631 | `cb2cf06766e403f0a88c5ec4764e78f579a1bf70ede80c967bc4c0b9c24f2a3e` |
| `SHA256SUMS` | 197,622 | `b2293d3ce60f955adf0b78f6ac4029a57b28318379a9ff453de859efd112915c` |
