# Reproducibility

How another researcher can verify what LunarLab does, which outputs reproduce exactly, and what is not
guaranteed. Results come from three sources, each named where it is used:

- **development machine** (Windows 11, i7-13620H, Python 3.12.13; described in [INITIAL_AUDIT.md](INITIAL_AUDIT.md)),
  2026-10-17 and 2026-10-18;
- **GitHub Actions run [39069730331](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/39069730331)** on revision
  `2c41b42` (2026-10-18): `ubuntu-latest` with Python 3.12.3, and `windows-latest` with Python 3.12 and 3.13;
- **controlled experiments** on the development machine (2026-10-18, branch `research/jmlr-mloss-corrections`),
  stored in `reports/jmlr/reproducibility/`.

## Four separate properties

A reproduction can succeed in one sense and fail in another, so `reproduce-artifact` reports four properties
separately and never calls them all "exact reproducibility":

| Property | Question | How it is checked | When it fails |
|---|---|---|---|
| **Artifact integrity** | Are these the published files, used as published? | SHA-256 of checkpoint, configuration and recorded evaluation; configuration hash; the evaluation used this checkpoint, the configuration's test seeds, protocol and reward; the recorded episodes are exactly the recorded seeds; the evaluated network holds exactly the checkpoint's weights | always blocking (status `integrity-failure`, exit 1) |
| **Within-platform reproducibility** | Does the recording platform give the same numbers? | every episode bit-identical, when the operating system and the numerical libraries (torch, NumPy, Box2D, Gymnasium, Stable-Baselines3) match the artifact's record | blocking (`unexpected-difference`, exit 1) |
| **Cross-platform numerical reproducibility** | How close is another platform? | per episode: return difference (absolute, relative where the recorded return is at least 1 in magnitude), length, termination and outcome agreement, final-observation difference; mean, median, 90th percentile and maximum | reported, not failed (`numerical-difference`, exit 3): bit-identical results across platforms are not a supported guarantee |
| **Scientific conclusion stability** | Would the published conclusions change? | paired comparison over the same seeds: sign-flip permutation test of the mean original return, exact McNemar tests of the pad-landing, timeout, crash and out-of-bounds rates, Holm correction (family-wise α = 0.05) | blocking (`aggregate-disagreement`, exit 1) |

Exit status 0 means every episode was bit-identical (`exact`) or, with `--tolerance`, within the requested
tolerance (`within-tolerance`); 2 is a usage error (for example a folder without `artifact.json`).

**Why this conclusion criterion.** A reproduction re-flies the recorded seeds, so episodes are paired. Numerical
noise moves episodes in both directions and leaves the paired differences centred on zero; a regression (a broken
environment, wrong weights, a changed protocol) moves them one way. The tests flag the second, not the first.
They are not an equivalence test, and they are not tuned to the supplied artifacts: an earlier criterion
("each reproduced aggregate inside the recorded 95 % interval") was replaced because a rate of 1/100 has a Wilson
interval that excludes 0, so a single episode changing category was flagged
(`ulp` experiment below, DQN out-of-bounds 1 → 0). Regression tests: `tests/test_reproduction_report.py`.

## Summary of verified results

| Check | Where | Result |
|---|---|---|
| End-to-end pipeline, PPO (`reproduce-smoke --training-determinism`) | development machine | 15/15 checks, 6.7 s (`reports/jmlr/artifacts/reproduce-smoke-ppo-windows.json`) |
| Same, DQN with replay buffer and exploration schedule | development machine | 15/15 (`…/reproduce-smoke-dqn-windows.json`) |
| `reproduce-smoke --training-determinism` | CI: Linux, Windows 3.12, Windows 3.13 | 15/15 on each |
| Training determinism across processes | development machine | identical final-weights, frozen-weights and final-test episode digests (checkpoint *file* digests differ: zip entries carry save times) |
| Published final tests (`reproduce-artifact`), artifact integrity | development machine; CI Linux, Windows 3.12, Windows 3.13 | file digests, configuration hash and "the recorded evaluation used this checkpoint" passed everywhere (CI ran report schema 1; the seed, protocol, reward and loaded-weights checks added since have run on the development machine) |
| Same, episodes bit-identical | development machine; CI Windows 3.12 and 3.13 | **300 / 300** |
| Same, episodes bit-identical | CI Linux | **0 / 300** (details below) |

## Cross-platform results (Linux, run 39069730331)

