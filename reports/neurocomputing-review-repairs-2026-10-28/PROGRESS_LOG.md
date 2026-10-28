# Progress log: independent-review repairs

Times are UTC. Machine: the author's Windows 11 laptop (the original recording machine). This task repairs
defects found by an independent review of the Neurocomputing revision. It trains nothing.

## 2026-10-28

- 14:45 Base recorded.
  - The working copy was on `research/neurocomputing-audit-evidence` at
    `69755008326f03bda150ef007723480a97c6cd78`, tracking its remote, with a clean tree and no stashes.
  - `origin/main` is `d5881cbbf396726ba56e5bfcc588e5b848dc54d9`, the merge of PR #1. Its parents are
    `932cf1c` and `6975500`, and its tree, `407bf34d`, is identical to `6975500`'s.
  - Main CI run 40703107313 on `d5881cb` completed with success.
  - The manuscript describes library code revision `30bd3f64b392b73f5a8d64422b05d801ba281f71`, whose CI run is
    40694880778.
- 14:48 Created `research/neurocomputing-review-repairs` from `origin/main` (`d5881cb`). The upstream set
  automatically (`origin/main`) was removed so that no push can reach `main`.
- 14:40-14:50 Reproduced the missing-records finding.
  - `git check-ignore` names `.gitignore` line 11 (`runs/`, unanchored) for every file under
    `reports/neurocomputing-2026-10-27/cartpole-study/records/{main,pilot}/runs/`.
  - The 72 JSON records there (15 main runs and 3 pilot runs, four files each) exist on the recording machine
    but were never committed. `git archive`, the source-archive builder (which uses tracked files, or
    `ls-files --exclude-standard`) and the previous return package therefore all omitted them.
  - The previous claim that the analysis "reproduces byte for byte from the committed records" was wrong: it
    had been run against the working tree, where the ignored files are present.
  - The only other ignored evidence files are the 14 comparison-fixture `policy.zip` files, excluded on
    purpose (`.gitignore` line 39) and delivered in the package, and two `__pycache__` folders.
  - No other directory under `reports/`, `examples/`, `paper/` or `docs/` is hidden by the unanchored `runs/` or
    `data/` rules. The remaining nested `runs`/`data` folders are browser-test homes, ignored by their own
    rules.
- 14:50-15:00 Recovery of the CartPole run records (`recovery/`). The study indexes
  (`records/{main,pilot}/study.json`) name 72 files.
  - Each file was found in two places: the ignored repository copy, and the study runner's original output
    directory outside the repository.
  - Each copy was compared with every digest recorded before the omission was found: the study index, the
    analysis's `inputs_sha256`, and the exported artifacts' manifests (where `evaluation.json` is a byte copy
    of `test-selected.json`).
  - All 72 match on both copies, the recorded digests agree with each other, and nothing is unresolved
    (`recovery/INVENTORY.md`, `recovery/inventory.json`).
  - The comparison fixtures have no such gap: 79 of 79 listed files are present and match, and the 14 untracked
    ones are the deliberately excluded `policy.zip` models.
  - `.gitignore` now anchors the data-home rules (`/data/`, `/runs/`). Only the 72 records and this folder became
    visible. The root data home, the browser-test homes, the fixture models and `__pycache__` stay ignored.
  - The 72 records were staged by explicit path, without force-adding. The staged bytes equal the recorded
    digests, and the files carry `-text`, so no line endings change.
- 15:05-15:15 Verification from the recovered records
  (`recovery/verify_cartpole_study.py TREE OUT --checkpoints DIR`). `TREE` was a fresh `git archive HEAD`
  extraction, so only committed files were used. The checkpoint files came from the study runner's output.
  - **Analysis:** the prespecified analysis, rerun into a fresh directory, reproduces the committed results
    for both the main study and the pilot: `results.json` equal, `RESULTS.md` byte-identical.
  - **Per run:** all 18 runs pass every check. Actual transitions are rollouts × 8 × 32 (100,096 main, 20,480
    pilot; 1,501,440 and 61,440 in total). The effective first-reset seeds equal `1,000,000 + 1000 × seed + i`,
    and no later reset was seeded. Checkpoints fall every 10,240 transitions plus the final step. Every
    validation mean equals the mean of its 20 episodes.
  - **Selection:** rerunning the rule gives the recorded step in every run, often among ties (up to 10
    checkpoints tied at the maximum). The earliest tied checkpoint is chosen, as the protocol states.
  - **Frozen digests and tests:** the frozen selected and final digests equal the chosen and last checkpoints.
    Both tests name those digests, ran after training finished, and use the protocol's test seeds (100 main,
    20 pilot), disjoint from the validation seeds. Their aggregates equal the mean of their episodes.
  - **Checkpoint files:** all 192 match their recorded digests.
  - **Source:** every run records source `e7c3fab` with a clean tree.
  - **Validation readings:** the flawed-bonus validation means lie between 9.05 and 9.55 at every evaluated
    checkpoint, from the first, at 10,240 transitions. That is the observation; the records say nothing about
    what happened before the first checkpoint.
