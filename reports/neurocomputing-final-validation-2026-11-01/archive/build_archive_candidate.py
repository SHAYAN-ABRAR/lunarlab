# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Assemble the public-archive candidate: software, study records, trained policies and their verification.

    python build_archive_candidate.py OUT --commit REV --evidence DIR --historical DIR \
        --source-archive DIR --described-source-archive DIR

Nothing is uploaded or published, and no identifier is created or reserved. ``OUT`` must not exist.

The layout is that of a review package, so ``source/tools/validate_review_package.py`` validates it from a
fresh extraction:

| Path | What |
|---|---|
| ``START_HERE.md``, ``REVISIONS.md``, ``INVENTORY.md``, ``inventory.json``, ``LICENSES.md`` | Written here |
| ``source/`` | ``git archive REV`` without line-ending conversion: the committed bytes of the complete tree |
| ``software/<rev>/``, ``software/c9b9384/`` | Deterministic source archives (``tools/build_source_archive.py``) of ``REV`` and of the library revision the manuscript describes |
| ``outside-git/`` | The 14 comparison-fixture policies, which Git does not hold, at their repository paths |
| ``cartpole-study-output/`` | The CartPole study's 36 frozen checkpoints and 18 exported artifacts, and ``INTERMEDIATE_CHECKPOINTS.json``: the 156 scheduled checkpoints that are not distributed, each with the digest its run record gives |
| ``lunarlander-study/`` | The historical 38-policy bundle and the source archive it was repaired with, byte for byte |
| ``SHA256SUMS`` | Every other file |

