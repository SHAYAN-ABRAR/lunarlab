# Follow-up comparison programs and runner (version 2)

Written 1 November 2026. The prespecified audit-workflow comparison is in
[`reports/neurocomputing-2026-10-27/workflow-comparison/`](../../neurocomputing-2026-10-27/workflow-comparison/).
Its protocol, fixtures, the three programs, `run_comparison.py` and the Windows results of 27 October are fixed
by `protocol/HASHES.sha256` and are **unchanged**. Version 2 is a separate, versioned program set for
portability. It changes no check, threshold, fixture or fault expectation.

## Why

An independent package verification on Linux (29 October 2026; `../received/independent-verification-2026-10-29/`) found three faults:

1. **Telemetry ended every program.** All three programs read `psutil.Process().memory_info()` after the audit.
   The reviewer's sandbox does not expose the process to psutil, so this raised `NoSuchProcess`, and no
   program printed its result. All 42 pairs were recorded as crashed.
2. **The validator crashed on that output.** `tools/validate_review_package.py` called `.items()` on a crashed
   row's `checks=None`, raised `AttributeError` and wrote no `validation.json`.
3. **A permitted difference was labelled a false alarm.** In a reviewer's diagnostic copy, telemetry returned null when unavailable. There the clean control
   C0 replayed as `accepted-numerical-difference` (exit 3) on Linux instead of `accepted` (exit 0) on Windows,
   with S1-S10 all passing. The frozen runner compares one literal expected verdict, so it labelled this a false
   alarm, and the validator compared literal labels.

## What changed

| File | Change |
|---|---|
| `workflows/w1_sb3_conventional_v2.py`, `w2_sb3_reference_v2.py`, `w3_lunarlab_v2.py` | Derived from the hashed originals by `derive_v2_programs.py`, by exact replacements listed in that file; the full diff is `CHANGES.diff`. Only `peak_rss()`, the result line and the docstrings differ. When memory is available, the value is the original's. When psutil raises `NoSuchProcess` or `AccessDenied`, `peak_rss_bytes_self` is null and `peak_rss_status` gives the reason, never zero. Other errors propagate. `tests/test_followup_comparison.py` checks node for node that every other top-level definition is the original's |
| `run_comparison_v2.py` | Verifies every input before anything runs: the frozen hash list (pinned digest), all 79 of its entries, the historical results (pinned digest) and `HASHES-v2.sha256`. Records a crashed, hung or malformed program with its exit status, stdout, stderr and reason, and continues. Refuses a non-empty output directory, and writes the run identifier into `summary.json`. Keeps each raw verdict and the frozen runner's literal-rule outcome, unchanged, as `literal_rule_outcome`, and adds the follow-up assessment |
| `assessment.py` | The follow-up assessment (below); standard library only, shared with the validator |
| `HASHES-v2.sha256` | The digests of the version-2 files, fixed at 15:32:17 UTC on 1 November 2026, before any of them ran on the fixtures |

## The follow-up assessment

Each (workflow, case) pair is compared with its historical Windows row and classed as one of:

- **exact-agreement:** the same verdict, exit status, episode count and S1-S10 statuses.
- **platform-numerical-difference** (not blocking, always listed). Every condition below must hold:
  - the case is the clean control, whose historical replay was exact, and the workflow runs S10 (W2 or W3);
  - every one of S1-S10 passes, and the replay status is the existing nonblocking `numerical-difference`
    (exit 3);
  - the same number of episodes ran;
  - the case and its recorded evaluation name the same recording platform;
  - the runner verified that this machine's operating system or a numerical library (torch, numpy, Box2D,
    gymnasium, stable-baselines3) differs from that platform. A component the record does not state is not
    evidence of a difference.
- **failure** (blocking): everything else. This includes:
  - crashed, absent or malformed results;
  - the same difference on the recording platform;
  - any change in a fault case;
  - a rejection after execution;
  - fewer episodes;
  - a failed check.

Set-level checks are also required:

- all 42 pairs present, once each;
- W2 and W3 report identical S1-S10 statuses in all 14 cases;
- W2 and W3 reject all 12 faults before any episode runs, through the targeted check;
- W1 is unchecked in every case.

What is **not** done:

- an exit status of 3 is not accepted by itself;
- no numerical threshold is relaxed;
- a fault expectation is not altered;
- a difference on the same platform is not normalized away.

`literal_rule_outcome` keeps the frozen runner's label ("false alarm" for such a C0 row), so the change of label
stays visible next to the assessment.

**A property of fixture C1:** C1's evaluation is recorded as made on a Linux machine
(`Linux-6.11.0-1018-azure`, torch `2.14.1`). Its designed replay difference is permitted only where the
replaying machine differs from that record. On a Linux machine with exactly those library versions, W2 and W3
would report `unexpected-difference`, and the assessment would fail C1. This is the specification working as
written; the runner does not override it.

## Runs

| Run | Where | What it is |
|---|---|---|
| `results-windows-2026-11-01/` | The author's Windows laptop, from the working tree | **Directly executed** development check of version 2 on the real fixtures |
| `../validation/` | A fresh extraction of the archive candidate, in a fresh locked environment | The package validator's run: version 2 and, separately, the unmodified frozen runner and programs |
| Linux | Pending | No Linux machine with the fixture policies was available to this work: they are not in Git, and no WSL or container runtime is installed. The reviewer's Linux results are **diagnostic results**, kept in `../received/` and assessed by `tests/test_followup_comparison.py`. The commands for a Linux run are in `../archive/START_HERE.md` |

```bash
python run_comparison_v2.py ../../neurocomputing-2026-10-27/workflow-comparison/fixtures OUT [--run-id ID]
python derive_v2_programs.py --check     # the v2 programs are exactly the documented derivation
```
