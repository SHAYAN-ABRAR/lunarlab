# Cover letter template (JMLR, Machine Learning Open Source Software section)

JMLR accepts the cover letter as plain text or as a PDF made with its LaTeX template. Every field below comes
from the JMLR author information page (marked **JMLR**) or the MLOSS page (marked **MLOSS**). Fields marked
**TODO** can only be completed by the authors; nothing has been filled in on their behalf. Do not send this
template as it is.

---

Dear Editors,

We submit **"LunarLab: A Reproducible Platform for Auditing Reward Shaping and Reward Exploitation in
Reinforcement Learning"** for review. **This submission is intended for the Machine Learning Open Source Software
(MLOSS) section** (MLOSS: the letter must state this).

- **Project web address** (MLOSS): https://github.com/SHAYAN-ABRAR/lunarlab (public repository with issue
  tracker); demonstration: https://shayan-abrar.github.io/lunarlab/
- **Software version to be reviewed** (MLOSS): **0.1.0**, the release candidate approved by the author on
  2026-10-18. **TODO** once tagged: the tag (`v0.1.0`), its commit hash and the SHA-256 of the source archive built
  with `tools/build_source_archive.py --rev v0.1.0`.
- **Open-source license** (MLOSS): MIT License (`LICENSE`; every source file carries an SPDX license notice;
  third-party components are listed in `THIRD_PARTY_NOTICES.md`).
- **Main contribution** (for the editors' orientation): an auditing layer around Stable-Baselines3 that records
  the original reward, every shaping term and the training reward on each transition, evaluates on the original
  reward with disjoint validation/test seeds and immutable final-test checkpoints, continues interrupted runs from
  checkpoints that restore the algorithm state (not bit-identically), records full provenance, and ships
  reproduction tooling; measured overhead: reward accounting at most 4 % of training-loop time, a complete run
  1.22–1.23 times as long as plain Stable-Baselines3 because of the validation episodes.
- **Relationship to existing software:** LunarLab builds on Stable-Baselines3 and Gymnasium and does not replace
  them; a sourced capability comparison with Stable-Baselines3, RL Baselines3 Zoo, CleanRL, rliable and imitation
  is in `docs/jmlr/COMPARISON_EVIDENCE.md`.
- **Evidence of an active user community** (MLOSS: "number of active developers, number of stars on github or
  similar metrics"; documented in the cover letter, not the paper): **TODO.** As observed on 2026-10-17 the
  repository was three days old, with one contributor, no stars, forks or issues. Report the figures current at
  submission and only real evidence (independent users, reproduction reports, citations); see
  `docs/jmlr/COMMUNITY_EVIDENCE.md`.
- **Previous publications that overlap with this submission** (JMLR): **TODO** — state "none" only if true. If
  the software was the main content of an earlier paper, MLOSS also requires a document in the repository listing
  the improvements and extensions since.
- **Co-author consent** (JMLR): not applicable — Shayan Abrar is the sole author.
- **Conflicts of interest** (JMLR): **TODO** — declare possible conflicts; name every action editor who has
  recently collaborated with any author (JMLR's criteria: family or close friend, advisor/advisee for life,
  any collaboration in the past three years, any other reason).
- **Suggested action editors, 3 to 5** (JMLR: from the list of Action Editors, not editorial-board reviewers, with
  no conflict): **TODO** — chosen by the authors after checking the current AE list and conflicts.
- **Suggested reviewers, 3 to 5** (JMLR; MLOSS: "particularly appreciated … explaining briefly why they are
  relevant"): **TODO** — chosen by the authors, with a one-line reason each and no conflict.
- **Keywords** (JMLR): reinforcement learning, reward shaping, reward hacking, reproducibility, open-source
  software.
- **Funding and competing interests** (JMLR, last 36 months): **TODO**.

Sincerely,
Shayan Abrar (sole author); **TODO** position, postal address and e-mail (JMLR asks for these on the title page).

---

## Still required before this letter can be sent

1. The author's affiliation, position, postal address and e-mail (the author is known: Shayan Abrar, sole author).
2. The release tag `v0.1.0` (version approved) and its archive digest.
3. Truthful, current community evidence (see `docs/jmlr/COMMUNITY_EVIDENCE.md`).
4. The overlap, consent, conflict-of-interest, funding and competing-interest statements.
5. Suggested action editors and reviewers, checked for conflicts.
6. The built manuscript PDF, checked for the four-page limit (`paper/jmlr-mloss/BUILD.md`).
