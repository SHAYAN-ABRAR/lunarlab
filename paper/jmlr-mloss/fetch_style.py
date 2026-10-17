# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Download the official JMLR style file next to main.tex and verify it.

The style file is not stored in this repository because its repository (github.com/JmlrOrg/jmlr-style-file)
declares no license. This script fetches the exact revision this manuscript was prepared with and refuses the
file if its SHA-256 differs, so the style is never modified or silently replaced.

    python paper/jmlr-mloss/fetch_style.py
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

COMMIT = "f413f638b407af76074813f8f88a82a7a5a81e9d"
FILES = {"jmlr2e.sty": "a430a875d561235951800e4e21d2631e18ddf0b369646ec276f43ea5080f27c3"}
HERE = Path(__file__).resolve().parent


def main() -> int:
    for name, sha in FILES.items():
        url = f"https://raw.githubusercontent.com/JmlrOrg/jmlr-style-file/{COMMIT}/{name}"
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
        got = hashlib.sha256(data).hexdigest()
        if got != sha:
            print(f"{name}: SHA-256 {got} does not match the pinned {sha}; not written", file=sys.stderr)
            return 1
        (HERE / name).write_bytes(data)
        print(f"{name}: verified ({sha[:16]}…) from JmlrOrg/jmlr-style-file@{COMMIT[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
