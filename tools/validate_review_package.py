# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Validate a review package: its checksums, its scientific dependencies and the reproduction of its results.

    python tools/validate_review_package.py PACKAGE OUT [--fresh-venv] [--commands]

A checksum manifest only covers the files that happen to be present. This script also checks that every file
the scientific records *name* is present with its recorded digest, then recomputes from those records.

**Package layout** (described in the package's ``SUMMARY.md``):

- ``source/``: the repository tree at the package's commit;
- ``outside-git/``: files Git does not hold, at their repository paths, overlaid on ``source/``;
- ``cartpole-study-output/``: the CartPole study runner's frozen checkpoints and exported artifacts;
- ``SHA256SUMS``: every other file of the package.

**Steps** (the report is ``OUT/validation.json``):

1. **Checksums:** every file in ``SHA256SUMS`` is present with its digest, and every file is listed.
2. **Dependencies:** every file named by the CartPole study indexes, the analysis inputs, the frozen-checkpoint
   list, the exported-artifact manifests, the comparison and protocol hash lists, the figure manifest and the
   learned-reward packages is present with its recorded digest.
3. **Recomputation:** in a working copy (``OUT/work``), the CartPole analysis is rerun from the run records
   and compared with the committed results. The run records are checked against the study protocol and the
   frozen checkpoints. Every figure is rebuilt, and its plotted values (``*.values.json``) are compared;
   identical bytes are reported separately, because PDF, SVG and PNG bytes depend on the Matplotlib and font
   versions.
4. **Documented commands** (``--commands``): these run in an empty data home, with the working copy's code:
   - a published artifact's replay;
   - a learned-reward replay;
   - verification and replay of every exported CartPole artifact;
   - the full workflow comparison on its fixtures.

   ``--fresh-venv`` first installs the working copy, with its locked dependencies, into a new virtual
   environment (with uv), so nothing is imported from the machine's own checkout.

Nothing is trained. The exit status is 0 only if every step passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPORTS = "reports/neurocomputing-2026-10-27"
STUDY = f"{REPORTS}/cartpole-study"
COMPARISON = f"{REPORTS}/workflow-comparison"
VERIFY_STUDY = "reports/neurocomputing-review-repairs-2026-10-28/recovery/verify_cartpole_study.py"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hash_list(path: Path) -> list[tuple[str, str]]:
    """``(digest, name)`` rows of a ``sha256sum``-style list; comment lines are skipped."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            digest, name = line.split(None, 1)
            rows.append((digest, name.strip().lstrip("*")))
    return rows


class Dependencies:
    """Every scientific dependency, checked as present with its recorded digest."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.problems: list[str] = []

    def need(self, group: str, path: Path, digest: str, shown: str) -> None:
        self.counts[group] = self.counts.get(group, 0) + 1
        if not path.is_file():
            self.problems.append(f"{group}: missing {shown}")
        elif sha256(path) != digest:
            self.problems.append(f"{group}: {shown} does not have its recorded digest")


def check_study_records(tree: Path, deps: Dependencies) -> None:
    """The files the CartPole study indexes and analysis name: what ``analyze.py`` needs to recompute."""
    for part, results in (("main", "results"), ("pilot", "pilot-results")):
        records = tree / STUDY / "records" / part
        for run in load(records / "study.json")["runs"]:
            for fname, digest in run["files"].items():
                rel = f"runs/{run['run']}/{fname}"
                deps.need("study index", records / rel, digest, f"{STUDY}/records/{part}/{rel}")
        for rel, digest in load(tree / STUDY / results / "results.json")["inputs_sha256"].items():
            deps.need("analysis input", records / rel, digest, f"{STUDY}/records/{part}/{rel}")


def check_dependencies(tree: Path, study_output: Path | None) -> Dependencies:
    deps = Dependencies()
    check_study_records(tree, deps)
    for digest, name in hash_list(tree / STUDY / "protocol/PROTOCOL.sha256"):
        deps.need("CartPole protocol", tree / STUDY / "protocol" / name, digest, f"{STUDY}/protocol/{name}")
    if study_output is not None:
        for digest, name in hash_list(tree / STUDY / "records/frozen-checkpoints.sha256"):
            deps.need("frozen checkpoint", study_output / name, digest, f"cartpole-study-output/{name}")
        for manifest_path in sorted((tree / STUDY / "records").glob("*/artifacts/*/manifest.json")):
            part, run = manifest_path.parts[-4], manifest_path.parts[-2]
            art = study_output / part / "artifacts" / run
            deps.need(
                "exported artifact",
                art / "manifest.json",
                sha256(manifest_path),
                f"{part}/artifacts/{run}/manifest.json",
            )
            for name, info in load(manifest_path)["files"].items():
                deps.need("exported artifact", art / name, info["sha256"], f"{part}/artifacts/{run}/{name}")
    for digest, name in hash_list(tree / COMPARISON / "protocol/HASHES.sha256"):
        deps.need(
            "comparison fixtures and programs", tree / COMPARISON / name, digest, f"{COMPARISON}/{name}"
        )
    for figure in load(tree / "paper/neurocomputing/figures/MANIFEST.json").values():
        for rel, digest in (figure.get("inputs") or {}).items() if isinstance(figure, dict) else ():
            deps.need("figure input", tree / rel, digest, rel)
    lr = tree / "examples/learned-reward-artifacts"
    for digest, name in hash_list(lr / "SHA256SUMS"):
        deps.need("learned-reward package", lr / name, digest, f"examples/learned-reward-artifacts/{name}")
    return deps


def check_checksums(package: Path) -> dict:
    listed = hash_list(package / "SHA256SUMS")
    bad = [
        name for digest, name in listed if not (package / name).is_file() or sha256(package / name) != digest
    ]
    names = {name for _, name in listed}
    present = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    unlisted = sorted(present - names - {"SHA256SUMS"})
    return {
        "listed": len(listed),
        "mismatched_or_missing": bad,
        "unlisted": unlisted,
        "ok": not bad and not unlisted,
    }


def run(cmd: list[str], cwd: Path, env: dict, log: Path) -> int:
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        f"$ {' '.join(cmd)}\n(exit {proc.returncode}, {time.perf_counter() - t0:.1f} s)\n{proc.stdout}{proc.stderr}",
        encoding="utf-8",
        newline="\n",
    )
    return proc.returncode


