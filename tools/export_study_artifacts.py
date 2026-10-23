# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Export every published study policy as a reproduction package, without touching the historical runs.

    python tools/export_study_artifacts.py --out <new folder>

For each run listed in ``docs/results/results.json`` this calls the existing command
``python -m lunarlab export-artifact --run-id <id> --out <folder>/<group>/<id>`` and records its exit code and
output. It then verifies, read-only, that every exported file is a byte-identical copy of its source in
``runs/<id>/`` and of the digest recorded in ``artifact.json``; that the exported checkpoint is the one the run's
freeze record names; and that the exported final-test evaluation is the evaluation ``results.json`` summarises
(file name, checkpoint, protocol hash, episode count, mean original return, strict pad-landing and time-limit
rates). Available provenance is copied unchanged into ``provenance/``: ``metadata.json``, ``status.json``,
``checkpoints/manifest.json``, ``events.jsonl``, and ``episodes.csv`` for the runs behind the learning-curve
figure (``reports/jmlr/figures/reward_accounting.sources.json``). A run that cannot be exported is reported with
the exact reason; nothing is repaired or regenerated. Writes ``inventory.json``, ``INVENTORY.md`` and
``SHA256SUMS`` into the output folder, and nothing anywhere else.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVENANCE = ("metadata.json", "status.json", "checkpoints/manifest.json", "events.jsonl")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _checks(rid: str, out: Path, summary: dict) -> list[dict]:
    """Read-only comparison of the export with the run's own files and the published summary."""
    run = ROOT / "runs" / rid
    manifest = json.loads((out / "artifact.json").read_text(encoding="utf-8"))
    meta = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    frozen = meta["frozen_for_test"]
    evaluation = json.loads((out / "evaluation.json").read_text(encoding="utf-8"))
    sources = {
        "checkpoint.zip": ROOT / manifest["files"]["checkpoint.zip"]["source"],
        "config.yaml": ROOT / manifest["files"]["config.yaml"]["source"],
        "evaluation.json": ROOT / manifest["files"]["evaluation.json"]["source"],
    }
    checks = []
    for name, src in sources.items():
        exported, original = sha256(out / name), sha256(src)
        checks.append(
            {
                "check": f"{name} is a byte-identical copy of {src.relative_to(ROOT).as_posix()}",
                "ok": exported == original == manifest["files"][name]["sha256"],
                "exported_sha256": exported,
                "source_sha256": original,
            }
        )
    checks.append(
        {
            "check": "the exported checkpoint is the one the freeze record names",
            "ok": manifest["files"]["checkpoint.zip"]["sha256"] == frozen["checkpoint_sha256"]
            and manifest["files"]["checkpoint.zip"]["checkpoint_name"] == frozen["checkpoint"],
            "frozen_record": {"checkpoint": frozen["checkpoint"], "sha256": frozen["checkpoint_sha256"]},
        }
    )
    agg = evaluation["aggregate"]
    published = summary["evaluation"]
    pairs = {
        "file": (Path(manifest["files"]["evaluation.json"]["source"]).name, published["file"]),
        "checkpoint": (evaluation["checkpoint"].get("name"), published["checkpoint"]),
        "protocol_hash": (evaluation["protocol_hash"], published["protocol_hash"]),
        "n_episodes": (len(evaluation["episodes"]), published["n_episodes"]),
        "mean_original_return": (agg["original_return"]["mean"], published["mean_original_return"]),
        "pad_landing_rate": (agg["pad_landing"]["rate"], published["pad_landing_rate"]),
        "timeout_rate": (agg["timeout"]["rate"], published["timeout_rate"]),
    }
    checks.append(
        {
            "check": "the exported evaluation is the evaluation docs/results/results.json summarises",
            "ok": all(a == b for a, b in pairs.values()),
            "compared": {k: {"exported": a, "published": b} for k, (a, b) in pairs.items()},
        }
    )
    return checks


def _copy_provenance(rid: str, out: Path, curve_runs: dict) -> list[dict]:
    run = ROOT / "runs" / rid
    copied = []
    names = list(PROVENANCE) + (["episodes.csv"] if rid in curve_runs else [])
    for name in names:
        src = run / name
        if not src.is_file():
            copied.append({"file": name, "copied": False, "reason": "not present in the run directory"})
            continue
        dst = out / "provenance" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        digest = sha256(dst)
        entry = {"file": name, "copied": True, "sha256": digest, "identical_to_source": digest == sha256(src)}
        if name == "episodes.csv":
            entry["matches_figure_source_digest"] = digest == curve_runs[rid]
        copied.append(entry)
    return copied


