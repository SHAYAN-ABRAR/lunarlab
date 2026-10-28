# LunarLab: software and research data for the Neurocomputing paper (deposit candidate)

This is a **candidate** for an archive deposit, assembled on 28 October 2026.

- **Not done:** it has not been uploaded or published, and it has no DOI or other persistent identifier.
- **The author's decisions:** whether to deposit it, the repository to use, the licences of the records and
  model files, and the final metadata.

## Contents

| Path | What | Licence |
|---|---|---|
| `software/` | `lunarlab-0.1.0-src.tar.gz`: the deterministic source archive of revision `c9b9384`, the implementation the paper describes. It is byte-identical when built by Linux CI (run 40712412847) and on the author's Windows machine. Also its manifest and `SHA256SUMS` | MIT (`LICENSE`); third-party notices in `THIRD_PARTY_NOTICES.md` |
| `evidence/reports/neurocomputing-2026-10-27/` | The research-strengthening evidence: CartPole protocol, run records, analysis and results; workflow-comparison protocol, fixtures, programs and raw outputs; Linux replay reports; CI logs; manuscript build logs | Code files carry MIT SPDX headers; licence for the records **to be chosen by the author** |
| `evidence/reports/neurocomputing-review-repairs-2026-10-28/` | The repairs after a review: record recovery and verification, defect reproductions, regression check, CI of `c9b9384`, validation, integrity | As above |
| `cartpole-study-output/` | The CartPole study runner's complete original output (`main/`, `pilot/`): every scheduled and frozen checkpoint (192 files), the exported audit artifacts (18), the study indexes, compute ledgers and logs | **To be chosen by the author.** The model files are trained policies |
| `comparison-fixture-policies/` | The 14 policy files of the workflow-comparison fixtures, at their fixture paths | As above |
| `lunarlander-study/` | The historical 38-policy LunarLander export (`LunarLab_38_Policy_Study.zip`) and its source archive (`lunarlab-0.1.0-444a4c5-src.tar.gz`), unchanged | As above; the export carries its own notices |
| `LICENSE`, `THIRD_PARTY_NOTICES.md`, `CITATION.cff` | The repository's licence, third-party notices and citation metadata | |
| `SHA256SUMS` | Every other file | |

The CartPole and comparison records name every checkpoint and fixture by SHA-256. The builder checked each
copy against those digests.

## Proposed citation metadata (not final)

- **Title:** LunarLab: auditable reward-design experiments. Software, study records and trained policies.
- **Creator:** Shayan Abrar, American International University-Bangladesh (AIUB). An ORCID, if any, is to be
  added by the author.
- **Version:** 0.1.0; software revision `c9b938446d26fd4890ecd7ff7e6099a319586ae8`.
- **Related identifiers:**
  - the repository, https://github.com/SHAYAN-ABRAR/lunarlab;
  - the article, once it has an identifier.
- **Keywords:** reinforcement learning; reward shaping; reward hacking; reproducibility; evaluation;
  stable-baselines3; gymnasium.
- **Licences:** MIT for the software. For the records and model files, the author must choose (for example
  CC BY 4.0) before any deposit.

## Checking

```bash
sha256sum -c SHA256SUMS
python tools/validate_review_package.py   # from the extracted software archive: see the review package's SUMMARY.md
```
