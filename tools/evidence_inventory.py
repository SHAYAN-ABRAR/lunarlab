# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Hash the protected research evidence, or compare two such inventories.

The protected areas are the historical runs, the data home (reward models, datasets, run registry), the
existing reports, the published result summaries and media, the demo snapshot, the exported example
packages and the JMLR manuscript directory with its figure inputs. Directories outside the repository (for
example an exported study bundle) can be added with ``--external NAME=PATH``. Paths listed with
``--exclude`` (repository-relative prefixes) are new work and are left out of the protected set.

    python tools/evidence_inventory.py --out before.json
    python tools/evidence_inventory.py --out after.json --compare before.json

Each inventory maps ``area/relative/path`` to ``[size, sha256]``. A comparison prints the files added,
removed and changed in every area and exits 1 if any protected file was removed or changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREAS = (
    "runs",
    "data",
    "reports",
    "docs/results",
    "docs/media",
    "demo/api",
    "examples/artifacts",
    "paper/jmlr-mloss",
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory(root: Path, externals: dict[str, Path], exclude: list[str]) -> dict[str, list]:
    """``{key: [size, sha256]}`` for every file in the protected areas, sorted by key."""
    out: dict[str, list] = {}
    bases = [(area, root / area) for area in AREAS] + [(f"external:{n}", p) for n, p in externals.items()]
    for label, base in bases:
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(base).as_posix()
            key = f"{label}/{rel}"
            if not label.startswith("external:") and any(
                key.startswith(x.rstrip("/") + "/") for x in exclude
            ):
                continue
            out[key] = [p.stat().st_size, sha256(p)]
    return dict(sorted(out.items()))


def area_of(key: str) -> str:
    for area in AREAS:
        if key.startswith(area + "/"):
            return area
    return key.split("/", 1)[0]


def combined_digest(inv: dict[str, list]) -> str:
    """One digest over the whole inventory (keys, sizes and hashes)."""
    return hashlib.sha256(json.dumps(inv, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def compare(before: dict[str, list], after: dict[str, list]) -> dict:
    """Files added, removed and changed between two inventories, with per-area counts."""
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    unchanged = len(set(before) & set(after)) - len(changed)
    return {
        "protected_files_before": len(before),
        "unchanged": unchanged,
        "added": added,
        "removed": removed,
        "changed": changed,
        "per_area_before": dict(sorted(Counter(area_of(k) for k in before).items())),
        "per_area_added": dict(sorted(Counter(area_of(k) for k in added).items())),
        "combined_before": combined_digest(before),
        "combined_after_of_before_keys": combined_digest({k: after[k] for k in before if k in after}),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, help="write the inventory (JSON) here")
    ap.add_argument("--compare", help="an earlier inventory to compare with")
    ap.add_argument("--external", action="append", default=[], metavar="NAME=PATH")
    ap.add_argument("--exclude", action="append", default=[], metavar="PREFIX")
    args = ap.parse_args(argv)
    externals = {}
    for item in args.external:
        name, _, path = item.partition("=")
        externals[name] = Path(path)
    inv = inventory(ROOT, externals, args.exclude)
    Path(args.out).write_text(json.dumps(inv, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    per_area = dict(sorted(Counter(area_of(k) for k in inv).items()))
    print(f"{len(inv)} files; combined digest {combined_digest(inv)}")
    print("per area:", per_area)
    if not args.compare:
        return 0
    result = compare(json.loads(Path(args.compare).read_text(encoding="utf-8")), inv)
    print(f"unchanged {result['unchanged']} of {result['protected_files_before']} protected files")
    for label in ("added", "removed", "changed"):
        print(f"{label}: {len(result[label])}")
        for key in result[label][:20]:
            print("   ", key)
    return 1 if result["removed"] or result["changed"] else 0


if __name__ == "__main__":
    sys.exit(main())
