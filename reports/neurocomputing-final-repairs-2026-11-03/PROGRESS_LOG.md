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
- **15:39–15:47 — ran the full local test suite.** 708 passed, in 7 min 47 s, on the base interpreter with the
  fresh target install (`tests/full-suite-windows.log`).
- **15:40 — committed and pushed `db8f937`.** Pushed `research/neurocomputing-final-repairs`, a normal push
  with no force; nothing was merged.
- **15:41–15:44 — read manuscript build 41666276641 (`db8f937`).** Every page was rendered at 120 dpi and read. Two lines ran past
  the right margin: the availability statement's file names and the CRediT file name.
- **15:46 — committed and pushed `c0d9e5d`.** The file names are set with `\path`.
  - Manuscript build 41667322790 has no overfull box. Its pages 1–17 and 20–22 are pixel-identical to the
    first build's, and pages 18–19 were read again (`manuscript/VISUAL_REVIEW.md`).
  - CI run 41666276854 on `db8f937` was cancelled by this push.
- **15:48 — built the new candidate.**
  - The source archive of `c0d9e5d`: 2,082 files, `c6cbdf69…`, built without `--verify`. CI's Linux build of
    the same revision is byte-identical.
  - The archive candidate `LunarLab-archive-candidate-2026-11-03-c0d9e5d`: 2,696 files; ZIP SHA-256
    `8e4889ce…`, MD5 `2b91a658…`; CRC passed.
  - Its licence map covers 2,696 of 2,696 files.
- **15:48–16:20 — validated the candidate.** From a fresh extraction, with `--fresh-target --commands
  --unmodified-comparison --lunarlander-replays all`, every step passed and the exit status was 0. All 38
  LunarLander replays were `exact`, all 18 CartPole artifacts, and the comparison was 42 of 42 with both
  program sets (`validation/`).
- **15:51–15:53 — ran the negative checks.**
  - On this machine, `--fresh-venv` stops at the blocked launcher, with both logs and a written report.
  - The damaged copy's two faults are named, with exit 1.
  - The follow-up runner refuses the damaged inputs and runs nothing.
- **Historical evidence:** 2,359 of 2,359 protected files unchanged (`integrity/`).
- **16:20 — CI run 41667323177 on `c0d9e5d` passed all six jobs.** Linux 704 passed and 4 skipped; Windows
  294 and 294; 195 release tests; 15 browser flows. Learned-reward replay 41667323024 also passed.
- **Then — recorded everything here and built the review ZIP** (its record is in `SUMMARY.md` of the ZIP).
  Nothing was merged, tagged, released, deposited, uploaded or submitted, and no one was contacted.

## Second round: after the author turned off Windows Application Control

The author turned off Windows Application Control and asked for the blocked steps to be tried again. The
project `.venv` and new uv virtual environments ran again. WSL and Docker are still not installed, so the two
Linux items stayed pending.

- **16:44–17:14 — repeated the validation in the documented `--fresh-venv` mode.** It used a new extraction of
  the candidate ZIP from Downloads, whose size, SHA-256, CRCs and 2,695 checksums were verified again. Exit 0,
  every step passed, with the same results as the `--fresh-target` run. All three setup logs survive
  (`validation/archive-c0d9e5d-windows-venv/`).
- **16:44–16:45 — ran `build_source_archive.py --rev c0d9e5d --verify` on Windows.** The archive is
  byte-identical (`c6cbdf69…`). It installs into a fresh virtual environment, passes `doctor` and 14 of 14 smoke
  checks, and passes 195 release tests (`archive/source-archive-c0d9e5d-verify-windows.log`).
- **16:45–16:50 — built the manuscript locally with Tectonic 0.17.0 (XeTeX), for the first time.** Exit 0; 22
  pages, all fonts embedded. Under XeTeX four lines run 1 to 12 pt past the margin; CI's pdfTeX build has
  none. Page 6 was read. Nothing was changed for this (`manuscript/local-tectonic-c0d9e5d/`,
  `VISUAL_REVIEW.md`). `BUILD.md` now describes both builds.
- **16:51–17:13 — ran the full test suite in the project's own `.venv`: 708 passed.** A first attempt's output
  was lost, because its log was rewritten while it ran; it was run again with a fresh log
  (`tests/full-suite-project-venv.log`).
- **16:36 and 16:53 — the author merged the branch.** The author opened pull request #4 at 16:36 UTC and
  merged it at 16:53:43 UTC, at `f9c2906`, as `d575925`. CI on the pull request (41675942076) passed. This
  round's commits were pushed after the merge, so they need a new pull request; I did not merge or push to
  `main`.
- **After the second round — dropped the Linux follow-up, at the author's request.** The author decided not to
  pursue further Linux runs, with neither WSL nor a Codespace. The DQN trace comparison and an uninterrupted
  Linux validator run with all 38 replays are therefore marked "not planned", and removed from the to-do
  lists. In the manuscript, two clauses that presented them as pending were removed: in Section 5.2, "a trace
  … for a Linux comparison that has not yet been run", and in Section 6, "the full validator has not yet
  completed an uninterrupted Linux run". The Linux audit's findings, the DQN disagreement, its interrupted
  parent run and its unidentified cause all stay disclosed, as the brief and the author's earlier instruction
  require. The builder's `START_HERE.md` text follows. The local candidate (`c0d9e5d`) is not rebuilt now.
