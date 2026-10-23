# Manuscript scientific-claims audit

Independent revision: 19 October 2026. Inspected public base: `67440c664f658ccd589f7198ee2182d5820ca7c1`. The manuscript is a revised description, not proof that its local code patch has been published. Paths below are repository-relative; historical files were not altered.

| Major claim | Evidence | Verification and limits |
|---|---|---|
| MIT source, version 0.1.0 | `LICENSE`, SPDX source headers, `lunarlab/__init__.py`, `CITATION.cff` | Direct inspection; public release/tag not asserted |
| Reward identity and per-step computation | `rewards/terms.py`, `rewards/wrapper.py`, `rewards/accounting.py`; reward/property tests | Direct code inspection and tests. Episode totals persist by default; full traces optional |
| Potential shaping and terminal semantics | `rewards/terms.py`, wrapper, `tests/test_properties.py`, generic-audit tests | Conditional policy-invariance theory; no claim of improved finite-budget learning |
| Validation-based selection; test seed separation | `config.py::EvalProtocol`, training callback, `evaluation.py` | Source inspection; original reward used for selection/evaluation. Human test-informed redesign remains possible |
| Protected final-test identity | `freeze.py`, frozen-copy and tampering tests | Digest/immutable-copy contract; no claim of adversarial-proof storage |
| DQN replay and learning-state restoration | `continuation.py`, `training.py`, DQN continuation tests | Environment/RNG restoration incomplete; not bit-identical uninterrupted training |
| Local interfaces and generic API | CLI, `server/`, `frontend/`, `audit/`, `examples/cartpole_audit.py` | Full application LunarLander-specific. CartPole demonstrates only generic audit layer |
| Revised source: 489 Python tests, 86% coverage, 15 browser tests; fresh source-archive installation | `reports/jmlr/original-machine-2026-10-19/VALIDATION.md` (Windows 11, Python 3.12.13) | Executed locally on the original machine on the uncommitted revision; CI has not run on it. The release-test count is the one measured for the final candidate archive |
| Public CI at base `67440c6` | GitHub Actions run 39147464434 | Linux 489 pass/4 Windows skips; each Windows job 298 targeted pass; source install 199; Playwright 15. Base revision only, not the revised source |
| Approx. 86% coverage | Linux coverage report in that CI; prior detailed report under `reports/jmlr/coverage/` | Combined statement/branch measure, not proof of correctness |
| Primary 20-policy PPO design | `docs/results/results.json` group records; configs in demo summaries | Five runs/design, actual training budget 1,003,520; selected checkpoint may be earlier |
| IQMs 268.6, 265.3, 262.3, −33.1 | `docs/results/results.json` per-policy means and `robust_stats`; independent verifier | Independently recomputed trimmed means; 95% intervals reproduced from run-level inputs; raw episode audit limited |
| Landings 488/500, 468/500, 470/500, 0/500; hover 400/500 timeouts | Each policy's rate and count in `results.json` | Reconstructed integer counts; not an independent reread of every raw final-test episode |
| Hover mean training return 496.3 vs original −23.5 | Group `training_return_rescored_mean` and `mean_original_return` | Final-test rescoring, not end-of-training rolling returns; reward scales intentionally differ |
| No demonstrated shaping improvement | Stored improvement-probability intervals [0,.72] and [0,.76] | Contain .5; no equivalence claim. Five seeds and fixed test-seed conditioning acknowledged |
| 38 policies / 3,800 main final-test episodes | Sum over 10 groups in `results.json` | Summary count only; separate robustness records are not added |
| All 38 exported; every summary recomputed from their episodes | `reports/jmlr/original-machine-2026-10-19/study-artifacts/` (inventory, SHA-256), `study_summary_comparison.json`; `tools/export_study_artifacts.py`, `tools/compare_study_summaries.py` | Byte-identical copies of the recorded checkpoints, configurations and evaluations; 38/38 policies and all ten group IQMs match. Not re-evaluated; bundle supplied for review, not yet publicly archived (marker in the paper) |
| Three distributed complete examples | `examples/artifacts/*/{artifact.json,config.yaml,evaluation.json,checkpoint.zip}` | Nine payload hashes checked; only these three policies independently re-evaluated here |
| Windows 300 exact selected-field matches; Linux 0 | Published reproduction logs and committed CI reports; recording-machine repeat with the revised source in `reports/jmlr/original-machine-2026-10-19/reevaluation/` | Fields explicitly enumerated; no full-trajectory guarantee. The recording-machine repeat: 300/300 exact, nine reference traces identical |
| Linux means and return maxima | `reports/jmlr/reproducibility/ci/run-39144191758-4fd30db/linux/`; latest logs | Original max .277, 11.9, ~192; hover training-return max ~126 is a different metric |
| Independent Linux repeat | `reports/jmlr/independent-review-2026-10-19/local-*.json` | DQN mean 156.8687 vs CI 156.8764; distinguish executions |
| Simulator-numerics hypothesis | Nine committed divergence trace reports and Windows perturbation experiments | Supports a mechanism class on sampled traces, not a unique Box2D/compiler cause |
| Table 1: throughput, ratios 1.021/1.053/1.221, peaks 310/310/314 MB | `reports/jmlr/benchmarks/standard-2026-10-19T180346+0000/` (`raw.jsonl`, `summary.json`, `source_state.json`); recomputed in `reports/jmlr/original-machine-2026-10-19/benchmark_recomputation.json` | Base `67440c6` plus the uncommitted review changes (training path unchanged since `2c41b42`); three repetitions, one Windows machine; no universal bound. Every configuration's peak is sampled before optional replay generation |
| Earlier benchmark, no longer in the paper | `reports/jmlr/benchmarks/standard-2026-10-18T132206+0000/` | Clean `2c41b42`; ratios 1.002/1.056/1.228; its 323 MB full-workflow peak included optional replay generation. Unchanged |
| Historical integrity | `reports/jmlr/original-machine-2026-10-19/integrity_claims_check.json`, `historical_manifest_check.json` | On the original machine all 1,667 listed files are byte-identical; the correction-pass count was 1,708, misreported as 1,699 |
| Broader studies and limitations | `docs/RESULTS.md`, result groups, preferences code | Unequal DQN budget; simulated labels/validation access true reward; no human study established |
| Related-software comparison | `docs/jmlr/RELATED_SOFTWARE.md` and `COMPARISON_EVIDENCE.md` | Primary docs/papers. Integration, not exclusive ownership of component features |

