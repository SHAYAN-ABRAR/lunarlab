# Progress log, 3 November 2026 (UTC)

The work followed the brief "LunarLab: final repairs and Neurocomputing submission handoff" (3 November 2026).
The author authorized commits and pushes; merging, tagging, releases, deposits, DOI reservation, submission and
contacting anyone were not authorized, and none was done.

## Starting state

- **Public state:**
  - `origin/main` is `05ca17f7308e4e0d34773371d1abe229ea6fdf0f`, the merge of pull request #3 (merged by the
    author at 2026-11-02 15:27:47 UTC).
  - Its CI run 41471828824 passed all six jobs; "Demo site" run 41471828604 also passed.
- **Local state:** branch `research/neurocomputing-final-validation` at `f9615d1`, clean. The new branch
  `research/neurocomputing-final-repairs` was created from `origin/main`.
- **Revision identities, kept distinct throughout:**
  - `c9b9384`: the library the manuscript describes;
  - `954607b`: the earlier validator revision;
  - `a38d07f`: the audited candidate's source;
  - `f9615d1`: the final commit of the earlier review branch;
  - `298562e` and later: this work's commits (`README.md`).
- **Library:** `git diff c9b9384 HEAD -- lunarlab` is empty, and so is that of the locks.

## Steps

- **14:48 — verified the audit ZIP.** `LunarLab_Linux_Validation_2026-11-03.zip`:
  - 9,980,079 bytes; SHA-256 `b55ad8f8…5ad958` as the brief gave it;
  - every CRC passed; 1,546 entries, `REPORT.md` first;
  - its `SHA256SUMS` verified 1,545 of 1,545 entries, with no file unlisted.

  Extracted into a new directory outside Git. Read `REPORT.md`, `REPAIR_NOTE_FOR_CLAUDE.txt` and the DQN
  policy's raw reports. A labelled 25-file subset is in `received/`.
- **14:54 — fetched Elsevier's generative-AI policy.** HTTP 200, page SHA-256 `6e0ca530…`; "Policy updated
  June 2026", unchanged. The Guide for Authors answered HTTP 403, as on 26 October, so the captured guide is
  used; no bot check was circumvented. Zenodo's help pages and developer documentation were read the same day.
- **14:56 — found the venv launcher blocked.** Windows Application Control now blocks uv's
  virtual-environment launcher, `Scripts/python.exe` (SHA-256 `49f0b48b…`), with os error 4551. It blocks
  both new venvs and the one that ran on 1 November, and uv cannot query it. The uv-managed base CPython
  3.12.13 still runs. Nothing was unblocked or bypassed.
- **15:12 — set up the diagnostic environment.** Installed `requirements.lock` and the `c9b9384` source
  archive into a new target directory, for the base interpreter (`dqn-diagnostic/environment.json`).
- **15:13–15:16 — reproduced the DQN policy on Windows.** `exact` with default threads and with one thread.
  Recorded a trace of seeds 20068, 20011 and 20033, and re-flew it identically. The Linux comparison is
  pending (`dqn-diagnostic/README.md`).
- **15:20 — committed `298562e`.** The validator now keeps a separate log and exit status for each setup
  command, and has the `--fresh-target` mode. The manuscript check gained `--draft`. Tests were added.
  Targeted tests: 55 passed (validator, manuscript check, project metadata), and lint and format were clean.
- **15:20–15:45 — edited the documents.** The manuscript and its evidence map, the AI inventory and
  declaration, the CRediT proposal, the highlights and submission files, the journal requirements and the
  third-party notices. Also the licence map, the archive builder, the Zenodo drafts, the deposit
  instructions, the licensing proposal and the README.
