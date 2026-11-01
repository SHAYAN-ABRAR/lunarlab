# Visual review of the manuscript builds of 1 November 2026

The PDF was built by CI (`.github/workflows/paper.yml`: TeX Live 2025 on Ubuntu, pdfLaTeX and BibTeX). Local
TeX remains blocked by Smart App Control, which was not bypassed. Each page was read as the 100-dpi rendering
in the CI artifact. The guide is Neurocomputing's, with no page limit for articles; the JMLR 4-page limit does
not apply. No figure was added.

## Build 41346694714 of `28c811a`

20 pages (US letter). All 34 fonts embedded. No overfull box. One underfull box, in reference [5]'s URL
line, the same as in the two previous builds. No undefined reference or citation.

| Page | Contents | Finding |
|---|---|---|
| 1 | Title, author, AIUB affiliation and address, abstract (180 words), keywords, corresponding-author email | Correct. The closing rule of the frontmatter is on page 1. The new footer reads "Working draft, not submitted (November 1, 2026)" and gives the page number |
| 2 | Section 1; start of 2.1 | Citations [1]-[9] and "Section 4.1" resolve |
| 3 | Table 1 (revision `c9b9384`); Equation 1 | Correct |
| 4 | Figure 1 (architecture) and caption | Unchanged figure; all text legible |
| 5 | 2.2 continued; Equation 2; 2.3 | Correct |
| 6 | 2.3, 2.4 | About five lines left blank at the foot, because Section 3's headings and first lines do not fit there. Normal float and heading behaviour |
| 7 | 3.1, 3.2 | Correct |
| 8 | Figure 2 and caption; 3.2 continued | Correct |
| 9 | 3.2 end; Section 4; 4.1 | The new sentence on recording-platform labels begins at the foot |
| 10 | 4.1 continued; 4.2 | "Section 5.3" resolves twice; the revised limitation sentence reads correctly |
| 11 | Figure 3 and caption | Unchanged; consistent with the new sentence |
| 12 | 4.2 end; Section 5; 5.1 | The historical CI numbers of `c9b9384` are kept |
| 13 | Figure 4 and caption | Correct |
| 14 | Table 2; 5.1 end; 5.2 | The numbers and the loop/elapsed distinction are kept. "First, integrity", "Second, exact reproduction", "Third, outcome agreement" |
| 15 | 5.2 end ("Fig. A.1"); 5.3 | The validator sentences, with revision `954607b` |
| 16 | 5.3 end (the AI paragraph); Section 6 | Correct |
| 17 | Section 7; availability statement | Each revision named separately; the long `\path` breaks inside the margin |
| 18 | Availability end; Funding; competing interest; Acknowledgments | **Fault:** the "Appendix A" heading stands alone at the foot, with Figure A.1 pushed to page 19 |
| 19 | Figure A.1; references [1]-[3] | |
| 20 | References [4]-[12] | Reference [5]'s line is loosely spaced: the underfull box above |

The fixed declarations are verbatim: the self-funding statement, "The author declares no competing interests."
and the AIUB acknowledgment.

**Also in the log:** "destination with the same identifier (name{figure.1}) has been already used". The
appendix resets the figure counter, so Figure A.1 and Figure 1 shared a link anchor, and the link to Fig. A.1
could lead to Fig. 1. The warning appears twice in builds 40734273141 and 40736268713 as well: it predates
this work.

**Fixed in `d840f50`:**

- the appendix starts on a new page;
- `\theHfigure` gives appendix figures their own anchors.

## Build 41347005235 of `d840f50`

- **Pages and log:** 21 pages. All 34 fonts embedded; no overfull box. The one underfull box is reference
  [5] again. The duplicate-destination warning is gone.
- **Pages 1-17:** the 100-dpi renderings are byte-identical to those of the previous build (SHA-256
  compared), so the review above stands for them.

| Page | Contents | Finding |
|---|---|---|
| 18 | Availability end; Funding; competing interest; Acknowledgments | The rest of the page is blank, as intended before a new section |
| 19 | Appendix A heading, Figure A.1 and caption, references [1]-[3] | The heading is with its figure |
| 20 | References [3] continued to [12] | |
| 21 | The last two lines of reference [12] | **Fault:** a page holding only two lines |

**Attempted in `ea219fc`:** the page holding Figure A.1 and the first references takes two more lines
(`\enlargethispage`).

## Build 41347218412 of `ea219fc`

- **Pages and log:** 20 pages, 34 fonts embedded, no overfull box, no duplicate destination.
- **Pages 1-18:** byte-identical to the previous build.
- **Page 20:** holds references [4]-[12] completely.
- **Page 19, fault:** its last line ("29304-29320.", reference [3]) collides with the working-draft footer.
  The enlarged text area ran into the footer.

**Withdrawn in `a38d07f`:** its tree is identical to that of `d840f50` (`git diff d840f50 a38d07f` is
empty). The final layout is therefore build 41347005235's, of 21 pages, and the build of `a38d07f` is checked
against it below. The two-line last page is cosmetic: it is not an overflow beyond the margins. It goes when
the working-draft footer is removed or the journal typesets the article. A collision is not acceptable,
whereas a short last page is.

## Build 41347412905 of `a38d07f`: the final working draft

21 pages, US letter. All 34 fonts embedded. No overfull box; the one underfull box is in reference [5]. No
duplicate destination; no undefined reference or citation. The PDF's SHA-256 is
`ebd27ba80c0491f8590dd4fbbf25da4ca7f65f724ffd4b4e02b8420808850d2f`. All 21 page renderings are
byte-identical to those of build 41347005235 (SHA-256 compared), every page of which was read above.

| Item | Pages |
|---|---|
| Figures | Figure 1 on p. 4; Figure 2 on p. 8; Figure 3 on p. 11; Figure 4 on p. 13; Figure A.1 on p. 19 |
| Tables | Table 1 on p. 3; Table 2 on p. 14 |
| Cross-references read | "Section 4.1" (p. 2); "Section 5.3" twice (p. 10); "Fig. 3" (p. 9); "Fig. 4" (p. 12); "Fig. A.1" (p. 15); "Fig. 1" and "Fig. 2" (p. 16); "Table 1" (p. 3); "Table 2" (p. 12) |
| References | [1]-[12], pp. 19-21 |
| Working-draft footer | Every page |
