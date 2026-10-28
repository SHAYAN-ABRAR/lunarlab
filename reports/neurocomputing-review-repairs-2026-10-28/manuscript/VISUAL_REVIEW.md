# Manuscript builds after the review, and their page-by-page review

The manuscript is built by the `Manuscript (Neurocomputing)` workflow:

- **Toolchain:** TeX Live 2023 (Debian), pdfLaTeX and BibTeX.
- **Pages:** every page was rendered at 100 dpi and read.
- **Logs and digests:** each build's text logs and `SHA256SUMS` are kept here; its PDF and page images are
  in the review package.

The earlier builds (1 to 3) are reviewed in `../../neurocomputing-2026-10-27/manuscript/VISUAL_REVIEW.md`.

## Build 4: commit 8f1258d, workflow run 40734273141

| Check | Result |
|---|---|
| Logs | `build-run-40734273141-8f1258d/` |
| PDF SHA-256 | `b16b3cb39d28162826acbc439783e6a9989f459efcef28a994e8ef30aad48822` |
| Pages | 19 |
| Fonts | 34 of 34 embedded |
| References | no undefined references |

This build has the manuscript corrections A to G. The reading found four problems, all fixed in `a9e164d`:

1. **Margin overruns:** in the availability statement, the branch name and the repairs path ran up to 111 pt
   into the right margin, because `\texttt` cannot break. They now use `\path`, which breaks at `/` and `-`.
2. **Section 4.1 overrun:** one line overran by 4.4 pt; the sentence is rephrased.
3. **Section 4.1 title:** it still said "an independent SB3 workflow". It now reads "Comparison with a
   conventional SB3 evaluation and a separately implemented reference".
4. **Title block:** the longer abstract (191 words) pushed the title block's closing rule onto page 2. The
   abstract was trimmed to 180 words without dropping content.

## Build 5: commit a9e164d, workflow run 40736268713

| Check | Result |
|---|---|
| Logs | `build-run-40736268713-a9e164d/` |
| PDF SHA-256 | `c42cf90e1909defe28d1ac4ea95b49bc4b8f2bddb52a56e53e30789e5ed1964e` |
| Pages | 19 |
| Fonts | 34 of 34 embedded |
| References | no undefined references |
| Overfull boxes | none |
| Underfull boxes | one, the bibliography line with the RL Baselines3 Zoo URL |

All 19 pages were read.

- **Title block:** it ends on page 1.
- **Figure placement:** each figure follows its first mention.

  | Figure | Page |
  |---|---|
  | 1 | 4 |
  | 2 | 8, beside its discussion |
  | 3 | 11 |
  | 4 | 13 |
  | A.1 | 18, before the references |

- **Corrected passages:** each reads as intended:
  - the adapter scope;
  - the separately implemented reference;
  - which command runs which checks;
  - the finite-value contract;
  - the CartPole validation observation;
  - the CI numbers of `c9b9384`;
  - the revision identities in the availability statement, whose branch name now wraps at the slash.
- **Figure 1:** its header reads "Reusable core via task adapters (LunarLander, CartPole)", inside the panel.
- **End matter:** unchanged and as fixed: the author, AIUB address and lowercase e-mail address,
  self-funding, the exact competing-interest sentence and the AIUB acknowledgement.

No fault remains. Later commits change no manuscript source, so this is the current PDF.
