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
not asserted to be a Neurocomputing OSP-specific template; none was found on the captured official pages, and
on 30 October 2026 the journal confirmed that none exists. The two files are listed, with their LPPL terms, in
the repository's `THIRD_PARTY_NOTICES.md`; the MIT License does not cover them.

## Build

With TeX Live or MiKTeX installed, from this directory:

```sh
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

You need `main.tex`, `AI_Disclosure_For_Submission.tex`, `references.bib`, `elsarticle.cls`,
`elsarticle-num.bst` and the figure PDFs under `figures/`. `python check_manuscript.py --draft` checks the
abstract (at most 250 words), the keywords (1 to 7), the figure digests against `figures/MANIFEST.json`, the
citations, the fixed author details and declarations, and that no placeholder remains. It lists every
"AUTHOR TO CONFIRM" item and accepts them only while the working-draft footer is active; CI and the package
validator use it. `python check_manuscript.py --final` is the submission check: it also fails on any such
item and on the footer itself.

The reference build is CI's: `.github/workflows/paper.yml` installs Ubuntu's TeX Live packages, runs the four
commands above, and fails on undefined references or non-embedded fonts. It records `pdffonts`, `pdfinfo`, the
logs and a 100-dpi render of every page as the artifact `manuscript`. The build logs and page reviews are kept
in the dated report folders (latest: `reports/neurocomputing-final-repairs-2026-11-03/manuscript/`).

On the author's Windows machine, Windows Application Control (Smart App Control) blocked the unsigned Tectonic
binary until 3 November 2026, when the author turned it off; it was never bypassed. Since then Tectonic 0.17.0
(`tectonic main.tex`) builds the PDF locally, 22 pages like CI's. Tectonic uses the XeTeX engine, where
`microtype`'s font expansion is not available, so four lines run 1 to 12 pt past the right margin
(`reports/neurocomputing-final-repairs-2026-11-03/manuscript/VISUAL_REVIEW.md`). The pdfTeX build has none:
use `pdflatex`, or CI, for the PDF that counts.

## Figures

`figures/build_figures.py` builds Figures 1, 3 and 4 and the appendix figure from the recorded data. It copies
Figure 2 byte for byte from `paper/jmlr-mloss/figures`, then re-derives each of its plotted values from
`docs/results/results.json`. `figures/MANIFEST.json` records the SHA-256 of every input and output, and each
figure has a `.values.json` of what was plotted. The new figures are drawn at the text width (390 pt, 5.39
inches) with text of at least 9 pt. Figure 2 was drawn at 6.0 inches with text of at least 10 pt and is scaled
to the text width, so its smallest text prints at 9.03 pt.

## Before submission

Updated 3 November 2026. The submission files and their status are listed in `SUBMISSION_FILES.md`.

- **AI declaration:** a two-sentence declaration after the appendix, immediately before the references, where
  Elsevier's policy ("Policy updated June 2026", fetched on 3 November) places it. Section 5.3 has one Methods
  sentence, and Figure 1's caption names the model for the explanatory diagram. At the author's request of 3
  November, the tools are named by model and developer: Anthropic's Opus 5.5 and OpenAI's GPT-6, the latter
  as the author gave it. The review-and-responsibility sentence is the author's statement
  (`AI_USE_INVENTORY.md`).
- **CRediT statement:** confirmed by the author on 3 November 2026: sole author, twelve roles; Funding
  acquisition and Supervision are not claimed (`CREDIT_CHECKLIST.md`). AIUB's faculty are thanked for
  discussions and ideas.
- **Licences of the models, records and text:** an "AUTHOR TO CONFIRM" item in the availability statement
  (`reports/neurocomputing-final-validation-2026-11-01/archive/LICENSING_PROPOSAL.md`).
- **Availability and archive:** the journal confirmed that the GitHub link can be cited under data
  availability and that the repository should stay accessible to the handling editor during review
  (`docs/neurocomputing/README.md`). The statement therefore cites the repository and the revisions, and
  lists what is not yet public. A Zenodo deposit is optional; it is the way to make the 29 local-only
  LunarLander policies, the CartPole checkpoints and artifacts and the fixture policies downloadable. None
  is deposited, and no DOI exists.
- **Journal questions, answered:** "Software publication"; no publication fee under Subscription; open access
  optional, with a charge; no OSP template (30 October); no word or page restriction; written peer review and
  revisions, with no mandatory interview (3 November). No further inquiry is needed.
- **Highlights:** a draft is in `highlights.txt` (3 to 5 bullets, at most 85 characters each), awaiting the
  author's approval.
- **Software revision:** the availability statement names the described library revision (`c9b9384`, merged
  as `98be27a`), the follow-up validator revision (`954607b`, merged as `05ca17f`), the setup-log repair
  (`298562e`) and each experiment's recorded source state. After a release, cite the released revision.
- **Working-draft footer:** every page's footer reads "Working draft, not submitted". Remove the `draft` page
  style from `main.tex` only when the declarations, the licences and the author's approval are complete;
  `check_manuscript.py --final` fails until then.
