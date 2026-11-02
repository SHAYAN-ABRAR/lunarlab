# Licensing proposal for the archive deposit (awaiting the author's decision)

Prepared 1 November 2026. **Nothing here is applied:** it is a proposal for the author. Only the software's
MIT licence is already in force; it is the repository's `LICENSE`, and the code files carry MIT SPDX headers.
The repository licence covers "this software and associated documentation files". It does not clearly cover
study records, trained models or article text, so the deposit should state their licence explicitly.

**Zenodo's default:** Zenodo pre-selects Creative Commons Attribution 4.0 for a new upload. That default
should **not** simply be accepted for the whole record. The software is MIT. Two files keep their own
licence. Article text needs the journal's terms checked first.

## Proposed file-to-licence map

`licence_map.py` applies these rules, in order, to every file of the archive candidate (its `inventory.json`). It
writes `licence-map.json`, one entry per file, and prints how many files each rule takes. The first matching rule
wins.

| Rule | Files | Proposed licence | Basis |
|---|---|---|---|
| third-party | `source/paper/neurocomputing/elsarticle.cls`, `elsarticle-num.bst` | LPPL 1.3c (their own) | Unmodified CTAN copies; not relicensed |
| received | `source/reports/neurocomputing-final-validation-2026-11-01/received/**` | **Author's decision** | Review material prepared for the author with an AI assistant; it may be omitted from a public deposit |
| manuscript | `source/paper/**/*.tex`, `*.bib`, `*.bbl`, the manuscript PDFs | **Author's decision** | Article text and preprints: check Elsevier's copyright and preprint-sharing terms before licensing them openly. They are already public in the repository |
| software | `software/**`; `lunarlander-study/lunarlab-0.1.0-444a4c5-src.tar.gz` | MIT | Source archives of the repository |
| models | trained policies and reward models with their packages: `outside-git/**`, `cartpole-study-output/**`, `lunarlander-study/LunarLab_38_Policy_Study.zip`, `source/examples/artifacts/**`, `source/examples/learned-reward-artifacts/**` | CC BY 4.0 (proposed) | Models and their evaluation records are research data. The alternative is CC0 1.0 (no attribution requirement) |
| code | programs (`*.py`, `*.ps1`, `*.sh`, `*.ts`, `*.tsx`, `*.js`, `*.css`, `*.html`, `*.ipynb`) anywhere under `source/`, and every file of the software trees (`lunarlab/`, `tests/`, `tools/`, `frontend/`, `scripts/`, `examples/` apart from the packages above, `notebooks/`, `.github/`, `.vscode/`) | MIT | The repository licence and SPDX headers |
| generated-docs | `source/docs/api/**`, the API reference generated from the code | MIT | Documentation of the software |
| records | the remaining files of `source/reports/**`, `source/docs/results/**` and `source/demo/**`: protocols, records, results, logs, digests | CC BY 4.0 (proposed) | Research data; attribution keeps the provenance visible |
| configuration | build and package configuration and lock files (`*.toml`, `*.yml`, `*.lock`, `package.json`, ...) | MIT | The repository licence |
| data | the remaining data files (JSON, CSV, NPZ, logs), such as plotted values and figure manifests | CC BY 4.0 (proposed) | Research data |
| media | figures and media (`*.pdf`, `*.svg`, `*.png`, `*.gif`, `*.webp`) outside the manuscript rule | CC BY 4.0 (proposed) | Data visualisations drawn from the records |
| documentation | the remaining `source/` files: Markdown documentation, `CITATION.cff`, `LICENSE` | MIT | The repository's "associated documentation files" |
| candidate | the candidate's own `START_HERE.md`, `REVISIONS.md`, `INVENTORY.md`, `inventory.json`, `LICENSES.md`, `SHA256SUMS` | CC BY 4.0 (proposed) | Descriptions of the data |

## Decisions for the author

1. **Data and models:** CC BY 4.0, CC0 1.0 or another licence.
2. **Manuscript text and PDFs:** whether to include them in the deposit, and under which terms, given the
   journal's agreement.
3. **Received review material:** whether to include it.
4. **Record licence field:** Zenodo's current interface accepts several licences per record. The proposal is
   to list **MIT** and **CC BY 4.0** and to keep `LICENSES.md` in the record as the file map.

After the decision, the author or an assistant can rebuild `LICENSES.md` in the candidate from that decision;
the rest of the candidate is unchanged.
