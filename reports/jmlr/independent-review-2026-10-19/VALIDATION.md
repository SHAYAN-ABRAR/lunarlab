# Independent validation record

Review date: 19 October 2026. Base: `67440c664f658ccd589f7198ee2182d5820ca7c1`. The working code and paper are local, uncommitted revisions. No historical checkpoint or evaluation was changed and no new scientific training study was performed. Tiny training workloads were executed by software tests.

## Source and historical integrity

- The supplied ZIP's 758 tracked files match GitHub blob identities. `source_verification.json` records the check; ZIP SHA-256: `37f787bc2479b574f57586b9431dde25b288a72f1d635627cbb53fb08271e6e5`.
- All nine payload files in the three distributed artifact packages match their manifests. This verifies distributed bytes, not the validity of an entire experiment.
- `preservation.json` records 502 supplied historical files compared between immutable source and working copy; every file remains byte-identical.
- Of 1,667 entries in the older integrity manifest, 393 are present: 391 match exactly and two differ only by LF/CRLF line endings (conversion reproduces the recorded hashes). The other 1,274 files are absent. The earlier report of approximately 1,699 protected files cannot be independently verified from this ZIP.

## Published CI, inspected separately

[GitHub Actions run 39147464434](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/39147464434) at the exact public base revision reports all six jobs successful: Linux 489 passed/4 skipped; Windows Python 3.12 and 3.13 each 298 targeted tests passed; fresh-source installation 199 passed; browser tests 15 passed. Published Linux coverage is approximately 86% combined statement/branch coverage. These are published results for the base revision, not locally executed validation of this new patch.

## Executed in this review environment

An isolated Python 3.12 environment was installed from the repository CI lock, with CPU PyTorch and the working source installed editable. Package versions are embedded in the three re-evaluation reports. This Linux execution environment restricts process inspection/lifecycle behavior; no process-ownership safeguards were disabled to get a green result.

| Execution | Result | Evidence |
|---|---|---|
| Initial full-suite attempt | 433 passed, 51 failed, 9 skipped | `logs/local_tests.xml`, `.log` |
| Revised full-suite attempt | **479 passed, 7 failed, 9 skipped** | `logs/revised_tests.xml`, `.log` |
| First focused reporting/benchmark run | 15 passed, 1 failed | `logs/focused_tests.xml`, `.log` |
| Focused reporting and memory-scope regression run | **15 passed, 1 existing multiprocess benchmark deselected** | `logs/reporting_regressions.xml`, `.log` |
| Documentation and metadata checks | **121 passed** | `logs/documentation_tests.xml`, `.log` |
| Separate diagnostic training-test retry | 1 passed | `logs/diagnostic.log` |

The full-suite rerun removed proxy variables for localhost tests. Remaining failures were live-worker adoption (`psutil.NoSuchProcess`), supervised resume timeout, process-discovery subprocess timeout, the three-worker overhead benchmark (`psutil.NoSuchProcess` in a child), parallel worker exit failures, termination/recovery timeout and server lifecycle timeout. Nine skips comprise five checks requiring a git checkout and four Windows-specific checks. The source is a ZIP, without `.git`.

Process inspection failure is directly observed in some failures; not every timeout is conclusively diagnosed. **The local full suite is not green.** These failures must be resolved or shown to pass on a normal supported system before integrating the patch. Previous public green CI does not validate uncommitted changes.

The focused memory-scope regression executes a real small PPO workload and verifies that process peak memory is sampled before optional recording. It does not rerun the standard performance benchmark. The existing multiprocess benchmark was deselected only in the focused follow-up, after its failed attempts were retained above.

Local full-suite combined coverage was 83.455%: 7,951/9,216 statements and 1,643/2,280 branches covered. See `logs/revised_coverage.json`. This incomplete local run does not replace the separately reported CI scope. No browser suite, Windows suite or fresh-source installation suite was executed locally during this review; their results above come from GitHub Actions.

## Recomputed and re-evaluated scientific evidence

`evidence.json` independently recomputes policy counts, IQMs, landing/time-limit counts, benchmark ratios and available-file hashes. `iqm_ci_verification.json` independently recomputes all ten groups' stored IQM intervals using 5,000 training-run bootstrap resamples. These checks use committed summaries; they do not recover all 3,800 raw episodes.

All three distributed policies were independently evaluated on their 100 recorded final-test seeds, without retraining. Artifact integrity passed for each; all three evaluations returned numerical-difference status (exit 3), with zero exact matches over the five compared episode-summary fields. Original-return means were 265.861546 for PPO baseline, -20.765847 for PPO hover, and 156.868713 for DQN baseline. Strict landing rates were 96%, 0% and 29%. Reports and paired confidence intervals are in `local-ppo-baseline.json`, `local-ppo-hover.json` and `local-dqn-baseline.json`.

These local executions are distinct from the published Linux CI run. In particular, its DQN mean was approximately 156.8764. Similar aggregate observations do not establish statistical equivalence, trajectory identity, or portability of the other 35 policies. See `docs/jmlr/REPRODUCIBILITY.md` for scale-specific maximum discrepancies and trace interpretation.

## Manuscript verification

The revised manuscript compiles with pdflatex/BibTeX through latexmk using the pinned, unmodified official JMLR style. It has four description pages and one reference page, 149 abstract words under the source checker, five keywords and 11 cited references. The final log has no overfull boxes or unresolved citations/references. The figure is included at its natural 6-inch width, with minimum 9-point labels. All five pages were rendered and visually inspected; the final corrected pages were re-rendered and checked.

Three author-input markers remain. This is a verified review draft, not a completed submission. See `paper/jmlr-mloss/BUILD.md`, `manuscript_qa.json`, `logs/manuscript_build.log` and `logs/manuscript_check.log`. After completing author fields, rebuild and inspect pagination again.

## Gates not completed here

Final supported-platform validation of the new patch; a corrected standard memory benchmark; fresh-source installation of the final integrated revision; inspection of the 35 missing raw study packages; independent-user exercises; human declarations and conflict checks; and final source/release identity. These are outstanding work, not implied successes. No commits, pushes, releases, submissions or outside contacts were performed.
