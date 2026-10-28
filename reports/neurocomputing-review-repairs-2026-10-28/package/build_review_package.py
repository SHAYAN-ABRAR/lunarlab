# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Assemble the review package; SUMMARY.md, validation/ and SHA256SUMS are added afterwards.

    python build_review_package.py COMMIT OUT --manuscript-build DIR --study-output DIR --source-archive DIR \
        --deposit DIR --historical DIR

The paths inside the package are the repository's own, so every documented command runs unchanged.

| Path | What |
|---|---|
| ``source/`` | ``git archive COMMIT`` without line-ending conversion (the committed bytes) and without ``demo/api/``: the 26 MB web-demo snapshot, which no reproduction step reads and which is in ``git/branch.bundle`` |
| ``outside-git/`` | Files Git does not hold, at their repository paths: the 14 comparison-fixture policies |
| ``cartpole-study-output/`` | The 36 frozen checkpoints and 18 exported artifacts of the CartPole study |
| ``manuscript/build/`` | A CI build of the manuscript: PDF, page images, logs, ``SHA256SUMS`` |
| ``source-archive/`` | The deterministic source archive of the described revision, and its Windows verification log |
| ``git/`` | The branch bundle from ``BASE``, the commit list and diffs |
| ``deposit-candidate/`` | The local deposit candidate's ``README.md`` and ``SHA256SUMS``, without its data |
| ``historical-unchanged/`` | Digests of the historical study bundle, which is not included |

Every copied file whose digest is recorded in the repository is checked against that record.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
E = "reports/neurocomputing-2026-10-27"
R = "reports/neurocomputing-review-repairs-2026-10-28"
BRANCH = "research/neurocomputing-review-repairs"
BASE = "d5881cb"


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


def rows(listing: Path) -> list[tuple[str, str]]:
    out = []
    for line in listing.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            digest, name = line.split(None, 1)
            out.append((digest, name.strip().lstrip("*")))
    return out


def remove_tree(path: Path) -> None:
    def writable_then_retry(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    shutil.rmtree(path, onexc=writable_then_retry)


def copy_checked(src: Path, dst: Path, digest: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    if sha256(dst) != digest:
        raise SystemExit(f"digest mismatch: {src}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("commit")
    ap.add_argument("out", type=Path)
    for name in ("manuscript-build", "study-output", "source-archive", "deposit", "historical"):
        ap.add_argument(f"--{name}", type=Path, required=True)
    a = ap.parse_args()
    out = a.out
    if out.exists():
        remove_tree(out)
    out.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", a.commit))) as tar:
        members = [m for m in tar.getmembers() if not m.name.startswith("demo/api/")]
        tar.extractall(out / "source", members=members, filter="data")
    src = out / "source"
    for digest, name in rows(src / E / "workflow-comparison/protocol/HASHES.sha256"):
        if name.endswith("policy.zip"):
            target = out / "outside-git" / E / "workflow-comparison" / name
            copy_checked(ROOT / E / "workflow-comparison" / name, target, digest)
    for digest, name in rows(src / E / "cartpole-study/records/frozen-checkpoints.sha256"):
        copy_checked(a.study_output / name, out / "cartpole-study-output" / name, digest)
    for manifest in sorted((src / E / "cartpole-study/records").glob("*/artifacts/*/manifest.json")):
        part, run = manifest.parts[-4], manifest.parts[-2]
        art, dst = (
            a.study_output / part / "artifacts" / run,
            out / "cartpole-study-output" / part / "artifacts" / run,
        )
        copy_checked(art / "manifest.json", dst / "manifest.json", sha256(manifest))
        for name, info in json.loads(manifest.read_text(encoding="utf-8"))["files"].items():
            copy_checked(art / name, dst / name, info["sha256"])
    shutil.copytree(a.manuscript_build, out / "manuscript" / "build")
    sa = out / "source-archive"
    sa.mkdir()
    for name in ("lunarlab-0.1.0-src.tar.gz", "lunarlab-0.1.0-src.manifest.json", "SHA256SUMS"):
        shutil.copy2(a.source_archive / name, sa / name)
    for digest, name in rows(sa / "SHA256SUMS"):
        if sha256(sa / name) != digest:
            raise SystemExit(f"digest mismatch: source-archive/{name}")
    shutil.copy2(
        src / R / "validation/source-archive-c9b9384-windows.log", sa / "build-and-verify-windows.log"
    )
    g = out / "git"
    g.mkdir()
    git("bundle", "create", str(g / "branch.bundle"), f"{BASE}..{BRANCH}")
    (g / "commits.txt").write_bytes(
        git("log", "--reverse", "--format=%H %ad %an <%ae>%n    %s", "--date=iso-strict", f"{BASE}..{BRANCH}")
    )
    (g / "diffstat.txt").write_bytes(git("diff", "--stat=160", BASE, BRANCH))
    excluded = (f":(exclude){E}/cartpole-study/records", f":(exclude){R}/ci", ":(exclude)docs/api")
    (g / "code-docs-paper.diff").write_bytes(git("diff", BASE, BRANCH, "--", ".", *excluded))
    (g / "docs-api.diff").write_bytes(git("diff", BASE, BRANCH, "--", "docs/api"))
    dep = out / "deposit-candidate"
    dep.mkdir()
    for name in ("README.md", "SHA256SUMS"):
        shutil.copy2(a.deposit / name, dep / name)
    hist = out / "historical-unchanged"
    hist.mkdir()
    lines = [
        "# Historical material (unchanged, not included)",
        "",
        "The 38-policy LunarLander study and its exports are historical. These repairs did not retrain, re-export or",
        f"modify them; `source/{R}/integrity/` shows all 2,359 protected files unchanged. The study bundle is part",
        "of the local deposit candidate (`deposit-candidate/`). Digests:",
        "",
        "| Item | Bytes | SHA-256 |",
        "|---|---:|---|",
    ]
    for name in ("LunarLab_38_Policy_Study.zip", "lunarlab-0.1.0-444a4c5-src.tar.gz"):
        p = a.historical / name
        lines.append(f"| `{name}` | {p.stat().st_size:,} | `{sha256(p)}` |")
    (hist / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    files = [p for p in out.rglob("*") if p.is_file()]
    print(f"assembled {out}: {len(files)} files, {sum(p.stat().st_size for p in files) / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