## Figure and numerical derivation

`build_audit_figure.py` reads only `docs/results/results.json` and writes `figures/final_test_audit.pdf`, SVG, PNG and a SHA-256 source manifest. Points represent five policies, each evaluated on the same fixed 100 test seeds. The diamond in (a) is the IQM with the recorded 5,000-resample, 95% run-bootstrap interval; the diamond in (b) is the mean landing rate. Zero observed landings is not zero population probability.

The new figure replaces the learning-curve figure whose 15 raw training CSVs are not included in this source snapshot. The old figure and derived historical data are preserved. No trajectory, checkpoint or training result was changed.

On 20 October 2026 panel (b)'s title was shortened from "Per-policy rate and mean" to "Per-policy rate, mean": the longer title ran 0.06 inch past the figure's right edge and was visibly cut off in the compiled PDF. Data, geometry and fonts are unchanged; the regenerated figure is deterministic (PDF SHA-256 `8acde7dcedd717b00b02a6667d48837690bfbd72e1b6971bde90fdd2ca922756` on two consecutive builds) and the source manifest is identical.

### Stacked redesign, 22–24 October 2026

Figure 1 now has two stacked, full-width panels (see `BUILD.md`). Circles are offset vertically only where they would touch, so they are no longer jittered. Every plotted quantity is a stored value from `docs/results/results.json`:

| Element | Source in `results.json` | Verification |
|---|---|---|
| Circles in (a) | `groups[*].per_seed[*].evaluation.mean_original_return` (identical to `robust_stats.groups[*].run_scores`) | Plotted x equals the stored value exactly |
| Circles in (b) | `groups[*].per_seed[*].evaluation.pad_landing_rate` (stored 0–1 scale; ticks show percent) | Exact |
| Diamond and bar in (a) | `robust_stats.groups[*].iqm`, `iqm_ci` | Exact; bar endpoints are drawn from the stored values |
| Diamond in (b) | `robust_stats.groups[*].pad_rate_mean` | Exact |

