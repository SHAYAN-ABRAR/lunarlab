# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Versioned provenance records for reward definitions.

A reward definition has two identities, and they are recorded separately because they establish different
things:

* the **declared definition** -- the original-reward weight and every term's JSON description. Its digest,
  ``definition_sha256``, is a full SHA-256 of the canonical JSON. Two terms with equal descriptions and
  different code have equal digests, so this digest alone never establishes what a term computes;
* the **implementation** -- the Python source file that defines each term's callables, with that file's
  SHA-256, and whether the file is tracked and unmodified in the git checkout at a known revision.

``implementation_identity`` summarises the second: ``recorded`` (every file tracked and unmodified at a
known revision), ``file-digests-only`` (every file hashed, but at least one untracked or modified, or no
revision), ``incomplete`` (at least one callable's source could not be located, as for code typed into
an interactive session), or ``no-terms`` (the definition is the original reward alone). A file digest covers that file's bytes only, not the modules it imports, data it
reads or the library versions it runs on.

The 16-character ``terms_hash`` of earlier records (schema 0) keeps its meaning and is carried as
``legacy_terms_hash`` so new records can be matched to old ones.
"""

from __future__ import annotations

import hashlib
import inspect
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lunarlab.audit.contracts import canonical_json, require_finite, require_json_finite

if TYPE_CHECKING:
    from lunarlab.audit.adapters import TaskAdapter
    from lunarlab.audit.core import RewardTerm

PROVENANCE_SCHEMA = "lunarlab.reward-provenance/1"
SCOPES = {
    "definition_sha256": (
        "SHA-256 of the canonical JSON of the declared term descriptions and the original-reward weight. "
        "It identifies what was declared, not what the term callables compute."
    ),
    "source_file_sha256": (
        "SHA-256 of the bytes of the file defining a callable, read at record time. It does not cover modules "
        "that file imports, data it reads, or interpreter and library versions."
    ),
    "source.revision": (
        "git revision of the checkout; it pins a callable's code only when that callable's file is tracked "
        "and unmodified."
    ),
    "legacy_terms_hash": (
        "schema-0 reward hash: the first 16 hex characters of SHA-256 over the same declared definition, "
        "kept so new records can be matched with older ones."
    ),
}


def definition_document(terms: Mapping[str, RewardTerm], original_weight: float) -> dict[str, Any]:
    """The declared definition: the original-reward weight and every term's description (validated)."""
    require_finite(original_weight, "original_weight")
    doc: dict[str, Any] = {"original_weight": original_weight, "terms": {}}
    for name, term in sorted(terms.items()):
        require_json_finite(dict(term.describe), f"reward term {name!r} description")
        doc["terms"][name] = dict(term.describe)
    return doc


def definition_sha256(terms: Mapping[str, RewardTerm], original_weight: float) -> str:
    """Full SHA-256 of the canonical JSON of the declared definition."""
    return hashlib.sha256(canonical_json(definition_document(terms, original_weight)).encode()).hexdigest()


def _repo_root() -> Path:
    from lunarlab.storage import project_root

    return project_root().resolve()


