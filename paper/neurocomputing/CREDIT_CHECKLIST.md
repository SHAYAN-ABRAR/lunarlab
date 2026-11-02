# CRediT statement: checklist for the author

Prepared on 1 November 2026. **Nothing is ticked:** the roles are the author's to state. The Guide for Authors
requires a CRediT statement ("Corresponding authors are required to acknowledge co-author contributions using
CRediT (Contributor Roles Taxonomy) roles"). The roles describe **human** contributions. AI tools are not
authors and receive no roles. Their use is disclosed separately (`AI_USE_INVENTORY.md`,
`AI_Disclosure_For_Submission.tex`).

| | Role (CRediT definition, abridged) | Notes |
|---|---|---|
| [ ] | **Conceptualization:** ideas; formulating or evolving the overarching research goals and aims | The records do not show who conceived the research questions |
| [ ] | **Data curation:** annotating, scrubbing and maintaining research data, including code needed to interpret it | The data were curated by scripts that Claude Code wrote and ran |
| [ ] | **Formal analysis:** applying statistical, mathematical or computational techniques to analyse the data | The analyses are scripts written by Claude Code |
| — | **Funding acquisition:** acquiring the financial support for the project | **Not to be claimed:** the work was self-funded, with no grant |
| [ ] | **Investigation:** conducting the research, specifically performing the experiments or collecting the evidence | Claude Code launched the training and evaluation runs on the author's machine |
| [ ] | **Methodology:** developing or designing the methodology; creating models | |
| [ ] | **Project administration:** managing and coordinating the planning and execution of the research | The author's briefs directed each stage of the work |
| [ ] | **Resources:** providing study materials, instrumentation, computing resources or analysis tools | The experiments ran on the author's laptop |
| [ ] | **Software:** programming and software development; implementing code and algorithms; testing code | The records show Claude Code wrote most of the code and two ChatGPT-prepared patches were integrated (`AI_USE_INVENTORY.md`) |
| — | **Supervision:** oversight and leadership of the research, including mentorship outside the core team | **Not to be claimed:** single author, no supervision |
| [ ] | **Validation:** verifying the replication or reproducibility of the results and other outputs | |
| [ ] | **Visualization:** preparing the published work's visualisations and data presentation | The figures are drawn by scripts written by Claude Code |
| [ ] | **Writing – original draft:** writing the initial draft | The records show drafts written with ChatGPT and Claude Code |
| [ ] | **Writing – review & editing:** critical review, commentary or revision | Claim this only for review and revision the author has done |

When the author has decided, the statement reads (only the confirmed roles, in this order):

```latex
\section*{CRediT authorship contribution statement}
\textbf{Shayan Abrar:} [the confirmed roles, separated by commas].
```
