# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Figures for the JMLR-MLOSS manuscript, from stored data only.

    python tools/paper_figures.py --derive    # read the published runs (local, read-only) -> derived CSV + sources
    python tools/paper_figures.py             # render every figure from the committed derived data

Figure "reward accounting": per reward design, the rolling mean (100 training episodes) of the ORIGINAL return
and of the TRAINING (shaped) return over environment transitions, median over the five PPO training seeds of the
published reward-shaping study with the min-max band. Derived data: ``reports/jmlr/figures/reward_accounting.csv``;
its sources (run IDs and the SHA-256 of every ``episodes.csv`` read) are in ``reward_accounting.sources.json``.

Figure "overhead": copied from the measured overhead benchmark (``reports/jmlr/benchmarks/standard-*``).

Figure "workflow": a conceptual diagram (no data).

Outputs go to ``reports/jmlr/figures/`` and ``paper/jmlr-mloss/figures/`` as PDF (vector), SVG and PNG, with
``reports/jmlr/figures/manifest.json`` describing how each was made.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "reports" / "jmlr" / "figures"
PAPER = ROOT / "paper" / "jmlr-mloss" / "figures"
STUDY = "exp-20261015-223113-reward-shaping-study-7f93"
PRESETS = {
    "baseline": "Original reward",
    "potential": "Potential-based shaping",
    "hover-bonus": "Flawed hover bonus",
}
GRID = np.linspace(0, 1_003_520, 121)
WINDOW = 100
sys.path.insert(0, str(ROOT))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive() -> None:
    """Read the study's runs (never modified) and write the binned curves and their sources."""
    from lunarlab.compare import experiment_run_ids
    from lunarlab.runs import load_config
    from lunarlab.storage import RunPaths

    rows, sources = [], []
    for preset in PRESETS:
        curves = {"original": [], "training": []}
        for rid in experiment_run_ids(STUDY):
            cfg = load_config(rid)
            if cfg.reward.preset != preset:
                continue
            path = RunPaths(rid).episodes
            with path.open(encoding="utf-8", newline="") as f:
                eps = list(csv.DictReader(f))
            t = np.array([float(e["transitions"]) for e in eps])
            for kind in curves:
                r = np.array([float(e[f"{kind}_return"]) for e in eps])
                roll = np.convolve(r, np.ones(WINDOW) / WINDOW, mode="valid")
                tt = t[WINDOW - 1 :]
                # value at each grid point: the last rolling mean reached by then (NaN before the first window)
                idx = np.searchsorted(tt, GRID, side="right") - 1
                curves[kind].append(np.where(idx >= 0, roll[np.clip(idx, 0, None)], np.nan))
            sources.append({"run_id": rid, "preset": preset, "seed": cfg.seed, "episodes": len(eps),
                            "episodes_csv_sha256": _sha(path)})  # fmt: skip
        for kind, runs in curves.items():
            a = np.vstack(runs)
            for i, x in enumerate(GRID):
                col = a[:, i]
                if np.isnan(col).any():
                    continue
                rows.append(
                    [
                        preset,
                        kind,
                        int(x),
                        float(np.median(col)),
                        float(col.min()),
                        float(col.max()),
                        len(col),
                    ]
                )
    FIG.mkdir(parents=True, exist_ok=True)
    with (FIG / "reward_accounting.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["preset", "return", "transitions", "median", "min", "max", "n_runs"])
        for r in rows:
            w.writerow([r[0], r[1], r[2], f"{r[3]:.4f}", f"{r[4]:.4f}", f"{r[5]:.4f}", r[6]])
    (FIG / "reward_accounting.sources.json").write_text(
        json.dumps({"experiment_id": STUDY, "window_episodes": WINDOW, "runs": sources}, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"derived {len(rows)} rows from {len(sources)} runs")


def _style():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.size": 9,
            "font.family": "DejaVu Sans",
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "svg.hashsalt": "lunarlab",
        }
    )
    return plt


