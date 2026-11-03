# Inventory of AI assistance, for the disclosure statements

Prepared on 1 November 2026 and updated on 3 November 2026, for the author to check and complete. It extends
[`docs/neurocomputing/AI_TOOL_VERSIONS.md`](../../docs/neurocomputing/AI_TOOL_VERSIONS.md), which was recovered on
26 October 2026. Only metadata was read from the records: timestamps, version and model fields, tool names,
the paths of edited files, and the sub-command of the commands that launched runs. No conversation text is
reproduced. **Nothing here asserts that the author has reviewed or approved any AI output.** Only the author
can state that, and only once it is true.

Elsevier's policy, fetched again on 3 November 2026 at 14:54 UTC (still "Policy updated June 2026"), asks for
three things.

- **AI declaration:** a separate statement titled "Declaration of generative AI and AI-assisted technologies
  in the manuscript preparation process", placed "at the end of your manuscript, immediately before the
  references". It names each tool and its purpose, declares any AI selection, collation or editing of
  references, and "should confirm that you reviewed the output and take full responsibility for the
  content"; authors should also document "the extent of their oversight". In the review draft it follows the
  appendix, which comes before the references.
- **Methods:** a reproducible description of AI use in the research process. This includes code written or
  edited with AI ("declare this in detail in the Methods section") and AI-assisted data visualisations, with
  "the name of the model or tool, the version used, and the developer or manufacturer". Section 5.3 does
  this.
- **Explanatory images:** "The use of AI tools should be disclosed in the caption of each image (including
  the specific tool, version, and how the tool was used) and in the general AI disclosure statement".
  Figure 1 is the paper's only explanatory image; its caption now names Claude Code 2.1.299 and its role.
  Figures 2 to 4 and A.1 are data visualisations, disclosed in Methods.

AI tools may not be authors. The guide requires a CRediT statement for human contributors only; see
`CREDIT_CHECKLIST.md`.

## Claude Code (developer: Anthropic)

Source: the workspace's Claude Code session transcript (session `719a132a-9630-4aa9-aea5-88625f532c94`, kept
locally, not published), read on 1 November 2026 at 15:42 UTC and again on 3 November 2026 at about 15:00 UTC.

| Recorded field | Value |
|---|---|
| Tool and entry point | Claude Code, VS Code extension (`claude-vscode`) |
| Versions | `2.1.283` on 14 October 2026 (14:27 to 20:03 UTC); `2.1.299` from 15 October 13:18 UTC to 28 October 18:17 UTC; `2.1.312` from 1 November 15:02 UTC, still in use on 3 November |
| Model | `claude-opus-5-5` on all 9,978 model-generated messages up to 3 November (20 further entries are `<synthetic>`, written by Claude Code itself); 9,195 up to 1 November |
| Repository file edits | 622 Write/Edit operations on repository paths up to 1 November. Changes made through shell commands are not counted |
| Figure code | All 22 Write/Edit operations on `paper/neurocomputing/figures/build_figures.py` (27 October), the 10 on `paper/jmlr-mloss/build_audit_figure.py` and the 6 on `tools/paper_figures.py` record version `2.1.299`. These scripts last changed in `af8bc4d` (28 October, 17:17 UTC) and `4116599` (23 October), both before `2.1.312` was used |

What the records show Claude Code did:

- **Wrote the software from the start.** The repository's first commit (`f9b5bd1`, 14 October 19:26 UTC) holds
  94 files. Before it, Claude Code had written 82 of them, including all 35 library files, all 10 test files,
  24 of the 33 frontend files, the documentation and the scripts.
- **Wrote and edited the code since then.** By area: `lunarlab/` 147 edits, `tests/` 71, `frontend/` 50,
  `tools/` 32, `.github/` (CI) 12, plus documentation and the evidence folders. This includes the reward
  accounting, the checkpoint and artifact handling, the adapter-based audit layer, the CartPole study runner,
  the three comparison programs and their fixtures, the follow-up comparison set, and the package validator.