Every copied file is checked against the digest a committed record gives it, and the builder stops at the first
mismatch. ``--evidence`` is the CartPole study's original output folder (it holds ``cartpole-study/``);
``--historical`` holds ``LunarLab_38_Policy_Study.zip`` and ``lunarlab-0.1.0-444a4c5-src.tar.gz``.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
E = "reports/neurocomputing-2026-10-27"
STUDY = f"{E}/cartpole-study"
COMPARISON = f"{E}/workflow-comparison"
FINAL = "reports/neurocomputing-final-validation-2026-11-01"
DESCRIBED = "c9b938446d26fd4890ecd7ff7e6099a319586ae8"
DIGEST_LINE = re.compile(r"^([0-9a-f]{64}) [ *](.+)$")
REVISIONS = [
    ("32823f35fd1b4b7495701ee0afa5a766119248d4", "Trained the 38 LunarLander policies (15 October 2026)",
     "`provenance/metadata.json` of every package (`system.git.revision`)"),
    ("41165997f9cda78bf30b26cf676b9db894c5d9e3", "Exported the 38 LunarLander packages",
     "`artifact.json` of every package (`exported_with`)"),
    ("444a4c5dc086ec6eb844b408453bd571c034ad96", "Repaired the bundle by adding the six learned-reward models (24 October)",
     "`lunarlander-study/lunarlab-0.1.0-444a4c5-src.tar.gz`; the bundle's `DEPENDENCIES.md`"),
    ("e7c3fabcc986ee66f56de6403f8772968559824d", "Ran the CartPole study and recorded the comparison fixtures (27 October)",
     "`run.json` (`software.git.revision`) and each fixture's `recorded_platform`"),
    ("30bd3f64b392b73f5a8d64422b05d801ba281f71", "Library revision described by the 27 October manuscript",
     f"`source/{E}/READINESS.md`"),
    (DESCRIBED, "Library revision the manuscript describes: the last commit that changed library code (28 October)",
     "`software/c9b9384/` (byte-identical to the Linux CI build of run 40712412847)"),
    ("98be27ac20b7b35bc82c8ec806edeffe2eee4efb", "`main` after the review repairs were merged (pull request #2; CI run 40755305285 passed)",
     "GitHub"),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rows(listing: Path) -> list[tuple[str, str]]:
    out = []
    for line in listing.read_text(encoding="utf-8").splitlines():
        m = DIGEST_LINE.match(line.strip())
        if m:
            out.append((m.group(1), m.group(2).strip()))
    return out


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-c", "core.autocrlf=false", *args], cwd=ROOT, check=True, capture_output=True).stdout


def copy_checked(src: Path, dst: Path, digest: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    if sha256(dst) != digest:
        raise SystemExit(f"digest mismatch: {src}")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def source_tree(out: Path, rev: str) -> None:
    with tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", rev))) as tar:
        tar.extractall(out / "source", filter="data")


def source_archives(out: Path, rev: str, current: Path, described: Path) -> dict:
    found = {}
    for label, folder in ((rev[:7], current), ("c9b9384", described)):
        target = out / "software" / label
        for name in ("lunarlab-0.1.0-src.tar.gz", "lunarlab-0.1.0-src.manifest.json", "SHA256SUMS"):
            target.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(folder / name, target / name)
        for digest, name in rows(target / "SHA256SUMS"):
            if sha256(target / name) != digest:
                raise SystemExit(f"digest mismatch: software/{label}/{name}")
        manifest = json.loads((target / "lunarlab-0.1.0-src.manifest.json").read_text(encoding="utf-8"))
        found[label] = {
            "sha256": sha256(target / "lunarlab-0.1.0-src.tar.gz"),
            "revision": (manifest.get("source") or {}).get("revision") or manifest.get("source"),
            "files": manifest.get("n_files"),
        }
    return found


def fixture_policies(out: Path) -> int:
    n = 0
    for digest, name in rows(out / "source" / COMPARISON / "protocol/HASHES.sha256"):
        if name.endswith("policy.zip"):
            copy_checked(ROOT / COMPARISON / name, out / "outside-git" / COMPARISON / name, digest)
            n += 1
    return n


def cartpole_output(out: Path, evidence: Path) -> dict:
    """Frozen checkpoints and artifacts, copied and checked; the scheduled checkpoints inventoried."""
    src = out / "source"
    original = evidence / "cartpole-study"
    dst = out / "cartpole-study-output"
    frozen_digests = set()
    for digest, name in rows(src / STUDY / "records/frozen-checkpoints.sha256"):
        copy_checked(original / name, dst / name, digest)
        frozen_digests.add(digest)
    artifacts = 0
    for manifest in sorted((src / STUDY / "records").glob("*/artifacts/*/manifest.json")):
        part, run = manifest.parts[-4], manifest.parts[-2]
        art, target = original / part / "artifacts" / run, dst / part / "artifacts" / run
        copy_checked(art / "manifest.json", target / "manifest.json", sha256(manifest))
        for name, info in json.loads(manifest.read_text(encoding="utf-8"))["files"].items():
            copy_checked(art / name, target / name, info["sha256"])
        artifacts += 1
    entries = []
    for run_json in sorted((src / STUDY / "records").glob("*/runs/*/run.json")):
        part, run = run_json.parts[-4], run_json.parts[-2]
        record = json.loads(run_json.read_text(encoding="utf-8"))
        for ck in record["checkpoints"]:
            path = f"{part}/runs/{run}/{ck['file']}"
            local = original / path
            if not local.is_file() or sha256(local) != ck["sha256"]:
                raise SystemExit(f"the original output lacks {path} with its recorded digest")
            entries.append(
                {
                    "path": path,
                    "step": ck["step"],
                    "bytes": local.stat().st_size,
                    "sha256": ck["sha256"],
                    "named_by": f"{STUDY}/records/{part}/runs/{run}/run.json",
                    "same_bytes_distributed_as_frozen": ck["sha256"] in frozen_digests,
                }
            )
    inventory = {
        "kind": "lunarlab.intermediate-checkpoints",
        "note": (
            "The scheduled checkpoints of the 18 CartPole runs, which this candidate does not distribute. Each is named, "
            "with its digest, by its run record; the digests here were checked against the study's original output "
            "on the author's machine. Entries marked same_bytes_distributed_as_frozen have the bytes of a frozen "
            "checkpoint that is distributed."
        ),
        "count": len(entries),
        "bytes": sum(e["bytes"] for e in entries),
        "not_distributed": entries,
    }
    write(dst / "INTERMEDIATE_CHECKPOINTS.json", json.dumps(inventory, indent=1) + "\n")
    return {
        "frozen": len(frozen_digests),
        "artifacts": artifacts,
        "intermediate_not_distributed": len(entries),
        "intermediate_bytes": inventory["bytes"],
        "intermediate_same_as_frozen": sum(e["same_bytes_distributed_as_frozen"] for e in entries),
    }


def historical(out: Path, folder: Path) -> None:
    for digest, name in rows(ROOT / FINAL / "archive/historical-bundle.sha256"):
        copy_checked(folder / name, out / "lunarlander-study" / name, digest)


PARTS = [
    ("source/", "The repository at the archive revision: code, tests, documentation, manuscript source, study records, protocols, comparison programs and results, figure scripts and plotted values"),
    ("software/", "Deterministic source archives (pip-installable)"),
    ("outside-git/", "Comparison-fixture policies, at their repository paths"),
    ("cartpole-study-output/", "CartPole frozen checkpoints, exported artifacts, inventory of undistributed checkpoints"),
    ("lunarlander-study/", "Historical 38-policy LunarLander bundle and its repair-time source archive"),
    ("", "This candidate's own documents"),
]


def part_of(rel: str) -> str:
    return next(p for p, _ in PARTS if rel.startswith(p))


def inventory(out: Path) -> list[dict]:
    files = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS" or (p.is_file() and p.parent != out):
            rel = p.relative_to(out).as_posix()
            files.append({"path": rel, "bytes": p.stat().st_size, "sha256": sha256(p), "part": part_of(rel)})
    return files


def start_here(rev: str, facts: dict) -> str:
    sa = facts["source_archives"]
    return f"""# LunarLab: archive candidate for the Neurocomputing software paper

**Status: a local candidate, not a deposit.** It was assembled on {facts["built_utc"]} from revision `{rev}`.
Nothing has been uploaded or published, and no DOI or other identifier exists or is reserved. The licence of the
records and model files is not yet chosen (`LICENSES.md`).

## What is here

| Path | Contents |
|---|---|
| `source/` | The repository at `{rev[:7]}` (`git archive`, committed bytes): library, tests, tools, documentation, the manuscript source, and under `source/reports/` the protocols, study records, comparison programs, fixtures (without their policies), results and validation records |
| `software/{rev[:7]}/` | Deterministic source archive of `{rev[:7]}` (SHA-256 `{sa[rev[:7]]["sha256"]}`), its manifest and digest |
| `software/c9b9384/` | Deterministic source archive of `c9b9384`, the library revision the manuscript describes (SHA-256 `{sa["c9b9384"]["sha256"]}`, byte-identical to the Linux CI build of run 40712412847). Library code is unchanged from `c9b9384` to `{rev[:7]}` |
| `outside-git/` | The {facts["fixture_policies"]} policy files of the workflow-comparison fixtures, at their repository paths |
| `cartpole-study-output/` | The CartPole study's {facts["cartpole"]["frozen"]} frozen checkpoints and {facts["cartpole"]["artifacts"]} exported artifacts. `INTERMEDIATE_CHECKPOINTS.json` lists the {facts["cartpole"]["intermediate_not_distributed"]} scheduled checkpoints that are not distributed ({facts["cartpole"]["intermediate_bytes"] / 1e6:.1f} MB), each with the digest its run record gives |
| `lunarlander-study/` | `LunarLab_38_Policy_Study.zip`: the 38 historical LunarLander policy packages (checkpoint, configuration, recorded 100-episode evaluation, provenance; the six learned-reward packages with their original reward models) and its inventory and digests. `lunarlab-0.1.0-444a4c5-src.tar.gz`: the source it was repaired with. Both byte for byte as recorded in `source/{FINAL}/archive/historical-bundle.sha256` |
| `REVISIONS.md` | Which revision produced which evidence |
| `INVENTORY.md`, `inventory.json` | Every file with its size and SHA-256, and the records that name the scientific dependencies |
| `LICENSES.md` | Licences: MIT for the software; the records and models await the author's choice |
| `SHA256SUMS` | Every other file |

The evidence sets are distinct and are not interchangeable:

- **LunarLander:** 3,800 recorded test episodes (38 policies x 100), recorded on Windows 11.
- **CartPole:** a separate prespecified study of 18 policies, whose final tests are 15 x 100 and 3 x 20
  episodes.
- **Comparison:** a fault-injection study of 14 cases and three workflows.
- **Replays:** re-evaluations of recorded episodes. They are a fourth kind of evidence and are not new
  episodes of any of the above.

## Checking it from a fresh extraction

Prerequisites: Python 3.12 and [uv](https://docs.astral.sh/uv/). The validator creates a new virtual environment from the locked dependencies in
`source/` and gives every command an empty data home (`LUNARLAB_HOME`), so nothing is read from an
existing LunarLab installation. Nothing is trained.

```bash
sha256sum -c SHA256SUMS                       # Linux; on Windows see the PowerShell line below
python source/tools/validate_review_package.py . ../lunarlab-validation \\
    --fresh-venv --commands --unmodified-comparison --lunarlander-replays all
```

```powershell
Get-Content SHA256SUMS | ForEach-Object {{ $d, $n = $_ -split ' \\*', 2; if ((Get-FileHash -Algorithm SHA256 $n).Hash.ToLower() -ne $d) {{ "MISMATCH $n" }} }}
```

The validator writes `../lunarlab-validation/validation.json`. It exits 0 only if every step passes, and it
writes its report even when a step fails. Its steps are:

1. **Checksums:** every file here is listed in `SHA256SUMS` with its digest.
2. **Dependencies:** every file a record names is present with its recorded digest:
   - the CartPole study indexes and analysis inputs, the frozen checkpoints and the exported artifacts;
   - the comparison fixtures and programs, and the follow-up comparison programs;
   - the figure inputs and the learned-reward packages;
   - the historical bundle.

   Every checkpoint a CartPole run record names is either distributed or listed in
   `INTERMEDIATE_CHECKPOINTS.json` with the same digest.
3. **CartPole analysis:** it is recomputed from the run records and compared with the committed results. All
   18 runs are checked against the study protocol and the frozen checkpoints.
4. **Figures:** they are rebuilt, and the plotted values are compared separately from the image bytes.
5. **LunarLander bundle:** each of its members is checked against the bundle's digest list, which equals the
   list committed in `source/reports/jmlr/learned-reward-repair-2026-10-24/`. The per-policy statistics and
   group IQMs are recomputed from the 3,800 recorded episodes, without LunarLab code.
6. **Replays:** with `--lunarlander-replays all`, each of the 38 policies is replayed from its package. On
   the recording platform (Windows) a replay is expected to be `exact`. Elsewhere the existing
   `numerical-difference` classification may apply, and the report shows it.
7. **CartPole artifacts:** all 18 are verified and replayed.
8. **Workflow comparison:**
   - **Version 2:** the follow-up runner `source/{FINAL}/comparison-v2/`, assessed against the historical
     Windows results;
   - **Unmodified:** with `--unmodified-comparison`, also the frozen runner and programs, assessed by the
     same rules.

## Limitations (also in `source/{FINAL}/READINESS.md`)

- **Linux coverage:** on Linux, nine of the 38 LunarLander policies have been replayed in CI: the three
  example packages and the six learned-reward packages. Bit-identical results across operating systems are
  not a supported guarantee.
- **Platforms of this validation:** it has been run on the author's Windows machine. A Linux run of this
  validator on this candidate has not been done.
- **Not recomputed or distributed:** bootstrap intervals are not recomputed. The scheduled CartPole
  checkpoints are not distributed; the inventory lists them.
- **Provenance:** reward-definition provenance does not cover imported modules, module-level data or library
  versions.
- **Users:** no independent person has yet installed or used LunarLab.
"""


def revisions(rev: str, facts: dict) -> str:
    lines = [
        "# Revisions",
        "",
        f"This candidate's `source/` is revision `{rev}`. Earlier revisions produced the historical evidence, which",
        "is preserved byte for byte, not regenerated.",
        "",
        "| Revision | What it is | Where it is recorded |",
        "|---|---|---|",
    ]
    lines += [f"| `{r}` | {what} | {where} |" for r, what, where in REVISIONS]
    lines.append(
        f"| `{rev}` | This candidate's source: the library of `c9b9384`, the follow-up comparison programs and the "
        f"repaired package validator, with the manuscript source | `source/`; `software/{rev[:7]}/` |"
    )
    lines += [
        "",
        "The manuscript PDF is built from `source/paper/neurocomputing/` by CI; the build run is recorded in",
        f"`source/{FINAL}/README.md`.",
    ]
    return "\n".join(lines) + "\n"


def licences() -> str:
    return f"""# Licences

- **Software:** the source code, scripts and tools (`source/`, `software/`) are under the MIT License
  (`source/LICENSE`). Third-party components and their licences are listed in `source/THIRD_PARTY_NOTICES.md`.
- **Records, results, trained policies and reward models:** **not yet licensed.** The author must choose a
  licence before any deposit. A proposal, with a file-to-licence map, is in
  `source/{FINAL}/archive/LICENSING_PROPOSAL.md`. Until a choice is recorded, no licence is granted for these
  files beyond what the law allows.
"""


def inventory_md(files: list[dict], facts: dict) -> str:
    by_part: dict[str, list[int]] = {}
    for f in files:
        by_part.setdefault(f["part"], [0, 0])
        by_part[f["part"]][0] += 1
        by_part[f["part"]][1] += f["bytes"]
    lines = [
        "# Inventory",
        "",
        "`inventory.json` lists every file of this candidate with its size and SHA-256 (as `SHA256SUMS` does) and",
        "the part it belongs to.",
        "",
        "| Part | Files | MB | Contents |",
        "|---|---:|---:|---|",
    ]
    for prefix, what in PARTS:
        n, b = by_part.get(prefix, [0, 0])
        lines.append(f"| `{prefix or '(top level)'}` | {n:,} | {b / 1e6:.1f} | {what} |")
    lines += [
        f"| **Total** | **{len(files):,}** | **{sum(f['bytes'] for f in files) / 1e6:.1f}** | (and `SHA256SUMS`) |",
        "",
        "## Scientific dependencies and the records that name them",
        "",
        "| Record (under `source/`) | What it names, by SHA-256 |",
        "|---|---|",
        f"| `{STUDY}/records/*/study.json`, `{STUDY}/results/results.json`, `pilot-results/results.json` | The 72 CartPole run records and the analysis inputs |",
        f"| `{STUDY}/records/frozen-checkpoints.sha256` | The 36 frozen checkpoints in `cartpole-study-output/` |",
        f"| `{STUDY}/records/*/artifacts/*/manifest.json` | The files of the 18 exported artifacts |",
        f"| `{STUDY}/records/*/runs/*/run.json` | Every scheduled checkpoint; the {facts['cartpole']['intermediate_not_distributed']} not distributed are listed in `cartpole-study-output/INTERMEDIATE_CHECKPOINTS.json` |",
        f"| `{COMPARISON}/protocol/HASHES.sha256` | The comparison protocol, the 14 fixtures (policies in `outside-git/`), the three programs and the runner (79 entries) |",
        f"| `{FINAL}/comparison-v2/HASHES-v2.sha256` | The follow-up programs, runner and assessment |",
        "| `paper/neurocomputing/figures/MANIFEST.json` | The figure inputs |",
        "| `examples/learned-reward-artifacts/SHA256SUMS` | The six learned-reward packages and their reward models |",
        f"| `{FINAL}/archive/historical-bundle.sha256` | `lunarlander-study/`: the bundle and its source archive |",
        "| `reports/jmlr/learned-reward-repair-2026-10-24/study-artifacts/SHA256SUMS` | The 333 listed members of the bundle (its `DEPENDENCIES.md`, `INVENTORY.md` and `inventory.json` are committed beside it) |",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--historical", type=Path, required=True)
    ap.add_argument("--source-archive", type=Path, required=True)
    ap.add_argument("--described-source-archive", type=Path, required=True)
    a = ap.parse_args()
    out = a.out
    if out.exists():
        raise SystemExit(f"{out} exists; choose a new directory")
    rev = git("rev-parse", a.commit).decode().strip()
    out.mkdir(parents=True)
    source_tree(out, rev)
    facts = {
        "built_utc": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "source_archives": source_archives(out, rev, a.source_archive, a.described_source_archive),
        "fixture_policies": fixture_policies(out),
        "cartpole": cartpole_output(out, a.evidence),
    }
    if facts["source_archives"][rev[:7]]["revision"] not in (rev, rev[:7], None):
        raise SystemExit(f"--source-archive was built from {facts['source_archives'][rev[:7]]['revision']}, not {rev}")
    historical(out, a.historical)
    write(out / "START_HERE.md", start_here(rev, facts))
    write(out / "REVISIONS.md", revisions(rev, facts))
    write(out / "LICENSES.md", licences())
    files = inventory(out)
    write(out / "INVENTORY.md", inventory_md(files, facts))
    files = inventory(out)
    record = {"kind": "lunarlab.archive-inventory", "revision": rev, "facts": facts, "files": files}
    write(out / "inventory.json", json.dumps(record, indent=1) + "\n")
    listing = [
        f"{sha256(p)} *{p.relative_to(out).as_posix()}" for p in sorted(out.rglob("*")) if p.is_file() and p != out / "SHA256SUMS"
    ]
    write(out / "SHA256SUMS", "\n".join(listing) + "\n")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(json.dumps({**facts, "files": len(listing) + 1, "bytes": size, "sha256sums": sha256(out / "SHA256SUMS")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
