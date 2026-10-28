# Building the Neurocomputing manuscript

This directory is the repository's single Neurocomputing manuscript. Its editorial starting point is
`manuscript/main.tex` from the handoff package `LunarLab_Neurocomputing_Package (1).zip` (SHA-256
`b2addc8d2f8fab377974c14df3101f01c1636e02c75c75c5f8daeba98ab4dc37`). `IMPORTED_FROM_PACKAGE.sha256` lists the
digest of every imported file. The diff from that draft to this source is in
`reports/neurocomputing-2026-10-27/manuscript/main.tex.diff`. The older JMLR draft in `paper/jmlr-mloss/` is
historical and unchanged.

The source uses Elsevier's generic `elsarticle` class in preprint mode. `elsarticle.cls` and
`elsarticle-num.bst` are unmodified copies from CTAN's official distribution, generated from the vendor
archive whose SHA-256 is in `IMPORTED_FROM_PACKAGE.sha256`. They remain under their own licence. This class is
not asserted to be a Neurocomputing OSP-specific template; none was found on the captured official pages.

## Build

With TeX Live or MiKTeX installed, from this directory:

```sh
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

You need `main.tex`, `references.bib`, `elsarticle.cls`, `elsarticle-num.bst` and the figure PDFs under
`figures/`. `python check_manuscript.py --final` checks the abstract (at most 250 words), the keywords (1 to
7), the figure digests against `figures/MANIFEST.json`, the citations, the fixed author details and
declarations, and that no placeholder remains.

On the author's Windows machine, Windows Application Control (Smart App Control) blocks the unsigned Tectonic
binary, and no signed TeX distribution is installed. It was not bypassed. The PDF is therefore built by CI
instead: `.github/workflows/paper.yml` installs Ubuntu's TeX Live packages, runs the four commands above, and
fails on undefined references or non-embedded fonts. It records `pdffonts`, `pdfinfo`, the logs and a 100-dpi
render of every page as the artifact `manuscript`. The build log and page renders of the final revision are kept
in `reports/neurocomputing-2026-10-27/manuscript/`.

## Figures

`figures/build_figures.py` builds Figures 1, 3 and 4 and the appendix figure from the recorded data. It copies
Figure 2 byte for byte from `paper/jmlr-mloss/figures`, then re-derives each of its plotted values from
`docs/results/results.json`. `figures/MANIFEST.json` records the SHA-256 of every input and output, and each
figure has a `.values.json` of what was plotted. The new figures are drawn at the text width (390 pt, 5.39
inches) with text of at least 9 pt. Figure 2 was drawn at 6.0 inches with text of at least 10 pt and is scaled
to the text width, so its smallest text prints at 9.03 pt.

## Before submission

- The manuscript-preparation AI disclosure is kept separately, at the author's request, in
  `AI_Disclosure_For_Submission.tex`. Elsevier's policy requires it in the submitted manuscript: review it,
  then restore `\input{AI_Disclosure_For_Submission}` before the bibliography.
- The study archive has no DOI yet. Replace the availability statement with the real record once it is
  deposited.
- The OSP-specific fee and format conditions remain unresolved (`docs/neurocomputing/README.md`).
- **CRediT statement:** the guide requires one ("Corresponding authors are required to acknowledge co-author
  contributions using CRediT roles"). The manuscript has none yet, and the roles are the author's to state.
- **Highlights:** encouraged but optional. Give 3 to 5 bullets of at most 85 characters each, in a separate
  file.
- **Software revision:** the availability statement cites the review branch. After a merge and a release,
  cite the released revision instead.