- **Launched the studies.** Claude Code started the runs reported in the manuscript on the author's machine:
  - **LunarLander, 15 October 2026:** `lunarlab suite` for the 20 PPO runs at 16:31:13 UTC and for the
    12 DQN runs at 16:43:15 UTC, and `lunarlab run-experiment` for the six learned-reward runs at 17:58:14
    UTC. The runs' recorded creation times (16:31:13 to 17:59:40 UTC) match.
  - **CartPole, 27 October 2026:** the study runner `cartpole_study.py`. The pilot runs started at 16:12:26
    UTC and the main runs at 16:13:24 UTC, seconds after its commands.
  - **Since then:** the evaluations, replays, the workflow comparison, CI runs and package validations.
- **Wrote the figures' code:** `paper/neurocomputing/figures/build_figures.py` (22 edits),
  `tools/paper_figures.py` (6) and `paper/jmlr-mloss/build_audit_figure.py` (see the 26 October record). The
  figures are drawn by these scripts from recorded data; no figure image was generated by a model.
- **Wrote much of the manuscript:**
  - **Import and integration:** it imported the handoff package's editorial draft into
    `paper/neurocomputing/` and integrated the new evidence (`21ceb66`).
  - **Revisions:** it revised the text in four later commits; `main.tex` was written or edited 14 times
    through the Write/Edit tool, and further through scripts.
  - **References:** it added one reference (`barto1983neuronlike`, the CartPole source) and wrote the
    citations of the integrated text. The other entries came from the handoff draft.
  - **Checks and evidence map:** it wrote `check_manuscript.py`, `EVIDENCE.md` and these disclosure drafts.

## ChatGPT or Codex (developer: OpenAI)

These records hold no model or version identifier for OpenAI's tools; they must come from the author's
account (the model shown for each conversation, or a data export). What the records show:

- **Integrated patches:** two reviewer patches, from packages the author reports were prepared with ChatGPT.
  `lunarlab-review.patch` (19 October) is in `109cd88`. The runtime, CLI, export, reporting and test hunks of
  `followup-review.patch` (21 October) are in `444a4c5`.
- **Editorial draft:** the handoff package `LunarLab_Neurocomputing_Package (1).zip` (27 October). Its README
  addresses its instructions to Claude and describes its manuscript as an "editorial and handoff revision".
  That draft is the editorial starting point of `paper/neurocomputing/main.tex`.
- **Reviews and briefs:** the reviews, repair notes and work briefs that directed the later work. The
  package verification of 29 October describes itself as "an assistant-executed independent review"
  (`reports/neurocomputing-final-validation-2026-11-01/received/`).
- **Linux audit, 2 to 3 November 2026:** `LunarLab_Linux_Validation_2026-11-03.zip`, whose report is headed
  "Assistant-executed". It ran the package validator and the replays on Linux in its own sandbox and wrote
  the repair note that the work of 3 November followed
  (`reports/neurocomputing-final-repairs-2026-11-03/received/`). It is not a human or independent
  researcher's reproduction.

**To be completed by the author:**

- the OpenAI products and models used (ChatGPT, Codex or both), and their versions;
- which drafts or sections each produced;
- whether they selected, collated or edited references.

## What these records do not show

The records show which files the assistant changed and which commands it ran. They do not show who wrote the
author's own earlier material, or whether, when or how a person reviewed the code, the figures or the text.
This file therefore claims no human review.

| Task | Tool shown by the records | Author to confirm |
|---|---|---|
| Research questions, study designs, reward designs | Not recorded | Who conceived them; AI help, if any |
| Software (library, tests, CI, frontend) | Claude Code; two ChatGPT-prepared patches | Own coding, if any |
| Running the experiments | Claude Code (commands on the author's machine) | That the author directed them |
| Linux validation | ChatGPT (OpenAI), in its sandbox | Product and model |
| Analysis code and figures | Claude Code | — |
| Manuscript text | Claude Code; ChatGPT (editorial draft) | Own writing; which parts |
| References | Claude Code added one | Earlier selections |
| Review of all outputs | Not recorded | Whether, and how, done |
