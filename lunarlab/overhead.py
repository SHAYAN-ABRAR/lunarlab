# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Overhead benchmark: what LunarLab's instrumentation costs compared with plain Stable-Baselines3.

Three configurations train the same PPO model on the same environment for the same number of
environment transitions:

* **A ``sb3``** -- plain SB3: ``PPO("MlpPolicy")`` on ``DummyVecEnv([Monitor(gym.make("LunarLander-v3"))] * n)``.
* **B ``accounting``** -- A plus LunarLab's reward wrapper (baseline preset, so the training reward equals the
  original reward): per-transition reward accounting, the episode accumulator and outcome classification.
* **C ``lunarlab``** -- LunarLab's full training pipeline (:func:`lunarlab.training.train`): B plus the run
  directory, episode CSV, metrics, status file, stop polling, periodic checkpoints and validation.

Equivalent in all three: PPO hyperparameters and network (LunarLab's defaults, passed to SB3's ``PPO`` by
:func:`lunarlab.training.build_model`), ``n_envs``, ``DummyVecEnv``, CPU, torch threads, seed, transition budget,
no rendering. C additionally runs validation episodes and writes checkpoints; their wall time and
environment steps are measured separately and reported, never counted as instrumentation overhead.

Each repetition runs in a fresh Python process (so peak memory is per configuration), configurations are
interleaved in a rotating order, and every repetition is kept (none is discarded).

    python -m lunarlab overhead-benchmark --profile smoke        # ~1 minute
    python -m lunarlab overhead-benchmark --profile standard     # ~10 minutes
    python -m lunarlab overhead-benchmark --profile comprehensive --yes   # hours; never started automatically
