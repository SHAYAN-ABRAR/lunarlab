# Manuscript builds and page-by-page review

The manuscript is built by the `Manuscript (Neurocomputing)` workflow (`.github/workflows/paper.yml`):
TeX Live 2023 (Debian) pdfLaTeX and BibTeX, run as pdflatex, bibtex, pdflatex, pdflatex. Each build's PDF was
downloaded from the workflow artifact, every page was rendered at 100 dpi with `pdftoppm` and every page image
was read. The text logs of each build are kept here. The PDFs and page images are kept outside Git, in the
evidence folder and in the return package, with their SHA-256 digests.

## Build 1: commit 21ceb66, workflow run 40548348163

- **Logs:** `build-run-40548348163-21ceb66/`.
- **Pages and paper:** 19 US-letter pages.
- **Fonts:** all 34 embedded (`pdffonts.txt`).
- **References:** no undefined references or citations.
- **Layout warnings:** no overfull boxes. One underfull line, in the bibliography entry for RL Baselines3
  Zoo, where the URL breaks.

Problems found by reading the pages:

1. **Figure placement:** the figures used `[tb]` placement and are tall, so LaTeX deferred all five of them to
   the end. The references are on pages 13 and 14, and the figures follow on pages 15 to 19, one per page, far
   from the text that discusses them.
2. **Text size:** the new figures were drawn 6.0 inches wide but the text width is 390 pt (5.39 inches).
   Included at the text width, their 9-pt text printed at about 8.1 pt.
3. **Figure numbering:** the appendix figure was numbered "Fig. A.5". elsarticle's `\appendix` prefixes figure
   numbers with the appendix letter, but it does not reset the figure counter.
4. **Availability statement:** the statement placed the evidence "at revision 11145b3". That is the software
   revision; the evidence files were committed later, on the review branch.
5. **Figure 1 caption:** the caption named the check markers "red diamonds"; they are vermilion. The caption
   should not depend on colour.

Fixes:

- **Figures 1, 3, 4 and A.1:** redrawn at 5.39 inches, so their text prints at 9 to 10 pt. Labels and titles
  were shortened where the narrower width required it. The plotted values are unchanged; compare the
  `.values.json` files.
- **Figure 2:** still the historical figure, byte for byte. It was drawn at 6.0 inches with text of at least
  10 pt. At the text width that text prints at 10 × 390/432 = 9.03 pt.
- **Figure placement:** `[!tbp]`, with `\FloatBarrier` before the end matter and before the references.
- **Figure numbering:** the counter is reset after `\appendix`.
- **Availability statement:** it now names the review branch and says that it is neither merged nor released.
- **Figure 1 caption:** it says "Diamonds mark checks" and names no colour.
