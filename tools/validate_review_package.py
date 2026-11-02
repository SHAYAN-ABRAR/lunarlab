# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Validate a review or archive package: its checksums, its scientific dependencies and the reproduction of its results.

    python tools/validate_review_package.py PACKAGE OUT [--fresh-venv] [--commands]
        [--unmodified-comparison] [--lunarlander-replays {published,all}]

A checksum manifest only covers the files that happen to be present. This script also checks that every file
the scientific records *name* is present with its recorded digest, then recomputes from those records.

**Package layout** (described in the package's ``SUMMARY.md`` or ``START_HERE.md``):

- ``source/``: the repository tree at the package's commit;
- ``outside-git/``: files Git does not hold, at their repository paths, overlaid on ``source/``;
- ``cartpole-study-output/``: the CartPole study runner's frozen checkpoints and exported artifacts, and in an
  archive candidate ``INTERMEDIATE_CHECKPOINTS.json``, the inventory of the checkpoints it does not distribute;
- ``lunarlander-study/`` (archive candidates): the historical 38-policy bundle and its source archive;
- ``SHA256SUMS``: every other file.

**Steps** (the report is ``OUT/validation.json``):

1. **Checksums:** every file in ``SHA256SUMS`` is present with its digest, and every file is listed.
2. **Dependencies:** every file named by these records is present with its recorded digest:
   - the CartPole study indexes, the analysis inputs and the frozen-checkpoint list;
   - the exported-artifact manifests;
   - the comparison and protocol hash lists, and the follow-up comparison's ``HASHES-v2.sha256``;
   - the figure manifest and the learned-reward packages;
   - in an archive candidate, the historical bundle's recorded digests. Every checkpoint that a CartPole run
     record names must be either distributed or listed, with the same digest, as not distributed.
3. **Recomputation:** in a working copy (``OUT/work``), the CartPole analysis is rerun from the run records
   and compared with the committed results. The run records are checked against the study protocol and the
   frozen checkpoints. Every figure is rebuilt, and its plotted values (``*.values.json``) are compared;
   identical bytes are reported separately, because PDF, SVG and PNG bytes depend on the Matplotlib and font
   versions.
4. **LunarLander statistics** (when the package holds the bundle):
   - every member of the 38-policy bundle is checked against the bundle's digest list, which must equal the
     list committed in ``reports/jmlr/learned-reward-repair-2026-10-24/``;
   - the per-policy statistics and group IQMs are recomputed from the 3,800 recorded LunarLander test episodes
     (``tools/compare_study_summaries.py``).
5. **Documented commands** (``--commands``): these run in an empty data home, with the working copy's code:
   - the published artifact's replay and the learned-reward replay (``--lunarlander-replays all``: also
     every one of the bundle's 38 packages);
   - verification and replay of every exported CartPole artifact;
   - the follow-up workflow comparison (``comparison-v2``), assessed against the historical Windows results:
     exact agreement, a verified platform-dependent numerical difference of a clean control, or a failure;
   - with ``--unmodified-comparison``, also the frozen runner and programs, assessed by the same rules.

   ``--fresh-venv`` first installs the working copy, with its locked dependencies, into a new virtual
   environment (with uv), so nothing is imported from the machine's own checkout.

A step that cannot complete is a failure. Its exit status, log and reason are recorded, and a crashed
comparison program is named with its stderr. Absent, invalid or wrongly typed output never passes.
``OUT`` must be new or empty, so nothing from an earlier run can be read as this run's. ``validation.json`` is
written even when a step fails or raises. Nothing is trained. The exit status is 0 only if every requested step
passes, 1 otherwise, and 2 if ``OUT`` is not empty.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
import zipfile
from pathlib import Path, PurePosixPath

REPORTS = "reports/neurocomputing-2026-10-27"
STUDY = f"{REPORTS}/cartpole-study"
COMPARISON = f"{REPORTS}/workflow-comparison"
VERIFY_STUDY = "reports/neurocomputing-review-repairs-2026-10-28/recovery/verify_cartpole_study.py"
FINAL = "reports/neurocomputing-final-validation-2026-11-01"
FOLLOWUP = f"{FINAL}/comparison-v2"
HISTORICAL_DIGESTS = f"{FINAL}/archive/historical-bundle.sha256"
BUNDLE_RECORD = "reports/jmlr/learned-reward-repair-2026-10-24/study-artifacts/SHA256SUMS"
BUNDLE = "lunarlander-study/LunarLab_38_Policy_Study.zip"
INTERMEDIATE = "cartpole-study-output/INTERMEDIATE_CHECKPOINTS.json"
PUBLISHED_REPLAYS = (
    ("replay-ppo-hover-bonus-s0", "examples/artifacts/ppo-hover-bonus-s0"),
    (
        "replay-learned-reward-0274",
        "examples/learned-reward-artifacts/20261015-235939-custom-s0-standard-0274",
    ),
)
COMMAND_TIMEOUT = 7200
COMPARISON_TIMEOUT = 4 * 3600
TAIL = 1500


def remove_tree(path: Path) -> None:
    """``shutil.rmtree`` that also removes read-only files (frozen checkpoints are read-only on purpose)."""

    def writable_then_retry(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    shutil.rmtree(path, onexc=writable_then_retry)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> tuple[object, str | None]:
    """A JSON file's value, or None and the reason it cannot be read."""
    if not path.is_file():
        return None, f"{path.name} is absent"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (UnicodeDecodeError, ValueError) as exc:
        return None, f"{path.name} is not valid JSON: {exc}"


DIGEST_LINE = re.compile(r"^([0-9a-f]{64}) [ *](.+)$")


def hash_list(path: Path) -> list[tuple[str, str]]:
    """``(digest, name)`` rows of a ``sha256sum``-style list.

    Only ``<64 hex digits> <space or *><name>`` lines are entries. Other lines are skipped, such as the
    prespecified lists' header "fixed at <time>, before ...".
    """
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = DIGEST_LINE.match(line.strip())
        if m:
            rows.append((m.group(1), m.group(2).strip()))
    return rows


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def named_checkpoints(tree: Path) -> dict[str, str]:
    """Every checkpoint the CartPole run records name, as ``<part>/runs/<run>/<file>`` to its SHA-256."""
    named = {}
    for run_json in sorted((tree / STUDY / "records").glob("*/runs/*/run.json")):
        part, run = run_json.parts[-4], run_json.parts[-2]
        record = load(run_json)
        entries = [*record["checkpoints"], *record["frozen"].values()]
        for entry in entries:
            named[f"{part}/runs/{run}/{entry['file']}"] = entry["sha256"]
    return named


def check_checkpoint_inventory(tree: Path, package: Path, deps: Dependencies) -> None:
    """Each checkpoint a run record names is distributed with its digest, or inventoried as not distributed."""
    inventory, problem = load_json(package / INTERMEDIATE)
    if problem or not isinstance(inventory, dict) or not isinstance(inventory.get("not_distributed"), list):
        deps.problems.append(f"checkpoint inventory: {problem or 'not_distributed is not a list'}")
        return
    listed = {}
    for entry in inventory["not_distributed"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            deps.problems.append(f"checkpoint inventory: malformed entry {entry!r:.80}")
            continue
        listed[entry["path"]] = entry.get("sha256")
    study_output = package / "cartpole-study-output"
    named = named_checkpoints(tree)
    for path, digest in named.items():
        deps.counts["named checkpoint"] = deps.counts.get("named checkpoint", 0) + 1
        if (study_output / path).is_file():
            if sha256(study_output / path) != digest:
                deps.problems.append(f"named checkpoint: {path} does not have its recorded digest")
        elif path not in listed:
            deps.problems.append(f"named checkpoint: {path} is neither distributed nor inventoried")
        elif listed[path] != digest:
            deps.problems.append(
                f"named checkpoint: the inventory gives {path} another digest than its record"
            )
    for path in sorted(set(listed) - set(named)):
        deps.problems.append(f"checkpoint inventory: {path} is not named by any run record")


def check_dependencies(tree: Path, study_output: Path | None, package: Path | None = None) -> Dependencies:
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
    v2_hashes = tree / FOLLOWUP / "HASHES-v2.sha256"
    if not v2_hashes.is_file():
        deps.problems.append(f"follow-up comparison programs: missing {FOLLOWUP}/HASHES-v2.sha256")
    else:
        for digest, name in hash_list(v2_hashes):
            deps.need("follow-up comparison programs", tree / FOLLOWUP / name, digest, f"{FOLLOWUP}/{name}")
    for figure in load(tree / "paper/neurocomputing/figures/MANIFEST.json").values():
        for rel, digest in (figure.get("inputs") or {}).items() if isinstance(figure, dict) else ():
            deps.need("figure input", tree / rel, digest, rel)
    lr = tree / "examples/learned-reward-artifacts"
    for digest, name in hash_list(lr / "SHA256SUMS"):
        deps.need("learned-reward package", lr / name, digest, f"examples/learned-reward-artifacts/{name}")
    if package is not None:
        archive = (package / "lunarlander-study").is_dir()
        if archive:
            for digest, name in hash_list(tree / HISTORICAL_DIGESTS):
                deps.need(
                    "historical bundle",
                    package / "lunarlander-study" / name,
                    digest,
                    f"lunarlander-study/{name}",
                )
        if archive or (package / INTERMEDIATE).is_file():  # an archive candidate must carry the inventory
            check_checkpoint_inventory(tree, package, deps)
    return deps


def check_checksums(package: Path) -> dict:
    listing = package / "SHA256SUMS"
    if not listing.is_file():
        return {"ok": False, "problems": ["no SHA256SUMS: missing or altered files cannot be detected"]}
    lines = [line for line in listing.read_text(encoding="utf-8").splitlines() if line.strip()]
    listed = hash_list(listing)
    bad = [
        name for digest, name in listed if not (package / name).is_file() or sha256(package / name) != digest
    ]
    names = {name for _, name in listed}
    present = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    unlisted = sorted(present - names - {"SHA256SUMS"})
    malformed = len(lines) - len(listed)
    return {
        "listed": len(listed),
        "mismatched_or_missing": bad,
        "unlisted": unlisted,
        "malformed_lines": malformed,
        "ok": bool(listed) and not bad and not unlisted and not malformed,
    }


def run(cmd: list[str], cwd: Path, env: dict, log: Path, timeout: float = COMMAND_TIMEOUT) -> int | None:
    """Run a command, logging it with its exit status, stdout and stderr. None if it timed out or did not start."""
    t0 = time.perf_counter()
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        code, stdout, stderr, status = proc.returncode, proc.stdout, proc.stderr, f"exit {proc.returncode}"
    except subprocess.TimeoutExpired as exc:
        code, status = None, f"timed out after {timeout:g} s"
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else exc.stdout or ""
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else exc.stderr or ""
    except OSError as exc:
        code, stdout, stderr, status = None, "", f"{exc}\n", "did not start"
    log.write_text(
        f"$ {' '.join(cmd)}\n({status}, {time.perf_counter() - t0:.1f} s)\n{stdout}{stderr}",
        encoding="utf-8",
        newline="\n",
    )
    return code


def make_venv(work: Path, out: Path) -> dict:
    venv = out / "venv"
    uv = shutil.which("uv")
    if uv is None:
        return {"ok": False, "problems": ["--fresh-venv needs uv on PATH"]}
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    lock = "requirements.lock" if os.name == "nt" else "requirements-ci.lock"
    env = dict(os.environ)
    for cmd in (
        [uv, "venv", "--python", "3.12", str(venv)],
        [uv, "pip", "install", "--python", str(python), "-r", str(work / lock)]
        + ([] if os.name == "nt" else ["--torch-backend", "cpu"]),
        [uv, "pip", "install", "--python", str(python), "--no-deps", str(work)],
    ):
        log = out / "logs" / f"venv-{cmd[1]}-{cmd[2]}.log"
        if run(cmd, out, env, log) != 0:
            return {
                "ok": False,
                "problems": [f"virtual environment step failed: {' '.join(cmd[:4])}"],
                "log": log.name,
            }
    return {"ok": True, "python": str(python), "lock": lock}


def same_figures(work: Path, pristine: Path) -> dict:
    figures = work / "paper/neurocomputing/figures"
    out = {
        "values_identical": [],
        "values_differ": [],
        "bytes_identical": [],
        "bytes_differ": [],
        "missing": [],
    }
    for path in sorted(figures.iterdir()):
        if path.suffix not in (".json", ".pdf", ".svg", ".png") or path.name == "MANIFEST.json":
            continue
        original = pristine / "paper/neurocomputing/figures" / path.name
        if not original.is_file():
            out["missing"].append(path.name)
            continue
        if path.name.endswith(".values.json"):
            a, problem_a = load_json(path)
            b, problem_b = load_json(original)
            same = problem_a is None and problem_b is None and a == b
            out["values_identical" if same else "values_differ"].append(path.name)
        out["bytes_identical" if sha256(path) == sha256(original) else "bytes_differ"].append(path.name)
    return out


def prepare_work(package: Path, out: Path) -> dict:
    """``OUT/work``: the package's ``source/`` with ``outside-git/`` overlaid."""
    if not (package / "source").is_dir():
        return {"ok": False, "problems": ["the package has no source/"]}
    work = out / "work"
    shutil.copytree(package / "source", work)
    overlay = package / "outside-git"
    copied = 0
    for path in sorted(overlay.rglob("*")) if overlay.is_dir() else ():
        if path.is_file():
            target = work / path.relative_to(overlay)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            copied += 1
    return {"ok": True, "overlaid_files": copied}


def extract_bundle(package: Path, work: Path, out: Path) -> dict:
    """Extract the 38-policy bundle into ``OUT/lunarlander-study`` and check every member."""
    target = out / "lunarlander-study"
    problems = []
    with zipfile.ZipFile(package / BUNDLE) as z:
        names = z.namelist()
        unsafe = [n for n in names if n.startswith(("/", "\\")) or ":" in n or ".." in PurePosixPath(n).parts]
        if unsafe:
            return {"ok": False, "problems": [f"unsafe member names: {unsafe[:5]}"]}
        bad = z.testzip()
        if bad:
            return {"ok": False, "problems": [f"CRC failure in {bad}"]}
        z.extractall(target)
    bundle = target / "study-artifacts"
    own, record = bundle / "SHA256SUMS", work / BUNDLE_RECORD
    if not own.is_file() or not record.is_file() or own.read_bytes() != record.read_bytes():
        problems.append(f"the bundle's SHA256SUMS is not the list committed as {BUNDLE_RECORD}")
    listed = hash_list(own) if own.is_file() else []
    for digest, name in listed:
        if not (bundle / name).is_file() or sha256(bundle / name) != digest:
            problems.append(f"study-artifacts/{name} is missing or differs from its recorded digest")
    present = {p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file()}
    unlisted = sorted(present - {n for _, n in listed} - {"SHA256SUMS"})
    for name in unlisted:  # such as DEPENDENCIES.md, written after the list: it must equal its committed copy
        committed = record.parent / name
        if not committed.is_file() or committed.read_bytes() != (bundle / name).read_bytes():
            problems.append(
                f"study-artifacts/{name} is in neither the bundle's SHA256SUMS nor the committed record"
            )
    packages = sorted(p.parent for p in bundle.rglob("artifact.json"))
    models = sorted(p.parent.parent.name for p in bundle.rglob("reward_model/model.npz"))
    return {
        "ok": bool(listed) and not problems,
        "members_checked": len(listed),
        "policy_packages": len(packages),
        "packages_with_reward_model": len(models),
        "problems": problems,
    }


def lunarlander_statistics(python: str, work: Path, out: Path, env: dict) -> dict:
    report = out / "lunarlander-statistics.json"
    code = run(
        [
            python,
            str(work / "tools/compare_study_summaries.py"),
            "--artifacts",
            str(out / "lunarlander-study/study-artifacts"),
            "--out",
            str(report),
        ],
        work,
        env,
        out / "logs" / "lunarlander-statistics.log",
    )
    data, problem = load_json(report)
    rr = data.get("raw_episode_recomputation") if isinstance(data, dict) else None
    if problem or not isinstance(rr, dict):
        return {
            "ok": False,
            "exit": code,
            "problems": [problem or "no raw_episode_recomputation in the report"],
        }
    return {
        "ok": code == 0 and rr.get("all_match") is True,
        "exit": code,
        "policies": rr.get("policies"),
        "episodes": rr.get("episodes"),
        "all_match": rr.get("all_match"),
        "scope": rr.get("scope"),
        "report": report.name,
    }


def probe_platform(python: str, work: Path, env: dict, out: Path) -> dict:
    """The validating interpreter's platform record, as the comparison assessment reads it."""
    log = out / "logs" / "platform.log"
    code = run([python, "-I", str(work / FOLLOWUP / "assessment.py"), "--platform"], work, env, log)
    text = log.read_text(encoding="utf-8").splitlines()
    data = None
    for line in reversed(text):
        if line.startswith("{"):
            with contextlib.suppress(ValueError):
                data = json.loads(line)
            break
    if code != 0 or not isinstance(data, dict):
        raise RuntimeError(f"the platform probe failed (exit {code}); see logs/platform.log")
    return {"ok": True, **data}


def case_platforms(fixtures: Path, cases: list[dict], current: dict, A) -> dict:
    """For every case: whether its two platform records agree, and how this machine compares (as the runner)."""
    out = {}
    for case in cases:
        record, _ = load_json(fixtures / case["id"] / "case.json")
        evaluation, _ = load_json(fixtures / case["id"] / "evaluation.json")
        recorded = record.get("recorded_platform") if isinstance(record, dict) else None
        with_ = evaluation.get("recorded_with") if isinstance(evaluation, dict) else None
        out[case["id"]] = {
            "consistent": recorded is not None and A.platform_key(recorded) == A.platform_key(with_),
            "comparison": A.compare_platform(recorded, current),
        }
    return out


def tail(path: Path, n: int = TAIL) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-n:]
    except OSError:
        return None


def comparison(python: str, work: Path, out: Path, env: dict, platform: dict, unmodified: bool) -> dict:
    """Run one comparison runner on the fixtures and assess its rows; never compare stale or malformed output."""
    A = load_module("comparison_assessment", work / FOLLOWUP / "assessment.py")
    fixtures = work / COMPARISON / "fixtures"
    out_dir = out / ("comparison-unmodified" if unmodified else "comparison")
    if out_dir.exists():
        return {"ok": False, "problems": [f"{out_dir.name}/ already exists; refusing to read old output"]}
    run_id = None if unmodified else uuid.uuid4().hex
    runner = work / (f"{COMPARISON}/run_comparison.py" if unmodified else f"{FOLLOWUP}/run_comparison_v2.py")
    cmd = [python, str(runner), str(fixtures), str(out_dir)] + ([] if unmodified else ["--run-id", run_id])
    log = out / "logs" / f"{out_dir.name}.log"
    code = run(cmd, work, env, log, timeout=COMPARISON_TIMEOUT)
    result: dict = {
        "runner": runner.relative_to(work).as_posix(),
        "programs": "the hashed originals" if unmodified else "comparison-v2/workflows/*_v2.py",
        "exit": code,
        "log": f"logs/{log.name}",
        "output": f"{out_dir.name}/",
    }
    problems = []
    summary, problem = load_json(out_dir / "summary.json")
    if problem:
        problems.append(f"the runner's {problem}")
    elif not isinstance(summary, dict):
        problems.append(f"summary.json holds {A.show(summary)}, not an object")
        summary = None
    if summary is not None and not unmodified:
        if summary.get("run_id") != run_id:
            problems.append("summary.json does not carry this run's identifier: it is not this run's output")
        inputs = summary.get("inputs") if isinstance(summary.get("inputs"), dict) else {}
        if inputs.get("verified") is not True:
            problems.append(f"the runner's inputs did not verify: {inputs.get('problems')}")
    inventory = load(work / COMPARISON / "protocol/fault_inventory.json")["cases"]
    historical = load(work / COMPARISON / "results/summary.json")["rows"]
    platforms = case_platforms(fixtures, inventory, platform, A)
    rows = summary.get("rows") if isinstance(summary, dict) else None
    assessed = A.assess(rows if rows is not None else [], historical, inventory, platforms)
    if rows is None and summary is not None:
        problems.append("summary.json has no rows")
    for row in assessed["rows"]:
        if row["blocking"]:
            raw = out_dir / "raw" / row["workflow"] / row["case"]
            row["stderr_tail"] = tail(raw / "stderr.txt")
            row["raw"] = f"{out_dir.name}/raw/{row['workflow']}/{row['case']}/"
    if not unmodified and isinstance(summary, dict):
        own = (summary.get("assessment") or {}).get("ok")
        if own is not assessed["ok"]:
            problems.append(f"the runner's own assessment ({own}) differs from this one ({assessed['ok']})")
        if (code == 0) is not assessed["ok"]:
            problems.append(f"the runner's exit status {code} does not match the assessment")
    if unmodified and code != 0:
        problems.append(f"the frozen runner exited with status {code}")
    result.update(
        ok=not problems and assessed["ok"],
        problems=problems,
        pairs_expected=assessed["pairs_expected"],
        pairs_present=assessed["pairs_present"],
        classes=assessed["classes"],
        blocking=[
            {
                k: r.get(k)
                for k in ("workflow", "case", "verdict", "exit_code", "reasons", "raw", "stderr_tail")
            }
            for r in assessed["rows"]
            if r["blocking"]
        ],
        platform_differences=assessed["platform_differences"],
        set_checks=assessed["set_checks"],
        assessment_problems=assessed["problems"],
        rows=[
            {k: r[k] for k in ("workflow", "case", "verdict", "exit_code", "literal_rule_outcome", "class")}
            for r in assessed["rows"]
        ],
    )
    return result


def replay(python: str, work: Path, out: Path, env: dict, label: str, artifact: Path) -> dict:
    """``reproduce-artifact`` of one LunarLander package from an empty data home."""
    report = out / "reports" / f"{label}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    empty = tempfile.mkdtemp(prefix="lunarlab-home-", dir=out)
    code = run(
        [
            python,
            "-m",
            "lunarlab",
            "reproduce-artifact",
            "--artifact",
            str(artifact),
            "--report",
            str(report),
        ],
        work,
        {**env, "LUNARLAB_HOME": empty},
        out / "logs" / f"{label}.log",
    )
    data, problem = load_json(report)
    status = data.get("status") if isinstance(data, dict) else None
    return {
        "exit": code,
        "status": status,
        "ok": code in (0, 3) and status in ("exact", "numerical-difference"),
        "data_home_left_empty": not any(Path(empty).iterdir()),
        **({"problem": problem} if problem else {}),
    }


def commands(python: str, work: Path, out: Path, env: dict, study_output: Path, options: dict) -> dict:
    results: dict = {}

    def home() -> str:
        return tempfile.mkdtemp(prefix="lunarlab-home-", dir=out)

    def cli(name: str, args: list[str], ok_codes=(0,)) -> int | None:
        code = run(
            [python, "-m", "lunarlab", *args],
            work,
            {**env, "LUNARLAB_HOME": home()},
            out / "logs" / f"{name}.log",
        )
        results[name] = {"exit": code, "ok": code in ok_codes}
        return code

    def guarded(name: str, func, *args) -> None:
        try:
            results[name] = func(*args)
        except Exception as exc:  # recorded as a failed command with its traceback; never as a pass
            results[name] = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }

    def cartpole_artifacts() -> dict:
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
            data, _ = load_json(report)
            statuses[tag] = {
                "verify_exit": verify,
                "reproduce_exit": reproduce,
                "status": data.get("status") if isinstance(data, dict) else None,
            }
        counts: dict[str, int] = {}
        for v in statuses.values():
            counts[str(v["status"])] = counts.get(str(v["status"]), 0) + 1
        return {
            "artifacts": statuses,
            "count": len(statuses),
            "statuses": counts,
            "ok": len(statuses) == 18
            and all(
                v["verify_exit"] == 0
                and v["reproduce_exit"] in (0, 3)
                and v["status"] in ("exact", "numerical-difference")
                for v in statuses.values()
            ),
        }

    cli("version", ["--version"])
    for label, artifact in PUBLISHED_REPLAYS:
        guarded(label, replay, python, work, out, env, label, work / artifact)
    if options["lunarlander_replays"] == "all":
        guarded("lunarlander-replays", all_replays, python, work, out, env)
    guarded("cartpole-artifacts", cartpole_artifacts)
    platform = options["platform"]
    guarded("comparison", comparison, python, work, out, env, platform, False)
    if options["unmodified_comparison"]:
        guarded("comparison-unmodified", comparison, python, work, out, env, platform, True)
    return results


def all_replays(python: str, work: Path, out: Path, env: dict) -> dict:
    """Every package of the 38-policy bundle, replayed from an empty data home."""
    bundle = out / "lunarlander-study" / "study-artifacts"
    packages = sorted(p.parent for p in bundle.rglob("artifact.json"))
    replays = {}
    for package in packages:
        replays[package.name] = replay(python, work, out, env, f"lunarlander-{package.name}", package)
    counts: dict[str, int] = {}
    for r in replays.values():
        counts[str(r["status"])] = counts.get(str(r["status"]), 0) + 1
    return {
        "ok": len(packages) == 38 and all(r["ok"] for r in replays.values()),
        "packages": len(packages),
        "statuses": counts,
        "replays": replays,
    }


def step(report: dict, name: str, func, *args) -> dict:
    """Run one validation step and record its result, or the exception that ended it, under ``report[name]``."""
    try:
        result = func(*args)
    except Exception as exc:  # recorded as a failed step with its traceback; never as a pass
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
    report[name] = result
    return result


def skipped(report: dict, name: str, reason: str) -> None:
    report[name] = {"ok": False, "skipped": reason}


def validate(a: argparse.Namespace, package: Path, out: Path, report: dict) -> None:
    step(report, "checksums", check_checksums, package)
    if not step(report, "work_copy", prepare_work, package, out)["ok"]:
        for name in ("dependencies", "cartpole_records", "figures"):
            skipped(report, name, "the working copy could not be prepared")
        return
    work = out / "work"
    study_output = package / "cartpole-study-output"
    has_bundle = (package / BUNDLE).is_file()

    def dependencies() -> dict:
        deps = check_dependencies(work, study_output if study_output.is_dir() else None, package)
        return {"checked": deps.counts, "problems": deps.problems, "ok": not deps.problems}

    step(report, "dependencies", dependencies)
    if a.fresh_venv:
        env_result = step(report, "environment", make_venv, work, out)
        python = env_result.get("python") if env_result.get("ok") else None
    else:
        python = sys.executable
        report["environment"] = {"ok": True, "python": python, "note": "this interpreter (no --fresh-venv)"}
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "LUNARLAB_HOME")}
    env.update(PYTHONIOENCODING="utf-8", PYTHONPATH="" if a.fresh_venv else str(work))
    if python is None:
        for name in ("cartpole_records", "figures", *(("lunarlander_statistics",) if has_bundle else ())):
            skipped(report, name, "the environment could not be created")
        if a.commands:
            skipped(report, "commands", "the environment could not be created")
        return
    platform = step(report, "platform", probe_platform, python, work, env, out)

    def cartpole_records() -> dict:
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
        return {"exit": code, "ok": code == 0, "report": "study-verification/VERIFICATION.md"}

    def figures() -> dict:
        figures_code = run(
            [python, "paper/neurocomputing/figures/build_figures.py"], work, env, out / "logs" / "figures.log"
        )
        check_code = run(
            [python, "paper/neurocomputing/check_manuscript.py", "--final"],
            work,
            env,
            out / "logs" / "check-manuscript.log",
        )
        same = same_figures(work, package / "source")
        return {
            **same,
            "build_exit": figures_code,
            "check_exit": check_code,
            "ok": figures_code == 0
            and check_code == 0
            and bool(same["values_identical"])
            and not same["values_differ"]
            and not same["missing"],
        }

    step(report, "cartpole_records", cartpole_records)
    step(report, "figures", figures)
    if has_bundle:
        if step(report, "lunarlander_bundle", extract_bundle, package, work, out)["ok"]:
            step(report, "lunarlander_statistics", lunarlander_statistics, python, work, out, env)
        else:
            skipped(report, "lunarlander_statistics", "the bundle did not verify")
    if a.commands:
        if a.lunarlander_replays == "all" and not report.get("lunarlander_bundle", {}).get("ok"):
            skipped(report, "commands", "--lunarlander-replays all needs a verified bundle in the package")
            return
        if not platform.get("platform"):
            skipped(report, "commands", "the platform probe failed, so a comparison could not be assessed")
            return
        options = {
            "platform": platform,
            "unmodified_comparison": a.unmodified_comparison,
            "lunarlander_replays": a.lunarlander_replays,
        }
        results = step(report, "commands", commands, python, work, out, env, study_output, options)
        if "error" not in results:
            report["commands"] = {
                "ok": bool(results) and all(r.get("ok") is True for r in results.values()),
                "results": results,
            }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("package", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--fresh-venv", action="store_true")
    ap.add_argument("--commands", action="store_true")
    ap.add_argument(
        "--unmodified-comparison",
        action="store_true",
        help="with --commands, also run the frozen comparison runner and programs, assessed by the same rules",
    )
    ap.add_argument(
        "--lunarlander-replays",
        choices=("published", "all"),
        default="published",
        help="with --commands: replay the two published packages (default) or all 38 of the bundle",
    )
    a = ap.parse_args(argv)
    package, out = a.package.resolve(), a.out.resolve()
    if out.exists() and any(out.iterdir()):
        print(
            f"refusing to write into {out}: it is not empty, and earlier output must not be read as this run's",
            file=sys.stderr,
        )
        return 2
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "package": package.name,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "options": {
            "fresh_venv": a.fresh_venv,
            "commands": a.commands,
            "unmodified_comparison": a.unmodified_comparison,
            "lunarlander_replays": a.lunarlander_replays if a.commands else None,
        },
    }
    completed = False
    try:
        validate(a, package, out, report)
        completed = True
    except Exception as exc:  # recorded, and the validation fails; never reported as a pass
        report["unexpected_error"] = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    finally:
        steps = {k: v for k, v in report.items() if isinstance(v, dict) and "ok" in v}
        report["completed"] = completed
        report["ok"] = completed and bool(steps) and all(v["ok"] is True for v in steps.values())
        report["failed_steps"] = sorted(k for k, v in steps.items() if v["ok"] is not True)
        report["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        (out / "validation.json").write_text(
            json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n"
        )
        summary = {k: v.get("ok") for k, v in steps.items()}
        summary.update(ok=report["ok"], failed_steps=report["failed_steps"])
        print(json.dumps(summary, indent=1))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
