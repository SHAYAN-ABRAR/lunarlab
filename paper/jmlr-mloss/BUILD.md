# Building the revised JMLR-MLOSS manuscript

## Requirements and commands

Use a LaTeX distribution with pdflatex, BibTeX and latexmk, plus Python with NumPy and Matplotlib to regenerate the figure. The reviewed build used these tools and the unmodified official `jmlr2e.sty`, `lastpage` and `booktabs`. Tectonic was used for an earlier draft; the revised manuscript has not been tested with that engine.

The JMLR style is fetched separately because its upstream repository does not declare a license. `fetch_style.py` pins revision `f413f638b407af76074813f8f88a82a7a5a81e9d` and verifies SHA-256 `a430a875d561235951800e4e21d2631e18ddf0b369646ec276f43ea5080f27c3`. Do not modify the style to make the paper fit.

From the repository root:

```bash
python paper/jmlr-mloss/fetch_style.py
python paper/jmlr-mloss/build_audit_figure.py
python paper/jmlr-mloss/check_manuscript.py
cd paper/jmlr-mloss
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

The delivered source contains the generated figure, so the second command is only needed to regenerate it. For a standalone manuscript directory, run `python fetch_style.py`, `python check_manuscript.py`, then the latexmk command from that directory. Figure regeneration requires the unchanged repository input `docs/results/results.json`.

## Verified build, 19 October 2026

This is an uncommitted manuscript revision based on public source `67440c664f658ccd589f7198ee2182d5820ca7c1`. It is a reviewed draft, not a submitted or accepted paper.

| Check | Observed result |
|---|---|
| Description length | Four pages, including acknowledgements |
| References | One additional page; five pages total |
| Abstract | 149 words under the source checker |
| Running title | 45 characters |
| Keywords | Five |
| Cited references | 11; all resolve |
| Build log | No overfull boxes or unresolved citations/references |
| Figure text | At least 9 pt, included at its natural 6-inch width |
| PDF size | 213,642 bytes |
| Delivered manuscript PDF SHA-256 | `b7198ca9b3065cb27b8a67fe17b3483a7d4fb1a2c71bebe34e90f84b4d2291fe` |
| Visual inspection | All five pages rendered and inspected; changed pages re-rendered after the last layout correction |

PDF creation metadata may change its byte hash on a fresh build. The recorded hash identifies the delivered PDF; it is not a promise of byte-identical output across TeX installations.

Three explicit author-input markers remain: email, affiliation/full postal address, and funding/competing-interest declarations. Submission dates and editorial metadata are provisional. Complete these truthfully, rebuild, and check the four-page description again. Adding disclosures can change pagination.

## Follow-up build, 20 October 2026

After the follow-up on the original machine, the test-count paragraph, Table 1 (the new benchmark run), the study-artifact sentence, the recording-machine re-evaluation and the availability sentence were updated from `reports/jmlr/original-machine-2026-10-19/` (claims mapped in `EVIDENCE.md`). A fourth author-input marker, "[final source revision and public archive of the 38-policy bundle]", replaces the base-revision statement because neither exists yet.

The panel (b) title of `figures/final_test_audit.pdf` ran 0.06 inch past the figure's right edge and was visibly cut off ("…rate and mean" printed as "…rate and mear"), also in the delivered review PDF. `build_audit_figure.py` now uses "(b) Per-policy rate, mean"; data, geometry and fonts are unchanged and the output is deterministic.

No pdflatex installation was available, so this build used Tectonic 0.17.0 (XeTeX engine, Latin Modern fonts) with the unmodified pinned `jmlr2e.sty` (SHA-256 verified). To check that engine first, the unchanged reviewed source was built with it and compared with the delivered pdflatex PDF. Both have five pages with the same page breaks. The text differs only in ligature and accent encoding and one intra-paragraph line break. Page 4's text ends 13 pt lower under Tectonic, so Tectonic is the stricter test of the length limit. The revised source fills page 4 exactly as far as the unchanged source does under Tectonic, so the edits are length-neutral.

| Check | Observed result |
|---|---|
| Description length | Four pages, including acknowledgements; references on page five |
| Build log | No overfull boxes; no undefined citations or references. Bold small caps for the title fall back to bold, as under pdflatex with Computer Modern |
| Source checker | Abstract 149 words, running title 45 characters, five keywords, 11 citations resolve, four author-input markers |
| Visual inspection | All five pages rendered at 110 dpi and inspected; page 4 re-inspected after the figure correction, and all five pages again after the final counts were filled in |
| Follow-up PDF (Tectonic) | 91,373 bytes, SHA-256 `25668e183c368cece377589e604e1e80ef36e89f169c2ee37e3539c1eb289eab`; supplied in the review-return package. Creation metadata makes the hash build-specific |

Before submission, rebuild with latexmk/pdflatex as above, after filling in the author fields, and check the four-page limit again.

## Figure and bibliography provenance

`figures/final_test_audit.pdf` and `.png` are generated by `build_audit_figure.py` directly from the 20 primary PPO per-policy summaries in `docs/results/results.json`. The adjacent `.source.json` records input identity and calculation details. The plot shows five training runs per reward design, with 100 final-test episodes per run, and training-run bootstrap intervals. It does not reconstruct absent episode-level records or rerun training.

The legacy `workflow` and `reward_accounting` figures remain in the repository, unused by this revised manuscript. Their historical inputs and figures were not changed. The current figure avoids depending on unavailable original learning-curve CSVs.

The 11 cited entries were checked against primary sources: JMLR records for Stable-Baselines3 and CleanRL; the RL Baselines3 Zoo repository's requested citation; the Gymnasium, PPO, imitation and AI Safety Gridworlds arXiv records; NeurIPS proceedings for statistical evaluation and reward gaming; the original potential-based shaping paper; and the AAAI record for reproducibility. `EVIDENCE.md` and `docs/jmlr/RELATED_SOFTWARE.md` identify sources and comparison scope. Unused historical bibliography entries are retained and do not print.

## Submission preparation

The official description limit is four pages excluding references. The current PDF is below the author-guidance file-size limit. Follow `COVER_LETTER_TEMPLATE.md` and `docs/jmlr/SUBMISSION_CHECKLIST.md`; author declarations, source identity and community evidence still require attention. Build any final source archive from the actual reviewed revision using the existing archive builder. No submission, release, tag, commit or push is authorized by these instructions.
