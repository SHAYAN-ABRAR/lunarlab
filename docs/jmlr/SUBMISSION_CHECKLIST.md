# JMLR-MLOSS submission checklist

In submission order. ✅ done and verified · ⬜ open (with who must do it). Details: [REQUIREMENTS_MATRIX.md](REQUIREMENTS_MATRIX.md).

## Before anything is submitted

- ⬜ **Review and commit this branch** (`research/jmlr-mloss-readiness`); nothing has been committed or pushed.
  *(maintainer)*
- ⬜ **Push and check CI** on GitHub: the extended workflow (coverage, Python 3.13 on Windows, source archive,
  reproduction reports) and the first Linux run of the new code have not run yet. Read the uploaded
  `reproducibility-linux` report: it shows whether the Windows-recorded artifacts re-evaluate identically on Linux.
  *(maintainer)*
- ⬜ **Confirm the license holder's name** in `LICENSE` and `CITATION.cff` ("Shayan Abrar", from the GitHub
  profile), and whether MIT should also cover the experiment data, figures and documentation (a CC-BY license for
  data and documentation is a common alternative). *(owner)*
- ⬜ **Choose the version** (for example `0.2.0`), set it in `lunarlab/__init__.py`, `CITATION.cff` and
  `frontend/package.json` (a test checks they agree), tag it, and build the archive:
  `python tools/build_source_archive.py --rev <tag> --verify`. *(maintainer)*
- ⬜ **Archive the release with a DOI** (optional; for example Zenodo) and add it to `CITATION.cff`. *(maintainer)*
- ⬜ **Enable a forum** (GitHub Discussions or a mailing list) if you want one for the openness criterion.
  *(owner: repository setting)*

## Evidence only real people can provide

- ⬜ **User community**: currently none (0 stars, 0 forks, 1 contributor on 2026-10-18). Collect real evidence —
  independent reproduction reports (`docs/jmlr/REPRODUCTION_REPORT_TEMPLATE.md`), external issues, users,
  citations — before submitting. *(authors)* See [COMMUNITY_EVIDENCE.md](COMMUNITY_EVIDENCE.md).
- ⬜ **Independent reproduction on Linux and another CPU** of the supplied artifacts. *(any user)*

## Manuscript (`paper/jmlr-mloss/`)

- ✅ Official style (fetched pinned and verified, not modified), structure validated by `check_manuscript.py`:
  abstract ≤ 200 words, running title ≤ 50 characters, five keywords, all citations verified.
- ✅ Every statement traced to evidence (`EVIDENCE.md`); figures made from stored data (`figures/`).
- ⬜ **Author list, affiliations, corresponding author's postal and e-mail address.** *(authors)*
- ⬜ **Acknowledgements and the funding and competing-interests declaration.** *(authors)*
- ⬜ **Build the PDF** (`BUILD.md`), check it is at most four pages without references, that figure text is at least
  9 pt, and that it is under 5 MB. *(authors; needs a LaTeX installation)*
- ⬜ Replace the `\TODO` markers (dates, editor and paper ID are assigned by JMLR). *(authors)*

## Cover letter (`paper/jmlr-mloss/COVER_LETTER_TEMPLATE.md`)

- ✅ MLOSS designation, license, project web address, keywords.
- ⬜ Version to be reviewed (tag, commit, archive digest). *(maintainer)*
- ⬜ Evidence of an active user community, with dates. *(authors)*
- ⬜ Previous overlapping publications (or "none"), co-author consent, conflicts of interest with action editors.
  *(authors)*
- ⬜ 3–5 suggested action editors (from JMLR's AE list) and 3–5 reviewers, each without conflicts, with reasons.
  *(authors)*

## Software (done in this branch, verified locally)

- ✅ MIT `LICENSE`, SPDX notice in every source file, generated third-party notices, `CITATION.cff`.
- ✅ One authoritative version; `python -m lunarlab --version` reports it with the source revision.
- ✅ Deterministic source archive without VCS or platform files; installed and tested in a fresh environment.
- ✅ Statement and branch coverage measured and reported (`reports/jmlr/coverage/SUMMARY.md`).
- ✅ Reproducibility: `reproduce-smoke`, three supplied published artifacts reproduced bit-identically on this
  machine, documented commands ([REPRODUCIBILITY.md](REPRODUCIBILITY.md)).
- ✅ Overhead benchmark against plain Stable-Baselines3 with raw data ([BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md)).
- ✅ Sourced comparison with related software ([COMPARISON_EVIDENCE.md](COMPARISON_EVIDENCE.md)).
- ✅ Task-adapter layer with a CartPole example ([EXTENDING_LUNARLAB.md](EXTENDING_LUNARLAB.md)).
- ✅ Tutorial executed by the tests; developer guide; generated API reference; contributing guide; issue forms.
- ✅ Historical experiment evidence verified unchanged (see the readiness report).

## Submit

- ⬜ Upload the PDF at https://jmlr.csail.mit.edu/manudb/ (register, log in, "submit manuscript") with the cover
  letter, stating the MLOSS section. *(corresponding author)*
- ⬜ After acceptance: LaTeX source and the code archive renamed to JMLR's convention (`<id>-code.tar.gz`); sign
  the release form for source code if asked. *(authors)*
