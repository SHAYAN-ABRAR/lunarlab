# Community evidence and independent-use plan

## Verified status

Inspected 18–19 October 2026: public repository, zero stars, zero forks, no open issues; documentation reports one contributor. No independent research users, reproductions or citations were established by this audit. CI and this assistant's technical review are not independent community adoption. A star is a weak attention metric; it is not proof of use.

MLOSS requests active-community evidence, without prescribing a minimum number of users. The objective is actual research utility, not increasing counters.

## A concrete independent-user exercise

Status on 27 October 2026: this exercise has not yet been given to anyone. Every run so far was the author's or
continuous integration's, and those are not independent use.

Prepare a pinned source archive with the example packages and give an independent researcher
[REPRODUCING.md](../REPRODUCING.md). Ask them to complete these tasks without live author intervention, and
record any help later required. Steps 1–6 of REPRODUCING.md cover the first five tasks, and each has an expected
output to compare against.

| Task | Evidence to retain | Success means |
|---|---|---|
| Install into a fresh supported environment | OS, Python, package versions, commit, command log | Documented installation succeeds or produces an actionable report |
| Evaluate a supplied policy | Artifact digest and JSON reproduction report | Integrity and numerical outcomes are correctly distinguished; exit 3 is understood |
| Replay a learned-reward policy from an empty data home | JSON report; the data-home listing afterwards | The bundled reward model is used, and nothing outside the package is needed |
| Reproduce a recorded figure | `build_figures.py` and `check_manuscript.py --final` output | The plotted values match the recorded evidence |
| Inspect a baseline and hover failure | Outcome/reward table and short explanation | User identifies reward/task mismatch without relying on animation |
| Add a custom reward term (REPRODUCING.md, step 8) | Minimal code, audit report and its provenance record | User reads original, training and term returns separately, and can explain `implementation_identity` |
| Run the generic audit on CartPole (smoke protocol), then verify and reproduce one artifact | Study folder, `audit-artifact` output | Integrity checks run before execution; the core works without the LunarLander interface |
| Report a failure | Reproducible issue with minimal environment details | Maintainer can reproduce or explain it and document the resolution |

The report form for each participant:

- **Machine record:** operating system, CPU, Python, the output of `python -m lunarlab --version`, and whether
  a GPU was present.
- **For each task:** start and end time as the participant recorded them, the commands run, the exit status,
  the JSON reports, and anything that was unclear or failed. Negative findings are kept as they are.
- **Author help:** what help was needed, and from whom.
- **Permission:** may this report be quoted, and may the participant be named? Ask separately for each, and
  quote or name only with explicit consent.
- **Relationship:** the participant's relationship to the author, and whether this was an installation
  exercise or use for their own research question.

A small initial cohort spanning more than one machine/platform is practical, but is an author planning choice, not a journal threshold. Do not pay for favorable testimonials or require stars. Ask permission before naming participants or quoting feedback. Preserve negative reports, fixes and follow-up verification. Report author assistance, prior relationships and whether the activity was an installation exercise or genuine research use.

## Evidence record template

- Date; participant identifier with consent; institution only if supplied.
- Relationship to author and reason for using LunarLab.
- Exact software revision and platform.
- Task attempted and commands/run IDs/artifact hashes.
- Outcome, failures and author help needed.
- Independent issue/report URL or archived report approved for sharing.
- What the user learned or used in a research question.
- Follow-up fix and independent verification.

## Practical priorities

First supply missing primary-study artifacts and ensure the tutorial explains numerical-difference exit codes. Next invite actual colleagues or researchers to try a relevant task, only after the author authorizes outreach. Turn observed friction into documentation/API fixes, then ask the same people to rerun the failing steps. Update the cover letter only with completed, dated evidence. No one was contacted and no promotional material was published during this work.