"""

from __future__ import annotations

import argparse
import io
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

CONFIGS = ("sb3", "accounting", "lunarlab")
LABELS = {
    "sb3": "A · plain SB3 (Monitor only)",
    "accounting": "B · + LunarLab reward accounting",
    "lunarlab": "C · full LunarLab pipeline",
}
PROFILES: dict[str, dict[str, int]] = {
    "smoke": {"transitions": 8_192, "repeats": 2},
    "standard": {"transitions": 102_400, "repeats": 3},
    "comprehensive": {"transitions": 1_003_520, "repeats": 5},
}


def _peak_memory_bytes() -> tuple[int | None, str]:
    import psutil

    info = psutil.Process().memory_info()
    if hasattr(info, "peak_wset"):  # Windows: peak working set
        return int(info.peak_wset), "peak working set (psutil, Windows)"
    try:
        import resource

        kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(kb) * 1024, "ru_maxrss (getrusage)"
    except (ImportError, AttributeError):  # pragma: no cover
        return None, "unavailable"


def _dir_bytes(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for p in path.rglob("*"):
        if p.is_file():
            key = p.relative_to(path).parts[0]
            out[key] = out.get(key, 0) + p.stat().st_size
    return out


def _run_config(config: str, transitions: int, seed: int, threads: int) -> dict[str, Any]:
    """One measurement, in this (fresh) process. Called through ``python -m lunarlab.overhead --worker``."""
    import gymnasium as gym
    import psutil
    import torch

    from lunarlab.config import PPOConfig, RunConfig, TrainingConfig
    from lunarlab.env import ENV_ID, ENV_KWARGS
    from lunarlab.rewards.config import preset
    from lunarlab.storage import utc_now

    torch.set_num_threads(threads)
    proc = psutil.Process()
    ppo = PPOConfig()
    result: dict[str, Any] = {"config": config, "seed": seed, "requested_transitions": transitions}

    if config in ("sb3", "accounting"):
        from stable_baselines3.common.monitor import Monitor
        from stable_baselines3.common.vec_env import DummyVecEnv

        from lunarlab.training import build_model, build_vec_env

        cfg = RunConfig(
            run_id="overhead-benchmark",
            created_at=utc_now(),
            reward=preset("baseline"),
            ppo=ppo,
            seed=seed,
            training=TrainingConfig(profile="custom", total_transitions=transitions, torch_threads=threads),
        )
        # Timed from environment construction on, as C's train() is.
        cpu0, t0 = proc.cpu_times(), time.perf_counter()
        if config == "sb3":
            venv = DummyVecEnv([lambda: Monitor(gym.make(ENV_ID, **ENV_KWARGS))] * cfg.n_envs)
            result["env_stack"] = "Monitor(gym.make('LunarLander-v3', continuous=False))"
        else:
            venv = build_vec_env(cfg, kind="dummy")
            result["env_stack"] = (
                "Monitor(LunarLabRewardWrapper(gym.make('LunarLander-v3', continuous=False)))"
            )
        venv.seed(cfg.worker_seeds(0)[0])
        model = build_model(cfg, venv, "cpu")
        model.learn(total_timesteps=transitions, log_interval=None)
        wall = time.perf_counter() - t0
        cpu1 = proc.cpu_times()
        with tempfile.TemporaryDirectory() as tmp:
            t1 = time.perf_counter()
            model.save(Path(tmp) / "model.zip")
            result["checkpoint_save_s"] = time.perf_counter() - t1
            result["artifact_bytes"] = {"model.zip": (Path(tmp) / "model.zip").stat().st_size}
        venv.close()
        result.update(
            transitions=int(model.num_timesteps),
            wall_s=wall,
            loop_s=wall,
            validation_s=0.0,
            validation_env_steps=0,
            checkpoint_s=0.0,
            n_checkpoints=0,
            cpu_s=(cpu1.user - cpu0.user) + (cpu1.system - cpu0.system),
        )
        result["hyperparameters"] = _hyperparameters(model)
    else:
        import lunarlab.evaluation as evaluation
        import lunarlab.training as training
        from lunarlab.runs import create_run
        from lunarlab.storage import RunPaths

        timers = {"validation_s": 0.0, "validation_env_steps": 0, "checkpoint_s": 0.0, "n_checkpoints": 0}
        evaluate, save, build = evaluation.evaluate_policy, training.save_model_atomic, training.build_model
        built: list = []

        def capturing_build(*args, **kwargs):  # keep the model object to read its hyperparameters
            built.append(build(*args, **kwargs))
            return built[-1]

        def timed_evaluate(*args, **kwargs):
            t = time.perf_counter()
            res = evaluate(*args, **kwargs)
            timers["validation_s"] += time.perf_counter() - t
            timers["validation_env_steps"] += sum(int(e["length"]) for e in res["episodes"])
            return res

        def timed_save(*args, **kwargs):
            t = time.perf_counter()
            entry = save(*args, **kwargs)
            timers["checkpoint_s"] += time.perf_counter() - t
            timers["n_checkpoints"] += 1
            return entry

        evaluation.evaluate_policy = timed_evaluate  # measurement only, inside this benchmark process
        training.save_model_atomic = timed_save
        training.build_model = capturing_build
        cadence = max(256, transitions // 4)
        cfg = create_run(
            reward=preset("baseline"),
            seed=seed,
            ppo=ppo,
            training=TrainingConfig(
                profile="custom",
                total_transitions=transitions,
                checkpoint_every=cadence,
                validation_every=cadence,
                torch_threads=threads,
            ),
            label="overhead benchmark",
        )
        result["env_stack"] = "lunarlab.training.train (Monitor(LunarLabRewardWrapper(...)) + callback)"
        result["cadence"] = {"checkpoint_every": cadence, "validation_every": cadence}
        cpu0, t0 = proc.cpu_times(), time.perf_counter()
        code = training.train(cfg.run_id, quiet=True)
        wall = time.perf_counter() - t0
        cpu1 = proc.cpu_times()
        if code != training.EXIT_COMPLETED:
            raise RuntimeError(f"training exited with code {code}")
        from lunarlab.runs import load_metadata

        seg = load_metadata(cfg.run_id)["segments"][0]
        result.update(
            transitions=int(seg["end_transitions"]),
            wall_s=wall,
            loop_s=wall - timers["validation_s"] - timers["checkpoint_s"],
            cpu_s=(cpu1.user - cpu0.user) + (cpu1.system - cpu0.system),
            artifact_bytes=_dir_bytes(RunPaths(cfg.run_id).root),
            checkpoint_save_s=timers["checkpoint_s"] / max(timers["n_checkpoints"], 1),
            **timers,
        )
        result["hyperparameters"] = _hyperparameters(built[0])
        result["recording"] = _measure_recording(cfg.run_id)
    peak, method = _peak_memory_bytes()
    result.update(peak_memory_bytes=peak, peak_memory_method=method)
    return result


def _hyperparameters(model) -> dict[str, Any]:
    return {
        "n_envs": int(model.n_envs),
        "n_steps": int(model.n_steps),
        "batch_size": int(model.batch_size),
        "n_epochs": int(model.n_epochs),
        "gamma": float(model.gamma),
        "net_arch": str(model.policy_kwargs.get("net_arch")),
        "activation": getattr(model.policy_kwargs.get("activation_fn"), "__name__", None),
        "parameters": int(sum(p.numel() for p in model.policy.parameters())),
    }


def _measure_recording(run_id: str) -> dict[str, Any]:
    """Recording cost, measured separately: one episode with video and per-step telemetry."""
    from lunarlab.recording import record_run

    t = time.perf_counter()
    summary = record_run(run_id, episode_seed=20_000)
    return {
        "seconds": time.perf_counter() - t,
        "steps": summary.get("length"),
        "frames": summary.get("n_frames"),
        "video": (summary.get("video") or {}).get("format"),
    }


def _system() -> dict[str, Any]:
    from lunarlab.sysinfo import hardware, version_info

    return {"software": version_info(), "hardware": hardware()}


def _summarize(rows: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for c in CONFIGS:
        rs = [r for r in rows if r["config"] == c]
        if not rs:
            continue

        def stats(key: str, rs=rs) -> dict[str, float | None]:
            vals = [float(r[key]) for r in rs if r.get(key) is not None]
            if not vals:
                return {"mean": None, "sd": None, "min": None, "max": None}
            return {
                "mean": statistics.fmean(vals),
                "sd": statistics.stdev(vals) if len(vals) > 1 else 0.0,
                "min": min(vals),
                "max": max(vals),
            }

        for r in rs:
            r["loop_transitions_per_s"] = r["transitions"] / r["loop_s"]
            r["wall_transitions_per_s"] = r["transitions"] / r["wall_s"]
            r["cpu_utilization"] = r["cpu_s"] / r["wall_s"]
            r["artifact_total_bytes"] = sum(r["artifact_bytes"].values())
        out[c] = {
            "label": LABELS[c],
            "n": len(rs),
            **{
                k: stats(k)
                for k in (
                    "wall_s",
                    "loop_s",
                    "loop_transitions_per_s",
                    "wall_transitions_per_s",
                    "validation_s",
                    "validation_env_steps",
                    "checkpoint_s",
                    "checkpoint_save_s",
                    "cpu_utilization",
                    "peak_memory_bytes",
                    "artifact_total_bytes",
                )
            },
        }
    base = out.get("sb3", {}).get("loop_s", {}).get("mean")
    if base:
        for c in out:
            out[c]["loop_time_relative_to_sb3"] = out[c]["loop_s"]["mean"] / base
    return out


def _table(summary: dict, meta: dict) -> str:
    def f(v, fmt):
        return "—" if v is None else format(v, fmt)

    lines = [
        f"Measured {meta['created_at']} on {meta['system']['hardware']['cpu']} ({meta['system']['hardware']['platform']}), "
        f"Python {meta['system']['software']['python']}, lunarlab {meta['system']['software']['lunarlab']} "
        f"(source {(meta['system']['software']['git'].get('revision') or 'n/a')[:12]}"
        f"{', uncommitted changes' if meta['system']['software']['git'].get('dirty') else ''}). "
        f"PPO, {meta['transitions']:,} transitions per run, {meta['repeats']} repetitions per configuration, "
        f"torch threads {meta['torch_threads']}, CPU only. Mean ± SD over repetitions.",
        "",
        "| Configuration | Training-loop time (s) | Loop throughput (transitions/s) | Loop time vs A | Validation (s, env steps) | Checkpoints (s) | CPU utilisation | Peak memory (MB) | Artifacts (MB) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in summary.values():
        lines.append(
            f"| {s['label']} | {f(s['loop_s']['mean'], '.1f')} ± {f(s['loop_s']['sd'], '.1f')} | "
            f"{f(s['loop_transitions_per_s']['mean'], ',.0f')} ± {f(s['loop_transitions_per_s']['sd'], ',.0f')} | "
            f"{f(s.get('loop_time_relative_to_sb3'), '.2f')}× | "
            f"{f(s['validation_s']['mean'], '.1f')} ({f(s['validation_env_steps']['mean'], ',.0f')}) | "
            f"{f(s['checkpoint_s']['mean'], '.2f')} | {f(s['cpu_utilization']['mean'], '.2f')} | "
            f"{f((s['peak_memory_bytes']['mean'] or 0) / 1e6, '.0f')} | {f(s['artifact_total_bytes']['mean'] / 1e6, '.2f')} |"
        )
    lines += [
        "",
        "Training-loop time excludes C's validation episodes and checkpoint writes (reported in their own columns). "
        "Artifacts: A and B save one SB3 model file; C keeps its whole run directory (checkpoints, episode CSV, "
        "metrics, events, status, validation results).",
    ]
    return "\n".join(lines) + "\n"


def _figure(summary: dict, rows: list[dict], out: Path, meta: dict) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {"font.size": 9, "svg.fonttype": "none", "pdf.fonttype": 42, "svg.hashsalt": "lunarlab"}
    )
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9), constrained_layout=True)
    names = list(summary)
    for ax, key, title in (
        (axes[0], "loop_transitions_per_s", "Training-loop throughput (transitions/s)"),
        (axes[1], "peak_memory_bytes", "Peak memory per process (MB)"),
    ):
        for i, c in enumerate(names):
            vals = [r[key] / (1e6 if key == "peak_memory_bytes" else 1) for r in rows if r["config"] == c]
            ax.scatter(
                [i] * len(vals), vals, s=14, color="#444", zorder=3, label="repetition" if i == 0 else None
            )
            ax.bar(i, sum(vals) / len(vals), color=["#9db4c0", "#5c8fa8", "#2d5f7a"][i], width=0.6, zorder=2)
        ax.set_xticks(range(len(names)), [summary[c]["label"].split(" · ")[0] for c in names])
        ax.set_title(title, loc="left")
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", color="#ddd", zorder=0)
    axes[0].legend(frameon=False, loc="upper right", bbox_to_anchor=(1.0, 1.0))
    axes[0].set_ylim(top=max(r["loop_transitions_per_s"] for r in rows) * 1.18)
    fig.suptitle(
        "A plain SB3 · B + LunarLab reward accounting · C full LunarLab pipeline\n"
        f"PPO, {meta['transitions']:,} transitions per run, {meta['repeats']} repetitions (dots), bars = mean; "
        f"{meta['system']['hardware']['cpu'].replace('(R)', '').replace('(TM)', '')}, CPU only",
        fontsize=8,
        x=0.01,
        ha="left",
    )
    files = []
    for ext in ("png", "pdf", "svg"):
        p = out / f"overhead.{ext}"
        if ext == "svg":  # SVG is text: write it with LF on every platform
            buf = io.StringIO()
            fig.savefig(buf, format="svg", metadata={"Date": None})
            p.write_text(buf.getvalue(), encoding="utf-8", newline="\n")
        else:
            fig.savefig(p, dpi=200, metadata={"Date": None} if ext == "pdf" else None)
        files.append(p.name)
    plt.close(fig)
    return files


def run_benchmark(
    profile: str = "smoke",
    *,
    transitions: int | None = None,
    repeats: int | None = None,
    out: Path | None = None,
    torch_threads: int = 1,
    seed: int = 0,
    echo=print,
) -> dict[str, Any]:
    """Run every configuration ``repeats`` times in fresh processes; write raw rows, summary, table and figure."""
    from lunarlab.storage import project_root, utc_now

    p = PROFILES[profile]
    transitions = transitions or p["transitions"]
    repeats = repeats or p["repeats"]
    created = utc_now()
    out = out or project_root() / "reports" / "jmlr" / "benchmarks" / f"{profile}-{created.replace(':', '')}"
    out.mkdir(parents=True, exist_ok=False)
    meta = {
        "kind": "lunarlab.overhead-benchmark",
        "schema": 1,
        "created_at": created,
        "profile": profile,
        "transitions": transitions,
        "repeats": repeats,
        "torch_threads": torch_threads,
        "seed": seed,
        "configurations": LABELS,
        "system": _system(),
        "command": f"python -m lunarlab overhead-benchmark --profile {profile} --transitions {transitions} --repeats {repeats}",
    }
    rows: list[dict] = []
    raw = out / "raw.jsonl"
    for rep in range(repeats):
        order = CONFIGS[rep % 3 :] + CONFIGS[: rep % 3]  # rotate so no configuration always runs first
        for c in order:
            with tempfile.TemporaryDirectory(prefix="lunarlab-overhead-") as home:
                env = {
                    **os.environ,
                    "LUNARLAB_HOME": home,
                    "SDL_VIDEODRIVER": "dummy",
                    "SDL_AUDIODRIVER": "dummy",
                }
                res_file = Path(home) / "result.json"
                cmd = [
                    sys.executable, "-m", "lunarlab.overhead", "--worker", c,
                    "--transitions", str(transitions), "--seed", str(seed), "--threads", str(torch_threads),
                    "--result", str(res_file),
                ]  # fmt: skip
                t0 = time.perf_counter()
                proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
                if proc.returncode != 0:
                    raise RuntimeError(f"benchmark worker {c} failed:\n{proc.stderr[-3000:]}")
                row = json.loads(res_file.read_text(encoding="utf-8"))
                row["repetition"] = rep
                row["process_s"] = time.perf_counter() - t0
                if c == "lunarlab":
                    _remove_readonly_tree(Path(home))
            rows.append(row)
            with raw.open("a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(row) + "\n")
            echo(
                f"  rep {rep + 1}/{repeats} {LABELS[c]:<36} loop {row['loop_s']:7.2f} s  "
                f"{row['transitions'] / row['loop_s']:8,.0f} transitions/s  peak {row['peak_memory_bytes'] / 1e6:6.0f} MB"
            )
    hp = {json.dumps(r["hyperparameters"], sort_keys=True) for r in rows}
    meta["equivalent_hyperparameters"] = len(hp) == 1
    meta["hyperparameters"] = rows[0]["hyperparameters"]
    meta["transitions_done"] = sorted({r["transitions"] for r in rows})
    summary = _summarize(rows)
    (out / "summary.json").write_text(
        json.dumps({"meta": meta, "summary": summary}, indent=2), encoding="utf-8", newline="\n"
    )
    (out / "raw.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n"
    )
    (out / "table.md").write_text(_table(summary, meta), encoding="utf-8", newline="\n")
    meta["figures"] = _figure(summary, rows, out, meta)
    (out / "summary.json").write_text(
        json.dumps({"meta": meta, "summary": summary}, indent=2), encoding="utf-8", newline="\n"
    )
    if not meta["equivalent_hyperparameters"]:
        raise RuntimeError("the configurations did not train equivalent models; see raw.jsonl")
    return {"out": str(out), "meta": meta, "summary": summary}


def _remove_readonly_tree(path: Path) -> None:
    import stat

    for p in path.rglob("*"):
        if p.is_file():
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)


def render(out: Path) -> list[str]:
    """Re-create ``table.md`` and the figures from a benchmark folder's saved ``raw.jsonl`` (no re-run)."""
    meta = json.loads((out / "summary.json").read_text(encoding="utf-8"))["meta"]
    rows = [json.loads(line) for line in (out / "raw.jsonl").read_text(encoding="utf-8").splitlines() if line]
    summary = _summarize(rows)
    (out / "table.md").write_text(_table(summary, meta), encoding="utf-8", newline="\n")
    return _figure(summary, rows, out, meta)


def main(argv: list[str] | None = None) -> int:
    """``python -m lunarlab.overhead``: one measurement in this process (``--worker``), or ``--render`` a folder."""
    ap = argparse.ArgumentParser(prog="python -m lunarlab.overhead")
    ap.add_argument(
        "--render", help="re-create the table and figures of this benchmark folder from raw.jsonl"
    )
    ap.add_argument("--worker", choices=CONFIGS)
    ap.add_argument("--transitions", type=int)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--result")
    args = ap.parse_args(argv)
    if args.render:
        print("rendered", ", ".join(render(Path(args.render))))
        return 0
    if not (args.worker and args.transitions and args.result):
        ap.error("--worker, --transitions and --result are required (or --render DIR)")
    res = _run_config(args.worker, args.transitions, args.seed, args.threads)
    Path(args.result).write_text(json.dumps(res), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
