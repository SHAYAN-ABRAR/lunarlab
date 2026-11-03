# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Map every file of an archive candidate to the licence the proposal assigns it (LICENSING_PROPOSAL.md).

    python licence_map.py CANDIDATE OUT.json

Reads ``CANDIDATE/inventory.json``, which lists every file of the candidate except itself and ``SHA256SUMS``;
those two are added explicitly (``NOT_IN_INVENTORY``), so the map covers every file of the candidate. The first
rule that matches a path decides. Nothing is applied: the map is a proposal for the author, and a mapped file
is not a determination of anyone's rights. Exit status 1 if a file matches no rule, or if a file of the
candidate is missing from the map.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

PROPOSED = "CC-BY-4.0 (proposed)"
DECIDE = "author's decision"
# The candidate's own index files, which inventory.json does not list: it cannot list itself, or the checksum
# list that covers it.
NOT_IN_INVENTORY = ("inventory.json", "SHA256SUMS")
PROGRAM = r"\.(py|ps1|sh|ts|tsx|js|mjs|cjs|css|html|ipynb)$"
CONFIG = (
    r"\.(toml|cfg|ini|lock|in|yml|yaml)$"
    r"|/(package(-lock)?\.json|tsconfig[^/]*\.json|\.gitignore|\.gitattributes|\.editorconfig)$"
)
DATA = r"\.(json|jsonl|csv|npz|npy|log|txt|sha256|diff|xml|zip)$"
MEDIA = r"\.(pdf|svg|png|gif|webp|jpg|jpeg|mp4)$"
RULES = [
    (
        "third-party",
        r"^source/paper/neurocomputing/elsarticle(-num)?\.(cls|bst)$",
        "LPPL 1.3 or later (their own headers)",
        "unmodified third-party copies; the MIT License does not cover them",
    ),
    (
        "received",
        r"^source/reports/neurocomputing-final-(validation-2026-11-01|repairs-2026-11-03)/received/",
        DECIDE,
        "AI-prepared review material; it may be left out of a public deposit",
    ),
    (
        "manuscript",
        r"^source/paper/.+\.(tex|bib|bbl)$|^source/paper/[^/]+/(main|draft)[^/]*\.pdf$"
        r"|^source/paper/neurocomputing/(highlights\.txt|COVER_LETTER_DRAFT\.md)$",
        DECIDE,
        "article text",
    ),
    (
        "source-archives",
        r"^software/|^lunarlander-study/lunarlab-0\.1\.0-444a4c5-src\.tar\.gz$",
        "mixed: MIT for the code and documentation inside; the models and records inside follow their rules",
        "a container's label does not relicense the trained models and records it holds",
    ),
    (
        "models",
        r"^(outside-git|cartpole-study-output)/|^lunarlander-study/LunarLab_38_Policy_Study\.zip$"
        r"|^source/examples/(artifacts|learned-reward-artifacts)/",
        PROPOSED,
        "trained policies and their records",
    ),
    (
        "code",
        rf"^source/.*{PROGRAM}|^source/(lunarlab|tests|tools|frontend|scripts|examples|notebooks|\.github|\.vscode)/",
        "MIT",
        "repository licence",
    ),
    ("generated-docs", r"^source/docs/api/", "MIT", "API reference generated from the code"),
    ("records", r"^source/(reports|docs/results|demo)/", PROPOSED, "research records"),
    (
        "configuration",
        rf"^source/.*({CONFIG})|^source/\.(gitignore|gitattributes|editorconfig)$",
        "MIT",
        "repository licence",
    ),
    ("data", rf"^source/.*{DATA}", PROPOSED, "research data"),
    ("media", rf"^source/.*{MEDIA}", PROPOSED, "figures and media"),
    ("documentation", r"^source/", "MIT", "associated documentation files"),
    ("candidate", r"^[^/]+$", PROPOSED, "the candidate's own documents"),
]


def classify(path: str) -> tuple[str, str, str] | None:
    for name, pattern, licence, basis in RULES:
        if re.search(pattern, path):
            return name, licence, basis
    return None


def main() -> int:
    candidate, out = Path(sys.argv[1]), Path(sys.argv[2])
    files = json.loads((candidate / "inventory.json").read_text(encoding="utf-8"))["files"]
    paths = [f["path"] for f in files] + [n for n in NOT_IN_INVENTORY if (candidate / n).is_file()]
    entries, unmapped = {}, []
    for path in paths:
        found = classify(path)
        if found is None:
            unmapped.append(path)
            continue
        rule, licence, basis = found
        entries[path] = {"rule": rule, "licence": licence, "basis": basis}
    on_disk = {p.relative_to(candidate).as_posix() for p in candidate.rglob("*") if p.is_file()}
    not_mapped = sorted(on_disk - set(entries) - set(unmapped))
    counts = Counter(e["rule"] for e in entries.values())
    record = {
        "kind": "lunarlab.licence-map-proposal",
        "status": "proposal awaiting the author's decision; nothing applied; not a determination of rights",
        "scope": {
            "files_in_candidate": len(on_disk),
            "from_inventory": len(files),
            "added_explicitly": [n for n in NOT_IN_INVENTORY if n in entries],
            "in_candidate_but_not_mapped": not_mapped,
        },
        "rules": [{"rule": r, "pattern": p, "licence": lic, "basis": b} for r, p, lic, b in RULES],
        "counts": {r: counts.get(r, 0) for r, *_ in RULES},
        "unmapped": unmapped,
        "files": entries,
    }
    out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(record["scope"]), json.dumps(record["counts"]), f"unmapped: {len(unmapped)}")
    return 1 if unmapped or not_mapped else 0


if __name__ == "__main__":
    sys.exit(main())
