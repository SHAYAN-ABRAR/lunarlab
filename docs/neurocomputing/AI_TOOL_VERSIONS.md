# AI tool and model identifiers

Recovered on 26 October 2026 from records kept on the author's machine, for the disclosures in Elsevier's
generative-AI policy. Only metadata was read: timestamps, version fields, model fields and the paths of edited
files. No conversation text is reproduced. The extraction scripts and their full output are in the review
package `LunarLab-neurocomputing-requirements-2026-10-26.zip`.

## Claude Code (developer: Anthropic)

Source: the workspace's Claude Code session transcript (session `719a132a-9630-4aa9-aea5-88625f532c94`; kept
locally, not published). It is the only transcript for this workspace and runs from 2026-10-14 14:27 UTC
onward. The counts below come from an extraction run at 2026-10-26 17:20 UTC.

| Recorded field | Value |
|---|---|
| Tool | Claude Code, VS Code extension. Entry point `claude-vscode` on all 14,447 entries that record one |
| Claude Code version | `2.1.283` from 2026-10-14 14:27 to 20:03 UTC. `2.1.299` from 2026-10-15 13:18 UTC to the end of the extraction |
| Model | `claude-opus-5-5` on all 6,794 model-generated assistant messages. Another 17 entries have the model value `<synthetic>`: Claude Code writes these entries itself; no model generated them |
| Effort setting | `max` on 6,001 messages, `xhigh` on 793 |

Corroboration: the extension folder `anthropic.claude-code-2.1.299-win32-x64` is installed. Folders for the later
versions 2.1.300, 2.1.301 and 2.1.304 are also present; the transcript records 2.1.299 for the rest of the
session. A separate command-line installation reports version 2.1.211. No transcript entry records that version.

### Figure code

| File | Origin | Edits made with Claude Code |
|---|---|---|
| `paper/jmlr-mloss/build_audit_figure.py` (manuscript Figure 1) | Created as a new file by `lunarlab-review.patch` in the 19 October independent-review package. The author reports that this package was prepared with ChatGPT. The package records no model or version | 10 edits, 2026-10-19 18:32 to 2026-10-21 17:54 UTC, all with `claude-opus-5-5` in Claude Code `2.1.299`. The committed script (`4116599`, unchanged at `444a4c5`) is the 21 October rewrite: 410 lines added and 65 removed relative to `109cd88`. It is not the replacement script supplied in the 21 October follow-up package |
| `tools/paper_figures.py` (results figures) | Created with Claude Code on 2026-10-17 | 6 edits, 2026-10-17 16:19 to 2026-10-18 14:42 UTC, all with `claude-opus-5-5` in Claude Code `2.1.299` |

### Research software

Claude Code made 330 Write/Edit operations on repository paths (`lunarlab/`, `tools/`, `tests/`, `frontend/`,
`scripts/`, `paper/`) between 2026-10-14 14:46 and 2026-10-23 20:30 UTC. All of them used `claude-opus-5-5`, in
Claude Code `2.1.283` and `2.1.299`. Changes made through shell commands are not counted. Two reviewer patches
from packages the author reports were prepared with ChatGPT were integrated. `lunarlab-review.patch`
(19 October) went into `109cd88`. The runtime, CLI, export, reporting and test hunks of `followup-review.patch`
(21 October) went into `444a4c5`. Every commit carries the repository owner's GitHub identity, and none has an
AI co-author line.

## ChatGPT (developer: OpenAI)

The model and version could not be recovered. This repository never mentions ChatGPT, GPT or OpenAI. The two
reviewer packages (`LunarLab_JMLR_Publication_Package.zip` of 19 October and its 21 October follow-up) contain no
model or version identifier. The identifier has to come from the author's ChatGPT account: the model shown for
each conversation, or an account data export. No version is assumed here.

## What these records do not show

The records show which model generated the assistant messages and which files the assistant edited. They do not
show whether, when or how a person reviewed that code or those figures, so this file makes no claim of human
review. For AI-assisted code and data visualisations,
[Elsevier's policy](https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals)
(updated June 2026) asks the Methods section to give the name of the model or tool, the version used, and the
developer or manufacturer. AI tools may not be listed as authors.
