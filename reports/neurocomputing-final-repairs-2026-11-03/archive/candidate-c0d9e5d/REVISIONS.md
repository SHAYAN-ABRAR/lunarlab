# Revisions

This candidate's `source/` is revision `c0d9e5d0823167584a7bff37de9661c35a58228c`. Earlier revisions produced the historical evidence, which
is preserved byte for byte, not regenerated.

| Revision | What it is | Where it is recorded |
|---|---|---|
| `32823f35fd1b4b7495701ee0afa5a766119248d4` | Trained the 38 LunarLander policies (15 October 2026) | `provenance/metadata.json` of every package (`system.git.revision`) |
| `41165997f9cda78bf30b26cf676b9db894c5d9e3` | Exported the 38 LunarLander packages | `artifact.json` of every package (`exported_with`) |
| `444a4c5dc086ec6eb844b408453bd571c034ad96` | Repaired the bundle by adding the six learned-reward models (24 October) | `lunarlander-study/lunarlab-0.1.0-444a4c5-src.tar.gz`; the bundle's `DEPENDENCIES.md` |
| `e7c3fabcc986ee66f56de6403f8772968559824d` | Ran the CartPole study and recorded the comparison fixtures (27 October) | `run.json` (`software.git.revision`) and each fixture's `recorded_platform` |
| `30bd3f64b392b73f5a8d64422b05d801ba281f71` | Library revision described by the 27 October manuscript | `source/reports/neurocomputing-2026-10-27/READINESS.md` |
| `c9b938446d26fd4890ecd7ff7e6099a319586ae8` | Library revision the manuscript describes: the last commit that changed library code (28 October) | `software/c9b9384/` (byte-identical to the Linux CI build of run 40712412847) |
| `98be27ac20b7b35bc82c8ec806edeffe2eee4efb` | `main` after the review repairs were merged (pull request #2; CI run 40755305285 passed) | GitHub |
| `954607b83853d3fbd1018b5992158f1c924ff0d5` | Validator revision: the follow-up comparison set and the repaired package validator (no library change) | `source/reports/neurocomputing-final-validation-2026-11-01/` |
| `a38d07f59f99dee53676b061955d25e8caef3e72` | Source of the archive candidate of 1 November 2026, audited on Linux on 2 to 3 November | `source/reports/neurocomputing-final-validation-2026-11-01/archive/CANDIDATE.md`; `source/reports/neurocomputing-final-repairs-2026-11-03/received/` |
| `05ca17f7308e4e0d34773371d1abe229ea6fdf0f` | `main` after pull request #3 merged the follow-up validation (2 November 2026; CI run 41471828824 passed) | GitHub |
| `298562ee3c86ecf989904e870075d00e8505297e` | Validator revision that keeps every installation log and adds the target-directory install (no library change) | `source/reports/neurocomputing-final-repairs-2026-11-03/` |
| `c0d9e5d0823167584a7bff37de9661c35a58228c` | This candidate's source: the library of `c9b9384`, the follow-up comparison programs and the package validator of `298562e`, with the manuscript source | `source/`; `software/c0d9e5d/` |

The manuscript PDF is built from `source/paper/neurocomputing/` by CI; the build run is recorded in
`source/reports/neurocomputing-final-validation-2026-11-01/README.md`.
