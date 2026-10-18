# JMLR-MLOSS submission checklist

In submission order. ✅ done and verified · ⬜ open (with who must do it). Details:
[REQUIREMENTS_MATRIX.md](REQUIREMENTS_MATRIX.md). State on 2026-10-18: the readiness work is on `main` at
`2c41b42` (CI run 39069730331: all six jobs passed); the corrections of the second pass are on the branch
`research/jmlr-mloss-corrections`, **uncommitted**.

## Before anything is submitted

- ⬜ **Review and commit the correction branch** (`research/jmlr-mloss-corrections`). *(maintainer)*
- ⬜ **Push and read CI.** New on this push: per-artifact reproduction statuses and the job summary, and the
  first Linux run of `trace-artifact --compare`, which locates where Linux trajectories part from the Windows
  traces and whether the difference starts in the simulator or in policy inference
  ([REPRODUCIBILITY.md](REPRODUCIBILITY.md)). Record its result there. *(maintainer)*
- ⬜ **Confirm the license holder's name** in `LICENSE` and `CITATION.cff` ("Shayan Abrar", from the GitHub
  profile), and whether MIT should also cover the experiment data, figures and documentation (a CC-BY license for
  data and documentation is a common alternative). *(owner)*
- ⬜ **Approve the release candidate.** Prepared: version **0.1.0**, the one every file already names
  (`lunarlab/__init__.py`, `CITATION.cff`, `frontend/package.json`; `tests/test_project_metadata.py` checks they
  agree). It has never been tagged or released, so no published version is reused. Provenance recorded before
  the release (`lunarlab 0.1.0 (source <commit> …)`) always names its commit. To release a different number, change
  `lunarlab/__init__.py`, `CITATION.cff` and `frontend/package.json` together. *(maintainer)*
- ⬜ **Tag and publish the release** — only after the CI run of the commit to be released has passed:

  ```bash
  git switch main && git pull --ff-only
  python tools/build_source_archive.py --rev HEAD --out dist --verify   # deterministic archive, fresh install, release tests
  git tag -a v0.1.0 -m "LunarLab 0.1.0"
  git push origin v0.1.0
  gh release create v0.1.0 dist/lunarlab-0.1.0-src.tar.gz dist/lunarlab-0.1.0-src.manifest.json dist/SHA256SUMS \
      --title "LunarLab 0.1.0" --notes "Release accompanying the JMLR-MLOSS submission."
  ```

  Then add `date-released` (and, once archived, the DOI) to `CITATION.cff`. *(maintainer)*
- ⬜ **Archive the release with a DOI** (optional; for example Zenodo). No DOI exists today. *(maintainer)*
- ⬜ **Enable a forum** (GitHub Discussions or a mailing list) if you want one for the openness criterion.
  *(owner: repository setting)*

## Evidence only real people can provide

- ⬜ **User community**: currently none (0 stars, 0 forks, 1 contributor on 2026-10-18). Collect real evidence —
  independent reproduction reports ([docs/REPRODUCING.md](../REPRODUCING.md)), external issues, users,
  citations — before submitting. *(authors)* See [COMMUNITY_EVIDENCE.md](COMMUNITY_EVIDENCE.md).
- ⬜ **Independent reproductions** on machines the authors do not control. *(any user)*

## Manuscript (`paper/jmlr-mloss/`)

- ✅ Official style (fetched pinned and verified, not modified); `check_manuscript.py`: abstract ≤ 200 words,
  running title ≤ 50 characters, five keywords, all citations verified.
- ✅ Every statement traced to evidence (`EVIDENCE.md`); claims corrected in the second pass (continuation,
  reproducibility, overhead, adapter scope).
- ✅ **PDF built** with Tectonic 0.17.0 (XeTeX engine): description on pages 1–4, references on pages 5–6, no
  overfull lines or undefined references, under 5 MB; figures drawn at the 6.0 in text width with all text ≥ 9 pt
  (checked by `tools/paper_figures.py`). About five lines remain free on page 4 for the acknowledgements.
- ⬜ Optionally confirm the page count with pdflatex (TeX Live or MiKTeX); see `BUILD.md`. *(authors)*
- ⬜ **Author list, affiliations, corresponding author's postal and e-mail address.** *(authors)*
- ⬜ **Acknowledgements and the funding and competing-interests declaration.** *(authors)*
- ⬜ Replace the `\TODO` markers (dates, editor and paper ID are assigned by JMLR). *(authors)*

## Cover letter (`paper/jmlr-mloss/COVER_LETTER_TEMPLATE.md`)

- ✅ MLOSS designation, license, project web address, keywords.
- ⬜ Version to be reviewed (tag, commit, archive digest). *(maintainer)*
- ⬜ Evidence of an active user community, with dates. *(authors)*
- ⬜ Previous overlapping publications (or "none"), co-author consent, conflicts of interest with action editors.
  *(authors)*
- ⬜ 3–5 suggested action editors (from JMLR's AE list) and 3–5 reviewers, each without conflicts, with reasons.
  *(authors)*

## Software

- ✅ MIT `LICENSE`, SPDX notice in every source file, generated third-party notices, `CITATION.cff`.
- ✅ One authoritative version; `python -m lunarlab --version` reports it with the source revision.
- ✅ Deterministic source archive without VCS or platform files; byte-identical on Windows and Linux for the same
  commit; installed and tested in a fresh environment (CI and locally).
- ✅ Statement and branch coverage measured and reported (`reports/jmlr/coverage/SUMMARY.md`).
- ✅ Reproducibility: `reproduce-smoke`; three supplied artifacts bit-identical on Windows (development machine and
  CI, Python 3.12 and 3.13); on Linux numerically different per episode, aggregates unchanged; integrity,
  within-platform, cross-platform and conclusion stability reported separately, and never hidden in CI.
- ✅ Overhead benchmark against plain Stable-Baselines3 on a clean checkout, loop and full wall clock reported
  ([BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md)).
- ✅ Sourced comparison with related software ([COMPARISON_EVIDENCE.md](COMPARISON_EVIDENCE.md)).
- ✅ Task-adapter layer with a CartPole example ([EXTENDING_LUNARLAB.md](EXTENDING_LUNARLAB.md)).
- ✅ Tutorial executed by the tests; developer guide; generated API reference; contributing guide; issue forms;
  independent-reproduction guide.
- ✅ Historical experiment evidence verified unchanged (see the readiness report).

## Submit

- ⬜ Upload the PDF at https://jmlr.csail.mit.edu/manudb/ (register, log in, "submit manuscript") with the cover
  letter, stating the MLOSS section. *(corresponding author)*
- ⬜ After acceptance: LaTeX source and the code archive renamed to JMLR's convention (`<id>-code.tar.gz`); sign
  the release form for source code if asked. *(authors)*
