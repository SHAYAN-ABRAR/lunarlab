# Validation of the archive candidate, 1 November 2026

Labels: **executed** means run in this work on the author's Windows laptop; **pending** means not done.

## The fresh-extraction run (`archive-a38d07f-windows/`): executed

**What was validated:** the archive candidate built from `a38d07f` (`../archive/CANDIDATE.md`). It was zipped
(SHA-256 `8a02752e…7cd7`), CRC-tested and extracted into a new, empty directory. The validator in the
extraction's own `source/` was then run:

```bash
env -u VIRTUAL_ENV -u PYTHONPATH -u LUNARLAB_HOME <base Python 3.12> -I \
    <fresh-extraction>/LunarLab-archive-candidate-2026-11-01-a38d07f/source/tools/validate_review_package.py \
    <fresh-extraction>/LunarLab-archive-candidate-2026-11-01-a38d07f <validation-run> \
    --fresh-venv --commands --unmodified-comparison --lunarlander-replays all
```

| | |
|---|---|
| Time | 20:38:07 to 21:32:42 UTC (55 minutes); exit status 0; every step passed (`validation.json`, `console.txt`) |
| Machine | Windows 11 (10.0.26300), Intel i7-13620H, the recording platform of the historical evidence |
| Interpreter running the validator | uv's base CPython 3.12.13. LunarLab, torch and the other project packages are not installed in it |
| Environment of every command | A new virtual environment, installed with uv from the extraction's `requirements.lock`, with LunarLab installed from the extraction's work copy. Its 65 packages equal the lock's pins; the lock's other 19 pins are Linux-only (`venv-freeze-after-run.txt`, taken from the same environment after the run) |
| Data home | Every command had its own new, empty `LUNARLAB_HOME`. Every replay left it empty. No log mentions the author's checkout or data home |

| Step | Result |
|---|---|
| Checksums | 2,179 of 2,179 files match `SHA256SUMS`; none missing, mismatched, unlisted or malformed |
| Dependencies | 624 checks, no problem, listed below |
| CartPole records | The analysis reproduces from the run records. All 18 runs pass the record checks, and the 36 frozen checkpoints match (`study-verification/`) |
| Figures | Rebuilt. Plotted values identical in 4 of 4 `*.values.json`; bytes identical in 20 of 20 output files on this toolchain. `check_manuscript.py --final` passes |
| LunarLander bundle | 333 of 333 listed members verified. The bundle's digest list equals the committed record. It holds 38 policy packages, 6 with their reward models |
| LunarLander statistics | For all 38 policies, recomputed with NumPy, without LunarLab code, from the 3,800 recorded test episodes: the episode counts, mean original returns, strict landing rates and timeout rates, and the ten group IQMs. **All match** (`lunarlander-statistics.json`). Bootstrap intervals are not recomputed |
| Published replays | `ppo-hover-bonus-s0` and the learned-reward package `…-0274`: both `exact` |
| All 38 LunarLander packages | Each replayed from its package: **38 of 38 `exact`** on the recording platform. 38 explicit reports are in `reports/`. Replays took 13 to 100 s each (median 34 s; 24 minutes in all) |
| CartPole artifacts | 18 of 18 verify (exit 0) and replay `exact` (`reports/cartpole-*.json`) |
| Comparison, follow-up set (`comparison/`) | Inputs verified against both hash lists. All 42 pairs are present, and all 42 agree exactly with the historical Windows rows. W2 and W3 report identical statuses in 14 of 14 cases, and reject all 12 faults through the targeted check before any episode runs. W1 is unchecked in all 14. Memory telemetry was measured in all 42. No platform-dependent difference: this machine is the clean control's recording platform |
| Comparison, unmodified frozen runner and hashed programs (`comparison-unmodified/`) | The same: 42 of 42 exact agreement, with all three set-level checks passed |

The 624 dependency checks:

- study index 72;
- analysis inputs 54;
- CartPole protocol 4;
- frozen checkpoints 36;
- exported-artifact files 108;
- comparison fixtures and programs 79;
- follow-up comparison programs 7;
- figure inputs 10;
- learned-reward package files 60;
- historical bundle 2;
- checkpoints named by the run records 192: 36 distributed, 156 inventoried with the same digests.

**What this does not show:**

- **Platforms:** this run says nothing about Linux; see below.
- **The clean control's difference:** it is permitted only on another platform. The assessment of that case is
  tested against the reviewer's diagnostic Linux output (`tests/test_followup_comparison.py`), not observed
  in a run of this work.
- **Users:** no independent person ran this.

**A minor defect found here:** the validator gives its two `uv pip install` steps the same log name, so the
log of the locked install was overwritten by the next step's log. Both steps' exit statuses were checked.
`venv-freeze-after-run.txt` records the installed versions instead. The defect is listed in `../READINESS.md`
rather than fixed after the run, so that the archive's validator stays the one that was run.

## Negative checks (`negative-damaged-copy/`): executed

A copy of the fresh extraction was damaged on purpose (`DAMAGE.txt`): one fixture policy removed, and one byte
of a CartPole artifact's policy inverted. The validator, run on it with `--fresh-venv`:

- wrote its report and exited 1;
- in the checksum and dependency steps, named both files, the missing one and the one without its recorded
  digest;
- passed every other step.

The follow-up runner, run directly on the damaged fixtures, refused before any program ran: it exited 2 and
named the missing policy, with no rows and no raw output (`runner-refusal/`).

## Linux: pending

Running the full validator on Linux needs a Linux machine with the candidate, since the fixture policies and
checkpoints are not in Git. None was available: no WSL or container runtime is installed. Linux CI ran the
regression tests (`../ci/`). The reviewer's Linux results are diagnostic results only (`../received/`). The
commands are the ones in the candidate's `START_HERE.md`:

```bash
sha256sum -c SHA256SUMS
python source/tools/validate_review_package.py . ../lunarlab-validation \
    --fresh-venv --commands --unmodified-comparison --lunarlander-replays all
```

On Linux, the validator installs from `requirements-ci.lock` with CPU-only torch. Expect these differences:

- **Clean control:** C0 may then appear as `platform-numerical-difference` in the follow-up comparison. That
  class is allowed only under the conditions in `../comparison-v2/README.md`.
- **Unmodified comparison:** its literal labels would show the same rows as "false alarm"; the assessment
  classes them identically.
- **LunarLander replays:** these may be `numerical-difference`, which is permitted on another platform. Of the
  38 policies, only 9 have been replayed on Linux so far.
