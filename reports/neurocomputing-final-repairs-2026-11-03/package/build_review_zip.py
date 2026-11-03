# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Assemble and seal the review ZIP of the final repairs, with ``SUMMARY.md`` as its first entry.

    python build_review_zip.py OUT.zip --commit REV --base BASE --summary SUMMARY.md --archive DIR \
        --archive-zip FILE --manuscript-build DIR --validation DIR --tests DIR

The ZIP holds (inside its top folder):

| Path | What |
|---|---|
| ``SUMMARY.md`` | Read first |
| ``READINESS.md`` | The current readiness record at ``REV`` |
| ``repository/`` | ``git archive REV`` of this work's paths: the dated folder, the validator, the notice generator and their tests, the manuscript source with its figures, highlights and drafts, the requirements, the archive drafts and tools, the README |
| ``git/`` | The branch bundle ``BASE..REV``, the commit list, the diff statistics, the full diff and the manuscript's diff |
| ``archive-candidate/`` | The new candidate's own documents and ``SHA256SUMS``, its ZIP's size and digests, its licence map |
| ``validation/`` | The candidate's fresh-extraction validation: its report, console and logs, unchanged |
| ``manuscript-build/`` | The CI build of the manuscript at ``REV``'s manuscript (PDF, page images, logs) |
| ``tests/`` | The local test logs |
| ``SHA256SUMS`` | Every other file |

The ZIP is written, CRC-tested, extracted into a new directory and checked against its ``SHA256SUMS``.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPAIRS = "reports/neurocomputing-final-repairs-2026-11-03"
PATHS = (
    REPAIRS,
    "reports/neurocomputing-final-validation-2026-11-01/archive",
    "tools/validate_review_package.py",
    "tools/third_party_notices.py",
    "tests/test_validator_failures.py",
    "tests/test_manuscript_check.py",
    "tests/test_followup_comparison.py",
    "tests/test_project_metadata.py",
    "paper/neurocomputing",
    "docs/neurocomputing",
    ".github/workflows/paper.yml",
    "THIRD_PARTY_NOTICES.md",
    "README.md",
)
MANUSCRIPT = ("paper/neurocomputing/main.tex", "paper/neurocomputing/AI_Disclosure_For_Submission.tex")
CANDIDATE_DOCS = (
    "START_HERE.md",
    "REVISIONS.md",
    "INVENTORY.md",
    "inventory.json",
    "LICENSES.md",
    "SHA256SUMS",
)


def git(*args: str) -> bytes:
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", *args], cwd=ROOT, check=True, capture_output=True
    ).stdout


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def md5(p: Path) -> str:
    h = hashlib.md5()  # noqa: S324 - Zenodo lists MD5 checksums; recorded beside SHA-256 for comparison only
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assemble(top: Path, a: argparse.Namespace) -> None:
    shutil.copyfile(a.summary, top / "SUMMARY.md")
    with tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", a.commit, *PATHS))) as tar:
        tar.extractall(top / "repository", filter="data")
    shutil.copyfile(top / "repository" / REPAIRS / "READINESS.md", top / "READINESS.md")
    g = top / "git"
    g.mkdir()
    branch = git("rev-parse", "--abbrev-ref", "HEAD").decode().strip()
    git("bundle", "create", str(g / "branch.bundle"), f"{a.base}..{branch}")
    (g / "commits.txt").write_bytes(
        git(
            "log",
            "--reverse",
            "--format=%H %ad %an <%ae>%n    %s",
            "--date=iso-strict",
            f"{a.base}..{a.commit}",
        )
    )
    (g / "diffstat.txt").write_bytes(git("diff", "--stat=160", a.base, a.commit))
    (g / "changes.diff").write_bytes(git("diff", a.base, a.commit, "--", ".", ":(exclude)docs/api"))
    (g / "manuscript.diff").write_bytes(git("diff", a.base, a.commit, "--", *MANUSCRIPT))
    (g / "manuscript.word-diff.txt").write_bytes(
        git("diff", "--word-diff=plain", a.base, a.commit, "--", *MANUSCRIPT)
    )
    ac = top / "archive-candidate"
    ac.mkdir()
    for name in CANDIDATE_DOCS:
        shutil.copyfile(a.archive / name, ac / name)
    zp = a.archive_zip
    (ac / "CANDIDATE_ZIP.txt").write_text(
        f"file: {zp.name}\nbytes: {zp.stat().st_size}\nsha256: {sha256(zp)}\nmd5: {md5(zp)}\n"
        "The candidate ZIP itself is not in this review ZIP; it stays with the author until any deposit.\n",
        encoding="utf-8",
        newline="\n",
    )
    shutil.copytree(a.validation, top / "validation")
    shutil.copytree(a.manuscript_build, top / "manuscript-build")
    shutil.copytree(a.tests, top / "tests")
    files = sorted(p for p in top.rglob("*") if p.is_file())
    (top / "SHA256SUMS").write_text(
        "".join(f"{sha256(p)} *{p.relative_to(top).as_posix()}\n" for p in files),
        encoding="utf-8",
        newline="\n",
    )


def seal(top: Path, out: Path) -> None:
    files = sorted(p for p in top.rglob("*") if p.is_file())
    order = [top / "SUMMARY.md"] + [p for p in files if p != top / "SUMMARY.md"]
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in order:
            z.write(p, f"{top.name}/{p.relative_to(top).as_posix()}")


def verify(out: Path) -> dict:
    with zipfile.ZipFile(out) as z:
        bad = z.testzip()
        first = z.namelist()[0]
        entries = len(z.namelist())
        target = Path(tempfile.mkdtemp(prefix="review-zip-check-"))
        z.extractall(target)
    top = next(target.iterdir())
    listed = [
        line.split(" *", 1) for line in (top / "SHA256SUMS").read_text(encoding="utf-8").splitlines() if line
    ]
    mismatched = [n for d, n in listed if not (top / n).is_file() or sha256(top / n) != d]
    present = {p.relative_to(top).as_posix() for p in top.rglob("*") if p.is_file()} - {"SHA256SUMS"}
    unlisted = sorted(present - {n for _, n in listed})
    shutil.rmtree(target)
    return {
        "crc_bad_member": bad,
        "first_entry": first,
        "entries": entries,
        "listed": len(listed),
        "mismatched": mismatched,
        "unlisted": unlisted,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--base", required=True)
    for name in ("summary", "archive", "archive-zip", "manuscript-build", "validation", "tests"):
        ap.add_argument(f"--{name}", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"{a.out} exists")
    stage = Path(tempfile.mkdtemp(prefix="review-zip-stage-")) / a.out.stem
    stage.mkdir()
    assemble(stage, a)
    seal(stage, a.out)
    shutil.rmtree(stage.parent)
    check = verify(a.out)
    ok = check["crc_bad_member"] is None and not check["mismatched"] and not check["unlisted"]
    print(f"{a.out}: {a.out.stat().st_size} bytes, sha256 {sha256(a.out)}")
    print(check)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
