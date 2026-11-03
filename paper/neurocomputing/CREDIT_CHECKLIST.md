# CRediT statement: checklist and proposal for the author

Prepared on 1 November 2026 and revised on 3 November 2026. **Nothing is ticked, and no role is established
here.** The roles are the author's to state, from the work the author actually did. The manuscript shows the
statement as an "AUTHOR TO CONFIRM" item until then.

- **What the guide asks:** a CRediT statement ("Corresponding authors are required to acknowledge co-author
  contributions using CRediT (Contributor Roles Taxonomy) roles"; Guide for Authors, captured 26 October 2026).
- **Human roles only:** the roles describe human contributions. AI tools are not authors and receive no
  roles; their use is disclosed separately (`AI_USE_INVENTORY.md`, `AI_Disclosure_For_Submission.tex`).
- **Sole authorship:** it does not settle the roles. Each role still needs the activity it names. Equally,
  AI-generated implementation does not by itself rule out genuine human direction, checking or validation.
- **Guidance:** [NISO's guidance](https://credit.niso.org/implementing-credit/) lets a contributor hold several
  roles and leaves out roles that do not apply.

| | Role (CRediT definition, abridged) | What the records show | Question for the author |
|---|---|---|---|
| [ ] | **Conceptualization:** ideas; formulating or evolving the overarching research goals and aims | Not recorded | Did you conceive the research questions and the reward-audit idea? |
| [ ] | **Data curation:** annotating, scrubbing and maintaining research data, including code needed to interpret it | The data were curated by scripts that Claude Code wrote and ran | Did you curate or check the records yourself, or direct their curation? |
| [ ] | **Formal analysis:** applying statistical, mathematical or computational techniques to analyse the data | The analyses are scripts written by Claude Code | Did you choose, check or interpret the analyses? |
| [ ] | **Funding acquisition:** acquiring the financial support for the project | The work was self-funded, with no grant | Not proposed: self-funding is not by itself the acquisition of financial support. Claim it only if you did that |
| [ ] | **Investigation:** conducting the research, specifically performing the experiments or collecting the evidence | Claude Code launched the training and evaluation runs on the author's machine, from the author's briefs | Did you perform or direct the experiments? |
| [ ] | **Methodology:** developing or designing the methodology; creating models | Not recorded | Did you design the protocols, reward designs and audit workflow? |
| [ ] | **Project administration:** managing and coordinating the planning and execution of the research | The author's briefs directed each stage of the work | — |
| [ ] | **Resources:** providing study materials, instrumentation, computing resources or analysis tools | The experiments ran on the author's laptop | — |
| [ ] | **Software:** programming and software development; implementing code and algorithms; testing code | Claude Code wrote most of the code; two ChatGPT-prepared patches were integrated (`AI_USE_INVENTORY.md`) | Did you write, direct, review or test the software? The AI's part is disclosed, not credited |
| [ ] | **Supervision:** oversight and leadership responsibility for the research activity, including mentorship outside the core team | Single author; no other team member is recorded | Not proposed. Claim it only for an activity that fits this definition |
| [ ] | **Validation:** verifying the replication or reproducibility of the results and other outputs | The validations were run by Claude Code on the author's machine and by ChatGPT in its sandbox | Did you verify any results yourself, or direct the verification? |
| [ ] | **Visualization:** preparing the published work's visualisations and data presentation | The figures are drawn by scripts written by Claude Code | Did you design or check the figures? |
| [ ] | **Writing – original draft:** writing the initial draft | The records show drafts written with ChatGPT and Claude Code | Did you write any of the initial draft, or direct it? |
| [ ] | **Writing – review & editing:** critical review, commentary or revision | Not recorded | Claim this only for review and revision you have done |

## Proposal, for the author's confirmation

The conventional statement of a sole author who directed the work, as the records describe it, would read as
follows. **It is a proposal.** Keep a role only if the answer to its question above is yes, and delete the
others:

```latex
\section*{CRediT authorship contribution statement}
\textbf{Shayan Abrar:} Conceptualization, Methodology, Software, Validation, Formal analysis, Investigation,
Resources, Data curation, Writing -- original draft, Writing -- review \& editing, Visualization,
Project administration.
```

The records most directly support **Project administration** (the briefs) and **Resources** (the author's
machine). The other roles depend on the answers above. Funding acquisition and Supervision are not proposed.
To use the statement, replace the "AUTHOR TO CONFIRM" item in `main.tex` with the confirmed roles, in this order.
