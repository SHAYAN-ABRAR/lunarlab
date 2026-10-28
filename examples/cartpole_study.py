# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Run a prespecified reward-design audit study through LunarLab's task-independent layer.

The study is defined by a protocol file (see ``lunarlab.audit.study``). The CartPole protocol of
27 October 2026 is ``reports/neurocomputing-2026-10-27/cartpole-study/protocol/protocol.json``.

    python examples/cartpole_study.py --protocol PROTOCOL.json --out OUT_DIR --workers 5
    python examples/cartpole_study.py --protocol PROTOCOL.json --out OUT_DIR --phase test

Phases run in this order (``--phase all``, the default):

1. ``train``: train every (design, training seed) run, then select and freeze its checkpoints.
2. ``verify``: check every frozen checkpoint's digest. No test starts unless all of them pass.
3. ``test``: final tests, first of the selected checkpoints, then of the final checkpoints (the prespecified
   secondary analysis).
4. ``export``: one artifact per run (``lunarlab audit-artifact verify|reproduce`` checks it).
5. ``summary``: ``study.json``, with the digests of every record and the compute used.

A phase never redoes completed work: a trained run is not retrained, and a recorded test is not repeated. A
run that fails keeps its directory and a ``FAILED.json`` with the error. It is reported, not rerun.
"""

from __future__ import annotations

import argparse
import json
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

from lunarlab.audit import study as st


def run_name(design: str, seed: int) -> str:
    return f"{design}-s{seed}"


def _train(protocol_path: str, design: str, seed: int, run_dir: str) -> dict:
    protocol = st.load_json(protocol_path)
    started = time.time()
    try:
        record = st.train_run(protocol, design, seed, run_dir, echo=lambda m: print(m, flush=True))
    except Exception as exc:  # retained and reported, never hidden or rerun
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        (Path(run_dir) / "FAILED.json").write_text(
            json.dumps(
                {"error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}, indent=1
            ),
            encoding="utf-8",
        )
        return {"run": run_name(design, seed), "failed": f"{type(exc).__name__}: {exc}"}
    return {
        "run": run_name(design, seed),
        "transitions": record["transitions"]["actual"],
        "training_seconds": record["training_seconds"],
        "wall_seconds": time.time() - started,
        "selected_step": record["selection"]["step"],
    }


def _test(run_dir: str, which: str) -> dict:
    record = st.final_test(run_dir, which=which)
    agg = record["report"]["aggregate"]
    return {
        "run": Path(run_dir).name,
        "which": which,
        "mean_original_return": agg["mean_original_return"],
        "test_seconds": record["test_seconds"],
    }


def _append(path: Path, obj: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--out", required=True, help="study directory (runs, artifacts, study.json)")
    ap.add_argument("--workers", type=int, default=1, help="parallel training/test processes")
    ap.add_argument("--phase", choices=["all", "train", "verify", "test", "export", "summary"], default="all")
    args = ap.parse_args(argv)

    protocol = st.load_json(args.protocol)
    st.require_valid_protocol(protocol)
    digest = st.protocol_sha256(protocol)
    out = Path(args.out)
    (out / "runs").mkdir(parents=True, exist_ok=True)
    ledger = out / "compute.jsonl"
    runs = [(d["name"], s) for d in protocol["designs"] for s in protocol["training_seeds"]]
    dirs = {run_name(d, s): out / "runs" / run_name(d, s) for d, s in runs}
    print(f"protocol {protocol['study_id']} sha256 {digest}; {len(runs)} runs", flush=True)
    phases = ["train", "verify", "test", "export", "summary"] if args.phase == "all" else [args.phase]
    ctx = get_context("spawn")

    if "train" in phases:
        todo = [(d, s) for d, s in runs if not (dirs[run_name(d, s)] / "run.json").exists()]
        blocked = [
            n for d, s in todo if (n := run_name(d, s)) and dirs[n].exists() and any(dirs[n].iterdir())
        ]
        if blocked:
            print(
                f"not retrained (directory exists without run.json; inspect FAILED.json): {blocked}",
                flush=True,
            )
        todo = [(d, s) for d, s in todo if run_name(d, s) not in blocked]
        t0 = time.time()
        _append(
            ledger,
            {"phase": "train", "event": "start", "time": t0, "runs": [run_name(d, s) for d, s in todo]},
        )
        with ProcessPoolExecutor(max_workers=args.workers, mp_context=ctx) as pool:
            futures = [pool.submit(_train, args.protocol, d, s, str(dirs[run_name(d, s)])) for d, s in todo]
            for f in futures:
                result = f.result()
                _append(ledger, {"phase": "train", **result})
                print(f"trained {result}", flush=True)
        _append(ledger, {"phase": "train", "event": "end", "time": time.time(), "elapsed": time.time() - t0})

    if "verify" in phases or "test" in phases:
        problems = []
        for name, d in dirs.items():
            if not (d / "run.json").exists():
                problems.append(f"{name}: no run.json")
                continue
            for which in ("selected", "final"):
                try:
                    st.verify_frozen(d, which)
                except Exception as exc:
                    problems.append(f"{name} {which}: {exc}")
        print(
            "frozen checkpoints verified" if not problems else f"verification problems: {problems}",
            flush=True,
        )
        if problems and "test" in phases:
            print("no test is run while any frozen checkpoint fails verification", flush=True)
            return 1

    if "test" in phases:
        t0 = time.time()
        _append(ledger, {"phase": "test", "event": "start", "time": t0})
        for which in ("selected", "final"):
            todo = [str(d) for d in dirs.values() if not (d / f"test-{which}.json").exists()]
            with ProcessPoolExecutor(max_workers=args.workers, mp_context=ctx) as pool:
                for result in pool.map(_test, todo, [which] * len(todo)):
                    _append(ledger, {"phase": "test", **result})
                    print(f"tested {result}", flush=True)
        _append(ledger, {"phase": "test", "event": "end", "time": time.time(), "elapsed": time.time() - t0})

    if "export" in phases:
        for name, d in dirs.items():
            target = out / "artifacts" / name
            if not target.exists():
                st.export_artifact(d, target)
        print("artifacts exported", flush=True)

    if "summary" in phases:
        from lunarlab.sysinfo import version_info

        entries = []
        for name, d in dirs.items():
            run = st.load_json(d / "run.json")
            entries.append(
                {
                    "run": name,
                    "design": run["design"],
                    "training_seed": run["training_seed"],
                    "transitions": run["transitions"],
                    "selected": run["selection"],
                    "frozen": run["frozen"],
                    "files": {
                        p.name: st._sha256_file(p)
                        for p in sorted(d.glob("*.json"))
                        if p.name in ("run.json", "test-selected.json", "test-final.json", "protocol.json")
                    },
                }
            )
        ledger_rows = [
            json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        summary = {
            "study_id": protocol["study_id"],
            "protocol_sha256": digest,
            "runs": entries,
            "training_transitions": sum(e["transitions"]["actual"] for e in entries),
            "compute_ledger": ledger_rows,
            "software": version_info(),
            "environment": st.environment_record(),
        }
        (out / "study.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
        print(f"study.json written: {summary['training_transitions']:,} training transitions", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
