# Manuscript builds of 3 November 2026 and their page-by-page review

The manuscript is built by CI (`.github/workflows/paper.yml`). Ubuntu's TeX Live 2025 runs pdfTeX 1.40.28 and
BibTeX 0.99d, then `pdflatex`, `bibtex`, `pdflatex` and `pdflatex` in turn. On the author's Windows machine,
Windows Application Control blocks the unsigned Tectonic binary, and no signed TeX engine is installed; neither
was bypassed. Each build's logs, `pdffonts`, `pdfinfo` and tool versions are in its folder here, with the
digests of its artifact (PDF, final log, bibliography and the 100-dpi page images). The PDFs themselves are in
the review package.

| Build | Source | PDF SHA-256 | Pages | Overfull boxes | Fonts |
|---|---|---|---|---|---|
| [41666276641](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/41666276641) | `db8f937` | `ab7f82c52765836901f72bfe3fb0d0a6940f3c813ca871257269e9da0d3554ad` | 22 | **2** (106.6 pt, 54.8 pt) | All 34 embedded |
| [41667322790](https://github.com/SHAYAN-ABRAR/lunarlab/actions/runs/41667322790) | `c0d9e5d` (the archive candidate's source) | `bbec5189c38a646054d0fef5e1c2b3ee5dbc4231ee1796a59cd488c2f51844a5` | 22 | 0 | All 34 embedded |

Both builds pass `check_manuscript.py --draft` (CI's first step), with no undefined reference or citation.
The draft check lists five AUTHOR TO CONFIRM items: two in `main.tex` (the CRediT roles, and the licence terms
of the models, records and text) and three in the AI declaration. They are printed in the PDF on purpose, so
that the draft cannot pass as final. `check_manuscript.py --final` fails on them and on the working-draft
footer, as it should.

## How the pages were inspected

Every page of build 41666276641 was rendered at 120 dpi (PyMuPDF) and read in full. Build 41667322790 changed
only two lines of source. Its pages were rendered the same way and compared pixel by pixel with the first
build: pages 1–17 and 20–22 are identical, and pages 18 and 19 were read again.

| Page | Content | Finding |
|---|---|---|
| 1 | Title, author, AIUB address, abstract (180 words), keywords, corresponding-author email | Correct, including lowercase `shayanabrar7@gmail.com`; footer "Working draft, not submitted" |
| 2 | Section 1; start of Section 2 | No fault |
| 3 | Table 1, Section 2.2 | The licence row wraps to three lines (MIT for the source code and documentation; copied third-party files keep their own licences) without overflow |
| 4 | Figure 1 and caption | The caption's new last sentence names Claude Code 2.1.299, the model and its role; the diagram is legible |
| 5–7 | Sections 2.2 to 3.2 | No fault |
| 8 | Figure 2 and caption; Section 3.2 | No fault |
| 9–10 | Sections 3.3, 4.1 | No fault |
| 11 | Figure 3 (a float page) | No fault; white space below the figure, as before |
| 12 | Sections 4.2, 5.1 | No fault |
| 13 | Figure 4 | No fault |
| 14 | Table 2, Section 5.2 | The new sentence on the 38 exports' exact Windows replay reads correctly |
| 15 | Section 5.2's new Linux-audit paragraph | Numbers as in `EVIDENCE.md`: 224.07 to 230.45, 6.38 [1.58, 12.77], 8 outcome changes, 230.25, 488 of 500 |
| 16–17 | Section 5.3 (the validator's narrowed checks, the 36 of 42 crashes, values versus bytes, the AI paragraph); Sections 6 and 7 | No fault |
| 18 | Code and data availability | **Build 1: one line ran 106.6 pt past the right margin** (`LunarLab_38_Policy_Study.zip` … `.tar.gz;`). **Build 2: fixed** (`\path` breaks the names); no overflow |
| 19 | End of availability; CRediT (an AUTHOR TO CONFIRM item); Funding; competing interests; Acknowledgments | **Build 1: the CRediT line ran 54.8 pt past the margin.** **Build 2: fixed.** The funding, competing-interest and acknowledgment sentences are exactly as fixed by the author; the rest of the page is white because the appendix starts on a new page, by design |
| 20 | Appendix A with Figure A.1; the AI declaration begins | The declaration follows the appendix and comes immediately before the references, as Elsevier's policy asks; its AUTHOR TO CONFIRM items are visible |
| 21 | End of the declaration; references 1–7 | No fault |
| 22 | References 8–12 | No fault |

Page 22 holds the last five references and white space. No `\enlargethispage` is used (it collides with the
draft footer). Nothing is cut, clipped or overlapping, and no figure label is unreadable.

Not checked here: how the pages look in the journal's own production class. The draft uses `elsarticle` in
preprint mode, which is not the journal's typeset layout.

## Local build with Tectonic (after the author turned off Windows Application Control)

**Executed** later on 3 November 2026. The author turned off Windows Application Control, which had blocked
the unsigned Tectonic binary, so the manuscript could be built on the author's machine for the first time.

- **Source:** `git archive c0d9e5d paper/neurocomputing`, the same source as CI build 41667322790.
- **Engine:** Tectonic 0.17.0, a XeTeX engine with its own TeX bundle, which ran BibTeX automatically.
- **Result:** exit 0 (`local-tectonic-c0d9e5d/build.log`, `main.log`, `main.blg`). The output has 22 pages,
  as in CI, and all 34 fonts are embedded. Its PDF SHA-256 is `f4cdd11a…44ea`; the PDF itself is not
  committed.

**Not identical to the CI build.** Under XeTeX, four lines run past the right margin, by 12.0 pt on page 6,
9.7 pt on page 18, 5.1 pt on page 2 and 1.2 pt on page 21 (`margins.json`, measured against the CI build's
widest line). The log reports five overfull boxes, at source lines 60, 121 (twice), 217 and 231. These are
paragraphs that pdfTeX sets within the margin, because `microtype`'s font expansion works only under pdfTeX.
CI's pdfTeX build, which `BUILD.md` declares, has none. Page 6 was rendered and read: the worst line, in
Section 2.4, protrudes visibly.

Nothing was changed for this: the source is not tuned for a second engine. If the submission system compiles
with XeLaTeX, these five paragraphs would need a reflow; with pdfLaTeX they need nothing.
