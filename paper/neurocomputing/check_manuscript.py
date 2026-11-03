# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Check the Neurocomputing manuscript source against the captured guide's stated limits and this repository.

    python paper/neurocomputing/check_manuscript.py [--draft | --final]

* abstract at most 250 words, 1 to 7 keywords (Guide for Authors, captured 26 October 2026);
* every figure the source includes exists, and its digest equals the figure manifest;
* every cited key is in references.bib;
* the author details and the declarations the author fixed are present verbatim;
* with ``--draft`` or ``--final``, no placeholder for the software revision or CI counts remains;
* "AUTHOR TO CONFIRM" items, in ``main.tex`` or a file it inputs, are listed. ``--draft`` (the review builds:
  CI and the package validator) accepts them only while every page carries the working-draft footer, so a
  page with an unconfirmed item cannot pass as a submission. ``--final`` (the submission check) fails on any
  of them and on the working-draft footer itself.

Comments (``%`` to the end of the line, unless escaped) are ignored. Exit status 0 when every check passes, 1
otherwise.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLACEHOLDERS = ("SWREV", "CIRUN", "CILINUX", "CISKIP", "CICOV", "CIWIN", "CIARCHIVE")
FIXED_TEXT = (
    "Shayan Abrar",
    "American International University-Bangladesh (AIUB)",
    "408/1 (Old KA 66/1), Kuratoli, Khilkhet",
    "postcode={1229}",
    "\\ead{shayanabrar7@gmail.com}",
    "The author declares no competing interests.",
    "This research was self-funded. It received no specific grant from funding agencies in the public, "
    "commercial or not-for-profit sectors.",
    "The author thanks American International University-Bangladesh (AIUB) for its institutional support.",
)
PENDING = "AUTHOR TO CONFIRM"
DRAFT_FOOTER = "Working draft, not submitted"


def active(text: str) -> str:
    """The source without its comments: an unescaped ``%`` ends the line."""
    return "\n".join(re.split(r"(?<!\\)%", line, maxsplit=1)[0] for line in text.splitlines())


def main() -> int:
    final = "--final" in sys.argv
    strict = final or "--draft" in sys.argv
    tex = (HERE / "main.tex").read_text(encoding="utf-8")
    bib = (HERE / "references.bib").read_text(encoding="utf-8")
    problems = []
    abstract = tex.split("\\begin{abstract}")[1].split("\\end{abstract}")[0]
    words = re.sub(r"\\[A-Za-z]+|[{}%~]", " ", abstract).split()
    keywords = tex.split("\\begin{keyword}")[1].split("\\end{keyword}")[0].split("\\sep")
    print(f"abstract: {len(words)} words; keywords: {len(keywords)}")
    if len(words) > 250:
        problems.append(f"abstract has {len(words)} words (at most 250)")
    if not 1 <= len(keywords) <= 7:
        problems.append(f"{len(keywords)} keywords (1 to 7)")
    manifest = json.loads((HERE / "figures" / "MANIFEST.json").read_text(encoding="utf-8"))
    digests = {
        name: sha
        for entry in manifest.values()
        if isinstance(entry, dict)
        for name, sha in entry.get("outputs", {}).items()
    }
    for path in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex):
        p = HERE / path
        if not p.is_file():
            problems.append(f"missing figure {path}")
        elif digests.get(p.name) != hashlib.sha256(p.read_bytes()).hexdigest():
            problems.append(f"{path} differs from figures/MANIFEST.json")
    keys = set(re.findall(r"@\w+\{([^,]+),", bib))
    cited = {k.strip() for group in re.findall(r"\\cite[pt]?\{([^}]+)\}", tex) for k in group.split(",")}
    missing = sorted(cited - keys)
    if missing:
        problems.append(f"citations missing from references.bib: {missing}")
    for text in FIXED_TEXT:
        if text not in tex:
            problems.append(f"fixed text missing: {text[:60]}")
    left = [p for p in PLACEHOLDERS if re.search(rf"\b{p}\b", tex)]
    if left:
        print("placeholders still in the source:", left)
        if strict:
            problems.append(f"placeholders remain: {left}")
    # A commented-out \input includes nothing.
    body = active(tex)
    sources = {"main.tex": body}
    for name in re.findall(r"\\input\{([^}]+)\}", body):
        source = HERE / (name if name.endswith(".tex") else f"{name}.tex")
        if source.is_file():
            sources[source.name] = active(source.read_text(encoding="utf-8"))
    pending = {name: text.count(PENDING) for name, text in sources.items() if PENDING in text}
    footer = DRAFT_FOOTER in body
    for name, count in pending.items():
        print(f"{name}: {count} {PENDING} item(s) awaiting the author")
    if pending and final:
        problems.append(f"{PENDING} items remain for the author: {pending}")
    elif pending and strict and not footer:
        problems.append(f"{PENDING} items remain, and the working-draft footer has been removed: {pending}")
    if final and footer:
        problems.append(f"the working-draft footer ({DRAFT_FOOTER!r}) is still active")
    print(f"{len(cited)} cited keys, {len(keys)} in references.bib")
    for p in problems:
        print("PROBLEM:", p)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
