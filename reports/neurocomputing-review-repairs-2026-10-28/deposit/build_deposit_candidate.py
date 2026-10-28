# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Assemble a local deposit candidate for the Neurocomputing paper's software and research data.

    python build_deposit_candidate.py OUT --commit REV --source-archive DIR --study-output DIR --historical DIR

Nothing is uploaded or published, and no identifier is created. ``OUT`` receives:

- ``software/``: the deterministic source archive of the described revision, its manifest and digest;
- ``evidence/``: ``reports/neurocomputing-2026-10-27/`` and ``reports/neurocomputing-review-repairs-2026-10-28/``
  exactly as committed at ``REV`` (``git archive``);
- ``cartpole-study-output/``: the study runner's complete original output, with every scheduled and frozen
  checkpoint, the exported artifacts, the study indexes and the compute ledgers;
- ``comparison-fixture-policies/``: the 14 policies of the comparison fixtures, which Git does not hold;
- ``lunarlander-study/``: the historical 38-policy export and its source archive, unchanged;
- ``LICENSE``, ``THIRD_PARTY_NOTICES.md``, ``CITATION.cff`` and ``README.md``;
- ``SHA256SUMS``: every other file.

Every copied file whose digest is recorded elsewhere is checked against that record.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import shutil
import stat
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
E = ROOT / "reports/neurocomputing-2026-10-27"
R = ROOT / "reports/neurocomputing-review-repairs-2026-10-28"


def remove_tree(path: Path) -> None:
    """``shutil.rmtree`` that also removes read-only files (frozen checkpoints are read-only on purpose)."""

    def writable_then_retry(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    shutil.rmtree(path, onexc=writable_then_retry)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rows(listing: Path) -> list[tuple[str, str]]:
    out = []
    for line in listing.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            digest, name = line.split(None, 1)
            out.append((digest, name.strip().lstrip("*")))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--source-archive", type=Path, required=True)
    ap.add_argument("--study-output", type=Path, required=True)
    ap.add_argument("--historical", type=Path, required=True)
    a = ap.parse_args()
    out = a.out
    if out.exists():
        remove_tree(out)
    out.mkdir(parents=True)
    problems: list[str] = []

    software = out / "software"
    software.mkdir()
    for name in ("lunarlab-0.1.0-src.tar.gz", "lunarlab-0.1.0-src.manifest.json", "SHA256SUMS"):
        shutil.copy2(a.source_archive / name, software / name)
    for digest, name in rows(software / "SHA256SUMS"):
        if sha256(software / name) != digest:
            problems.append(f"software/{name}")

    archive = subprocess.run(
        [
            "git",
            "-c",
            "core.autocrlf=false",  # the committed bytes, without line-ending conversion
            "archive",
            "--format=tar",
            a.commit,
            E.relative_to(ROOT).as_posix(),
            R.relative_to(ROOT).as_posix(),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(out / "evidence", filter="data")

    study = out / "cartpole-study-output"
    shutil.copytree(a.study_output, study, ignore=shutil.ignore_patterns("__pycache__"))
    for digest, name in rows(E / "cartpole-study/records/frozen-checkpoints.sha256"):
        if sha256(study / name) != digest:
            problems.append(f"cartpole-study-output/{name}")

    fixtures = out / "comparison-fixture-policies"
    for digest, name in rows(E / "workflow-comparison/protocol/HASHES.sha256"):
        if name.endswith("policy.zip"):
            target = fixtures / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(E / "workflow-comparison" / name, target)
            if sha256(target) != digest:
                problems.append(f"comparison-fixture-policies/{name}")

    historical = out / "lunarlander-study"
    historical.mkdir()
    for name in ("LunarLab_38_Policy_Study.zip", "lunarlab-0.1.0-444a4c5-src.tar.gz"):
        shutil.copy2(a.historical / name, historical / name)

    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "CITATION.cff"):
        shutil.copy2(ROOT / name, out / name)
    shutil.copy2(Path(__file__).with_name("DEPOSIT_README.md"), out / "README.md")

    lines = [
        f"{sha256(p)}  {p.relative_to(out).as_posix()}"
        for p in sorted(out.rglob("*"))
        if p.is_file() and p != out / "SHA256SUMS"
    ]
    (out / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    files = sum(1 for p in out.rglob("*") if p.is_file())
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"{files} files, {size / 1e6:.1f} MB; digest problems: {problems or 'none'}")
    print(f"SHA256SUMS digest: {sha256(out / 'SHA256SUMS')}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
