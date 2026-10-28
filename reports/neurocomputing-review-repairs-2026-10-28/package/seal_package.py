# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Write a package's SHA256SUMS and zip it, with SUMMARY.md (when present) and SHA256SUMS first.

    python seal_package.py PACKAGE_DIR ZIP

Prints the number of files, the ZIP's size and its SHA-256, and writes ``ZIP.sha256`` beside the ZIP.
"""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(root: Path, zpath: Path) -> int:
    files = sorted(p for p in root.rglob("*") if p.is_file() and p != root / "SHA256SUMS")
    listing = "".join(f"{sha256(p)}  {p.relative_to(root).as_posix()}\n" for p in files)
    (root / "SHA256SUMS").write_text(listing, encoding="utf-8", newline="\n")
    first = [p for p in (root / "SUMMARY.md", root / "SHA256SUMS") if p.is_file()]
    order = first + [p for p in files if p not in first]
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in order:
            z.write(p, f"{root.name}/{p.relative_to(root).as_posix()}")
    with zipfile.ZipFile(zpath) as z:
        bad = z.testzip()
        first_entry = z.namelist()[0]
    digest = sha256(zpath)
    Path(f"{zpath}.sha256").write_text(f"{digest}  {zpath.name}\n", encoding="utf-8", newline="\n")
    print(
        f"{len(files)} files listed; first entry {first_entry}; testzip {bad}; {zpath.stat().st_size} bytes; sha256 {digest}"
    )
    return 0 if bad is None else 1


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
