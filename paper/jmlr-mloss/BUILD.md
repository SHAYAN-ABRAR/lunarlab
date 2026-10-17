# Building the JMLR-MLOSS manuscript

## Requirements

A LaTeX distribution with `pdflatex` and `bibtex` (TeX Live or MiKTeX). Packages: the official JMLR style
`jmlr2e.sty` (which loads `natbib`, `graphicx`, `amssymb`, `epsfig` and `hyperref`), `lastpage` and `booktabs`.

The style file is **not** stored here: its repository (<https://github.com/JmlrOrg/jmlr-style-file>) declares no
license. Fetch the exact revision this manuscript was prepared with; the script refuses a file whose SHA-256
differs, and the style must not be modified (JMLR: "Papers not in the JMLR style file will be rejected without
review").

```powershell
.venv\Scripts\python.exe paper\jmlr-mloss\fetch_style.py      # jmlr2e.sty @ f413f638…, SHA-256 a430a875…
.venv\Scripts\python.exe paper\jmlr-mloss\check_manuscript.py # title-page limits, citations, figures, TODOs
cd paper\jmlr-mloss
pdflatex main ; bibtex main ; pdflatex main ; pdflatex main  # or: latexmk -pdf main
```

## Status on the preparation machine (2026-10-17)

- No LaTeX engine is installed, so **the PDF has not been built and the four-page limit has not been verified**.
  `check_manuscript.py` passes: abstract 189 words (limit 200), running title 38 characters (limit 50), five
  keywords, 16 citations all present in `references.bib`, all figures present, all cross-references defined;
  about 1,200 words of body text with two figures and one table.
- The manuscript contains `\TODO{…}` markers for information only the authors can provide (author list,
  affiliation, e-mail, release tag, acknowledgements and the funding and competing-interests declaration);
  nothing has been filled in on their behalf. The test count and coverage are the measured final values.

## Figures

`figures/` holds PDF (vector), SVG and PNG versions made by `python tools/paper_figures.py` from committed data:

| Figure | Kind | Source |
|---|---|---|
| `workflow` | conceptual diagram (no data) | drawn by the script |
| `reward_accounting` | measured: training episodes of the published study (15 PPO runs) | `reports/jmlr/figures/reward_accounting.csv` (derived with `--derive` from the runs' `episodes.csv`, whose SHA-256 digests are in `reward_accounting.sources.json`) |
| `overhead` | measured: overhead benchmark | `reports/jmlr/benchmarks/standard-2026-10-17T154705+0000/raw.jsonl` |

`reports/jmlr/figures/manifest.json` records how each figure was made. Fonts are embedded as Type 42 (PDF) and
text stays text (SVG); figure text is at least 7 pt at the printed size (JMLR asks for at least 9 pt in
illustrations: check this in the built PDF and enlarge if needed).

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
