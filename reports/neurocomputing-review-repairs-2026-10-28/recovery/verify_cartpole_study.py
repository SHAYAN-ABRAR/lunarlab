# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Independent checks of the CartPole study from its recovered run records.

    python verify_cartpole_study.py TREE OUT [--checkpoints DIR [--frozen-only]]

``TREE`` is a source tree holding ``reports/neurocomputing-2026-10-27`` (for example a fresh ``git archive``
extraction). ``--checkpoints`` points at the study runner's output, whose ``<part>/runs/<run>/`` folders hold
the scheduled and frozen checkpoint files.

**Analysis.** The prespecified analysis (``analyze.py``) is rerun into ``OUT/analysis-<part>`` and compared with
the committed results.

**Per run.** The checks, for every main and pilot run, are made from the records themselves and do not reuse
the study code's own conclusions:

- **Budget:** actual transitions are ``rollouts × n_envs × n_steps``, at least the configured budget.
- **Seeds:** the effective first-reset seeds equal the protocol's (``root + 1000 × seed + i``), and no later
  reset was seeded.
- **Checkpoints:** the schedule is every ``eval_every_rollouts`` rollouts, plus the final step. Each checkpoint
  has one validation episode per protocol validation seed, in order. Each recorded mean equals the mean of its
  episodes.
- **Selection:** the rule is rerun over all candidates as the protocol states it: the highest mean original
  validation return, with ties going to the earliest checkpoint.
- **Frozen digests:** the selected and final digests equal the selected and last checkpoint.
- **Tests:** each test names the frozen digest it should, ran after training finished on the protocol's 100
  test seeds (disjoint from the validation seeds), and its aggregate equals the mean of its episodes.