def export_all(out: Path) -> dict:
    results = json.loads((ROOT / "docs" / "results" / "results.json").read_text(encoding="utf-8"))
    curve = json.loads(
        (ROOT / "reports/jmlr/figures/reward_accounting.sources.json").read_text(encoding="utf-8")
    )
    curve_runs = {r["run_id"]: r["episodes_csv_sha256"] for r in curve["runs"]}
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for group in results["groups"]:
        for summary in group["per_seed"]:
            rid = summary["run_id"]
            target = out / slug(group["reward_name"]) / rid
            if target.exists():
                raise SystemExit(f"{target} already exists; choose a new output folder")
            target.parent.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, "-m", "lunarlab", "export-artifact", "--run-id", rid, "--out", str(target)]
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            row = {
                "run_id": rid,
                "group": group["reward_name"],
                "algorithm": group["algo"],
                "seed": summary["seed"],
                "folder": target.relative_to(out).as_posix(),
                "command": f"python -m lunarlab export-artifact --run-id {rid} --out {target.relative_to(out).as_posix()}",
                "exit_code": proc.returncode,
                "output": (proc.stdout + proc.stderr).strip()[-2000:],
            }
            if proc.returncode == 0:
                row["checks"] = _checks(rid, target, summary)
                row["provenance"] = _copy_provenance(rid, target, curve_runs)
                row["verified"] = all(c["ok"] for c in row["checks"]) and all(
                    p.get("identical_to_source", True) and p.get("matches_figure_source_digest", True)
                    for p in row["provenance"]
                )
            else:
                row["verified"] = False
            rows.append(row)
            print(f"{'ok  ' if row['verified'] else 'FAIL'} {group['reward_name']:<32} {rid}", flush=True)
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name not in {"SHA256SUMS"})
    inventory = {
        "kind": "lunarlab.study-artifact-inventory",
        "source": "docs/results/results.json",
        "source_sha256": sha256(ROOT / "docs" / "results" / "results.json"),
        "experiments": results["experiments"],
        "policies": len(rows),
        "exported": sum(r["exit_code"] == 0 for r in rows),
        "verified": sum(r["verified"] for r in rows),
        "runs": rows,
    }
    (out / "inventory.json").write_text(
        json.dumps(inventory, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    lines = [
        "# Study artifact inventory",
        "",
        f"{inventory['exported']} of {inventory['policies']} published policies exported with `export-artifact`; "
        f"{inventory['verified']} verified byte for byte against `runs/` and against `docs/results/results.json` "
        f"(SHA-256 `{inventory['source_sha256'][:16]}…`). Details: `inventory.json`; digests: `SHA256SUMS`.",
        "",
        "| Group | Algorithm | Seed | Run | Export | Verified | Provenance copied |",
        "|---|---|---:|---|---|---|---|",
    ]
    for r in rows:
        prov = ", ".join(p["file"] for p in r.get("provenance", []) if p.get("copied")) or "-"
        lines.append(
            f"| {r['group']} | {r['algorithm']} | {r['seed']} | `{r['run_id']}` | exit {r['exit_code']} | "
            f"{'yes' if r['verified'] else 'NO'} | {prov} |"
        )
    failed = [r for r in rows if not r["verified"]]
    lines += [
        "",
        "**Failures:** " + ("; ".join(f"`{r['run_id']}`: {r['output'][-300:]}" for r in failed) or "none"),
    ]
    (out / "INVENTORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (out / "SHA256SUMS").write_text(
        "".join(f"{sha256(p)}  {p.relative_to(out).as_posix()}\n" for p in files),
        encoding="utf-8",
        newline="\n",
    )
    return inventory


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--out", required=True, help="new folder for the exports (outside the repository is best)"
    )
    args = ap.parse_args()
    inv = export_all(Path(args.out).resolve())
    print(f"exported {inv['exported']}/{inv['policies']}, verified {inv['verified']}/{inv['policies']}")
    return 0 if inv["verified"] == inv["policies"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
