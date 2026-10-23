# LunarLab — independent JMLR-MLOSS readiness review

Reviewed 19 October 2026. **Readiness: 6/10. Do not submit yet.** This is an editorial judgment of readiness, not a 60% acceptance probability. JMLR-MLOSS remains a plausible and appropriate target. The software has substantial engineering safeguards; its evidence of independent usefulness is immature.

## Source and version actually reviewed

The uploaded `lunarlab-main.zip` is the public revision **67440c664f658ccd589f7198ee2182d5820ca7c1**, not the old `2c41b42` snapshot described in the handoff. All 758 tracked files match GitHub blob identities. ZIP SHA-256: `37f787bc2479b574f57586b9431dde25b288a72f1d635627cbb53fb08271e6e5`. GitHub was checked again on 19 October; HEAD was unchanged. The correction pass was committed as `4fd30db`, followed by the UI race fix at `38c9703` and author/version documentation at `67440c6`. No inaccessible correction branch is needed for this review. Public version is 0.1.0; no public release was found in the inspected release listing.

The accompanying working changes are **local, uncommitted revisions based on that source**. No remote source, historical result, checkpoint, or evaluation was modified. The patch must be reviewed and tested on its eventual submission revision; it must not be described as already merged or released.

## What is independently supported

| Evidence type | Finding | Limit |
|---|---|---|
| GitHub Actions logs, exact HEAD | [Run 39147464434](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/39147464434): all six jobs succeeded; Linux 489 passed/4 skipped; Windows 298 targeted tests each on Python 3.12 and 3.13; archive install 199; browser 15 | These are published CI results, not a claim that 493 tests ran on each Windows job |
| Source and stored summaries | 38 policy records, 100 final-test episodes each; the 20-policy primary PPO comparison uses 1,003,520 transitions/run | Only three complete re-evaluation packages are distributed; 3,800 raw episodes were not independently reconstructed |
| File hashing | All nine payload files in the three example packages match their manifests | Digests establish bytes, not simulator equivalence or validity of the original experiment |
| Independent summary calculation | IQMs, policy counts, landing counts, and benchmark timing ratios recomputed from committed inputs | Original training and most raw evaluations were unavailable |
| Re-evaluation on this Linux runtime | All three supplied policies were evaluated again on their 100 recorded seeds; integrity passes, summary-level exact equality fails, landing rates agree | One independent execution environment; no claim about the other 35 policies |
| Source inspection | Reward accounting, seed separation, checkpoint digests, DQN replay restoration, continuation limits are implemented | An audit and tests do not prove absence of defects |

Local execution details, including the initial runtime failures and subsequent reruns, are recorded in `reports/jmlr/independent-review-2026-10-19/VALIDATION.md`. Those records take precedence over an informal “all tests passed” assertion.

## Follow-up on the original machine, 19–20 October 2026

The review's `lunarlab-review.patch` was applied unchanged with `git apply` to `67440c6` (local branch `review/jmlr-2026-10-19`; nothing committed or pushed). Five of its files were then reformatted to pass the repository's ruff gates: three are syntactically identical to the review's, and the two new scripts produce identical outputs. The following was then executed on the Windows 11 machine that holds the original data home. The reviewer's 6/10 judgment above is not re-rated here. Records: `reports/jmlr/original-machine-2026-10-19/`.

| Gate | Result |
|---|---|
| Study artifacts | All 38 published policies exported with `export-artifact`, without retraining. Every exported checkpoint, configuration and recorded evaluation is byte-identical to the run's file, and every checkpoint is the one its freeze record names (`study-artifacts/INVENTORY.md`) |
| Published summaries | `lunarlab results` regenerated them: 0 published values changed, 0 fields missing, 267 fields added by newer code; all five result figures byte-identical. Recomputing from the 3,800 raw episodes: 38/38 policies and all ten group IQMs match (`STUDY_SUMMARY_COMPARISON.md`) |
| Python suite with coverage | Final candidate: 489 passed, 0 failed, 0 skipped; 85.8% combined statement and branch coverage. The first run, before the follow-up added four tests, gave 485 passed. The reviewer sandbox's seven failures and nine skips all pass here; in that sandbox psutil could not see the calling process itself (`VALIDATION.md`) |
| Frontend | Typecheck, lint and production build pass; installed packages match `package-lock.json`; Playwright 15/15 with Edge |
| Recording-platform re-evaluation | Three of three artifacts `exact` (300/300 episodes), nine of nine reference traces identical, `reproduce-smoke --training-determinism` passes |
| Benchmark, corrected memory sampling | New run `reports/jmlr/benchmarks/standard-2026-10-19T180346+0000/`: loop ratios 1.021 and 1.053, workflow ratio 1.221, peaks 310/310/314 MB measured over the same phases (`BENCHMARK_PROTOCOL.md`) |
| Historical integrity | All 1,667 files of the committed manifest byte-identical. The correction pass's "1,699 identical" was a miscount of 1,708, and those 1,708 are all still identical (`integrity_claims_check.json`) |
| Static gates | Ruff lint and format, generated API reference current, SPDX headers, manuscript checker |
| Manuscript | Test counts, Table 1 and artifact availability updated from these records. Builds with the unmodified official style: four description pages plus one reference page. A clipped figure title was fixed (`paper/jmlr-mloss/BUILD.md`) |

