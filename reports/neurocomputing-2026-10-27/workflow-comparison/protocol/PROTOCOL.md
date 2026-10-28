# Audit-workflow comparison: prespecified protocol

Written 27 October 2026, before any comparative outcome was produced. `specification.json` and
`fault_inventory.json` are the machine-readable parts. `HASHES.sha256` fixes these files, the main fixtures
and the three workflow programs before the comparison runs.

## Question

Given the same inputs, can each of three workflows produce and validate the evidence needed to
investigate a reward-design result? The inputs are a frozen policy, its reward definition and dependency,
its evaluation protocol, a recorded evaluation and a recorded trajectory. The comparison also asks what
each workflow checks, what setup it needs and what it costs to run.

This is a designed fault-injection study of 14 prespecified cases. It does not estimate how often such
faults occur in practice, and it is not a general reward-hacking detector. A workflow that does not
attempt a check is recorded as **unsupported**, not as having implemented it incorrectly.

## The three workflows

- **W1, conventional SB3** (`workflows/w1_sb3_conventional.py`). This is the evaluation a competent SB3
  user writes. It does no custom audit checks.
  - Load the saved model with `PPO.load`, which validates the archive and reports the saved system
    information next to the current one.
  - Read the saved configuration (environment, seeds).
  - Evaluate the deterministic policy once per test seed in a `Monitor`-wrapped environment. `Monitor` is
    innermost, so it records the original episode reward and length; this is SB3's documented way to keep
    the original reward.
  - Report the mean and standard deviation of the return, the episode lengths and the time-limit completion
    rate.
  - Seeds are passed to `reset(seed=int(s))`, as in common SB3 practice.
  - What SB3 provides beyond this (`EvalCallback`, best-model saving, `evaluate_policy`, `check_env`) acts
    during training or checks environment API compliance. None of it verifies a recorded audit.
- **W2, independent SB3 reference** (`workflows/w2_sb3_reference.py`). It implements the whole
  specification below in explicit custom code on SB3, Gymnasium, NumPy and the Python standard library,
  with no LunarLab import. The same developer wrote it from this written specification, so it is an
  independent implementation, not the work of an independent team.
- **W3, LunarLab** (`workflows/w3_lunarlab.py`). It maps the case onto LunarLab's public interfaces.
  - The seed contract and split validation, finite-value checks, file digests and the outcome schema of the
    `cartpole` adapter.
  - `check_recorded_episodes`, `check_trajectory`, `audit_policy` and the reproduction comparison.
  - The reproduction comparison is `compare_episodes`, `compare_generic_aggregates`, `compare_platforms` and
    `classify_reproduction`.

## Common input boundary (the neutral case format)

Every workflow reads the same directory. The format belongs to none of them.

| File | Content |
|---|---|
| `case.json` | Environment (`CartPole-v1`, default arguments), γ, the reward definition (original weight 1.0 and the `upright_potential` term, whose parameters are read from `reward_parameters.json`), the outcome schema (`cartpole` version 1, its four categories and the success category), validation and test seeds, the SHA-256 recorded for the policy at selection, the SHA-256 of every dependency and record file, and the platform that recorded the evaluation |
| `policy.zip` | The frozen SB3 PPO policy |
| `reward_parameters.json` | The reward definition's dependency, the parameters of the shaping term. It stands in for a learned reward-model file; LunarLab's learned-reward model dependencies are tested separately |
| `evaluation.json` | The recorded test evaluation: for each of 100 episodes the seed, length, original return, training return, term returns, termination and truncation flags, and outcome. It also records the environment, γ and reward definition it was made with |
| `trajectory.json` | One recorded test episode: observations, actions, original rewards, final flags and the per-step value of every reward term |

Each fault case changes one property and recomputes every digest that would otherwise catch it. A case
therefore isolates the check it targets, and an early parse error cannot mask the others.

## Specification (the audit every workflow is measured against)

