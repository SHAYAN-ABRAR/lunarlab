# Independent follow-up validation

Completed 21 October 2026. Base `67440c664f658ccd589f7198ee2182d5820ca7c1` plus the return's complete uncommitted patch. Full Linux tests concern that source before the additional dependency fix. Historical records were not changed.

## Full Linux execution

Runtime: Linux, Python 3.12.14, CPU PyTorch 2.14.1 and NumPy 2.5.4. Dependencies were reused from the earlier audit environment, not freshly installed from every lock-file pin. The reconstructed source was installed editable with `uv pip install --no-deps --no-build-isolation -e ...`.

Command: `python -m pytest -q --cov=lunarlab --cov-branch --cov-report=json:<coverage.json> --junitxml=<tests.xml>`, with inherited HTTP proxy variables unset for loopback checks. Retained execution: **473 passed, 7 failed, 9 skipped in 824.56 seconds**. Combined coverage: 82.71%. Exact results: `linux_test_summary.json`, `linux_tests.xml`, `linux_tests.log`. No failure is relabelled as a pass.

Failures involve process discovery, workers, supervision, benchmark workers, parallel jobs and server lifecycle. Observed traces show psutil unable to inspect a live child's PID and a benchmark worker's own PID before training. These support a runtime explanation for some failures, not proof of a single cause or a normal-Linux CI pass. No process-safety check was disabled. Five skips require Git checkout metadata, four require Windows semantics.

## Learned-reward dependency failure and local patch

A fresh-home `reproduce-artifact --episodes 1` attempt on supplied run `20261015-235940-custom-s0-standard-d28b` passes nine checks, then raises `FileNotFoundError` for reward model `rm-20261015-235939-rm-3000-cfd0`. No episode runs. Six configs use one of two absent models. `REQUIRED_REWARD_MODELS.json` records four original files, 58,250 bytes and historical expected hashes.

The additional patch bundles original model/metadata files, checks digests and ID, uses a disposable replay registry, clears the ID-only cache at both boundaries, and returns an explicit blocking report for missing/corrupt dependencies before evaluating. Legacy baseline packages remain compatible. The isolated-home context changes process-level state and is intended for CLI use, not simultaneous threaded reproductions.

Executed on the edited source: `python -m pytest -q tests/test_artifact_reward_dependencies.py tests/test_reproduce.py tests/test_reproduction_report.py tests/test_study_tools.py` -> **35 passed in 7.46 seconds**, including nine new cases. These cover exact export bytes, missing/corrupt source files, actual two-episode clean-home replay despite stale cache, incomplete/corrupt/incorrect-ID packages, and CLI/CI reporting. Small existing smoke trainings are software checks, not new study policies.

The patched preflight returns six `integrity-failure` reports, all with `evaluation_skipped: true` and zero episodes. This detects incomplete artifacts; it is not six successful reproductions.

## Independent recalculation and supplied logs

`verify_return.py` and `independent_verification.json` recompute 38-policy original/training means and landing/timeout rates, ten group IQMs and 3,800 accounting identities; verify 114 payload digests and checkpoint/freeze identity; match 425 archive files to reconstructed source; compare five historical figures; and recompute nine-row benchmark statistics with identical hyperparameters.

Supplied Windows records contain 489 passes and no failures/skips; coverage 88.52% statements, 74.78% branches, 85.80% combined. Browser/release logs report 15/189 passes. Three replay reports contain 300/300 matching five-field episode summaries and nine identical selected traces. These are inspected original-machine evidence, not this reviewer's executions on Windows, and they predate the dependency patch.

Older correction manifests show 1,708 unchanged entries, 74 changed, 21 added and zero removed. Available bytes cover only part of the committed 1,667-file historical manifest: 672 exact, two line-ending-only, 993 missing here, zero other differences. The separate original-machine 1,905-file preservation claim comes from supplied scans, not a new scan of the inaccessible Windows disk.

## Paper and outstanding gates

The updated source builds with pdfLaTeX via latexmk and the unmodified pinned JMLR style: four description pages plus one reference page, 149-word abstract, 45-character running title, five keywords, eleven resolved citations. All five pages were rendered and visually inspected, including figure titles and the benchmark. No overfull boxes or unresolved citation/reference warnings. A standard bold-small-caps fallback is cosmetic. `PDF_QA.json` identifies the PDF.

Changed Python files pass Ruff lint and format checks; generated API docs are current. Documentation tests: **110 passed in 5.24 seconds**. Final normal Linux/Windows CI, a fresh archive installation of the integrated release, stable source/study identities, independent-use evidence and human author inputs remain open. Focused test passes do not establish a final full-suite pass. No remote action, outreach or scientific retraining was performed.