def _git(args: list[str], root: Path) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _callable_location(fn: Callable) -> tuple[str | None, str | None]:
    """(source file, reason it is unavailable)."""
    target = inspect.unwrap(fn)
    try:
        path = inspect.getsourcefile(target)
    except TypeError:
        return None, f"{type(target).__name__} objects have no Python source file (built-in or C extension)"
    if path is None:
        return None, "no source file is recorded for this callable"
    if path.startswith("<") and path.endswith(">"):
        return None, f"defined in {path}, an interactive or generated source that cannot be re-read"
    if not Path(path).is_file():
        return None, f"its source file {path} no longer exists"
    return path, None


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def callable_records(fns: list[Callable]) -> list[dict[str, Any]]:
    """Where each callable is defined, that file's SHA-256, and its git status (tracked, modified)."""
    root = _repo_root()
    records = []
    in_repo: dict[str, dict] = {}
    for fn in fns:
        target = inspect.unwrap(fn)
        rec: dict[str, Any] = {
            "module": getattr(target, "__module__", None),
            "qualname": getattr(target, "__qualname__", type(target).__name__),
        }
        path, reason = _callable_location(target)
        if path is None:
            rec.update(source_file=None, source_file_sha256=None, status="unavailable", reason=reason)
        else:
            p = Path(path).resolve()
            rec["source_file_sha256"] = _sha256_file(p)
            try:
                rel = p.relative_to(root).as_posix()
                rec["source_file"] = rel
                in_repo[rel] = rec
            except ValueError:
                rec["source_file"] = p.as_posix()
                rec["git"] = None
                rec["status"] = "file-digest-only"
                rec["reason"] = "the file is outside the repository checkout"
        records.append(rec)
    if in_repo:
        tracked_out = _git(["ls-files", "--", *sorted(in_repo)], root)
        status_out = _git(["status", "--porcelain", "--", *sorted(in_repo)], root)
        tracked = set(tracked_out.stdout.split()) if tracked_out and tracked_out.returncode == 0 else None
        modified = (
            {line[3:].strip().strip('"') for line in status_out.stdout.splitlines() if len(line) > 3}
            if status_out and status_out.returncode == 0
            else None
        )
        for rel, rec in in_repo.items():
            if tracked is None or modified is None:
                rec["git"] = None
                rec["status"] = "file-digest-only"
                rec["reason"] = "git status is unavailable"
                continue
            is_tracked, is_modified = rel in tracked, rel in modified
            rec["git"] = {"tracked": is_tracked, "modified": is_modified}
            if is_tracked and not is_modified:
                rec["status"] = "tracked-unmodified"
            else:
                rec["status"] = "file-digest-only"
                rec["reason"] = "untracked file" if not is_tracked else "uncommitted changes in the file"
    return records


def _implementation_callables(term: RewardTerm) -> list[Callable]:
    return [term.fn, *getattr(term, "components", ())]


def reward_provenance(
    terms: Mapping[str, RewardTerm] | None, original_weight: float, *, adapter: TaskAdapter | None = None
) -> dict[str, Any]:
    """The versioned provenance record of a reward definition (see the module docstring for scopes)."""
    from lunarlab.audit.core import terms_hash
    from lunarlab.sysinfo import git_state

    terms = dict(terms or {})
    doc = definition_document(terms, original_weight)
    term_records = {}
    statuses = []
    reasons = []
    for name, term in sorted(terms.items()):
        impl = callable_records(_implementation_callables(term))
        term_records[name] = {
            "term_id": getattr(term, "term_id", None),
            "term_version": getattr(term, "version", None),
            "implementation": impl,
        }
        for rec in impl:
            statuses.append(rec["status"])
            if rec["status"] != "tracked-unmodified":
                reasons.append(f"{name}: {rec['qualname']}: {rec.get('reason')}")
    source = git_state()
    if not terms:
        identity = "no-terms"
    elif "unavailable" in statuses:
        identity = "incomplete"
    elif statuses and (not source.get("available") or "file-digest-only" in statuses):
        identity = "file-digests-only"
    else:
        identity = "recorded"
    if not source.get("available"):
        reasons.append(f"source revision unavailable: {source.get('reason')}")
    return {
        "schema": PROVENANCE_SCHEMA,
        "definition": doc,
        "definition_sha256": hashlib.sha256(canonical_json(doc).encode()).hexdigest(),
        "legacy_terms_hash": terms_hash(terms, original_weight),
        "adapter": {"name": adapter.name, "version": adapter.version} if adapter is not None else None,
        "terms": term_records,
        "source": source,
        "implementation_identity": identity,
        "incomplete_reasons": reasons,
        "scopes": SCOPES,
    }
