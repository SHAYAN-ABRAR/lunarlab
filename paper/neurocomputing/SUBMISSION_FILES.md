# Submission files for Neurocomputing (status of 3 November 2026)

Article type **"Software publication"**; publication option **Subscription** (no publication fee), with open
access optional and charged (the journal's reply of 30 October 2026). There is no word or page restriction,
and review is written, with revisions and no mandatory interview (its reply reported on 3 November 2026).
Nothing has been submitted. **Nothing here is approved by the author yet.**

The rules come from the Guide for Authors captured on 26 October 2026 (`docs/neurocomputing/README.md`). On
3 November 2026 the guide answered automated requests with HTTP 403, so it could not be read again. No
requirement is assumed beyond the captured guide, Elsevier's generative-AI policy (fetched on 3 November) and
the journal's replies.

| File or item | Guide | Status | Remaining step |
|---|---|---|---|
| `main.tex`, `AI_Disclosure_For_Submission.tex`, `references.bib`, `elsarticle.cls`, `elsarticle-num.bst` | Source files are required ("A PDF is not an acceptable source file") | **Draft.** `check_manuscript.py --draft` passes; five AUTHOR TO CONFIRM items remain | The author's decisions below; then `check_manuscript.py --final` must pass |
| `figures/*.pdf` (Figures 1 to 4 and A.1) | Separate files, each with a caption; vector PDF with embedded fonts | Built and digest-checked (`figures/MANIFEST.json`) | None, unless the author changes a figure |
| Title page (in `main.tex`) | Title, author, affiliation with postal address, corresponding author and email | Present: Shayan Abrar; AIUB, 408/1 (Old KA 66/1), Kuratoli, Khilkhet, Dhaka 1229, Bangladesh; `shayanabrar7@gmail.com` | — |
| `highlights.txt` | Encouraged: 3 to 5 bullets, at most 85 characters each, a separate editable file | **Draft**, 5 bullets of 78 to 85 characters | The author's approval |
| AI declaration (section before the references) | Required when generative AI was used | **Draft** with AUTHOR TO CONFIRM items | The OpenAI products and models, any other use, references, and the review sentence only when true (`AI_USE_INVENTORY.md`) |
| CRediT statement | Required | **AUTHOR TO CONFIRM** item | The roles (`CREDIT_CHECKLIST.md`) |
| Competing interests | The declarations tool "should always be completed" | The sentence "The author declares no competing interests." is in the manuscript | The author completes the tool at submission ("I have nothing to declare") |
| Funding | Required | "This research was self-funded. It received no specific grant…" | — |
| Data availability | Required; the journal confirmed that the GitHub link can be cited | Drafted: the repository, the revisions, what is not yet public | The licence item; a deposit if the author wants the local-only policies public |
| Author biography and photograph | Requested ("maximum 100 words" and a passport-type photograph) | **Not drafted:** it needs facts only the author has | The author writes it |
| `COVER_LETTER_DRAFT.md` | Not stated in the captured guide | **Draft** for the author | Edit, approve or omit |
| Graphical abstract | Not stated | None prepared | If one is made, Elsevier's policy forbids general-purpose generative AI image tools for it |
| Suggested reviewers | Not stated | None | — |