The figure manifest records each plotted value with its seed and run ID, plus the lanes and axes geometry. An independent read-back of all 56 marker and interval positions from the rendered SVG agrees with the stored values within 5.4e-7 return units and 1.3e-9 rate units. The input's SHA-256 (`35dcd0f9…`) equals the committed blob at HEAD and the digests recorded by the two previous figure versions. No raw episode was reconstructed, nothing was smoothed, and no new data were created.

## Author revision of 21 October 2026 and length edits

The author revision supplies the affiliation, postal address (AIUB's official contact page) and email, the institutional-support and funding-management acknowledgment, the `preprint` option and the positive contribution wording; see `reports/jmlr/author-revision-2026-10-21/AUTHOR_REVISION.md` in the 21 October package. Its sentence "six learned-reward exports still need two original reward models before replay" comes from that package's independent follow-up (`REQUIRED_REWARD_MODELS.json`); it was not re-verified in this figure task, and the follow-up's dependency patch is not applied here.

To keep four description pages with the taller figure, the reward identity is set inline (same formula), and sentences were merged or reworded in the introduction, the workflow paragraphs, the related-software, testing and runtime paragraphs, the Table 1 caption, Section 4 and the re-evaluation paragraph. Every number, citation and limitation is unchanged: the policy-invariance caveat; the test-exposure limit; non-bit-identical continuation; LunarLander scope; benchmark measurements, not bounds, with the memory scope; exploitation shown only under the studied configuration; improvement not established; the learned-reward, DQN-budget and simulated-label limits; no equivalence from paired tests; no unique compiler cause. The Figure 1 caption was rewritten for the new layout and keeps the five-seed and zero-landing qualifications.

## Learned-reward repair, 24 October 2026

The 22–24 October note above, that the 21 October dependency patch was not applied, is superseded: its
runtime, CLI, export, reporting and test changes are now integrated, without its manuscript or figure hunks.

| Statement | Evidence | Status in `main.tex` |
|---|---|---|
| The two original reward models exist and are unchanged | `reports/jmlr/learned-reward-repair-2026-10-24/reward_models_verification.json`: four files, sizes and SHA-256 equal to the historical manifest | Not stated |
| The six learned-reward exports bundle their models and replay exactly from an empty data home | `.../bundle_repair_comparison.json` (payload bytes unchanged for all 38) and `.../replay/` (600/600 episodes `exact`; three negative cases blocked with exit 1) | **Outdated:** the PDF still says the exports "still need two original reward models"; the correction waits for a rebuild (`BUILD.md`) |
| CI passed at `4116599` | `reports/jmlr/reproducibility/ci/run-40015498622-4116599/` | **Not yet cited:** the PDF cites CI at `67440c6`; same pending correction |

Exact replays on the recording machine show selected-field agreement on one platform. They do not show
cross-platform numerical agreement for the learned-reward packages, which has not been tested.

## Bibliography checks

The 11 citations used by this manuscript were checked against primary JMLR paper records (SB3, CleanRL), NeurIPS records (Agarwal, Skalse), AAAI (Henderson), original shaping paper, project documentation (Zoo), and arXiv records (Gymnasium, PPO, imitation, AI Safety Gridworlds). The published Skalse title is “Reward Gaming,” not the preprint's “Reward Hacking.” ArXiv entries now carry explicit printable venue identifiers/URLs; the previous BibTeX-only `eprint` field was not sufficient under the JMLR style. Gymnasium is cited by its 2024 arXiv record; its current record notes later NeurIPS 2025 acceptance. Legacy uncited entries remain but are not printed.

## Evidence not claimed

No independent community adoption, public availability or re-evaluation of all 38 models (they are exported and checked, not published or replayed), Linux or CI results for the revised source, new matched-budget algorithm results, universal platform identity, confirmed compiler cause, or guaranteed acceptance was established. The competing-interest declaration, the final source revision and the public study archive remain placeholders until supplied; the author identity, affiliation and acknowledgment are author-supplied (21 October 2026).
