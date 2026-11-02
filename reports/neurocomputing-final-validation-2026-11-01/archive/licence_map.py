# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Map every file of an archive candidate to the licence the proposal assigns it (LICENSING_PROPOSAL.md).

    python licence_map.py CANDIDATE OUT.json

Reads ``CANDIDATE/inventory.json``. The first rule that matches a path decides. Nothing is applied: the map is a
proposal for the author. Exit status 1 if a file matches no rule.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

PROPOSED = "CC-BY-4.0 (proposed)"
DECIDE = "author's decision"
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
        "LPPL-1.3c",
        "their own licence",
    ),
    (
        "received",
        r"^source/reports/neurocomputing-final-validation-2026-11-01/received/",
        DECIDE,
        "review material",
    ),
    (
        "manuscript",
        r"^source/paper/.+\.(tex|bib|bbl)$|^source/paper/[^/]+/(main|draft)[^/]*\.pdf$",
        DECIDE,
        "article text",
    ),
    (
        "software",
        r"^software/|^lunarlander-study/lunarlab-0\.1\.0-444a4c5-src\.tar\.gz$",
        "MIT",
        "source archives",
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
    entries, unmapped = {}, []
    for f in files:
        found = classify(f["path"])
        if found is None:
            unmapped.append(f["path"])
            continue
        rule, licence, basis = found
        entries[f["path"]] = {"rule": rule, "licence": licence, "basis": basis}
    counts = Counter(e["rule"] for e in entries.values())
    record = {
        "kind": "lunarlab.licence-map-proposal",
        "status": "proposal awaiting the author's decision; nothing applied",
        "rules": [{"rule": r, "pattern": p, "licence": lic, "basis": b} for r, p, lic, b in RULES],
        "counts": {r: counts.get(r, 0) for r, *_ in RULES},
        "unmapped": unmapped,
        "files": entries,
    }
    out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(record["counts"]), f"unmapped: {len(unmapped)}")
    return 1 if unmapped else 0


if __name__ == "__main__":
    sys.exit(main())
