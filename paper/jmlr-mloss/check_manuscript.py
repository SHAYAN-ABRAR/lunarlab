# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Validate the manuscript source without a LaTeX installation.

    python paper/jmlr-mloss/check_manuscript.py

Checks the requirements JMLR states for the title page (abstract of at most 200 words, a running title of at
most 50 characters, five keywords) and the source's integrity (balanced environments and braces, every citation
present in references.bib, every figure file present, every \\ref defined). Lists the remaining TODO markers.
Exit status 1 on a structural error; TODOs alone are reported, not failed. Page count needs a LaTeX build.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def strip_latex(text: str) -> str:
    text = re.sub(r"(?<!\\)%.*", "", text)
    text = re.sub(r"\\TODO\{([^}]*)\}", r"TODO \1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?\{([^{}]*)\}", r"\2", text)
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
    return re.sub(r"[{}$]", " ", text)


def main() -> int:
    tex = (HERE / "main.tex").read_text(encoding="utf-8")
    bib = (HERE / "references.bib").read_text(encoding="utf-8")
    body = re.sub(r"(?<!\\)%.*", "", tex)
    errors, report = [], []

    depth = 0
    for ch in re.sub(r"\\[{}]", "", body):
        depth += {"{": 1, "}": -1}.get(ch, 0)
        if depth < 0:
            errors.append("unbalanced braces: '}' without '{'")
            break
    if depth > 0:
        errors.append(f"unbalanced braces: {depth} unclosed '{{'")
    stack = []
    for kind, env in re.findall(r"\\(begin|end)\{([^}]+)\}", body):
        if kind == "begin":
            stack.append(env)
        elif not stack or stack.pop() != env:
            errors.append(f"\\end{{{env}}} does not close the current environment")
    if stack:
        errors.append(f"unclosed environments: {stack}")

    m = re.search(r"\\begin\{abstract\}%?(.*?)\\end\{abstract\}", body, re.S)
    words = len(strip_latex(m.group(1)).split()) if m else 0
    (errors if not m or words > 200 else report).append(f"abstract: {words} words (limit 200)")
    m = re.search(r"\\ShortHeadings\{([^}]*)\}", body)
    running = strip_latex(m.group(1)).strip() if m else ""
    (errors if not running or len(running) > 50 else report).append(
        f"running title: {running!r}, {len(running)} characters (limit 50)"
    )
    m = re.search(r"\\begin\{keywords\}(.*?)\\end\{keywords\}", body, re.S)
    keywords = [k.strip() for k in m.group(1).split(",") if k.strip()] if m else []
    (errors if len(keywords) != 5 else report).append(f"keywords: {len(keywords)} (JMLR asks for five)")

    cited = {
        k.strip()
        for group in re.findall(r"\\cite[pt]?\*?(?:\[[^\]]*\])*\{([^}]*)\}", body)
        for k in group.split(",")
    }
    entries = set(re.findall(r"@\w+\{([^,\s]+),", bib))
    missing = sorted(cited - entries)
    if missing:
        errors.append(f"citations without a references.bib entry: {missing}")
    report.append(
        f"citations: {len(cited)} keys, all in references.bib" if not missing else "citations: see errors"
    )
    unused = sorted(entries - cited)
    if unused:
        report.append(f"bibliography entries not cited (they will not be printed): {unused}")
    for fig in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", body):
        if not (HERE / fig).exists():
            errors.append(f"missing figure file: {fig}")
    labels = set(re.findall(r"\\label\{([^}]+)\}", body))
    for ref in re.findall(r"\\ref\{([^}]+)\}", body):
        if ref not in labels:
            errors.append(f"undefined reference: {ref}")
    todos = re.findall(r"\\TODO\{([^}]*)\}", body)
    text = body.split(r"\section{Introduction}", 1)[-1].split(r"\bibliography", 1)[0]
    report.append(f"body text: about {len(strip_latex(text).split())} words (page count needs a LaTeX build)")
    report.append(f"TODO markers: {len(todos)}" + "".join(f"\n  - {t}" for t in todos))
    for line in report:
        print(line)
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
