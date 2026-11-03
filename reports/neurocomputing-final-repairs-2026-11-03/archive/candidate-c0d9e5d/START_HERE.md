# LunarLab: archive candidate for the Neurocomputing software paper

**Status: a local candidate, not a deposit.** It was assembled on 2026-11-03 15:48 UTC from revision `c0d9e5d0823167584a7bff37de9661c35a58228c`.
Nothing has been uploaded or published, and no DOI or other identifier exists or is reserved. The source code
and documentation are MIT-licensed; the licence of the records, model files and manuscript text is not yet
chosen (`LICENSES.md`).

## What is here

| Path | Contents |
|---|---|
| `source/` | The repository at `c0d9e5d` (`git archive`, committed bytes): library, tests, tools, documentation, the manuscript source, and under `source/reports/` the protocols, study records, comparison programs, fixtures (without their policies), results and validation records |
| `software/c0d9e5d/` | Deterministic source archive of `c0d9e5d` (SHA-256 `c6cbdf69b00aaad03ad44495549500e7f1cecba7d7f3f598889130b5c53b0648`), its manifest and digest |
| `software/c9b9384/` | Deterministic source archive of `c9b9384`, the library revision the manuscript describes (SHA-256 `3427d9a91de84606ffd19e52cc8c2c28eba68559cfd62ed278a33afcdf5eac60`, byte-identical to the Linux CI build of run 40712412847). Library code is unchanged from `c9b9384` to `c0d9e5d` |
| `outside-git/` | The 14 policy files of the workflow-comparison fixtures, at their repository paths |
| `cartpole-study-output/` | The CartPole study's 36 frozen checkpoints and 18 exported artifacts. `INTERMEDIATE_CHECKPOINTS.json` lists the 156 scheduled checkpoints that are not distributed (22.5 MB), each with the digest its run record gives |
| `lunarlander-study/` | `LunarLab_38_Policy_Study.zip`: the 38 historical LunarLander policy packages (checkpoint, configuration, recorded 100-episode evaluation, provenance; the six learned-reward packages with their original reward models) and its inventory and digests. `lunarlab-0.1.0-444a4c5-src.tar.gz`: the source it was repaired with. Both byte for byte as recorded in `source/reports/neurocomputing-final-validation-2026-11-01/archive/historical-bundle.sha256` |
| `REVISIONS.md` | Which revision produced which evidence |
| `INVENTORY.md`, `inventory.json` | Every file with its size and SHA-256, and the records that name the scientific dependencies |
| `LICENSES.md` | Licences: MIT for the software; LPPL for the two copied LaTeX files; the records, models and manuscript text await the author's choice |
| `SHA256SUMS` | Every other file |

The evidence sets are distinct and are not interchangeable:

- **LunarLander:** 3,800 recorded test episodes (38 policies x 100), recorded on Windows 11.
- **CartPole:** a separate prespecified study of 18 policies, whose final tests are 15 x 100 and 3 x 20
  episodes.
- **Comparison:** a fault-injection study of 14 cases and three workflows.
- **Replays:** re-evaluations of recorded episodes. They are a fourth kind of evidence and are not new
  episodes of any of the above.

## Checking it from a fresh extraction