| Artifact | Bit-identical | Mean original return, recorded → Linux | Largest return difference | Pad landing, recorded → Linux |
|---|---:|---:|---:|---:|
| `ppo-baseline-s0` | 0 / 100 | 265.8558 → 265.8615 | 0.277 | 96 % → 96 % |
| `ppo-hover-bonus-s0` | 0 / 100 | −21.2456 → −20.7658 | 126 | 0 % → 0 % |
| `dqn-baseline-s0` | 0 / 100 | 155.3644 → 156.8764 | 192 | 29 % → 29 % |

The reports of that run (schema 1) listed only the first 20 differing episodes per artifact. In those samples
the episode length agreed in 19/20 (PPO baseline), 20/20 (hover bonus) and 16/20 (DQN) episodes, the
environment outcome and the pad-landing classification agreed in all 60, and every difference was in the return. Full per-episode agreement statistics and the paired conclusion tests come from the
reproduction report of the next CI run (schema 2), which records every episode; they have not been measured yet.

What the published results depend on is unchanged on Linux: the mean returns moved by 0.006, 0.48 and 1.51,
inside the recorded 95 % intervals ([256.7, 273.6], [−25.1, −17.4] and [128.4, 182.2]), and the
pad-landing rates, including the hover bonus's 0 % that demonstrates reward exploitation, were identical.

## What causes the Windows/Linux differences

The per-step trajectories of the original evaluations were not recorded, so the first diverging step cannot be
read from the published records. Three controlled experiments on the development machine narrow the cause down
(`python tools/reproducibility_experiments.py libm|ulp`, and `reproduce-artifact` / `trace-artifact` with other
MKL settings; reports in `reports/jmlr/reproducibility/`):

| Experiment | Result | Conclusion |
|---|---|---|
| Replace `math.sin`/`math.cos` in Gymnasium's LunarLander step by correctly rounded values (mpmath, 120 bits) — the only platform-dependent library calls in that Python code; the native values differed from correctly rounded ones on 14–53 of 11,216–40,040 calls | all 60 episodes (20 per artifact) unchanged bit for bit; none matches the Linux values | the C library's double-precision trigonometry is **not** the cause: Box2D receives these values as float32, which absorbs the last-bit differences |
| Run the policy network with other BLAS kernels (`MKL_ENABLE_INSTRUCTIONS=SSE4_2`, `MKL_CBWR=COMPATIBLE`) | network outputs differ from step 0–1 (up to 1.9e-6 for PPO logits, 3.1e-5 for DQN Q-values) but no greedy action changes: 300/300 episodes bit-identical | rounding differences in **policy inference** of this size do not explain the Linux results |
| Perturb the simulator once, by one float32 unit in the last place of the lander's horizontal velocity after reset | 93–94 % of episodes change (6–7 bit-identical); median return difference 0.0015 (PPO baseline), 2.4 (hover bonus), 0.0005 (DQN); largest 0.18, 15 and 134; outcome agreement 100 %, 100 %, 99 %; no significant aggregate change (all p ≥ 0.33) | a minimal **simulator** difference is amplified by the closed loop into the pattern seen on Linux |

The most plausible cause is therefore floating-point behaviour inside the simulator's compiled code (Box2D built
by different compilers and C runtimes on Windows and Linux), amplified by the closed loop; on Linux every
episode differs, consistent with a difference that recurs at every step rather than once. **This is not yet
confirmed on Linux.** The direct test runs in CI from now on: `trace-artifact --compare` re-flies three traced
episodes per artifact against Windows reference traces (`reports/jmlr/reproducibility/traces/`) and separates
the two sources — the network evaluated on the *reference* observations (inference) and the environment stepped
open-loop with the *reference* actions (dynamics) — and reports the first step at which each differs.

## Continuous integration

Since this correction, no reproduction outcome is discarded. Each `reproduce-artifact` and `trace-artifact` exit
code is recorded; `tools/reproduction_summary.py` writes a machine-readable summary
(`reproduction-summary-<platform>.json`), a table in the job summary (status, exit code, integrity, bit-identical
episodes, outcome agreement, return differences, aggregates, where trajectories part), and fails the job on any
blocking status, a missing report, or an exit code that contradicts its report. On Windows the artifacts are on
their recording platform, so a difference fails CI; on Linux a numerical difference is listed as tolerated with
the reason. The previous Linux step (`… || true`) hid exit codes; `tests/test_reproduction_report.py` now fails
if any reproduction command in the workflow is masked that way.

## What is recorded at each step

