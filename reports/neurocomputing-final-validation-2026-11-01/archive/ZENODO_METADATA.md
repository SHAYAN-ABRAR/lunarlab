# Zenodo metadata for the archive candidate (draft; nothing uploaded)

Prepared 1 November 2026 for the author to review. `zenodo-metadata.json` holds the same fields in the
deposit format of Zenodo's REST API, which is also the format of a `.zenodo.json` file. Its licence field is
deliberately left invalid until the author chooses, so it cannot be used unreviewed. No DOI exists, and none is
invented here. Zenodo assigns one only when a draft is created, and it resolves only once the record is
published.

| Field | Proposed value | Note |
|---|---|---|
| Resource type | Dataset | The record holds research data (trained policies, recorded evaluations, study records) together with the software that produced and verifies them. An alternative is two records: software, through a GitHub release, and dataset. The author decides |
| Title | LunarLab: software, study records and trained policies for auditable reward-design experiments | |
| Creator | Abrar, Shayan; affiliation American International University-Bangladesh (AIUB) | Add an ORCID iD if the author has one |
| Description | See below | Paste as is; Zenodo accepts simple HTML |
| Version | 0.1.0 | The software version. The exact source revision is named in the description and in the archive's `REVISIONS.md` |
| Publication date | Set when the record is published | |
| Licences | **To be chosen by the author** (`LICENSING_PROPOSAL.md`; proposed: MIT and CC BY 4.0, with `LICENSES.md` as the file map) | Do not accept Zenodo's pre-selected licence for the whole record |
| Keywords | reinforcement learning; reward shaping; reward hacking; reproducibility; evaluation; research software; Stable-Baselines3; Gymnasium; LunarLander; CartPole | |
| Related works | `https://github.com/SHAYAN-ABRAR/lunarlab`, "is supplement to", resource type software | Add the article's DOI ("is described by") once it exists |
| Language | English | |
| Funding | None | The work was self-funded |
| Access | Open | |

## Description

> Software and research data for LunarLab, a toolkit for auditable reward-design experiments in reinforcement
> learning, prepared for a software article (manuscript in preparation).
>
> - **source/:** the LunarLab repository at the archived revision (see `REVISIONS.md`). It holds the library
>   whose code is that of revision c9b9384, the tests, the documentation, the protocols, the study records,
>   the audit-workflow comparison programs and their fixtures, and the results.
> - **software/:** deterministic, installable source archives.
> - **lunarlander-study/:** the historical 38-policy LunarLander export. It holds 3,800 recorded test
>   episodes; the six learned-reward packages carry their original reward models. Also its repair-time source
>   archive.
> - **cartpole-study-output/:** the CartPole study's 36 frozen checkpoints and 18 exported audit artifacts,
>   and an inventory of the 156 scheduled checkpoints that are not distributed.
> - **outside-git/:** the 14 policies of the comparison fixtures.
>
> `START_HERE.md` explains how to check the archive from a fresh extraction with the included validator,
> which installs locked dependencies into a new environment and uses an empty data home. Nothing is trained.
>
> **Limitations:**
>
> - Only nine of the 38 LunarLander policies have been replayed on Linux.
> - Bit-identical results across operating systems are not a supported guarantee.
> - The LunarLander policies were trained from a modified working tree based on revision 32823f3, as their
>   records state.
> - No independent person has yet used LunarLab.

## Citation (once published)

Abrar, S. (2026). *LunarLab: software, study records and trained policies for auditable reward-design
experiments* (Version 0.1.0) [Data set]. Zenodo. DOI: assigned by Zenodo at publication.

After publication, add the DOI to:

- `CITATION.cff`;
- the manuscript's availability statement;
- `README.md`.