Prerequisites: Python 3.12 and [uv](https://docs.astral.sh/uv/). The validator creates a new virtual environment from the locked dependencies in
`source/` and gives every command an empty data home (`LUNARLAB_HOME`), so nothing is read from an
existing LunarLab installation. Nothing is trained.

```bash
sha256sum -c SHA256SUMS                       # Linux; on Windows see the PowerShell line below
python source/tools/validate_review_package.py . ../lunarlab-validation \
    --fresh-venv --commands --unmodified-comparison --lunarlander-replays all
```

```powershell
Get-Content SHA256SUMS | ForEach-Object { $d, $n = $_ -split ' \*', 2; if ((Get-FileHash -Algorithm SHA256 $n).Hash.ToLower() -ne $d) { "MISMATCH $n" } }
```

Where application control blocks a virtual environment's launcher (as Windows Application Control does on the
author's machine since 3 November 2026), use `--fresh-target` instead of `--fresh-venv`: it installs the same
lock into a new directory for the validating Python 3.12 and runs nothing it would block.

The validator writes `../lunarlab-validation/validation.json`. It exits 0 only if every step passes, and it
writes its report even when a step fails. Its steps are:

1. **Checksums:** every file here is listed in `SHA256SUMS` with its digest.
2. **Dependencies:** every distributed file a record names is present with its recorded digest:
   - the CartPole study indexes and analysis inputs, the frozen checkpoints and the exported artifacts;
   - the comparison fixtures and programs, and the follow-up comparison programs;
   - the figure inputs and the learned-reward packages;
   - the historical bundle.

   Every checkpoint a CartPole run record names is either distributed with its digest or listed in
   `INTERMEDIATE_CHECKPOINTS.json` with the same digest: of the 192 named, the
   36 frozen checkpoints are distributed and the 156 scheduled ones are inventoried. The inventory
   records their digests; their bytes are not here, so they cannot be checked.
3. **CartPole analysis:** it is recomputed from the run records and compared with the committed results. All
   18 runs are checked against the study protocol and the frozen checkpoints.
4. **Figures:** they are rebuilt, and the plotted values are compared separately from the image bytes.
5. **LunarLander bundle:** each of its members is checked against the bundle's digest list, which equals the
   list committed in `source/reports/jmlr/learned-reward-repair-2026-10-24/`. The per-policy statistics and
   group IQMs are recomputed from the 3,800 recorded episodes, without LunarLab code.
6. **Replays:** with `--lunarlander-replays all`, each of the 38 policies is replayed from its package. On
   the recording platform (Windows) a replay is expected to be `exact`. Elsewhere the existing
   `numerical-difference` classification may apply, and the report shows it. An `aggregate-disagreement`
   fails the step: on Linux, one DQN policy does so (see the limitations below).
7. **CartPole artifacts:** all 18 are verified and replayed.
8. **Workflow comparison:**
   - **Version 2:** the follow-up runner `source/reports/neurocomputing-final-validation-2026-11-01/comparison-v2/`, assessed against the historical
     Windows results;
   - **Unmodified:** with `--unmodified-comparison`, also the frozen runner and programs, assessed by the
     same rules.

## Limitations (also in `source/reports/neurocomputing-final-repairs-2026-11-03/READINESS.md`)

- **Linux coverage:** nine of the 38 LunarLander policies were replayed on Linux in CI (historical). An
  assistant-executed audit of the previous candidate (`a38d07f`, 2 to 3 November 2026) replayed all 38 on
  Linux in a diagnostic run limited to one thread, whose parent validation was interrupted before its final
  report. All 38 kept integrity; 37 showed permitted numerical differences, and one,
  `dqn-flawed-hover-bonus/20261015-224318-dqn-hover-bonus-s0-custom-aefc`, an aggregate disagreement (mean
  original return 224.07 recorded, 230.45 on Linux), which remains blocking. On Windows it replays exactly.
  Its cause is not identified; a Windows trace for the Linux comparison is in `source/reports/neurocomputing-final-repairs-2026-11-03/dqn-diagnostic/`.
  Bit-identical results across operating systems are not a supported guarantee.
- **Platforms of this validation:** it has been run on the author's Windows machine. The full validator has
  not completed an uninterrupted Linux run with all 38 replays.
- **Not recomputed or distributed:** bootstrap intervals are not recomputed. The scheduled CartPole
  checkpoints are not distributed; the inventory lists them with their digests.
- **Provenance:** reward-definition provenance does not cover imported modules, module-level data or library
  versions.
- **Users:** no independent person has yet installed or used LunarLab.