def make_venv(work: Path, out: Path) -> Path:
    venv = out / "venv"
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("--fresh-venv needs uv on PATH")
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    lock = "requirements.lock" if os.name == "nt" else "requirements-ci.lock"
    env = dict(os.environ)
    for cmd in (
        [uv, "venv", "--python", "3.12", str(venv)],
        [uv, "pip", "install", "--python", str(python), "-r", str(work / lock)]
        + ([] if os.name == "nt" else ["--torch-backend", "cpu"]),
        [uv, "pip", "install", "--python", str(python), "--no-deps", str(work)],
    ):
        if run(cmd, out, env, out / "logs" / f"venv-{cmd[1]}-{cmd[2]}.log") != 0:
            raise SystemExit(f"virtual environment step failed: {' '.join(cmd[:4])}")
    return python


def same_figures(work: Path, pristine: Path) -> dict:
    figures = work / "paper/neurocomputing/figures"
    out = {"values_identical": [], "values_differ": [], "bytes_identical": [], "bytes_differ": []}
    for path in sorted(figures.iterdir()):
        if path.suffix not in (".json", ".pdf", ".svg", ".png") or path.name == "MANIFEST.json":
            continue
        original = pristine / "paper/neurocomputing/figures" / path.name
        if path.name.endswith(".values.json"):
            key = "values_identical" if load(path) == load(original) else "values_differ"
            out[key].append(path.name)
        out["bytes_identical" if sha256(path) == sha256(original) else "bytes_differ"].append(path.name)
    return out


