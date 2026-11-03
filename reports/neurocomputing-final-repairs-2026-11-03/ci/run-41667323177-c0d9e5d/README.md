# CI of the candidate's source revision `c0d9e5d`

Run [41667323177](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/41667323177) concluded **success** in all
six jobs. The logs are the job logs as GitHub served them, with line endings normalized to LF. This is **CI
evidence**: it was run by GitHub, not on the author's machine.

| Job | Result |
|---|---|
| Python, Linux: lint and tests | 704 passed, 4 Windows-only skips (686 at `a38d07f`, plus this work's 18 new tests); coverage of 10,155 statements with 1,160 missed and of 2,596 branches, as before, since the library is unchanged |
| Windows, Python 3.12 and 3.13 | 294 targeted tests passed on each; reproducibility smoke test and artifact re-evaluation |
| Source archive | Built twice, byte for byte: 2,082 files, SHA-256 `c6cbdf69b00aaad03ad44495549500e7f1cecba7d7f3f598889130b5c53b0648`, **the same bytes as the Windows build** in the archive candidate (`../../archive/source-archive-c0d9e5d.log`). Installed fresh; 195 release tests passed (one more than before: the notice test) |
| Frontend | Typecheck, lint, build |
| Browser end-to-end | 15 flows passed |

The same push also ran two other workflows, and both succeeded:

- manuscript build [41667322790](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/41667322790), reviewed
  in `../../manuscript/VISUAL_REVIEW.md`;
- the Linux replay of the six learned-reward packages,
  [41667323024](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/41667323024).

The CI run on `db8f937` (41666276854) was cancelled by the next push, because the workflow cancels superseded
runs. Its manuscript build (41666276641) and learned-reward replay (41666276688) completed with success.
