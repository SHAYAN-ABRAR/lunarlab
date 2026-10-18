# Building the JMLR-MLOSS manuscript

## Requirements

Either a LaTeX distribution with `pdflatex` and `bibtex` (TeX Live or MiKTeX), or the single-binary
[Tectonic](https://tectonic-typesetting.github.io/) engine (XeTeX; downloads the packages it needs on first use,
no installation). Packages: the official JMLR style `jmlr2e.sty` (which loads `natbib`, `graphicx`, `amssymb`,
`epsfig` and `hyperref`), `lastpage` and `booktabs`.

The style file is **not** stored here: its repository (<https://github.com/JmlrOrg/jmlr-style-file>) declares no
license. Fetch the exact revision this manuscript was prepared with; the script refuses a file whose SHA-256
differs, and the style must not be modified (JMLR: "Papers not in the JMLR style file will be rejected without
review").

```powershell
.venv\Scripts\python.exe paper\jmlr-mloss\fetch_style.py      # jmlr2e.sty @ f413f638…, SHA-256 a430a875…
.venv\Scripts\python.exe tools\paper_figures.py                # figures from the stored data (checks print size)
.venv\Scripts\python.exe paper\jmlr-mloss\check_manuscript.py # title-page limits, citations, figures, TODOs
cd paper\jmlr-mloss
pdflatex main ; bibtex main ; pdflatex main ; pdflatex main  # or: latexmk -pdf main
tectonic -X compile main.tex                                  # alternative: one command, same style file
```

## Status (2026-10-18)

- **Built** with Tectonic 0.17.0 (official Windows release, SHA-256 verified, run from a temporary folder with its
  package cache there; nothing installed system-wide). XeTeX uses Latin Modern, whose metrics equal pdflatex's
  Computer Modern, so the line and page breaks should match a pdflatex build; that has not been checked with
  pdflatex itself.
- **Pages:** the description (abstract to acknowledgements) fills pages 1–4; the references are on pages 5–6. A
  test with filler text showed room for about **three lines** beyond the current two-line acknowledgements
  placeholder; longer acknowledgements need cuts elsewhere.
- **Build log:** no overfull or underfull lines in the text (the only remaining warnings are vertical-spacing
  notes on float and reference pages), no undefined citations or references; PDF about 120 KB.
- **Figures:** drawn at the 6.0 in text width and included at natural size, so the printed text is the drawn
  text: at least 9 pt everywhere (`tools/paper_figures.py` refuses a figure wider than the text block, with text
  under 9 pt, or with text or boxes outside the canvas). Earlier versions were drawn 7 in wide with 6.5–9 pt text
  and scaled down, about 5.6–7.7 pt printed; that was corrected.
- `check_manuscript.py` passes: abstract within 200 words, running title 38 characters, five keywords, 16
  citations all present in `references.bib`, all figures present, all cross-references defined.
- The manuscript contains `\TODO{…}` markers for information only the authors can provide (author list,
  affiliation, e-mail, release tag, acknowledgements and the funding and competing-interests declaration);
  nothing has been filled in on their behalf.

## Figures

`figures/` holds PDF (vector), SVG and PNG versions made by `python tools/paper_figures.py` from committed data:

| Figure | Kind | Source |
|---|---|---|
| `workflow` | conceptual diagram (no data) | drawn by the script |
| `reward_accounting` | measured: training episodes of the published study (15 PPO runs) | `reports/jmlr/figures/reward_accounting.csv` (derived with `--derive` from the runs' `episodes.csv`, whose SHA-256 digests are in `reward_accounting.sources.json`) |

`reports/jmlr/figures/manifest.json` records how each figure was made. Fonts are embedded as Type 42 (PDF) and
text stays text (SVG); figure text is at least 9 pt at the printed size (checked when the figures are made). The
manuscript reports the overhead benchmark as a table; its figure stays with the benchmark data.

## Bibliography verification

Each entry of `references.bib` was checked on 2026-10-17 against:

| Key | Verified against |
|---|---|
| `raffin2021sb3` | citation metadata of https://jmlr.org/papers/v22/20-1364.html |
| `huang2022cleanrl` | citation metadata of https://jmlr.org/papers/v23/21-1342.html |
| `raffin2020zoo` | the citation requested in the RL Baselines3 Zoo README (github.com/DLR-RM/rl-baselines3-zoo) |
| `towers2024gymnasium`, `schulman2017ppo`, `amodei2016concrete`, `leike2017gridworlds`, `gleave2022imitation` | arXiv API (export.arxiv.org) records 2407.17032, 1707.06347, 1606.06565, 1711.09883, 2211.11972 |
| `mnih2015dqn`, `akiba2019optuna`, `henderson2018matters`, `bradley1952paired` | Crossref records of their DOIs (10.1038/nature14236, 10.1145/3292500.3330701, 10.1609/aaai.v32i1.11694, 10.2307/2334029) |
| `agarwal2021precipice`, `christiano2017preferences`, `skalse2022gaming` | citation metadata of their NeurIPS proceedings pages (proceedings.neurips.cc) |
| `ng1999shaping` | the ML Anthology record (mlanthology.org/icml/1999/ng1999icml-policy) |

Two deliberate details: Skalse et al. appear under their proceedings title ("Reward *Gaming*"; the preprint says
"Hacking"), and fields missing from the authoritative record (AAAI page numbers, Biometrika's last page) are
omitted rather than filled in from memory.

## What is submitted, and when

- **Submission:** the PDF (at most 5 MB) through https://jmlr.csail.mit.edu/manudb/, with the cover letter
  ([COVER_LETTER_TEMPLATE.md](COVER_LETTER_TEMPLATE.md)) and the link to the public repository.
- **After acceptance:** the LaTeX source and one archive of the source code, named by JMLR's convention (for
  example `jones03a-code.tar.gz`): build it from the release tag with
  `python tools/build_source_archive.py --rev <tag> --verify` and rename it.