TEXT_WIDTH_IN = 6.0  # \textwidth of jmlr2e.sty: figures are drawn at this width and included at natural size
MIN_TEXT_PT = 9.0  # JMLR: "Captions, labels, and other text in illustrations: at least 9 pt"


def check_print_size(fig) -> None:
    """Refuse a figure wider than the text block, with text under 9 pt, or with text outside the canvas."""
    width, _ = fig.get_size_inches()
    if width > TEXT_WIDTH_IN + 1e-6:
        raise ValueError(f"figure is {width:.2f} in wide; the JMLR text block is {TEXT_WIDTH_IN} in")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    canvas = fig.bbox
    for t in fig.findobj(lambda a: hasattr(a, "get_fontsize") and hasattr(a, "get_text")):
        if not t.get_visible() or not t.get_text().strip():
            continue
        if t.get_fontsize() < MIN_TEXT_PT:
            raise ValueError(f"text {t.get_text()!r} is {t.get_fontsize()} pt (minimum {MIN_TEXT_PT})")
        box = t.get_window_extent(renderer)
        if (
            box.x0 < canvas.x0 - 1
            or box.x1 > canvas.x1 + 1
            or box.y0 < canvas.y0 - 1
            or box.y1 > canvas.y1 + 1
        ):
            raise ValueError(f"text {t.get_text()!r} extends beyond the figure")
    for ax in fig.axes:
        for patch in ax.patches:  # boxes and arrows drawn on the figure must not be clipped either
            box = patch.get_window_extent(renderer)
            if (
                box.x0 < canvas.x0 - 1
                or box.x1 > canvas.x1 + 1
                or box.y0 < canvas.y0 - 1
                or box.y1 > canvas.y1 + 1
            ):
                raise ValueError(f"{type(patch).__name__} extends beyond the figure")


def _save(fig, name: str) -> list[str]:
    check_print_size(fig)
    out = []
    for target in (FIG, PAPER):
        target.mkdir(parents=True, exist_ok=True)
        for ext in ("pdf", "svg", "png"):
            path = target / f"{name}.{ext}"
            if ext == "svg":  # SVG is text: write it with LF on every platform
                buf = io.StringIO()
                fig.savefig(buf, format="svg", metadata={"Date": None})
                path.write_text(buf.getvalue(), encoding="utf-8", newline="\n")
            else:
                fig.savefig(path, dpi=200, metadata={"Date": None} if ext == "pdf" else None)
            out.append(f"{target.relative_to(ROOT).as_posix()}/{name}.{ext}")
    return out


def render_reward_accounting() -> dict:
    plt = _style()
    data: dict = {}
    with (FIG / "reward_accounting.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            data.setdefault((r["preset"], r["return"]), []).append(
                (int(r["transitions"]), float(r["median"]), float(r["min"]), float(r["max"]))
            )
    fig, axes = plt.subplots(1, 3, figsize=(TEXT_WIDTH_IN, 2.0), sharey=True, layout="constrained")
    for ax, (preset, title) in zip(axes, PRESETS.items(), strict=True):
        for kind, style in (
            ("original", dict(color="#1f5f8b", ls="-")),
            ("training", dict(color="#c0392b", ls="--")),
        ):
            pts = np.array(data[(preset, kind)])
            ax.fill_between(pts[:, 0] / 1e6, pts[:, 2], pts[:, 3], color=style["color"], alpha=0.15, lw=0)
            ax.plot(pts[:, 0] / 1e6, pts[:, 1], color=style["color"], ls=style["ls"], lw=1.6,
                    label={"original": "original return (task)", "training": "training return (optimised)"}[kind])  # fmt: skip
        ax.set_title(title, loc="left", fontsize=9)
        ax.axhline(200, color="#999", lw=0.7, ls=":")
        ax.set_xticks([0, 0.5, 1.0])
        ax.grid(color="#eee")
    axes[0].set_ylabel("return per episode\n(rolling mean of 100)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside upper center", ncol=2, frameon=False, fontsize=9)
    fig.supxlabel("environment transitions (millions)", fontsize=9)
    files = _save(fig, "reward_accounting")
    plt.close(fig)
    src = json.loads((FIG / "reward_accounting.sources.json").read_text(encoding="utf-8"))
    return {
        "name": "reward_accounting",
        "kind": "measured data (training episodes of the published study)",
        "description": "Original vs training return during PPO training, median over 5 seeds with min-max band, per reward design.",
        "derived_data": "reports/jmlr/figures/reward_accounting.csv",
        "derived_data_sha256": _sha(FIG / "reward_accounting.csv"),
        "sources": "reports/jmlr/figures/reward_accounting.sources.json",
        "source_runs": [r["run_id"] for r in src["runs"]],
        "files": files,
    }


