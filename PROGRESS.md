# Progress

_Last updated: 2026-10-15._

## Status

| Milestone | State |
|---|---|
| Software (all stages 1–7) | **complete and verified** |
| SMOKE pipeline check on this laptop | done (artifacts listed below) |
| Full STANDARD multi-seed experiment | **not run.** No claims about landing performance or reward hacking yet |

## Completed

1. **Workspace and dependencies.** Empty folder, not a git repo. Python 3.14 is the machine default, but
   Box2D/pygame have no cp314 Windows wheels and no C++ toolchain is installed, so the project venv uses the
   already-present uv-managed CPython 3.12.13. Locked with uv (`requirements.lock`): gymnasium 1.4.0, Box2D
   2.3.10, pygame 2.6.1, stable-baselines3 2.9.0, torch 2.14.1+cpu, numpy 2.5.4, pandas 3.0.6, matplotlib
   3.11.2, fastapi 0.143.1, pydantic 2.14.1, uvicorn 0.54.0, imageio-ffmpeg 0.6.0 (ffmpeg 7.1). Frontend:
   Node 26.3, Vite 8.3.4, React 19.3, TypeScript 6.0.3, Tailwind 4.3.3, Recharts 3.10.1, React Router 8.4
   (`frontend/package-lock.json`).
2. **RL core**: environment adapter, reward schema/presets/terms/wrapper, outcome classification, hover
   detector, CLI training with checkpoints, validation selection and cooperative stop/resume, evaluation
   with the original reward, recording, rescoring, comparison, reports.
3. **SMOKE pipeline**: trained, reloaded (weights-only), evaluated, recorded. See artifacts.
4. **Backend**: FastAPI, SQLite metadata, subprocess job supervisor with queue lanes, duplicate prevention,
   graceful stop, force-terminate with ownership verification, restart reconciliation.
5. **Frontend**: Mission Overview, Training Console (+ per-run console), Reward Studio, Flight Replay
   (incl. side-by-side), Compare & Diagnose (incl. reward-hacking diagnostic and reports), Reward Stress
   Test, Learn.
6. **Diagnostics, rescoring, reports, portfolio summary** (evidence-gated).
7. **Verification and docs**: see below; README, docs/, walkthrough.

## Test evidence (executed, all passing)

| Check | Result |
|---|---|
| `python -m pytest` | **115 passed** (unit, real LunarLander integration, real PPO, real worker subprocesses, API) |
| `ruff check lunarlab tests` / `ruff format --check` | clean |
| `npm run typecheck` (tsc -b, strict) | clean |
| `npm run lint` (oxlint, correctness + suspicious) | clean |
| `npm run build` | OK |
| `npx playwright test` (installed Edge, real backend on a disposable home) | **7 passed**: empty state, random-agent replay (3-D view, playback, footage toggle), config revisions, SMOKE job to completion, record+replay trained flight, STANDARD stop → resume → stop, compare/stress-test/learn |
| `python -m lunarlab doctor` | 10/10 OK |
| `scripts\setup.ps1`, `start.ps1 -Background`, duplicate start, `stop.ps1` (Windows PowerShell 5.1) | OK |
| SB3 `check_env` on the wrapper with every preset | no warnings |
| Visual inspection at 1920×1080, 1280×800 and 390×844 | no horizontal overflow, no console errors |
| Reproducibility | two independent SMOKE runs of the same config (supervised worker vs in-process) gave identical validation returns to 6 decimals |
| Throughput (`lunarlab benchmark`) | PPO, 4 in-process envs: ≈5,100 transitions/s; subprocess envs slower |

## Real artifacts in this project

- Demos (shared seed 20000): `data/demos/*random-seed20000*` (crash, −126.9, 99 steps) and
  `*heuristic-seed20000*` (at rest **off the pad**, 155.9, 807 steps; seed 20000 is a hard episode).
- SMOKE suite `exp-20261014-215427-smoke-pipeline-check-2a9a` (4 presets × seed 0, 8,192 transitions each):
  `runs/20261014-2154*-smoke-*/` with checkpoints, validation + frozen final-test evaluations
  (`evaluations/`), and one recorded flight each (`videos/`, `trajectories/`).
  Final-test (100 episodes, original reward): baseline −73.3, time-penalty −72.4, hover-bonus −73.3,
  potential −45.6; 0% pad landings for all. These are **technical tests, not trained agents**. Baseline and
  hover-bonus are identical because the bonus never fired in 8k transitions and both used seed 0, which
  confirms deterministic seeding rather than saying anything about the reward.
- Report: `reports/exp-20261014-215427-smoke-pipeline-check-2a9a/` (`report.html`, `report.md`, 4 figures,
  `portfolio_summary.md`, where all results correctly read "[not yet measured]").
- `data/benchmark.json` (throughput, used for time estimates).

## Added after the first delivery

- **3-D Flight Replay** (`frontend/src/components/Scene3D.tsx`, lazy-loaded three.js 0.186): a reconstruction
  from recorded telemetry on the episode's real terrain (the env's `sky_polys`, stored with new recordings
  and re-derived from the seed for older ones; equality is tested). Chase, wide and orbit cameras, engine
  plumes placed where the env emits its particles, exhaust and dust particles, leg-contact lights, an impact
  burst on crashes, pad lights that turn green only for a strict pad landing, and a HUD. It is labelled as a
  reconstruction; the simulator footage stays one click away on the same timeline.
- Found while building it: Gymnasium's "left leg" flag (obs 6) belongs to the leg on the **+x** side; the
  terrain under the pad is 3.30 (Gymnasium smooths with 0.33 rather than 1/3) while `helipad_y` is 3.333.

## Issues found and fixed during verification

- LunarLander's per-leg contact flag can read 0 while a sleeping lander rests on the pad (terrain-segment
  begin/end ordering). The strict pad-landing rule was changed to "leg contact seen during the episode"
  (documented, tested).
- Windows `os.replace` of a fresh checkpoint failed with `WinError 5` (antivirus scan); all checkpoint
  replacements now retry. Buffered training episodes are now flushed even if training fails.
- Stop clicked while a resume job was still *starting* was discarded by the worker's stale-request
  cleanup; stop requests now carry the job id and are honoured at start (regression test added).
- Chart palette re-validated for colour-vision deficiencies (blue/violet failed all-pairs); presets now use a
  validated set plus dash/marker secondary encoding. Matplotlib figures match.
- Mobile overflow from implicit grid tracks; fixed with `minmax(0, …)` tracks.

## Known limitations

- Only SMOKE runs have been executed; no conclusions about reward designs exist yet.
- An observation from a partial e2e STANDARD baseline run (seed 7, ≈500k transitions, later stopped): its
  recent training episodes mostly hit the time limit (83%, length ≈900) with a positive return. PPO on the
  *original* reward can hover before it learns to land. This is anecdotal (one partial run, training
  episodes); the full suite and the preset-independent hover detector are the way to measure it.
- A resumed run is not bit-for-bit identical to an uninterrupted run (documented).
- GPU training is optional and untested here (CPU torch build installed; CPU is faster for this MLP).
- Not a git repository: run metadata records "git: not available". Initialise git to record revisions.

## Next step

Run the full experiment (about 1–2 hours of CPU time at the measured throughput; keep the laptop awake):

```powershell
.venv\Scripts\python.exe -m lunarlab suite --presets baseline,time-penalty,hover-bonus,potential --seeds 0,1,2 --profile standard --yes
.venv\Scripts\python.exe -m lunarlab report --experiment-id <printed id>
```

or *Training Console → Multi-seed experiment suite* in the UI, then *Final test…* on each completed run.
