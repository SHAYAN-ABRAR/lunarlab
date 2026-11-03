# Zenodo metadata for the archive candidate (draft; nothing uploaded)

Prepared 1 November 2026; revised 3 November 2026. The journal confirmed that the GitHub link can be cited
under data availability, so **a Zenodo deposit is optional**. It is the way to make the local-only trained
policies, checkpoints and records downloadable and durable; nothing in the submission depends on it. No DOI
exists, and none is invented here. Zenodo registers a DOI only when a record is published; a reserved DOI does
not resolve before that.

**Not ready to submit:** the licences are the author's to choose (`LICENSING_PROPOSAL.md`), and every field
below needs the author's review. Neither JSON file below carries a licence, a publication date or a draft
marker. So neither can be used unreviewed, and the REST API refuses an open record without a licence.

## Three routes, three formats

| Route | Format | Licences | Use |
|---|---|---|---|
| **A. Zenodo web form** (recommended for the candidate ZIP) | The fields of the table below, entered by hand | Several licences per record are accepted (Zenodo's licence help page) | Upload the candidate ZIP and `START_HERE.md` |
| **B. Legacy REST deposit API** | `zenodo-rest-deposit.draft.json`: the request body, with every field inside a top-level `metadata` object | **One** `license` identifier, which "applies to all files in this deposition" (developers.zenodo.org). A mixed record cannot be expressed: choose one licence, deposit separate records, or use route A. Never invent a combined identifier | Scripted upload |
| **C. GitHub integration** | `zenodo-github.draft.json`, which would be committed as `.zenodo.json` at the repository root. Its keys sit at the **top level**, with no `metadata` wrapper | As for route B | A software record created by each GitHub release; it holds the repository only, not the local-only policies |

The two JSON files are drafts beside this document, not active configuration: nothing is committed as
`.zenodo.json`, and no release is made.

## Fields

| Field | Proposed value | Note |
|---|---|---|
| Resource type | Dataset (routes A and B); software (route C) | The candidate holds research data (trained policies, recorded evaluations, study records) together with the software that produced and verifies them. The author decides |
| Title | LunarLab: software, study records and trained policies for auditable reward-design experiments | |
| Creator | Abrar, Shayan; affiliation American International University-Bangladesh (AIUB) | Add an ORCID iD only if the author has one; none is assumed |
| Description | See below | Zenodo accepts simple HTML |
| Version | 0.1.0 | The software version. The exact source revision is named in the description and in the archive's `REVISIONS.md`. For the candidate of 3 November it is `c0d9e5d0823167584a7bff37de9661c35a58228c` (`../../neurocomputing-final-repairs-2026-11-03/archive/CANDIDATE.md`), which the REST draft names |
| Publication date | Set on the day the record is published | Not filled in here |
| Licences | **To be chosen by the author** (`LICENSING_PROPOSAL.md`; proposed: MIT and CC BY 4.0, with `LICENSES.md` as the file map) | Do not accept Zenodo's pre-selected licence for the whole record |
| Keywords | reinforcement learning; reward shaping; reward hacking; reproducibility; evaluation; research software; Stable-Baselines3; Gymnasium; LunarLander; CartPole | |
| Related works | `https://github.com/SHAYAN-ABRAR/lunarlab`, "is supplement to", resource type software; also the tree of the archived revision, `https://github.com/SHAYAN-ABRAR/lunarlab/tree/<revision>` (that revision must be pushed) | Add the article's DOI ("is described by") only once the article has one |
| Language | English | |
| Funding | None | The work was self-funded |
| Access | Open | |

## Description

> Software and research data for LunarLab, a toolkit for auditable reward-design experiments in reinforcement
> learning, prepared for a software article (manuscript in preparation).
>
> - **source/:** the LunarLab repository at the archived revision (see `REVISIONS.md`). It holds the library
>   whose code is that of revision c9b9384, the tests, the documentation, the protocols, the study records,
>   the audit-workflow comparison programs and their fixtures, the package validator and the results.
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
> - On Windows, the recording platform, all 38 LunarLander policies replay exactly from a fresh extraction.
> - On Linux, nine policies were replayed in CI, and an assistant-executed audit replayed all 38 in a
>   diagnostic run whose parent validation was interrupted: all kept integrity, 37 showed permitted
>   numerical differences, and one DQN policy disagreed significantly with its recorded mean return (224.07
>   recorded, 230.45 on Linux). Its cause is not identified.
> - Bit-identical results across operating systems are not a supported guarantee.
> - The LunarLander policies were trained from a modified working tree based on revision 32823f3, as their
>   records state; that tree is not reconstructed.
> - No independent person has yet used LunarLab.

## Citation (once published)

Abrar, S. (2026). *LunarLab: software, study records and trained policies for auditable reward-design
experiments* (Version 0.1.0) [Data set]. Zenodo. DOI: assigned by Zenodo at publication.

After publication, add the DOI to:

- `CITATION.cff`;
- the manuscript's availability statement;
- `README.md`.

**Superseded:** `zenodo-metadata.json` of 1 November mixed the two formats: it wrapped the fields in
`metadata` and added a `_status` marker and a deliberately invalid `license` string. It is withdrawn (it
remains in the history at `f9615d1`) in favour of the two route-specific drafts.
