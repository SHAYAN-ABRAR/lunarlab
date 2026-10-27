# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Check or add the SPDX license header of every project-authored source file.

    python tools/spdx_headers.py           # list files without the header (exit 1 if any)
    python tools/spdx_headers.py --fix     # add the header where it is missing

JMLR-MLOSS asks that the licensing terms be "clearly stated in the source package and mentioned in
each source file". Every source file therefore starts with two SPDX lines (after a doctype or shebang
line where one is required first)::

    SPDX-FileCopyrightText: 2026 Shayan Abrar
    SPDX-License-Identifier: MIT

in the file type's comment syntax. Data, documentation and lock files are covered by LICENSE.
Files are found with ``git ls-files`` (tracked and untracked-but-not-ignored); outside a git checkout
(an extracted source archive) the tree is walked instead.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOLDER = "2026 Shayan Abrar"
LICENSE_ID = "MIT"
MARK = "SPDX-License-Identifier:"

COMMENT = {  # suffix -> (line prefix, line suffix)
    ".py": ("# ", ""),
    ".ps1": ("# ", ""),
    ".yml": ("# ", ""),
    ".yaml": ("# ", ""),
    ".ts": ("// ", ""),
    ".tsx": ("// ", ""),
    ".js": ("// ", ""),
    ".mjs": ("// ", ""),
    ".cjs": ("// ", ""),
    ".css": ("/* ", " */"),
    ".html": ("<!-- ", " -->"),
}
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "dist-demo",
    "__pycache__",
    "test-results",
    "playwright-report",
    ".e2e-home",
    ".e2e-audit-home",
    "data",
    "runs",
    "reports",
    "demo",
}


# Data, not source: byte-identical copies whose SHA-256 digests are recorded (a header would change them).
DATA_PREFIXES = ("examples/artifacts/", "examples/learned-reward-artifacts/", "demo/", "reports/")


def source_files(root: Path = ROOT) -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        paths = [root / p for p in out]
    except (OSError, subprocess.CalledProcessError):
        paths = [p for p in root.rglob("*") if not (set(p.relative_to(root).parts) & SKIP_DIRS)]
    return sorted(
        p
        for p in paths
        if p.suffix in COMMENT
        and p.is_file()
        and not p.relative_to(root).as_posix().startswith(DATA_PREFIXES)
    )


def header_lines(suffix: str) -> list[str]:
    pre, post = COMMENT[suffix]
    return [f"{pre}SPDX-FileCopyrightText: {HOLDER}{post}", f"{pre}{MARK} {LICENSE_ID}{post}"]


def has_header(path: Path) -> bool:
    head = path.read_text(encoding="utf-8", errors="replace").splitlines()[:4]
    return any(MARK in line for line in head)


def add_header(path: Path) -> None:
    raw = path.read_bytes()
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    lines = raw.split(newline) if raw else []
    insert_at = 0
    if lines and (lines[0].startswith(b"#!") or lines[0].lower().startswith(b"<!doctype")):
        insert_at = 1  # a shebang or doctype must stay first
    block = [line.encode("utf-8") for line in header_lines(path.suffix)]
    if path.suffix == ".ps1":
        # PowerShell only finds comment-based help (<# .SYNOPSIS #>) that is separated from
        # preceding comments by a blank line.
        block.append(b"")
    path.write_bytes(
        newline.join(lines[:insert_at] + block + lines[insert_at:])
        if lines
        else newline.join(block) + newline
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fix", action="store_true", help="add the header to files that lack it")
    args = ap.parse_args()
    missing = [p for p in source_files() if not has_header(p)]
    if args.fix:
        for p in missing:
            add_header(p)
        print(f"added the SPDX header to {len(missing)} file(s)")
        return 0
    for p in missing:
        print(p.relative_to(ROOT).as_posix())
    print(f"{len(missing)} source file(s) without an SPDX header", file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
