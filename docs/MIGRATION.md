# Release and migration notes: audit repair (2026-10-17)

What changes for someone who already uses LunarLab, what stays compatible, and which steps are optional.
Details per finding: [AUDIT_FIXES.md](AUDIT_FIXES.md).

## Behaviour changes

| Area | Before | Now |
|---|---|---|
| DQN resume | weights and two counters only; empty replay buffer, greedy first steps, target updates out of phase | full continuation from checkpoints written from now on; older DQN checkpoints are refused for resume and offer a **warm restart** (a new run) |
| Stopping DQN | rolled back like PPO | stops at the next rollout boundary (after the current rollout's gradient steps); discarded interactions are recorded |
| Validation-selected checkpoint | `best_validation.zip`, rewritten at every new best | `best_validation-<transitions>.zip`, one file per selection; the manifest's best entry moves |
| Final test | freezes a file name; the run could still train; no lock | freezes an immutable read-only copy; the run never trains again; runs under the run lock; attempts recorded; incomplete tests retried |
| Robustness, showcase recordings, ghosts | resolved the frozen checkpoint by name | always the frozen bytes, digest-checked |
| Episode outcomes | "landed off pad" also covered on-pad landings that failed angle/contact | classifier version 2 categories; older results labelled legacy with derived values |
| Evaluation protocols | duplicates, overlap, coerced seeds and undeclared environments accepted | refused for new runs, training and evaluation (historical ones still load, marked) |
| Tuning → normal runs | always treated like any run | exploratory when their test seeds were already used; `--holdout-seeds` for confirmatory runs |
| `export-demo` | always exported, recorded a short commit and a dirty flag | release exports need a clean tree; `--draft` for labelled drafts; manifest with full provenance |
| CLI refusals | Python tracebacks | `error: …` and exit code 1 |
| `start.ps1` / `stop.ps1` with `LUNARLAB_HOME` set | log and `backend.json` in the project's `data\` | in `LUNARLAB_HOME\data`, where the server writes them |

API: additive fields (`summary.resume`, `summary.test_status`, `summary.evidence_role`, `summary.lineage`,
`summary.protocol_valid`, `test_status` and `warm_restart` in run detail, `usable_as` on checkpoints, outcome
categories and `outcome_classifier_version` in evaluation summaries); new `POST /api/runs/{id}/warm-restart`
(`confirm: true` required); `POST /api/runs/{id}/resume` and `/train` answer 409 with an explanation for frozen
runs, legacy DQN checkpoints and invalid protocols.

New CLI commands: `warm-restart`, `test-status`, `freeze-migrate`, `reclassify-outcomes`; new options
`--holdout-seeds` (`suite`, `tune-apply`) and `--draft` (`export-demo`).

## Compatibility

- Run and protocol configuration hashes are unchanged (pinned in `tests/test_protocol.py` against two published
  runs), so existing checkpoints keep their identity and PPO runs stay resumable.
- Every existing checkpoint still loads for evaluation, recording and replay (weights-only, as before).
- PPO periodic and stop checkpoints written earlier remain resumable under the PPO contract.
- All existing evaluation files, recordings and experiment definitions are read unchanged.
- The published snapshot in `demo/api/` was re-exported after the repair as a release snapshot of revision
  `ad1ee9f` (the earlier one had been exported with uncommitted changes and showed as a draft). Same experiments
  and runs; no value changed, the re-export only added the new fields and the provenance manifest.

## New files LunarLab writes

| Path | When |
|---|---|
| `runs/<id>/checkpoints/<ckpt>.replay.npz`, `<ckpt>.state.json` | with every periodic and stop checkpoint of a DQN run (the two most recent are kept) |
| `runs/<id>/checkpoints/best_validation-<n>.zip` | at every new validation best |
| `runs/<id>/checkpoints/frozen/<sha256>.zip` (read-only) | at the first final test of a run |
| `runs/<id>/.metadata.lock` | lock file for metadata updates |
| `data/test_exposure.jsonl` | after every completed final test |

## Optional, explicit steps for existing data

Nothing below runs automatically, and nothing was run on the published data during the repair.

1. **Legacy freeze records** (43 published runs). They keep working: the tested bytes of all 43 were verified
   intact. To give them immutable copies:
   ```powershell
   .venv\Scripts\python.exe -m lunarlab freeze-migrate --all --dry-run   # report only
   .venv\Scripts\python.exe -m lunarlab freeze-migrate --all             # copy + record, logged per run
   ```
   This adds one read-only `checkpoints/frozen/<sha256>.zip` per run and upgrades `frozen_for_test` to schema 2
   (`migrated_from_schema: 1`, `migrated_at`); existing values are not changed. Runs whose tested bytes are no
   longer intact are reported and left unchanged.
2. **Derived outcome report** for other experiments (the published ones are in `docs/results/`):
   ```powershell
   .venv\Scripts\python.exe -m lunarlab reclassify-outcomes --experiment-id <id> --out <folder>
   ```
3. **A release demo snapshot**: commit first, then `export-demo --experiment-ids …` (without `--draft`). Done
   for the published snapshot on 2026-10-17 (revision `ad1ee9f`).

## Deleting run folders

Frozen artifacts are read-only so that nothing replaces them by accident. Clear the attribute before deleting a
run folder, e.g. `Get-ChildItem runs\<id> -Recurse -File | ForEach-Object { $_.IsReadOnly = $false }`.

## Launch and verify (PowerShell)

```powershell
cd D:\Rocket
powershell -ExecutionPolicy Bypass -File scripts\stop.ps1                 # if an older backend still runs
powershell -ExecutionPolicy Bypass -File scripts\start.ps1                # http://127.0.0.1:8765
.venv\Scripts\python.exe -m lunarlab doctor
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check lunarlab tests
.venv\Scripts\python.exe -m ruff format --check lunarlab tests
cd frontend; npm run typecheck; npm run lint; npm run build; npx playwright test; cd ..
.venv\Scripts\python.exe -m lunarlab freeze-migrate --all --dry-run
.venv\Scripts\python.exe -m lunarlab test-status --run-id <id>
```