| Step | Recorded | Where | Verified by |
|---|---|---|---|
| Installation | exact dependency pins; package version and source revision | `requirements.lock`, `requirements-ci.lock`; `python -m lunarlab --version` / `version --json` | `tests/test_project_metadata.py` |
| Configuration | full run configuration; content hashes of the configuration, the reward and the evaluation protocol | `runs/<id>/config.yaml`, `metadata.json` (`config_hash`, `reward_hash`, `eval_protocol_hash`) | smoke check "configuration identity survives a reload"; historical hashes pinned in `tests/test_protocol.py` |
| Environment | environment id and keyword arguments, Gymnasium version, robustness overrides, effective physics read back from the instantiated environment | `metadata.json → environment`; every evaluation's `environment` | evaluations refuse an environment that differs from the protocol's declaration |
| Training | worker seeds (disjoint from evaluation seeds), transitions in environment interactions, discarded interactions at a stop, source revision per segment, versions and hardware | `metadata.json → segments`, `system` | smoke checks "training budget recorded in environment transitions", "worker seeds and source revision recorded" |
| Rewards | original reward, every term and the training reward, per transition (identity checked) and per episode | `info["lunarlab"]`, `episodes.csv` (rounded to 5 decimals), evaluation episodes (full precision) | smoke check "identity holds" (within the CSV rounding bound); `tests/test_rewards.py`, `tests/test_properties.py` |
| Checkpoints | name, kind, transitions, size, SHA-256, configuration hash; DQN continuation bundles | `checkpoints/manifest.json` | smoke check "every checkpoint matches its recorded size, SHA-256 and configuration hash" |
| Validation and selection | validation-seed results; the selected checkpoint and the statistic that selected it | `evaluations/validation-*.json`, manifest `best_validation` | smoke check "validation evaluation uses the original reward" |
| Frozen final test | immutable read-only copy of the selected checkpoint; its digest; every attempt | `checkpoints/frozen/<sha256>.zip`, `metadata.json → frozen_for_test`, `test_attempts` | smoke checks "final test evaluated the frozen copy …", "frozen checkpoint is read-only" |
| Evaluation | per-episode original return, would-be training return, terms, outcome (classifier version), seeds, protocol hash, checkpoint digest, code revision | `evaluations/test-*.json` | smoke check "a repeated final-test evaluation matches the saved one exactly" |
| Continuation vs warm restart | resume = same run (see the contract below); warm restart = new run with lineage | `segments`, `lineage`, `config.warm_start` | `tests/test_dqn_continuation.py`, `tests/test_freeze.py` |
| Export | results with source digests; demo snapshots with full provenance (release or draft) | `docs/results/results.json`, `demo/api/demo.json` | `tests/test_provenance.py` |
| Replay | recorded steps with the policy's outputs, the checkpoint digest, the protocol hash | `trajectories/*.json` | `tests/test_video_rescoring.py` |

Missing evidence is never filled in: an evaluation made before a field existed shows it as absent (for example,
`evaluation_code` for evaluations older than the code-revision record), and legacy outcome-classifier results are
labelled as such, with derived values marked derived.

## Interrupted training: what continuation restores

| Level | Meaning | LunarLab |
|---|---|---|
| 1. Safe checkpoint-based continuation | training resumes from a verified checkpoint written at a safe boundary | **yes**: the boundary is the start of a rollout; PPO discards and records the partial rollout, DQN stops after a completed, trained rollout (one step per environment discarded and recorded); checkpoints are digest-verified bundles |
| 2. Algorithm-state restoration | the learner continues the same state | **yes**: policy and value networks, optimizer state, transition and update counters; for DQN also the replay buffer (with position and wrap state), the target network and its update phase (`_n_calls`), exploration rate and schedule basis (`lunarlab/continuation.py`; `tests/test_dqn_continuation.py` checks the restored state against the stop checkpoint) |
| 3. Equivalent continuation at the boundary | the continued run is a valid continuation of the same training | **partly**: the learner's state equals the stopped one, but environments restart from new episodes (the next segment's recorded worker seeds), so the experience collected after the boundary differs from an uninterrupted run's |
| 4. Bit-identical continuation | interrupted + resumed = uninterrupted, bit for bit | **no**: random-number streams and environment states are not restored (`training.py` `PPO_CONTRACT`, `DQN_CONTRACT`, recorded with every resumable checkpoint) |

Of the stored runs, two were resumed: seed 1 of the potential-based shaping group in the published study (stopped
by a Windows file lock at 200,704 transitions and resumed from its last periodic checkpoint, disclosed in
`docs/RESULTS.md`) and the single 3 M-transition baseline run outside the study; none of the 12 published DQN
runs was resumed (`docs/AUDIT_FIXES.md`).

## Commands

