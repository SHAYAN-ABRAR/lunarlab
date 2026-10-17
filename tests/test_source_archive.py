# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""The source archive is deterministic, complete for installation and review, and free of extra files."""

from __future__ import annotations

import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / ".git").exists(), reason="needs a git checkout")


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_source_archive", ROOT / "tools" / "build_source_archive.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_archive_is_deterministic_and_contains_exactly_the_reviewable_sources(tmp_path):
    b = _builder()
    files, source = b.collect(None)
    m1 = b.build(files, source, tmp_path / "a")
    m2 = b.build(files, source, tmp_path / "b")
    assert m1["archive"]["sha256"] == m2["archive"]["sha256"]
    archive = tmp_path / "a" / m1["archive"]["file"]
    assert (tmp_path / "a" / "SHA256SUMS").read_text().split()[0] == m1["archive"]["sha256"]

    top = f"lunarlab-{b.version()}/"
    with tarfile.open(archive) as tf:
        members = tf.getmembers()
        names = [m.name for m in members]
        assert all(n.startswith(top.rstrip("/")) for n in names)
        assert all(
            m.uid == 0 and m.gid == 0 and m.uname == "" and m.mtime == source["source_date_epoch"]
            for m in members
        )
        paths = {n[len(top) :] for n, m in zip(names, members, strict=True) if m.isfile()}
        for required in ("LICENSE", "THIRD_PARTY_NOTICES.md", "CITATION.cff", "README.md", "pyproject.toml",
                         "requirements.lock", "requirements-ci.lock", "lunarlab/__init__.py", "tests/conftest.py",
                         "examples/artifacts/ppo-baseline-s0/checkpoint.zip", "frontend/package-lock.json"):  # fmt: skip
            assert required in paths, required
        assert not [p for p in paths if p.startswith(("demo/api/", "paper/", ".vscode/", ".git/"))]
        assert ".gitignore" not in paths
        # Text is stored exactly as git stores it (LF), so the archive does not depend on the checkout's platform.
        lic = tf.extractfile(f"{top}LICENSE").read()
        assert b"\r\n" not in lic
    manifest = json.loads(
        (tmp_path / "a" / f"{top.rstrip('/')}-src.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["n_files"] == len(paths) == len(manifest["files"])
    assert manifest["source"]["revision"] and manifest["source"]["mode"] == "working-tree"


def test_refused_files_stop_the_build():
    b = _builder()
    for bad in ("docs/.DS_Store", "frontend/._index.html", ".env", "lunarlab/x.pyc", "a/.git/config"):
        assert b._refused(bad), bad
    assert not b._refused("lunarlab/env.py") and not b._refused(".github/workflows/ci.yml")


def test_byte_exact_evidence_is_never_converted():
    """Files whose digests are recorded are stored byte for byte (.gitattributes ``-text``)."""
    b = _builder()
    paths = [
        "examples/artifacts/ppo-baseline-s0/config.yaml",
        "reports/jmlr/figures/reward_accounting.csv",
        "README.md",
    ]
    assert b._byte_exact(paths) == set(paths[:2])


def test_a_revision_packs_the_bytes_git_stores_on_every_platform():
    """git archive applies core.autocrlf (CRLF on Windows checkouts); the builder turns that off."""
    b = _builder()
    files, source = b.collect("HEAD")
    assert source["mode"] == "revision"
    for path in ("LICENSE", "README.md", "lunarlab/__init__.py"):
        assert b"\r\n" not in files[path], path


def test_working_tree_text_is_normalised_like_git():
    b = _builder()
    assert b._as_git_stores(b"a\r\nb\r\n") == b"a\nb\n"
    binary = b"\x89PNG\r\n\x1a\n\0\0\r\n"
    assert b._as_git_stores(binary) == binary
    raw = io.BytesIO()
    assert b._as_git_stores(raw.getvalue()) == b""