Still open: no CI or Linux run of the revised source, which needs a push (an author decision). The 38-policy bundle is not yet publicly archived. There is no independent-user evidence. Author declarations and the final source identity are missing. A pdflatex rebuild was not run; Tectonic reproduced the reviewer's pdflatex pagination on the unchanged source.

## Current status, 24 October 2026

The independent follow-up of 21 October rated readiness 7/10 and advised holding submission (`reports/jmlr/independent-followup-2026-10-21/`); that judgment is the reviewer's and is not re-rated here. Since then:

| Item | Status |
|---|---|
| Pushed source | `109cd88` (review integration and original-machine follow-up) and `41165997f9cda78bf30b26cf676b9db894c5d9e3` (the author's manuscript revision and the stacked Figure 1) |
| CI of `4116599` | Run 40015498622: all six jobs passed. Linux 485 tests passed and 4 Windows-only skipped, 85.68% combined coverage. Windows Python 3.12 and 3.13: 288 targeted tests each. 189 release tests from the source archive. 15 browser flows. Reproduction: Linux `numerical-difference`, Windows `exact`. Logs, coverage and reports retained in `reports/jmlr/reproducibility/ci/run-40015498622-4116599/` |
| Learned-reward dependencies (working tree after `4116599`) | The two original reward models (four files) match the historical manifest. The reviewer's dependency fix is ported for runtime, CLI, export, reporting and tests. All 38 policies were re-exported with unchanged payloads, and the six learned-reward policies replay exactly from an empty data home. Incomplete or corrupt packages block before evaluation. See `REPRODUCIBILITY.md` and `reports/jmlr/learned-reward-repair-2026-10-24/` |
| Local validation of that working tree | Windows 11: 498 Python tests passed, none failed or skipped (85.90% combined coverage; includes the nine new dependency tests). Ruff, generated API reference, SPDX headers and manuscript checks pass. Frontend typecheck, lint and build pass, and all 15 browser flows pass. The example packages remain `exact`. CI on this change runs after it is pushed |

Still open: the competing-interest declaration (author); a public archive, DOI or final release identity for the study bundle (author decision; none invented); independent-user evidence; and CI on the commit that contains the dependency fix. Also open is the manuscript rebuild. Two sentences in it, on the learned-reward exports and the CI revision, are now out of date, and the corrected text is ready. Windows Application Control now blocks the unsigned Tectonic binary, no other TeX engine is installed, and the four-page limit must be confirmed by a build, so the committed LaTeX still matches its 22 October PDF (`paper/jmlr-mloss/BUILD.md`).

## The decisive remaining risks

1. **No demonstrated independent research community.** The inspected repository has zero stars and forks, one reported contributor, and no documented independent use or citations. MLOSS explicitly asks for community evidence in the cover letter. There is no invented minimum user count, but this is a serious review weakness.
2. **The public study is only partially replayable.** Release the final-test JSONs, configurations, frozen-checkpoint manifests and preferably selected checkpoint bytes for all 38 policies. At minimum prioritize the 20-policy primary comparison. The summary is internally consistent; a summary is not the underlying experiment. *Follow-up: all 38 packages now exist and verify against the published summary. They are supplied for review; publishing them is the author's decision and still outstanding.*
3. **The contribution must earn significance through use.** Accounting, evaluation callbacks, preference learning and robust statistics already exist elsewhere. The credible contribution is an integrated, traceable workflow, primarily for LunarLander. Independent tasks completed by researchers would support that claim much more than another interface feature.
4. **Reproducibility language needed correction.** Exactness is over five summary fields. Cross-platform agreement is limited to three policies; non-significant paired tests are not equivalence tests. Trace evidence supports a simulator-numerics explanation, not an identified compiler cause.
5. **The benchmark has a memory-scope defect.** Historical full-pipeline memory was sampled after optional replay generation. A local patch moves that sample earlier. Historical data remain unchanged and the paper discloses the scope difference. Repeat the modest benchmark on the intended release version before claiming comparable training memory. *Follow-up: repeated on the revised source with the corrected sampling. The paper now uses that run. Repeat it if the submitted revision changes training code.*
6. **Human and release information is unfinished.** Author email/address/affiliation, funding, conflicts, overlapping publications, conflict-screened reviewer/editor choices and final source identity remain to be confirmed.

## What this revision changes

The manuscript now argues for an auditable evaluation/provenance workflow, compares related software fairly, reports the exact CI scopes, distinguishes per-transition computation from optional trace persistence, and separates integrity, exact matching and aggregate agreement. Its example figure is generated directly from committed per-policy summaries, with training-seed uncertainty disclosed. The local code patch clarifies reproduction reports and separates maximum original-return and training-return discrepancies; it also samples training-workflow memory before replay generation. Two targeted regression tests cover these changes. No new scientific training study was run.

## Editorial judgment

Engineering evidence is the strongest part of the submission. Novelty and demonstrated external usefulness are the weakest. The current project should not be called “submission-ready,” “guaranteed reproducible,” or “likely accepted” on the strength of a green CI run. A sound next submission decision requires genuine outside-use evidence, a reviewable study bundle, a clean final-version validation run, and completed author declarations. A small number of substantive independent reports can be useful evidence; superficial star collection cannot substitute for it.

See `SCIENTIFIC_REVIEW.md`, `SUBMISSION_CHECKLIST.md`, `REPRODUCIBILITY.md`, `BENCHMARK_PROTOCOL.md`, `COMMUNITY_EVIDENCE.md`, and `paper/jmlr-mloss/EVIDENCE.md` for the detailed basis.