### Windows (PowerShell) — executed on the development machine

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1        # virtual environment from requirements.lock
.venv\Scripts\python.exe -m lunarlab --version
.venv\Scripts\python.exe -m lunarlab doctor
.venv\Scripts\python.exe -m lunarlab reproduce-smoke --training-determinism --report smoke.json
.venv\Scripts\python.exe -m lunarlab reproduce-smoke --algo dqn --training-determinism
.venv\Scripts\python.exe -m lunarlab reproduce-artifact --artifact examples\artifacts\ppo-baseline-s0 --report baseline.json
.venv\Scripts\python.exe -m lunarlab reproduce-artifact --artifact examples\artifacts\ppo-hover-bonus-s0
.venv\Scripts\python.exe -m lunarlab reproduce-artifact --artifact examples\artifacts\dqn-baseline-s0
.venv\Scripts\python.exe -m lunarlab trace-artifact --artifact examples\artifacts\dqn-baseline-s0 --compare reports\jmlr\reproducibility\traces\dqn-baseline-s0-windows.npz
.venv\Scripts\python.exe -m pytest -q
```

### Linux (bash) — executed by CI

These are the commands the `ubuntu-latest` job runs (CPU-only PyTorch, no proprietary packages); at revision
`2c41b42` they all completed there (run 39069730331).

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-ci.lock --torch-backend cpu
uv pip install --python .venv/bin/python --no-deps -e .
.venv/bin/python -m lunarlab --version
.venv/bin/python -m lunarlab doctor
.venv/bin/python -m lunarlab reproduce-smoke --training-determinism --report smoke.json
.venv/bin/python -m lunarlab reproduce-artifact --artifact examples/artifacts/ppo-baseline-s0 --report baseline.json
.venv/bin/python -m lunarlab trace-artifact --artifact examples/artifacts/ppo-baseline-s0 --compare reports/jmlr/reproducibility/traces/ppo-baseline-s0-windows.npz
.venv/bin/python -m pytest -q
```

`reproduce-smoke` needs no web interface and no existing data: it creates and removes a temporary LunarLab home
(`--keep` keeps it for inspection) and exits with status 1 if any check fails.

## What reproduces exactly, and what is not guaranteed

- **Same operating system and numerical libraries:** evaluation is bit-identical — on the development machine
  (repeatedly, days apart) and on GitHub's Windows machines, a different CPU, with Python 3.12 and 3.13; training
  is bit-identical with LunarLab's defaults (CPU, one torch thread, `DummyVecEnv`), within and across processes.
- **Different operating system or library builds:** not bit-identical. On Linux every published episode differed
  numerically while the aggregates did not; see above. Stable-Baselines3 states that "completely reproducible
  results are not guaranteed across PyTorch releases or different platforms".
- **Not verified for determinism:** more than one torch thread, `SubprocVecEnv`, CUDA, and randomized physics
  across machines.
- **Expected differences:** timestamps, durations, process IDs, checkpoint file digests (zip metadata), and the
  outcome-classifier version of results produced before version 2 (only fields whose meaning does not depend on
  the version are compared).

## Supplied artifacts

`examples/artifacts/` contains three published final tests, copied byte-for-byte from the experiment runs with
`python -m lunarlab export-artifact` (checkpoint, configuration, recorded evaluation, and `artifact.json` with
their SHA-256 digests and the documented metric):

| Folder | Source run | Algorithm, reward | Checkpoint SHA-256 | Documented final test (100 episodes) |
|---|---|---|---|---|
| `ppo-baseline-s0` | `20261015-223113-baseline-s0-standard-c5af` | PPO, original reward | `a3a89f43dd2d…` | mean original return 265.8558, pad landing 96 % |
| `ppo-hover-bonus-s0` | `20261015-223115-hover-bonus-s0-standard-3376` | PPO, flawed hover bonus | `0ee843850038…` | −21.2456, pad landing 0 % (reward exploitation) |
| `dqn-baseline-s0` | `20261015-224317-dqn-baseline-s0-custom-2fe1` | DQN, original reward | `8f1438011d97…` | 155.3644, pad landing 29 % |

`tests/test_reproduce.py` checks their digests, configuration hashes and documented metrics on every test run.
Reproductions: `reports/jmlr/artifacts/reproduce-*-windows.json` (development machine) and the CI artifacts
`reproducibility-<platform>`. Windows reference traces of seeds 20000–20002 of each artifact:
`reports/jmlr/reproducibility/traces/`.

## Reporting a reproduction

Use the reproducibility-report issue form, or, without a GitHub account,
[REPRODUCTION_REPORT_TEMPLATE.md](REPRODUCTION_REPORT_TEMPLATE.md). Attach the JSON written by `--report`; the
independent-reproduction steps are in [docs/REPRODUCING.md](../REPRODUCING.md).