- 15:20-15:50 The two validation defects (`defects/`).
  - **Reproduced on the unfixed code** with `defects/reproduce_defects.py` (output `before-fix-d1f69c6.json`):
    - Two steps of reward 1e308 through `RewardAccountingWrapper` (gamma 0.99) emitted a completed
      `audit_episode`, and set `last_episode`, with infinite original, training and discounted totals.
    - Two finite terms of 1e308 raised a bare `OverflowError`.
    - `rescore_transitions` returned infinite totals.
    - The audit aggregate crashed with `OverflowError` on two finite episode totals of 1.5e308.
    - `check_recorded_episodes` raised `TypeError` on null returns. Booleans and text were caught but reported
      only as "episodes [0]", and a null optional value passed silently.
  - **Fixed:**
    - `EpisodeAudit.add` validates every input and every new total before changing anything. If a total
      overflows, `NonFiniteValueError` names each affected quantity and the audit is unchanged.
    - The wrapper does its accounting, outcome classification and summary under one guard. On failure it emits
      no summary, clears `last_episode` and refuses steps until reset.
    - `training_reward()` turns an `fsum` overflow into the audit error; `rescore_transitions` reuses it.
    - Audit means use `finite_mean`. It equals `statistics.fmean` for ordinary values, and is exact when only
      the plain sum would overflow.
    - `check_recorded_episodes` now has explicit required fields (`original_return`, `training_return`,
      `term_returns`) and optional ones (the discounted returns, `term_discounted_returns`). Every present value
      must be a finite `int` or `float`. Each problem is reported with its episode, field and type, and nothing
      raises.
    - Artifact checks carry a kind, `integrity` or `record`. `audit-artifact` prints
      `MALFORMED-RECORD (blocking)` when only record checks fail. The status stays `integrity-failure`, exit 1,
      with no episode run, distinct from numerical differences (exit 3).
  - **After the fix:** `after-fix-working-tree.json` shows every case handled.
  - **Tests:** six overflow tests use independent oracles (1e308 + 1e308 exceeds the largest double, and
    powers of two near the limit are exact). Eleven record tests cover direct calls, the tampered-artifact
    path and the CLI, plus the two new tampering cases. 109 audit tests pass, 316 with the documentation,
    CLI and reproduction suites.
  - **Main LunarLander pipeline:** not changed. Its inputs are bounded by the configuration schema (every term
    parameter bounded, `tanh`-bounded potential features, original-reward weight at most 1, learned-reward
    scale at most 100), and its episodes end within 1,000 steps, so its totals cannot approach the
    floating-point range.
- 15:52 Regression check (`regression/rerun_w3.py`). The comparison's W3 program was rerun with the repaired
  code on all 14 fixtures (evaluation only). Its status vectors, verdicts, exit statuses and episode counts are
  identical to the recorded results of 27 October in 14 of 14 cases.
- 15:20 CI run 40712412847 on `c9b9384` (pushed 15:05): all six jobs passed.
  - Linux: 594 passed and 4 Windows-only tests skipped; 86.04% combined coverage (8,995 of 10,155 statements,
    1,976 of 2,596 branches).
  - Windows Python 3.12 and 3.13: 293 each. Source archive: 194. Browser: 15 flows.
  - Learned-reward replay 40712412965: passed.
- 15:35 The source archive of `c9b9384` built locally is byte-identical to CI's (`3427d9a9…`, 1,112 files) and
  passes 194 release tests after a fresh install (`validation/`).
- 15:25-16:00 Manuscript corrections, following the brief's items A to G:
  - **Scope (A):** the layer is described as adapter-based, with adapters for LunarLander and CartPole, the two
    tasks it has been used on. Figure 1's header now reads "Reusable core via task adapters (LunarLander,
    CartPole)"; a longer first version was clipped and shortened.
  - **Agreement (B):** "a separately implemented reference", wherever the text said "independent".
  - **Checks (C):** which command runs which checks. `audit-artifact verify` runs the equivalents of S1-S7 and
    S9, `reproduce` adds S10, and S8 is a library function, because exported artifacts carry no trajectory.
  - **Contract (D):** the finite-value contract as implemented.
  - **Validation readings (E):** stated as an observation; no learning chronology is asserted.
  - **Identity (F):** the merged `30bd3f6`, the repair revision `c9b9384`, the experiments' own source states,
    and the absence of any release.
  - **Provenance (G):** its limits.
  - **Section 5.1:** CI numbers of `c9b9384`. "Independent review" became "subsequent review", because the
    review was AI-assisted, as the paper discloses.
- 16:00 Wording aligned in the README, `docs/DEVELOPER.md`, the comparison README and FINDINGS. The comparison's
  hash-listed `PROTOCOL.md` is unchanged. The 27 October readiness report and log carry dated correction notes,
  and their earlier text is kept. `paper/neurocomputing/EVIDENCE.md` was rewritten for the corrected claims.
- 16:05 `tools/validate_review_package.py`: a package validator that checks scientific dependencies as well as
  checksums. It recomputes, rebuilds and (with `--commands`) runs the documented commands in a fresh
  environment. Its tests show the dependency check names a missing or altered run record.
- 17:05-17:30 Pushed `8f1258d`.
  - CI run 40734273117: all six jobs passed. Linux: 596 passed and 4 skipped, which includes the two
    validator tests. Windows: 293 each. Source archive: 194. Browser: 15.
  - Manuscript build 40734273141: 19 pages, all fonts embedded, no undefined references. Every page was read,
    and the reading found four problems:
    - the branch name and the repairs path in the availability statement ran up to 111 pt into the margin
      (`\texttt` cannot break), as did one line in Section 4.1 (4.4 pt);
    - the Section 4.1 title still said "independent";
    - the longer abstract pushed the title block's closing rule onto page 2.
  - Fixes: `\path` for branch names and paths, which breaks at `/` and `-`; the 4.1 sentence and title
    rephrased; the abstract shortened to 180 words without dropping content.
- 17:18 Integrity (`integrity/`). The 2,359 protected historical files are unchanged; the combined digest
  equals the one before any change. Since `d5881cb`, the 27 October evidence folder has 72 added run records
  and 5 documentation edits, and no change to protocols, raw outputs, results or figure inputs.