| Id | Check | Must run before policy execution |
|---|---|---|
| S1 | The policy file's SHA-256 equals the digest recorded at selection | yes |
| S2 | Every dependency and record file is present and has its recorded SHA-256 | yes |
| S3 | The recorded evaluation was made with the case's environment, γ and test seeds (identical lists) | yes |
| S4 | Seed contract: validation and test seeds are non-empty lists of nonnegative integers (no booleans, floats or strings, nothing coerced), each without duplicates, and disjoint | yes |
| S5 | Every reward parameter (original weight, term coefficients) and γ is finite | yes |
| S6 | Every recorded episode has the original return, the training return and every declared term, all finite | yes |
| S7 | Accounting identity: training return = weight × original return + Σ term returns, within 1e-9 relative | yes |
| S8 | Potential convention: the trajectory's recorded per-step shaping values equal F = α(γΦ(s') − Φ(s)), with Φ(s) = −\|θ\|/θmax, θmax = 12·2π/360, and Φ(s') = 0 only on a true termination, within 1e-9 | yes |
| S9 | The case's outcome schema (name, version, categories) is the evaluator's, and every recorded outcome is one of its categories | yes |
| S10 | Replay: re-evaluate on the test seeds and compare length, original return, training return, outcome and the termination flags exactly. `exact` when everything matches. Otherwise the result is `numerical-difference` when the recording platform differs and a paired aggregate screen finds no significant difference: a sign-flip permutation test of the return differences and an exact McNemar test of success flips, Holm-corrected at 0.05. It is `unexpected-difference` on the same platform, and `aggregate-disagreement` when the screen rejects | no; only after S1–S9 pass |

Verdicts:

- `accepted`: every check passes and the replay is exact.
- `accepted-numerical-difference`: a permitted replay difference.
- `rejected-before-execution`: an integrity check fails and no episode runs.
- `rejected-after-execution`: a failure detected only after episodes ran.
- `unchecked`: the workflow produced results without the checks that would have caught the fault.
- `crashed`: an unhandled error ended the program.

## Output specification (required of every workflow)

The output is one JSON object with:

- `workflow` and `case`;
- `checks`, mapping S1–S10 to `pass`, `fail`, `warn`, `unsupported` or `not-run`, each with a detail;
- `verdict`;
- `episodes_executed`, and whether execution began before the first failure;
- the mean original return and completion rate if it evaluated.

Exit status:

- 0: accepted.
- 3: a permitted numerical difference.
- 1: rejected.
- 4: unchecked, meaning results were produced without the specification's checks; used by W1.
- Any other exit, or no JSON on stdout, is a crash.

The comparison runner keeps each program's stdout, stderr and exit code.

## Outcome classification of each (workflow, case)

The fault inventory gives each case's targeted check and its known expected outcome. A workflow's result
for a case is:

- **rejected** (correct): it rejected the case through the targeted check, before execution when the
  specification requires that.
- **warned**: it reported the problem without rejecting.
- **unsupported**: it does not attempt the targeted check.
- **missed**: it attempted the targeted check but reported no problem, or it accepted the case.
- **false alarm**: on a control case, it rejected or warned where the expected outcome is acceptance.
- **late**: correct rejection, but only after policy execution began.

A manifest check (S1, S2) establishes that bytes are the recorded ones. It does not establish that the
recorded scientific labels are correct; S6–S9 check the records' internal consistency against the
declared definitions.

## Execution cost (prespecified)

The clean control (C0) is run by each workflow 5 times, in 5 blocks. Each block is a permutation of
(W1, W2, W3) drawn with `numpy.random.default_rng(20261027)`.

- **Environment:** a fresh process for each run, `OMP_NUM_THREADS=1` and `MKL_NUM_THREADS=1`, and one
  PyTorch thread.
- **Wall time:** measured from process start to exit, including interpreter start-up, imports and every
  check.
- **Memory:** the child's own peak working set, read at exit by the program; and the process-tree resident
  set sampled every 10 ms, including any `git` subprocess, so short peaks can be missed.

The workloads are equal in episodes: each workflow evaluates the same 100 test episodes once. They differ
in checks, which is what the comparison measures, so the time difference is the cost of those checks and
of each implementation, not "overhead" of an identical workload. Distributions are reported (median,
range, a bootstrap interval of the median), not a universal percentage.

Custom code: non-blank, non-comment, non-docstring source lines of each workflow program, counted with
Python's `tokenize`. W3's count excludes the LunarLab library it calls. The count indicates the setup a
user writes. It is not a measure of researcher productivity, and no installation time, task-completion
time or user satisfaction is reported.

## Fixtures

The main fixtures come from the CartPole study's frozen `upright-potential-s50` policy, its recorded test
evaluation (test seeds 210000–210099) and one recorded trajectory of test seed 210000. The trajectory's
per-step shaping values are computed by `build_fixtures.py` with plain NumPy from the recorded
observations, as an oracle independent of every workflow. Development used separate fixtures built from
the pilot policy `upright-potential-s90` on the pilot's test seeds. The main fixtures were not run by any
workflow before `HASHES.sha256` was written.
