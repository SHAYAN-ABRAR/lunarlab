# Community evidence

JMLR-MLOSS asks that "evidence of an active user community should be demonstrated in the cover letter by, for
example, number of active developers, number of stars on github or similar metrics", and reviewers consider "the
openness of the project, such as a public source code repository, bug tracker, mailing list/forum". Evidence of
this kind cannot be produced by changing code. This page separates what has been **observed** from what **people
still have to do**. Nothing here is estimated or invented.

## Observed (GitHub API)

| Metric | 2026-10-18, first pass | 2026-10-18, correction pass |
|---|---|---|
| Repository created | 2026-10-14 (public) | — |
| Stars / forks / watchers | 0 / 0 / 0 | 0 / 0 / 0 |
| Open issues / pull requests from others | 0 / 0 | 0 / 0 |
| Contributors | 1 (the author, 12 commits) | 1 (the author, 14 commits) |
| Issues enabled / Discussions enabled | yes / no | yes / no |
| Views, last 14 days (GitHub traffic) | 2 views, 2 unique visitors | 2 views, 2 unique visitors |
| Clones, last 14 days (GitHub traffic) | 88 clones, 25 unique | 152 clones, 53 unique — **not evidence of users**: every CI and Pages run checks the repository out and is counted (the increase coincides with the CI and Pages runs of 2026-10-18) |
| Citations of LunarLab, independent reproductions, external users | none known | none known |

**Conclusion: there is currently no evidence of an active user community.** On this criterion the submission is
not ready, and only real use can change that.

## Infrastructure in place for outside users (added or verified in this work)

- Public repository, MIT License, issue tracker with forms for bug reports, feature requests and **reproducibility
  reports** (`.github/ISSUE_TEMPLATE/`), and a pull-request checklist.
- `CONTRIBUTING.md` (setup, checks, conventions, review expectations), `docs/DEVELOPER.md`, a generated API
  reference, and a tutorial whose commands are executed by the test suite.
- A reproduction package that does not need the authors' data: `python -m lunarlab reproduce-smoke` and three
  supplied published artifacts re-evaluated with `python -m lunarlab reproduce-artifact`.
- A report form that needs no GitHub account (`docs/jmlr/REPRODUCTION_REPORT_TEMPLATE.md`), which asks whether
  the report may be cited; its outcome choices are the statuses `reproduce-artifact` reports.
- A 15-minute independent-reproduction guide, [docs/REPRODUCING.md](../REPRODUCING.md): install from a release
  archive, check the installation, re-evaluate a published policy, read exact versus numerical-difference
  results, send the report.
- A read-only live demo of the published results (https://shayan-abrar.github.io/lunarlab/).

## What real people still need to do (suggestions, not done)

1. **Ask colleagues or students to follow the tutorial** and send a reproduction report (template above); record
   each report, its outcome and platform. Independent reproductions on Linux and on other CPUs are also the
   missing cross-platform evidence.
2. **Enable GitHub Discussions** (a repository setting, not changed here) or name another public forum, so users
   have a place to ask questions (MLOSS mentions "mailing list/forum").
3. **Publish a tagged release** and archive it with a DOI (for example Zenodo), so it can be cited; then update
   `CITATION.cff`.
4. **Present the tool where reward-design researchers are** (a workshop, a course, a talk) and point to the
   reproduction package. This must be done by the authors; no message was sent and no account was created here.
5. **Report real numbers in the cover letter** at submission time (stars, forks, contributors, external issues,
   reproduction reports, citations, downloads), with their date — including small ones.

## Evidence the maintainer should collect (and how to record it)

Record each item with its date, source and a link, so the cover letter can cite it verbatim. JMLR names no
minimum, and none is assumed here.

| Evidence | Counts | Does not count |
|---|---|---|
| Reproduction reports | reports from people other than the authors, with the attached `--report` JSON and platform | runs by the authors on their own machines; CI runs |
| Research users | people or groups using LunarLab in their own work (a thesis, a course, an experiment), confirmed by them | downloads, clones, page views |
| External contributions | issues, pull requests, reviews or discussions by others | the authors' own accounts |
| Citations | papers, theses or preprints citing LunarLab or its archived release | self-citations, listed separately if mentioned |
| Public engagement | talks, courses or workshops where the tool was used, with a link or programme | announcements alone |

No outreach was made, no account was created and no metric was changed in this work.
