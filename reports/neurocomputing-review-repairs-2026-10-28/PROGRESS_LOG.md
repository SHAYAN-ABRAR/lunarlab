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