def commands(python: str, work: Path, out: Path, env: dict, study_output: Path) -> dict:
    results: dict = {}

    def home() -> str:
        return tempfile.mkdtemp(prefix="lunarlab-home-", dir=out)

    def cli(name: str, args: list[str], ok_codes=(0,)) -> int:
        code = run(
            [python, "-m", "lunarlab", *args],
            work,
            {**env, "LUNARLAB_HOME": home()},
            out / "logs" / f"{name}.log",
        )
        results[name] = {"exit": code, "ok": code in ok_codes}
        return code

    cli("version", ["--version"])
    for label, artifact in (
        ("replay-ppo-hover-bonus-s0", "examples/artifacts/ppo-hover-bonus-s0"),
        (
            "replay-learned-reward-0274",
            "examples/learned-reward-artifacts/20261015-235939-custom-s0-standard-0274",
        ),
    ):
        report = out / "reports" / f"{label}.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        empty = home()
        code = run(
            [python, "-m", "lunarlab", "reproduce-artifact", "--artifact", artifact, "--report", str(report)],
            work,
            {**env, "LUNARLAB_HOME": empty},
            out / "logs" / f"{label}.log",
        )
        status = load(report)["status"] if report.is_file() else None
        results[label] = {
            "exit": code,
            "status": status,
            "ok": code in (0, 3),
            "data_home_left_empty": not any(Path(empty).iterdir()),
        }
    statuses = {}
    for art in sorted(study_output.glob("*/artifacts/*")):
        copy = out / "cartpole-artifacts" / art.parts[-3] / art.name
        shutil.copytree(art, copy)
        tag = f"{art.parts[-3]}-{art.name}"
        verify = cli(f"cartpole-verify-{tag}", ["audit-artifact", "verify", "--artifact", str(copy)])
        report = out / "reports" / f"cartpole-{tag}.json"
        reproduce = cli(
            f"cartpole-reproduce-{tag}",
            ["audit-artifact", "reproduce", "--artifact", str(copy), "--report", str(report)],
            ok_codes=(0, 3),
        )
        statuses[tag] = {
            "verify_exit": verify,
            "reproduce_exit": reproduce,
            "status": load(report)["status"] if report.is_file() else None,
        }
    results["cartpole-artifacts"] = {
        "artifacts": statuses,
        "ok": all(v["verify_exit"] == 0 and v["reproduce_exit"] in (0, 3) for v in statuses.values()),
    }
    comp_out = out / "comparison"
    code = run(
        [
            python,
            str(work / COMPARISON / "run_comparison.py"),
            str(work / COMPARISON / "fixtures"),
            str(comp_out),
        ],
        work,
        {**env, "LUNARLAB_HOME": home()},
        out / "logs" / "comparison.log",
    )
    recorded = {
        (r["workflow"], r["case"]): r for r in load(work / COMPARISON / "results/summary.json")["rows"]
    }
    now = (
        {(r["workflow"], r["case"]): r for r in load(comp_out / "summary.json")["rows"]} if code == 0 else {}
    )

    def key(r: dict) -> tuple:
        return (
            r["verdict"],
            r["outcome"],
            r["exit_code"],
            r["episodes_executed"],
            {k: v["status"] for k, v in r["checks"].items()},
        )

    differences = [
        f"{w}/{c}" for (w, c), r in recorded.items() if (w, c) not in now or key(now[(w, c)]) != key(r)
    ]
    results["comparison"] = {
        "exit": code,
        "pairs": len(recorded),
        "differences": differences,
        "ok": code == 0 and not differences,
    }
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("package", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--fresh-venv", action="store_true")
    ap.add_argument("--commands", action="store_true")
    a = ap.parse_args()
    package, out = a.package.resolve(), a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "package": package.name,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    report["checksums"] = (
        check_checksums(package)
        if (package / "SHA256SUMS").is_file()
        else {"ok": None, "note": "no SHA256SUMS"}
    )
    work = out / "work"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(package / "source", work)
    overlay = package / "outside-git"
    for path in sorted(overlay.rglob("*")) if overlay.is_dir() else ():
        if path.is_file():
            target = work / path.relative_to(overlay)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    study_output = package / "cartpole-study-output"
    deps = check_dependencies(work, study_output if study_output.is_dir() else None)
    report["dependencies"] = {"checked": deps.counts, "problems": deps.problems, "ok": not deps.problems}
    python = str(make_venv(work, out)) if a.fresh_venv else sys.executable
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "LUNARLAB_HOME")}
    env.update(PYTHONIOENCODING="utf-8", PYTHONPATH="" if a.fresh_venv else str(work))
    report["python"] = python
    code = run(
        [
            python,
            str(work / VERIFY_STUDY),
            str(work),
            str(out / "study-verification"),
            "--checkpoints",
            str(study_output),
            "--frozen-only",
        ],
        work,
        env,
        out / "logs" / "study-verification.log",
    )
    report["cartpole_records"] = {
        "exit": code,
        "ok": code == 0,
        "report": "study-verification/VERIFICATION.md",
    }
    figures_code = run(
        [python, "paper/neurocomputing/figures/build_figures.py"], work, env, out / "logs" / "figures.log"
    )
    check_code = run(
        [python, "paper/neurocomputing/check_manuscript.py", "--final"],
        work,
        env,
        out / "logs" / "check-manuscript.log",
    )
    figures = same_figures(work, package / "source")
    report["figures"] = {
        **figures,
        "build_exit": figures_code,
        "check_exit": check_code,
        "ok": figures_code == 0 and check_code == 0 and not figures["values_differ"],
    }
    if a.commands:
        report["commands"] = commands(python, work, out, env, study_output)
    steps = [
        report["checksums"].get("ok") is not False,
        report["dependencies"]["ok"],
        report["cartpole_records"]["ok"],
        report["figures"]["ok"],
    ]
    steps += [v.get("ok", False) for v in report.get("commands", {}).values()]
    report["ok"] = all(steps)
    report["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (out / "validation.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    summary = {
        k: (v.get("ok") if isinstance(v, dict) else v)
        for k, v in report.items()
        if k not in ("package", "python")
    }
    print(json.dumps(summary, indent=1))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
