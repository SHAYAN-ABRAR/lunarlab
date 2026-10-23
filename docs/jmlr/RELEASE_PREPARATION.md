# Local release preparation — no publication commands

These steps prepare reviewable artifacts. They do not authorize committing, pushing, merging, tagging, publishing, submitting or contacting anyone.

## Apply and inspect the local revision

Use a separate checkout/worktree at base `67440c664f658ccd589f7198ee2182d5820ca7c1`. Check for your own uncommitted edits first. The delivered `lunarlab-review.patch` contains text changes; the package also contains the complete replacement manuscript directory, including its generated figure. Run `git apply --check` before applying. Do not reset or overwrite unrelated work. A clean git worktree is required only for the later release-identity gate, not as permission to discard changes.

```bash
git status --short
git rev-parse HEAD
git apply --check /path/to/lunarlab-review.patch
git apply /path/to/lunarlab-review.patch
python tools/verify_publication_evidence.py --out review/evidence.json
python paper/jmlr-mloss/build_audit_figure.py
python paper/jmlr-mloss/check_manuscript.py
```

The figure builder creates the new PDF/PNG from unchanged committed summaries; it avoids manual binary patching. The text patch does not install build outputs or overwrite historical reports.

## Validate without changing historical evidence

Use the existing `requirements-ci.lock`, platform install guidance and CI commands. Run the complete Python suite, the documented tutorial, continuation/freeze/reproduction tests, frontend typecheck/build/lint and Playwright. Record actual outcomes rather than reusing prior counts. Execute all three example artifact re-evaluations and preserve exit 3 reports as numerical differences. Test a source archive installed into a fresh environment, including license/component notices and import/API access. The current review's validation record documents what was and was not executed here.

`tools/build_source_archive.py --working-tree` can prepare an honestly labelled uncommitted candidate in a git checkout. A final `--rev` archive must refer to a real reviewed revision after the author separately approves source integration. Do not pass HEAD while silently excluding uncommitted corrections.

```bash
python tools/build_source_archive.py --working-tree --out review/source-candidate
```

After an actual final revision exists, use its full SHA with the archive builder's `--rev` and `--verify` options. Compare repeated archive hashes and retain the manifest. Do not invent a release tag or DOI. Update `CITATION.cff`, manuscript and cover letter to the version actually supplied.

## Export the missing study evidence on the original machine

*Status, 19 October 2026: done for all 38 policies with `tools/export_study_artifacts.py`, which calls `export-artifact` for each run and verifies the copies; see `reports/jmlr/original-machine-2026-10-19/study-artifacts/`. The bundle has not been uploaded anywhere.*

The public ZIP does not contain most `runs/` data. It is unnecessary to resend another source ZIP. The minimum useful next input is a **study-artifact bundle from the original LunarLab data home**, not fresh training runs.

For each run listed in `docs/results/results.json`, export its frozen selected checkpoint, original recorded final evaluation, configuration and manifest into a new folder using the existing command:

```bash
python -m lunarlab export-artifact --run-id RUN_ID_FROM_RESULTS_JSON --out review/study-artifacts/RUN_ID_FROM_RESULTS_JSON
```

The IDs are enumerated in `reports/jmlr/independent-review-2026-10-19/evidence.json`. Begin with all 20 primary PPO policies; include all 38 if the paper claims the full study is replayable. Preserve original JSON and checkpoint bytes. Also include run metadata, checkpoint manifests and any source-version records. If using the former learning-curve figure, include the 15 original `episodes.csv` files behind it. The revised figure needs only the already available per-policy summaries, but full evidence is still important for the primary study.

Do not fabricate absent provenance. If an export refuses a legacy artifact, retain the refusal and source files and document the migration requirement instead of editing historical data to pass. Zip the new bundle, compute SHA-256, and provide it to the reviewer. No uploading or release publication has been performed here.

## Exact instructions for a local Claude Code follow-up

Review the delivered diff against base `67440c6`. Preserve every historical evaluation, checkpoint, experiment input and frontend feature. Apply the report-scope and pre-recording-memory patches and run their regression tests, then the supported-platform release gates. Export the existing 20-policy primary study (preferably all 38 policies) with `export-artifact`, without training new policies or changing old results. Repeat the small standard benchmark with the corrected memory sampling and retain all raw measurements. Regenerate API documentation if needed. Update only claims justified by these new outputs; keep equivalence and simulator-cause caveats. Supply a concise changed-file list, exact test results, archive/manifest hashes, and remaining author fields. **Stop before any commit, push, merge, tag, release, submission or outreach.**
