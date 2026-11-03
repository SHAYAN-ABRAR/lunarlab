# Validation of the archive candidate of 3 November 2026 (`c0d9e5d`), on Windows

**Executed** on the author's Windows 11 machine. This is the recording platform, so it cannot close the Linux
task: the full validator has not yet completed an uninterrupted Linux run with all 38 replays.

## The run

| | |
|---|---|
| Package | A fresh extraction of `LunarLab-archive-candidate-2026-11-03-c0d9e5d.zip` (SHA-256 `8e4889ce…610f`), extracted into a new, empty directory; `sha256sum -c SHA256SUMS` verified 2,695 of 2,695 entries before the run |
| Command | `python -I source/tools/validate_review_package.py . <validation-run> --fresh-target --commands --unmodified-comparison --lunarlander-replays all` |
| Interpreter | uv-managed CPython 3.12.13, run directly. Windows Application Control blocks uv's virtual-environment launcher on this machine (os error 4551), so `--fresh-venv` cannot run here (see the negative check below); nothing was unblocked |
| Environment | A new target directory with `requirements.lock` and the working copy (`logs/target-install-lock.log`, `logs/target-install-source.log`; the interpreter's own packages: `pip` only). `PYTHONNOUSERSITE=1`; every command had an empty `LUNARLAB_HOME` |
| Threads | `OMP_NUM_THREADS` and `MKL_NUM_THREADS` unset (default); the comparison runners set their programs to one thread, as recorded |
| Time | 2026-11-03 15:48:54 to 16:19:50 UTC |
| Result | **Exit 0; every step passed**, `failed_steps: []` ([`archive-c0d9e5d-windows/validation.json`](archive-c0d9e5d-windows/validation.json), `console.txt`) |

| Step | Result |
|---|---|
| Checksums | 2,695 listed, none missing, changed, unlisted or malformed |
| Dependencies | 624 checks, no problem: study index 72, analysis inputs 54, CartPole protocol 4, frozen checkpoints 36, exported artifacts 108, comparison fixtures and programs 79, follow-up programs 7, figure inputs 10, learned-reward package files 60, historical bundle 2, named checkpoints 192. Of the 192 named checkpoints, 36 are distributed (checked by digest) and 156 are inventoried (their digests equal the run records'; their bytes are not in the candidate) |
| Environment | `install-lock` exit 0 and `install-source` exit 0, **each with its own log**; both logs survive |
| Platform | Windows-11-10.0.26300-SP0, Python 3.12.13; torch 2.14.1, NumPy 2.5.4, Box2D 2.3.10, Gymnasium 1.4.0, Stable-Baselines3 2.9.0 |
| CartPole records | The analysis recomputed from the run records equals the committed results; all 18 runs checked against the protocol and the frozen checkpoints (`study-verification/VERIFICATION.md`) |
| Figures | Plotted values identical in 4 of 4 value files; bytes identical in 20 of 20 outputs on this machine; `check_manuscript.py --draft` exit 0 |
| LunarLander bundle | 333 members checked against the committed list; 38 policy packages, 6 with reward models |
| LunarLander statistics | 38 policies and 3,800 episodes recomputed; every per-policy mean and rate and all ten group IQMs match (bootstrap intervals are not recomputed) |
| Published replays | Both `exact`, data homes left empty |
| All 38 LunarLander replays | **38 `exact`**, including `20261015-224318-dqn-hover-bonus-s0-custom-aefc`, the policy that disagrees on Linux; every data home left empty |
| CartPole artifacts | 18 of 18 verified and `exact` |
| Follow-up comparison (`comparison-v2`) | 42 of 42 pairs `exact-agreement`; no platform difference, no blocking row; set checks pass (W2/W3 agreement in 14 cases, 12 faults rejected before execution, W1 unchecked) |
| Unmodified comparison | 42 of 42 pairs `exact-agreement`; set checks pass. On this machine the hashed programs' memory telemetry works, unlike in the audit's sandbox |

## Negative checks (executed)

| Check | What was done | Result |
|---|---|---|
| [Damaged copy](negative-damaged-copy/) | A copy of the extraction with one fixture policy removed and one byte of an exported CartPole artifact inverted (`DAMAGE.txt`); `--fresh-target`, no commands | Exit 1, with `validation.json` written. `checksums` names both files. `dependencies` names "exported artifact: main/artifacts/original-s50/policy.zip does not have its recorded digest" and "comparison fixtures and programs: missing …/F01-checkpoint-swapped/policy.zip". Both install logs are present |
| [Follow-up runner on the damaged inputs](negative-damaged-copy/runner-refusal/) | `run_comparison_v2.py` on the damaged copy's fixtures | "inputs did not verify; nothing ran: missing fixtures/F01-checkpoint-swapped/policy.zip"; exit 2; no program ran |
| [`--fresh-venv` where the launcher is blocked](negative-fresh-venv-blocked/) | The intact extraction with `--fresh-venv` | Exit 1, with `validation.json` written. `environment` records `create` (exit 0, `logs/venv-create.log`) and `install-lock` (exit 2, `logs/venv-install-lock.log`: uv cannot query the blocked interpreter), and names the failed step and its log. The later steps are reported as skipped, with the reason |

A replay disagreement is exposed rather than suppressed. On this machine every replay is exact, so this is
shown by the tests (`tests/test_validator_failures.py`): an `aggregate-disagreement` replay fails its command,
and one among 38 fails the step and is named. On Linux, the audit's reports show the same behaviour for the
real policy (`../received/`).

## Paths

The records here have this machine's paths replaced by labels (`<fresh-extraction>`, `<validation-run>`,
`<uv>`, `<home>`, …). Nothing else is changed. No file mentions the author's checkout, which shows that the run
did not use it. The unlabelled originals are in the review package of 3 November 2026.
