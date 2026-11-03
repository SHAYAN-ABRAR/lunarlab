# Licences

The candidate holds files under different terms. No single label covers it, and a folder's or archive's label
does not relicense the files inside it.

- **Software:** LunarLab's source code, scripts, tools and documentation are under the MIT License
  (`source/LICENSE`).
- **Third-party files:** `source/paper/neurocomputing/elsarticle.cls` and `elsarticle-num.bst` are unmodified
  copies of Elsevier's `elsarticle` bundle under the LaTeX Project Public License, version 1.3 or later, as
  their headers state. The installed dependencies keep their own licences. Both are listed in
  `source/THIRD_PARTY_NOTICES.md`.
- **Source archives** (`software/`, `lunarlander-study/lunarlab-0.1.0-444a4c5-src.tar.gz`): the code and
  documentation inside are MIT; the trained models and records inside follow the next item.
- **Records, results, trained policies and reward models:** **not yet licensed.** The author must choose a
  licence before any deposit.
- **Manuscript text and the AI-prepared review material** (`source/paper/`, `source/reports/neurocomputing-final-validation-2026-11-01/received/`,
  `source/reports/neurocomputing-final-repairs-2026-11-03/received/`): their terms, and whether they belong in a deposit, are the author's decision.

A proposal, with a file-to-licence map, is in `source/reports/neurocomputing-final-validation-2026-11-01/archive/LICENSING_PROPOSAL.md`. Until a choice is
recorded, no licence is granted for the files without one beyond what the law allows. Changing this file
changes `inventory.json`, `SHA256SUMS` and the candidate's ZIP digests: rebuild and re-validate the candidate,
and never reuse an earlier candidate's digests.
