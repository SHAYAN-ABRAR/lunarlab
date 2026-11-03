# Licensing proposal for the archive deposit (awaiting the author's decision)

Prepared 1 November 2026; revised 3 November 2026 after the Linux audit (`../../neurocomputing-final-repairs-2026-11-03/`).
**Nothing here is applied:** it is a proposal for the author, and mapping a file is not a determination of
anyone's rights. Only the software's MIT licence is already in force: it is the repository's `LICENSE`, and the
code files carry MIT SPDX headers. The repository licence covers "this software and associated documentation
files". It does not clearly cover study records, trained models or article text, and it does not relicense the
third-party files the repository copies. The deposit, and the repository itself, should therefore state those
terms explicitly.

**Zenodo's default:** Zenodo pre-selects Creative Commons Attribution 4.0 for a new upload. That default
should **not** simply be accepted for the whole record. The software is MIT. Two files keep their own licence.
Article text needs the journal's terms checked first.

## Proposed file-to-licence map

`licence_map.py` applies these rules, in order, to every file of an archive candidate. It reads the files
`inventory.json` lists, which are all of them except `inventory.json` itself and `SHA256SUMS`, and adds those
two explicitly. It writes `licence-map-<rev>.json`, one entry per file, records that scope, and fails if any
file of the candidate is left out. The first matching rule wins.

| Rule | Files | Proposed licence | Basis |
|---|---|---|---|
| third-party | `source/paper/neurocomputing/elsarticle.cls`, `elsarticle-num.bst` | LPPL 1.3 or later, as their headers state | Unmodified copies of Elsevier's `elsarticle` bundle; not relicensed (`THIRD_PARTY_NOTICES.md`) |
| received | `source/reports/neurocomputing-final-validation-2026-11-01/received/**`, `source/reports/neurocomputing-final-repairs-2026-11-03/received/**` | **Author's decision** | Review material prepared for the author by an AI assistant; it may be left out of a public deposit |
| manuscript | `source/paper/**/*.tex`, `*.bib`, `*.bbl`, the manuscript PDFs, the highlights and the cover-letter draft | **Author's decision** | Article text and preprints: check Elsevier's copyright and preprint-sharing terms before licensing them openly. Most are already public in the repository |
| source-archives | `software/**`; `lunarlander-study/lunarlab-0.1.0-444a4c5-src.tar.gz` | **Mixed:** MIT for the code and documentation inside; the trained models and records inside follow the models and records rules | A container's label does not relicense what it holds: these archives contain example policies, learned-reward packages and records as well as code |
| models | trained policies and reward models with their packages: `outside-git/**`, `cartpole-study-output/**`, `lunarlander-study/LunarLab_38_Policy_Study.zip`, `source/examples/artifacts/**`, `source/examples/learned-reward-artifacts/**` | CC BY 4.0 (proposed) | Models and their evaluation records are research data. The alternative is CC0 1.0 (no attribution requirement) |
| code | programs (`*.py`, `*.ps1`, `*.sh`, `*.ts`, `*.tsx`, `*.js`, `*.css`, `*.html`, `*.ipynb`) anywhere under `source/`, and every file of the software trees (`lunarlab/`, `tests/`, `tools/`, `frontend/`, `scripts/`, `examples/` apart from the packages above, `notebooks/`, `.github/`, `.vscode/`) | MIT | The repository licence and SPDX headers |
| generated-docs | `source/docs/api/**`, the API reference generated from the code | MIT | Documentation of the software |
| records | the remaining files of `source/reports/**`, `source/docs/results/**` and `source/demo/**`: protocols, records, results, logs, digests | CC BY 4.0 (proposed) | Research data; attribution keeps the provenance visible |
| configuration | build and package configuration and lock files (`*.toml`, `*.yml`, `*.lock`, `package.json`, ...) | MIT | The repository licence |
| data | the remaining data files (JSON, CSV, NPZ, logs), such as plotted values and figure manifests | CC BY 4.0 (proposed) | Research data |
| media | figures and media (`*.pdf`, `*.svg`, `*.png`, `*.gif`, `*.webp`) outside the manuscript rule | CC BY 4.0 (proposed) | Data visualisations drawn from the records |
| documentation | the remaining `source/` files: Markdown documentation, `CITATION.cff`, `LICENSE` | MIT | The repository's "associated documentation files" |
| candidate | the candidate's own `START_HERE.md`, `REVISIONS.md`, `INVENTORY.md`, `LICENSES.md`, and `inventory.json` and `SHA256SUMS` (added explicitly) | CC BY 4.0 (proposed) | Descriptions of the data |

The map of the 1 November candidate (`licence-map-a38d07f.json`, 2,178 files) predates the explicit scope: it
did not cover `inventory.json` and `SHA256SUMS`. Rerun on that candidate, the revised mapper covers all 2,180.

## Decisions for the author

1. **Data and models:** CC BY 4.0, CC0 1.0 or another licence.
2. **Manuscript text, highlights and PDFs:** whether to include them in the deposit, and under which terms,
   given the journal's agreement.
3. **Received review material:** whether to include it.
4. **The public repository:** whether to state the same terms there for the models and records it holds
   (`examples/`, `docs/results/`, `reports/`), for instance in `README.md` and `CITATION.cff`.
5. **Record licence field:** Zenodo's web form accepts several licences per record. The proposal is to list
   **MIT** and **CC BY 4.0** (and the LPPL for the two style files, or leave those files out) and to keep
   `LICENSES.md` in the record as the file map. The legacy REST API takes **one** licence identifier: do not
   invent a combined identifier for it (`ZENODO_METADATA.md`).

After the decision, an assistant can rebuild the candidate's `LICENSES.md` from it. The scientific files stay
byte for byte as they are, but `inventory.json`, `SHA256SUMS` and the candidate ZIP's size and digests change:
rebuild and re-validate the candidate, record the new digests, and never reuse an earlier candidate's digests
for a changed deposit.