def render_overhead() -> dict:
    bench = sorted((ROOT / "reports" / "jmlr" / "benchmarks").glob("standard-*"))[-1]
    files = []
    for ext in ("pdf", "svg", "png"):  # the manuscript reports the benchmark as a table, not this figure
        for target in (FIG,):
            target.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bench / f"overhead.{ext}", target / f"overhead.{ext}")
            files.append(f"{target.relative_to(ROOT).as_posix()}/overhead.{ext}")
    return {
        "name": "overhead",
        "kind": "measured data (overhead benchmark)",
        "description": "Training-loop throughput and peak memory: plain SB3 vs LunarLab's reward accounting vs the full pipeline.",
        "derived_data": f"{bench.relative_to(ROOT).as_posix()}/raw.jsonl",
        "derived_data_sha256": _sha(bench / "raw.jsonl"),
        "files": files,
    }


def render_workflow() -> dict:
    plt = _style()
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    fig = plt.figure(figsize=(TEXT_WIDTH_IN, 1.35))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 22)
    ax.axis("off")
    width, step = 17.4, 20.4
    boxes = [
        "Reward design\nstrict schema,\ncontent hash",
        "Training (SB3)\nevery reward\nterm recorded",
        "Checkpoints\nSHA-256\nmanifest",
        "Validation\nselects the\ncheckpoint",
        "Final test\nfrozen copy,\nunseen seeds",
    ]
    for i, text in enumerate(boxes):
        x = 0.6 + i * step
        ax.add_patch(
            FancyBboxPatch(
                (x, 8.4), width, 13.0, boxstyle="round,pad=0.25", fc="#eef3f7", ec="#1f5f8b", lw=0.9
            )
        )
        ax.text(x + width / 2, 14.9, text, ha="center", va="center", fontsize=9, linespacing=1.2)
        if i:
            ax.add_patch(
                FancyArrowPatch(
                    (x - step + width + 0.4, 14.9),
                    (x - 0.4, 14.9),
                    arrowstyle="-|>",
                    mutation_scale=8,
                    color="#1f5f8b",
                )
            )
    ax.text(50, 4.5, "Audit record: original and training return per term, exploitation diagnostics,",
            ha="center", va="center", fontsize=9)  # fmt: skip
    ax.text(50, 1.4, "statistics across seeds, per-step replay, provenance (hashes, seeds, versions)",
            ha="center", va="center", fontsize=9)  # fmt: skip
    files = _save(fig, "workflow")
    plt.close(fig)
    return {
        "name": "workflow",
        "kind": "conceptual diagram (no data)",
        "description": "LunarLab's audited research workflow.",
        "files": files,
    }


def render() -> None:
    entries = [render_workflow(), render_reward_accounting(), render_overhead()]
    manifest = {
        "generated_by": "python tools/paper_figures.py",
        "figures": entries,
        "note": "Re-derive the reward-accounting data from the local runs with --derive (reads, never writes, runs/).",
    }
    (FIG / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("rendered", ", ".join(e["name"] for e in entries))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--derive", action="store_true", help="re-derive the curves from the local published runs first"
    )
    args = ap.parse_args()
    if args.derive:
        derive()
    render()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
