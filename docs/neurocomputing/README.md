# Neurocomputing submission requirements

Captured 26 October 2026 from the journal's official pages. Quotations are verbatim. Nothing was submitted, paid
or sent, and the journal was not contacted.

ScienceDirect refuses automated requests (HTTP 403). The author therefore saved the Guide for Authors, the
open-access page and the journal homepage from a normal browser between 17:33 and 17:37 UTC. Elsevier's shop
page, pricing policy, generative-AI policy, APC price list and LaTeX template were fetched directly between 17:18
and 17:40 UTC. The saved copies, PDFs rendered from them and their SHA-256 digests are in the review package
`LunarLab-neurocomputing-requirements-2026-10-26.zip`. They are not committed here because the pages are
Elsevier's copyright.

## Fee-free OSP route: not verified

The current pages describe a subscription option with no publication fee, but they describe it for the journal
as a whole. None of them addresses Original Software Publications (OSPs), and the OSP instructions they link to no
longer exist. Current official sources therefore establish neither of the following:

- whether an OSP can be published by the subscription route at no cost;
- whether the older USD 500 OSP open-access fee still applies, or whether it was mandatory or optional.

| Source | What it says |
|---|---|
| [Journal homepage](https://www.sciencedirect.com/journal/neurocomputing), Subscription | "No publication fee charged to authors, and published articles are immediately available to subscribers." |
| Journal homepage, Open Access | "Article Publishing Charge (APC): USD 2,660 (excluding taxes). Actual APCs may differ based on individual author circumstances." |
| [Open-access page](https://www.sciencedirect.com/journal/neurocomputing/publish/open-access-options) | "Neurocomputing offers authors two choices to publish their research". Open access: "An open access publication fee is payable by authors, or their institution or funder." Subscription: "No open access publication fee." Also: "Your publication choice will have no effect on the peer review process or acceptance of your submission." |
| [Guide, submission checklist](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#submitting-your-manuscript-submission-checklist) | "For open access articles, all authors understand that they are responsible for payment of the Article Publishing Charge (APC) if the manuscript is accepted." |
| [Elsevier pricing policy](https://www.elsevier.com/about/policies-and-standards/pricing) | "Authors publishing in hybrid journals can publish under the subscription model at no cost". Also: "A small percentage of titles may support more than one APC, for example when a journal supports one or more article types that require different APCs." |
| [Elsevier APC price list](https://legacyfileshare.elsevier.com/els_com_pricing/article-publishing-charge.xlsx), "Prices as of date: 05-Oct-2026" | A single row: `0925-2312`, Neurocomputing, Hybrid Open Access, USD 2,660. The list has exactly one row per journal and no article-type column, so it cannot show an OSP-specific price |
| OSP instructions ("See the detailed Submission instructions … here" in the guide, homepage and shop page) | `https://www.elsevier.com/about/content-innovation/original-software-publications` answers 301 and redirects to `https://www.elsevier.com/about`, Elsevier's generic About page (checked at 17:18 and 17:40 UTC) |
| USD 500 OSP fee | Not mentioned on any captured official page. The older secondary guide that mentions it was not located |

None of the captured pages mentions a submission fee, page charges or colour charges. That silence is not an
explicit statement that none apply. The only explicit no-fee statements are the subscription sentences above,
and they are journal-wide. The author could settle the question in two ways; neither was tried here:

- The submission system (`https://submit.elsevier.com/NEUCOM`, linked as "Submit your article") shows the
  article types. According to the open-access page, it also presents "a personalized OA Article Publishing
  Charge" during submission.
- Elsevier's author support could be asked in writing.

## Article type and template

- [Article types](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#about-the-journal-article-types):
  "Neurocomputing welcomes novel, timely, substantial contributions in the following 7 types." Type 5 reads
  "Software publication" and is described as follows: "Software publications are to disseminate existing and
  useful software in the areas of neural networks and learning systems that contain non-trivial contributions
  related to the implementations of algorithms, toolboxes, and real systems, where the software must adhere to a
  recognized legal license."
- [Aims and scope](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#about-the-journal-aims-and-scope):
  "Neurocomputing Software Track publishes a new format, the Original Software Publication (OSP)". The section
  continues: "the software will be a full peer reviewed publication that is able to capture your software
  updates once they are released". The guide therefore uses two names for the format: "Software publication" in
  the article-type list and "Original Software Publication (OSP)" in the Software Track text. The label used by
  the submission system was not checked.
- Template. The guide links no OSP template, and its OSP instructions link is dead (above). The one template it
  links is Elsevier's general LaTeX template, under "We encourage you use our LaTeX template when preparing a
  LaTeX submission": `els-cas-templates.zip`. That file holds the CAS single- and double-column classes; it is
  3,305,507 bytes, carries a server date of 13 May 2024 and has SHA-256
  `36d97da01c6bbd134f315bff6c3de553735e2550444a6ddd4f869ddc67a20757`. SoftwareX and Software Impacts publish
  their own OSP templates; those were not used.

## Requirements

Status follows the guide's wording. **Required**: "required", "must" or an instruction. **Encouraged**:
"encouraged" or "recommend". **Requested**: "Please submit". **Not stated**: the guide does not cover the item.
Links go to sections of the
[Guide for Authors](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors).

| Item | Status | Rule |
|---|---|---|
| Article length | Not stated | No word or page limit for articles. The only length limits are the abstract (250 words), highlights (85 characters per bullet) and author biographies (100 words). OSP-specific limits would be in the missing OSP instructions |
| [Abstract](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-abstract) | Required | "You are required to provide a concise and factual abstract that does not exceed 250 words." |
| [Keywords](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-keywords) | Required | "You are required to provide 1 to 7 keywords for indexing purposes." |
| [Section headings](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-article-structure) | Required format | "Divide your manuscript into clearly defined and numbered sections." "Do not include the article abstract within section numbering." No particular headings are prescribed, for OSPs or otherwise |
| Code-metadata tables | Not stated | Neither the guide nor any captured page mentions them. An OSP table format would be in the missing OSP instructions. SoftwareX's tables are not assumed |
| [Software licence](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#about-the-journal-aims-and-scope) | Required | "The software must adhere to a recognized legal license, such as OSI approved licenses." |
| [Source code and research data](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-research-data) | Required (Option C) | "you are required to: Deposit your research data in a relevant data repository. Cite and link to this dataset in your article. If this is not possible, make a statement explaining why research data cannot be shared." Research data "may also include software, code, models, algorithms, protocols, methods and other useful materials" |
| [Data statement](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-data-statement) | Required | "you are required to state the availability of any data at submission." |
| [Software and data citations](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-references) | Recommended elements | Software: "preferably a PID … DOIs are preferred … If there is no PID for the software, a URL to the software is the best identifier available." Data references "should include" a "global persistent identifier". No DOI is mandated |
| [Supplementary material](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-supplementary-material) | Encouraged | "We encourage the use of supplementary materials such as applications, images, and sound clips". "Submit all supplementary material at the same time as your manuscript." Files "will appear online exactly as received". No general size limit is given. For [video](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-video): "preferred maximum file size of 150 MB per file, 1 GB in total" |
| The 38-policy bundle | Deposit rule applies | The guide accepts supplementary files and gives them no general size limit. However, research data includes "models", and Option C asks for it to be deposited in a relevant data repository and cited and linked, or for a statement of why it cannot be shared. Supplementary files alone do not meet that rule. No DOI is mandated, and no minimum number of independent users is stated anywhere |
| [Highlights](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-highlights) | Encouraged | "You are encouraged to provide article highlights at submission." 3 to 5 bullets, "each a maximum of 85 characters, including spaces", supplied as a separate editable file with "highlights" in its name |
| Graphical abstract | Not stated | Not mentioned in the guide. If one is supplied, Elsevier's AI policy says "General-purpose generative AI image tools must not be used to create graphical abstracts" |
| [CRediT](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-article-structure) | Required | "Corresponding authors are required to acknowledge co-author contributions using CRediT (Contributor Roles Taxonomy) roles" |
| Suggested reviewers | Not stated | Not mentioned. [Peer review](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#about-the-journal-peer-review) is "single anonymized", typically with "a minimum of two reviewers" |
| Interview or presentation | Not stated | The guide mentions neither. Video is optional: "This journal accepts video material" |
| [Competing interests](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#ethics-and-policies-declaration-of-competing-interests) | Required | "The declarations tool should always be completed." Authors with nothing to declare "should select the option "I have nothing to declare."" The manuscript's placeholder awaits the author |
| [Funding](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#ethics-and-policies-funding-sources) | Required | "Authors must disclose any funding sources". If there was none: "This research did not receive any specific grant from funding agencies in the public, commercial, or not-for-profit sectors." |
| [Generative AI](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#ethics-and-policies-declaration-of-generative-ai-use) | Required when used | "Authors must declare the use of generative AI tools in the manuscript preparation process upon submission of the paper", in a new section before the references. The guide's example statement adds "After using this tool/service, the author(s) reviewed and edited the content as needed"; that sentence fits only if it is true. For research use, [Elsevier's policy](https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals) ("Policy updated June 2026") asks authors to "disclose the name of the model or tool, the version used, and the developer or manufacturer, in the Methods section". It also says that if authors write or edit code with AI tools "they should declare this in detail in the Methods section". AI tools may not be authors. The identifiers recovered for LunarLab are in [AI_TOOL_VERSIONS.md](AI_TOOL_VERSIONS.md) |
| [Title page](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-title-page) | Required | Title, authors, affiliations with full postal address, and corresponding author. "The email address of the corresponding author must be included on the title page and will be published in the article." |
| [Source files](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-file-format) | Required | "A PDF is not an acceptable source file." Submit .doc/.docx or .tex. Double-column layout is allowed only for LaTeX. The LaTeX template is encouraged |
| [Author biographies](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-article-structure) | Requested | "Please submit a short (maximum 100 words) biography of each author and include a passport-type photograph as a separate figure." |
| [Figures](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-figures-images-and-other-artwork) | Required | Supplied as separate files; "All artwork must have a caption." Vector EPS/PDF with embedded fonts or text saved as graphics; photographs at 300 dpi |
| [References](https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors#writing-and-formatting-references) | Free format at submission | "References can be in any style or format as long as the style is consistent." Numbered in square brackets. "Every reference included must correspond to a real, existing source." |

## Sources and capture times (UTC, 26 October 2026)

| Page | Address | Captured |
|---|---|---|
| Guide for Authors | `https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors` | 17:37:39, saved by the author in a browser. The first attempt, at 17:33:24, landed on the ScienceDirect homepage |
| Open-access options | `https://www.sciencedirect.com/journal/neurocomputing/publish/open-access-options` | 17:33:41, saved by the author |
| Journal homepage | `https://www.sciencedirect.com/journal/neurocomputing` | 17:37:07, saved by the author |
| Shop page | `https://shop.elsevier.com/journals/neurocomputing/0925-2312` | 17:18:18 |
| Pricing policy | `https://www.elsevier.com/about/policies-and-standards/pricing` | 17:19:15 |
| APC price list | `https://legacyfileshare.elsevier.com/els_com_pricing/article-publishing-charge.xlsx` | 17:19:12 (server date 5 October 2026) |
| Generative-AI policy | `https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals` | 17:19:16 |
| LaTeX instructions and template | `https://www.elsevier.com/latex` (now `…/researcher/author/policies-and-guidelines/latex-instructions`) and the template linked from the guide | 17:40:19–17:40:21 |
| OSP instructions link | `https://www.elsevier.com/about/content-innovation/original-software-publications` | 301 to `https://www.elsevier.com/about` at 17:18:20 and 17:40:22 |