- **Files:** the checkpoint files, when supplied, match every recorded digest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def check_run(
    part: str, run_dir: Path, protocol: dict, ckpt_dir: Path | None, frozen_only: bool = False
) -> tuple[dict, list[str]]:
    problems: list[str] = []
    name = run_dir.name

    def need(cond: bool, msg: str) -> None:
        if not cond:
            problems.append(f"{part}/{name}: {msg}")

    run = load(run_dir / "run.json")
    tests = {w: load(run_dir / f"test-{w}.json") for w in ("selected", "final")}
    algo = protocol["algorithm"]
    rollout = algo["n_envs"] * algo["kwargs"]["n_steps"]
    tr = run["transitions"]
    need(tr["rollout_size"] == rollout, f"rollout size {tr['rollout_size']} != n_envs*n_steps {rollout}")
    need(tr["actual"] == tr["rollouts"] * rollout, "actual transitions != rollouts * rollout size")
    need(tr["configured"] == protocol["budget_transitions"], "configured budget differs from the protocol")
    need(
        tr["actual"] >= tr["configured"] and tr["actual"] - tr["configured"] < rollout,
        "rounding is not to one rollout",
    )

    seed = run["training_seed"]
    sd = run["seeding"]
    expected_seeds = [protocol["train_env_seed_root"] + 1000 * seed + i for i in range(algo["n_envs"])]
    need(
        sd["intended_first_reset_seeds"] == expected_seeds,
        "intended first-reset seeds differ from the protocol",
    )
    need(
        sd["effective_first_reset_seeds"] == expected_seeds,
        "effective first-reset seeds differ from the protocol",
    )
    need(sd["later_resets_with_a_seed"] == 0, "a later reset was seeded")
    need(sd["validation_seeds"] == protocol["validation_seeds"], "validation seeds differ from the protocol")

    ckpts = run["checkpoints"]
    every = protocol["eval_every_rollouts"] * rollout
    scheduled = list(range(every, tr["actual"], every))
    if tr["actual"] not in scheduled:
        scheduled.append(tr["actual"])
    need([c["step"] for c in ckpts] == scheduled, f"checkpoint steps differ from the schedule {scheduled}")
    for c in ckpts:
        eps = c["validation"]["episodes"]
        need(
            [e["seed"] for e in eps] == protocol["validation_seeds"],
            f"step {c['step']}: validation seeds differ",
        )
        need(
            close(
                c["validation"]["mean_original_return"], statistics.fmean(e["original_return"] for e in eps)
            ),
            f"step {c['step']}: recorded validation mean differs from its episodes",
        )
    best = max(c["validation"]["mean_original_return"] for c in ckpts)
    tied = [c for c in ckpts if c["validation"]["mean_original_return"] == best]
    chosen = tied[0]  # ties go to the earliest checkpoint
    need(
        run["selection"]["step"] == chosen["step"],
        f"selected step {run['selection']['step']} != rule {chosen['step']}",
    )
    need(
        run["selection"]["sha256"] == chosen["sha256"], "selected digest differs from the chosen checkpoint's"
    )
    fz = run["frozen"]
    need(
        fz["selected"]["sha256"] == chosen["sha256"] and fz["selected"]["step"] == chosen["step"],
        "frozen selected != chosen",
    )
    need(
        fz["final"]["sha256"] == ckpts[-1]["sha256"] and fz["final"]["step"] == tr["actual"],
        "frozen final != last checkpoint",
    )

    for which, frozen in (("selected", fz["selected"]), ("final", fz["final"])):
        t = tests[which]
        rep = t["report"]
        need(
            t["checkpoint_sha256"] == frozen["sha256"] and t["checkpoint_step"] == frozen["step"],
            f"test-{which} checkpoint differs from the frozen one",
        )
        need(t["protocol_sha256"] == run["protocol_sha256"], f"test-{which} protocol digest differs")
        need(t["tested_at"] >= run["finished_at"], f"test-{which} ran before training finished")
        need(rep["seeds"] == protocol["test_seeds"], f"test-{which} seeds differ from the protocol")
        need(
            [e["seed"] for e in rep["episodes"]] == protocol["test_seeds"],
            f"test-{which} episode seeds differ",
        )
        need(
            rep["aggregate"]["n_episodes"] == len(rep["episodes"]) == len(protocol["test_seeds"]),
            f"test-{which} episode count",
        )
        need(
            close(
                rep["aggregate"]["mean_original_return"],
                statistics.fmean(e["original_return"] for e in rep["episodes"]),
            ),
            f"test-{which} aggregate differs from its episodes",
        )
    need(
        not set(protocol["validation_seeds"]) & set(protocol["test_seeds"]),
        "validation and test seeds overlap",
    )

    files_checked = 0
    if ckpt_dir is not None:
        rd = ckpt_dir / part / "runs" / name
        for c in [] if frozen_only else ckpts:
            p = rd / c["file"]
            need(
                p.is_file() and sha256(p) == c["sha256"], f"checkpoint file {c['file']} missing or different"
            )
            files_checked += 1
        for which in ("selected", "final"):
            p = rd / fz[which]["file"]
            need(
                p.is_file() and sha256(p) == fz[which]["sha256"], f"frozen {which} file missing or different"
            )
            files_checked += 1
    summary = {
        "run": name,
        "transitions": tr["actual"],
        "checkpoints": len(ckpts),
        "validation_episodes": sum(len(c["validation"]["episodes"]) for c in ckpts),
        "best_validation_mean": best,
        "checkpoints_tied_at_best": [c["step"] for c in tied],
        "selected_step": chosen["step"],
        "test_episodes": {w: len(tests[w]["report"]["episodes"]) for w in tests},
        "checkpoint_files_verified": files_checked,
        "source_revision": run["software"]["git"]["revision"],
        "source_dirty": run["software"]["git"]["dirty"],
    }
    return summary, problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tree", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--checkpoints", type=Path)
    ap.add_argument("--frozen-only", action="store_true", help="check only the frozen checkpoint files")
    a = ap.parse_args()
    study = a.tree / "reports/neurocomputing-2026-10-27/cartpole-study"
    a.out.mkdir(parents=True, exist_ok=True)
    report: dict = {"analysis": {}, "runs": {}, "problems": []}
    for part, results in (("main", "results"), ("pilot", "pilot-results")):
        out = a.out / f"analysis-{part}"
        proc = subprocess.run(
            [sys.executable, str(study / "analyze.py"), str(study / "records" / part), str(out)],
            capture_output=True,
            text=True,
            check=False,
        )
        (a.out / f"analysis-{part}.log").write_text(proc.stdout + proc.stderr, encoding="utf-8", newline="\n")
        same_json = proc.returncode == 0 and load(out / "results.json") == load(
            study / results / "results.json"
        )
        same_md = (
            proc.returncode == 0
            and (out / "RESULTS.md").read_bytes() == (study / results / "RESULTS.md").read_bytes()
        )
        report["analysis"][part] = {
            "exit": proc.returncode,
            "results_json_equal": same_json,
            "results_md_identical": same_md,
        }
        if not (same_json and same_md):
            report["problems"].append(f"{part}: the recomputed analysis differs from the committed results")
        protocol = load(
            study
            / "records"
            / part
            / "runs"
            / sorted(p.name for p in (study / "records" / part / "runs").iterdir())[0]
            / "protocol.json"
        )
        index = load(study / "records" / part / "study.json")
        rows = []
        for entry in index["runs"]:
            run_dir = study / "records" / part / "runs" / entry["run"]
            if load(run_dir / "protocol.json") != protocol:
                report["problems"].append(f"{part}/{entry['run']}: protocol differs from the other runs'")
            summary, problems = check_run(part, run_dir, protocol, a.checkpoints, a.frozen_only)
            rows.append(summary)
            report["problems"] += problems
        report["runs"][part] = rows
        report["analysis"][part]["total_transitions"] = sum(r["transitions"] for r in rows)
    (a.out / "verification.json").write_text(
        json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    lines = ["# CartPole study: verification from the run records", ""]
    for part, info in report["analysis"].items():
        lines.append(
            f"- **{part}:** analysis exit {info['exit']}; results.json equal: {info['results_json_equal']}; "
            f"RESULTS.md byte-identical: {info['results_md_identical']}; transitions {info['total_transitions']:,}."
        )
    lines += [
        "",
        "| Part | Run | Checkpoints | Validation episodes | Best validation mean | Tied at best (steps) | Selected | Test episodes (selected, final) | Checkpoint files verified |",
        "|---|---|---:|---:|---:|---|---:|---|---:|",
    ]
    for part, rows in report["runs"].items():
        for r in rows:
            lines.append(
                f"| {part} | {r['run']} | {r['checkpoints']} | {r['validation_episodes']} | {r['best_validation_mean']:.2f} | "
                f"{', '.join(f'{s:,}' for s in r['checkpoints_tied_at_best'])} | {r['selected_step']:,} | "
                f"{r['test_episodes']['selected']}, {r['test_episodes']['final']} | {r['checkpoint_files_verified']} |"
            )
    lines += ["", f"Problems: {len(report['problems'])}"] + [f"- {p}" for p in report["problems"]]
    (a.out / "VERIFICATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines[:4]))
    print(f"problems: {len(report['problems'])}")
    for p in report["problems"][:20]:
        print(" ", p)
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
