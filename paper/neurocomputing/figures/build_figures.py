# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Build and verify the figures of the Neurocomputing manuscript from recorded data.

    python paper/neurocomputing/figures/build_figures.py

* Figure 1, architecture and evidence flow (``architecture``). It is drawn from a node and edge list.
  Every module and function the diagram names is imported and checked to exist, so each arrow names a real
  code path.
* Figure 2, the historical LunarLander audit (``final_test_audit``). It is copied byte for byte from
  ``paper/jmlr-mloss/figures``, and every plotted value is re-derived from ``docs/results/results.json``
  (``final_test_audit.verification.json``).
* Figure 3, the audit-workflow comparison (``workflow_comparison``), read from that study's
  ``results/summary.json``.
* Figure 4, the CartPole study (``cartpole_study``), read from that study's ``results/results.json``.

Each new figure is written as PDF (TrueType fonts embedded) and SVG, with a PNG preview and a
``.values.json`` of what was plotted. ``MANIFEST.json`` records the SHA-256 of every input and output.
The new figures are drawn at the manuscript's text width (390 pt, 5.39 inches) with text of at least 9 pt,
so they print at that size when included at full width. Figure 2 was drawn at 6.0 inches with text of at
least 10 pt; at the text width it prints at 390/432 of that, so its smallest text is 9.03 pt.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
EVIDENCE = ROOT / "reports" / "neurocomputing-2026-10-27"
WIDTH = 5.39  # the manuscript's text width (390 pt): figures print at their designed size
FONT = 9.5
# Okabe-Ito colours (colour-blind safe); every encoding is also carried by a symbol or text.
BLACK, ORANGE, SKY, GREEN, BLUE, VERMILLION, PURPLE, GREY = (
    "#000000",
    "#E69F00",
    "#56B4E9",
    "#009E73",
    "#0072B2",
    "#D55E00",
    "#CC79A7",
    "#BBBBBB",
)
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": FONT,
        "axes.titlesize": FONT,
        "axes.labelsize": FONT,
        "xtick.labelsize": FONT,
        "ytick.labelsize": FONT,
        "legend.fontsize": FONT,
        "pdf.fonttype": 42,
        "svg.fonttype": "path",
        "svg.hashsalt": "lunarlab",
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(fig, stem: str, values: dict, inputs: list[Path], manifest: dict) -> None:
    outputs = {}
    for ext, kw in (
        ("pdf", {"metadata": {"CreationDate": None, "ModDate": None}}),
        ("svg", {"metadata": {"Date": None}}),
        ("png", {"dpi": 150}),
    ):
        p = HERE / f"{stem}.{ext}"
        fig.savefig(p, **kw)
        if ext == "svg":  # Matplotlib writes the platform's line endings; store LF, as git does
            p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n"))
        outputs[p.name] = sha256(p)
    plt.close(fig)
    vp = HERE / f"{stem}.values.json"
    vp.write_text(json.dumps(values, indent=1) + "\n", encoding="utf-8", newline="\n")
    outputs[vp.name] = sha256(vp)
    manifest[stem] = {
        "inputs": {p.relative_to(ROOT).as_posix(): sha256(p) for p in inputs},
        "outputs": outputs,
        "command": "python paper/neurocomputing/figures/build_figures.py",
    }


# --------------------------------------------------------------------------- #
# Figure 1: architecture and evidence flow
# --------------------------------------------------------------------------- #

STAGES = [
    (
        "Reward specification",
        "named terms, original-reward weight and a\nversioned provenance record",
        [
            "lunarlab.audit.core:RewardTerm",
            "lunarlab.audit.provenance:reward_provenance",
            "lunarlab.rewards.config:RewardConfig",
        ],
    ),
    (
        "Training with reward accounting",
        "SB3 learns the training reward; the original\nreward and every term are recorded with it",
        [
            "lunarlab.audit.core:RewardAccountingWrapper",
            "lunarlab.rewards.wrapper:LunarLabRewardWrapper",
            "lunarlab.audit.study:train_run",
        ],
    ),
    (
        "Checkpoint selection",
        "checkpoints scored with the original reward\non validation seeds; prespecified rule",
        [
            "lunarlab.audit.evaluate:audit_policy",
            "lunarlab.audit.study:select_checkpoint",
            "lunarlab.evaluation:evaluate_policy",
        ],
    ),
    (
        "Frozen policy",
        "content-addressed, read-only copy of the\nselected checkpoint",
        ["lunarlab.freeze:immutable_copy", "lunarlab.freeze:freeze_for_test"],
    ),
    (
        "Held-out test",
        "fixed test seeds; per episode: original,\ntraining and term returns, ending, outcome",
        ["lunarlab.audit.study:final_test", "lunarlab.evaluation:evaluate_run"],
    ),
    (
        "Artifact verification and replay",
        "integrity checked first; then exact, numerical\ndifference or blocking difference",
        [
            "lunarlab.reproduce:reproduce_artifact",
            "lunarlab.audit.study:reproduce_artifact",
            "lunarlab.reproduce:classify_reproduction",
        ],
    ),
]
CHECKS = [
    (
        0.5,
        "seed contract, finite\nvalues, protocol validated",
        ["lunarlab.audit.contracts:normalize_seeds", "lunarlab.config:EvalProtocol"],
    ),
    (1.5, "SHA-256 of every\ncheckpoint recorded", ["lunarlab.storage:sha256_file"]),
    (2.5, "selection sees\nvalidation seeds only", ["lunarlab.audit.study:protocol_problems"]),
    (
        3.5,
        "frozen digest checked\nbefore the test opens",
        ["lunarlab.audit.study:verify_frozen", "lunarlab.freeze:resolve_frozen_checkpoint"],
    ),
    (
        5.0,
        "files, reward model and\nrecords checked before\nany episode runs",
        ["lunarlab.audit.study:verify_artifact"],
    ),
]
APPLICATION = [
    ("Strict pad-landing\nclassifier", "lunarlab.outcomes:classify_outcome", 4),
    ("Hover diagnostic,\nreplay, re-scoring", "lunarlab.hover:hover_state", 4),
    ("Web interface\n(FastAPI, React)", "lunarlab.server", 5),
]


def resolve(ref: str) -> bool:
    module, _, name = ref.partition(":")
    mod = importlib.import_module(module)
    return hasattr(mod, name) if name else True


def _box(ax, x, y, w, h, edge, lw=1.1):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor="white",
            edgecolor=edge,
            linewidth=lw,
            zorder=2,
        )
    )


def _arrow(ax, start, end, color=BLACK, dashed=False, lw=1.1):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=10,
            color=color,
            linewidth=lw,
            linestyle=(0, (3, 2)) if dashed else "-",
            zorder=1,
        )
    )


def figure_architecture(manifest: dict) -> None:
    refs = [r for s in STAGES for r in s[2]] + [r for c in CHECKS for r in c[2]] + [a[1] for a in APPLICATION]
    missing = [r for r in refs if not resolve(r)]
    if missing:
        raise SystemExit(f"the diagram names code that does not exist: {missing}")
    height = 5.85
    fig = plt.figure(figsize=(WIDTH, height))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, WIDTH)
    ax.set_ylim(0, height)
    ax.axis("off")
    x0, w, h, gap, top = 0.18, 3.0, 0.56, 0.17, height - 0.42
    core_bottom = top - 6 * h - 5 * gap - 0.1
    ax.add_patch(
        Rectangle(
            (0.06, core_bottom),
            WIDTH - 0.12,
            top - core_bottom + 0.36,
            facecolor="#EAF4FB",
            edgecolor="none",
            zorder=0,
        )
    )
    ax.text(
        0.14,
        top + 0.12,
        "Reusable research core: any Gymnasium task, via an adapter",
        ha="left",
        va="bottom",
        fontsize=FONT,
        color=BLUE,
        fontweight="bold",
    )
    ys = []
    for i, (title, detail, _) in enumerate(STAGES):
        y = top - h - i * (h + gap)
        ys.append(y)
        _box(ax, x0, y, w, h, BLUE)
        ax.text(
            x0 + 0.08, y + h - 0.06, title, ha="left", va="top", fontsize=FONT, fontweight="bold", zorder=3
        )
        ax.text(
            x0 + 0.08,
            y + h - 0.24,
            detail,
            ha="left",
            va="top",
            fontsize=FONT - 0.5,
            linespacing=1.12,
            zorder=3,
        )
        if i:
            _arrow(ax, (x0 + w / 2, ys[i - 1]), (x0 + w / 2, y + h))
    xr = x0 + w + 0.24
    for pos, text, _ in CHECKS:
        yc = ys[int(pos)] + h / 2 if float(pos).is_integer() else (ys[int(pos)] + ys[int(pos) + 1] + h) / 2
        ax.plot(
            [x0 + w / 2 + 0.03, xr - 0.07],
            [yc, yc],
            color=VERMILLION,
            linewidth=0.9,
            linestyle=(0, (3, 2)),
            zorder=1,
        )
        ax.plot([xr], [yc], marker="D", markersize=6, color=VERMILLION, zorder=3)
        ax.text(xr + 0.12, yc, text, ha="left", va="center", fontsize=FONT - 0.5, linespacing=1.1)
    band_top = core_bottom - 0.1
    ax.add_patch(
        Rectangle(
            (0.06, 0.06), WIDTH - 0.12, band_top - 0.06, facecolor="#EEEEEE", edgecolor="none", zorder=0
        )
    )
    ax.text(
        0.14,
        0.35,
        "LunarLander\napplication\n(task-specific)",
        ha="left",
        va="center",
        fontsize=FONT,
        fontweight="bold",
        color="#444444",
        linespacing=1.1,
    )
    bw, bh, by = 1.22, 0.46, 0.12
    centers = []
    for k, (label, _ref, _stage) in enumerate(APPLICATION):
        bx = 1.3 + k * (bw + 0.06)
        centers.append(bx + bw / 2)
        _box(ax, bx, by, bw, bh, "#777777", lw=0.9)
        ax.text(
            bx + bw / 2,
            by + bh / 2,
            label,
            ha="center",
            va="center",
            fontsize=FONT - 0.5,
            linespacing=1.05,
            zorder=3,
        )
    for c in centers[
        :2
    ]:  # outcome definitions and diagnostics plug into every evaluation through the adapter
        _arrow(ax, (c, by + bh), (c, core_bottom + 0.02), "#555555", dashed=True, lw=0.9)
    _arrow(ax, (centers[2], core_bottom + 0.02), (centers[2], by + bh), "#555555", dashed=True, lw=0.9)
    label_y = (by + bh + core_bottom) / 2
    for x, text in (
        (centers[0] - 0.08, "plug in through\nthe task adapter"),
        (centers[2] - 0.08, "reads recorded\nartifacts"),
    ):
        ax.text(
            x, label_y, text, ha="right", va="center", fontsize=FONT - 0.5, color="#444444", linespacing=1.05
        )
    values = {
        "stages": [{"title": t, "detail": d.replace("\n", " "), "code": c} for t, d, c in STAGES],
        "checks": [{"between_stages": p, "text": t.replace("\n", " "), "code": c} for p, t, c in CHECKS],
        "application": [
            {"label": a.replace("\n", " "), "code": r, "connects_to_stage": s} for a, r, s in APPLICATION
        ],
        "all_named_code_exists": True,
        "edges": "solid: data passes from each stage to the next along the listed functions; red dashed with a "
        "diamond: a check that must pass before the next stage; grey dashed: application components that plug in "
        "(outcome definitions, diagnostics) or read recorded artifacts (interface)",
    }
    save(fig, "architecture", values, [], manifest)


# --------------------------------------------------------------------------- #
# Figure 2: historical LunarLander audit (copied, then verified)
# --------------------------------------------------------------------------- #


def trimmed_mean(values) -> float:
    a = np.sort(np.asarray(values, dtype=float))
    k = int(0.25 * a.size)
    return float(a[k : a.size - k].mean())


def figure_historical(manifest: dict) -> None:
    src = ROOT / "paper" / "jmlr-mloss" / "figures"
    names = ("final_test_audit.pdf", "final_test_audit.svg", "final_test_audit.source.json")
    for n in names:
        # The bytes git stores for the file: a Windows checkout may convert the SVG's line endings to CRLF.
        data = (src / n).read_bytes()
        (HERE / n).write_bytes(data.replace(b"\r\n", b"\n") if n.endswith(".svg") else data)
        if n.endswith(".pdf") and sha256(HERE / n) != sha256(src / n):
            raise SystemExit(f"copy of {n} differs")
    source = json.loads((src / "final_test_audit.source.json").read_text(encoding="utf-8"))
    results_path = ROOT / source["source"]
    results = json.loads(results_path.read_text(encoding="utf-8"))
    by_group = {g["base_name"]: g for g in results["groups"] if g["algo"] == "ppo"}
    rows, ok = [], True
    for group in source["plotted"]:
        g = by_group[group["group"]]
        per_seed = {p["run_id"]: p["evaluation"] for p in g["per_seed"]}
        means = []
        for pol in group["policies"]:
            ev = per_seed[pol["run_id"]]
            same = (
                ev["mean_original_return"] == pol["mean_original_return"]
                and ev["pad_landing_rate"] == pol["pad_landing_rate"]
            )
            ok &= same
            means.append(ev["mean_original_return"])
            rows.append(
                {
                    "group": group["group"],
                    "run_id": pol["run_id"],
                    "plotted_return": pol["mean_original_return"],
                    "results_return": ev["mean_original_return"],
                    "plotted_landing": pol["pad_landing_rate"],
                    "results_landing": ev["pad_landing_rate"],
                    "identical": same,
                }
            )
        iqm_ok = abs(trimmed_mean(means) - group["iqm"]) <= 1e-12
        ok &= iqm_ok
        rows.append(
            {
                "group": group["group"],
                "integer_trimmed_mean_recomputed": trimmed_mean(means),
                "plotted_iqm": group["iqm"],
                "identical_within_1e-12": iqm_ok,
            }
        )
    verification = {
        "results_sha256": sha256(results_path),
        "source_manifest_records": source["sha256"],
        "results_unchanged": sha256(results_path) == source["sha256"],
        "rows": rows,
        "all_plotted_values_identical": ok,
        "figure_files_copied_from": "paper/jmlr-mloss/figures: the PDF and the source manifest byte for byte; the "
        "SVG as stored in git (LF line endings), which a Windows checkout may present with CRLF",
    }
    if not (ok and verification["results_unchanged"]):
        raise SystemExit("the historical figure no longer matches its recorded inputs")
    vp = HERE / "final_test_audit.verification.json"
    vp.write_text(json.dumps(verification, indent=1) + "\n", encoding="utf-8", newline="\n")
    manifest["final_test_audit"] = {
        "inputs": {results_path.relative_to(ROOT).as_posix(): sha256(results_path)},
        "outputs": {n: sha256(HERE / n) for n in (*names, vp.name)},
        "command": "copied from paper/jmlr-mloss/figures (built there by build_audit_figure.py); verified by this script",
    }


# --------------------------------------------------------------------------- #
# Figure 3: audit-workflow comparison
# --------------------------------------------------------------------------- #

CASE_LABELS = {
    "C0-clean": "C0 clean control",
    "C1-numerical-difference": "C1 replay on another platform",
    "F01-checkpoint-swapped": "F01 selected checkpoint swapped",
    "F02-recorded-digest-corrupted": "F02 recorded digest corrupted",
    "F03-protocol-mismatch": "F03 protocol and record disagree",
    "F04-dependency-missing": "F04 reward dependency missing",
    "F05-dependency-changed": "F05 reward dependency changed",
    "F06-coercible-seed": "F06 seed given as a float",
    "F07-overlapping-seeds": "F07 validation, test seeds overlap",
    "F08-nonfinite-parameter": "F08 non-finite reward parameter",
    "F09-original-channel-absent": "F09 no original-reward channel",
    "F10-inconsistent-totals": "F10 recorded totals inconsistent",
    "F11-potential-at-truncation": "F11 potential wrong at truncation",
    "F12-outcome-schema-mismatch": "F12 outcomes from other schema",
}
OUTCOME_STYLE = {
    "correct": ("✓", GREEN),
    "rejected": ("✗", BLUE),
    "unsupported": ("—", "#999999"),
    "missed": ("!", VERMILLION),
    "false alarm": ("!", VERMILLION),
    "warned": ("?", ORANGE),
    "late": ("✗", ORANGE),
    "crashed": ("☠", VERMILLION),
}


def cell_text(row: dict) -> str:
    o = row["outcome"]
    if o == "correct":
        return "accepted"
    if o == "rejected":
        return ", ".join(row["targets"])
    if o == "unsupported":
        return "not checked"
    return o


def figure_workflows(manifest: dict) -> None:
    summary_path = EVIDENCE / "workflow-comparison" / "results" / "summary.json"
    inventory_path = EVIDENCE / "workflow-comparison" / "protocol" / "fault_inventory.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    cases = [c["id"] for c in inventory["cases"]]
    workflows = ["W1", "W2", "W3"]
    titles = ["W1 SB3\nconventional", "W2 SB3\nreference", "W3\nLunarLab"]
    rows = {(r["case"], r["workflow"]): r for r in summary["rows"]}
    n = len(cases)
    label_w, col_w, row_h = 2.24, 1.03, 0.27
    height = 0.62 + n * row_h + 0.95
    fig = plt.figure(figsize=(WIDTH, height))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, WIDTH)
    ax.set_ylim(0, height)
    ax.axis("off")
    top = height - 0.6
    ax.text(
        0.06,
        top + 0.08,
        "Designed case\n(2 controls, 12 faults)",
        ha="left",
        va="bottom",
        fontsize=FONT,
        fontweight="bold",
        linespacing=1.05,
    )
    for j, t in enumerate(titles):
        ax.text(
            label_w + (j + 0.5) * col_w,
            top + 0.08,
            t,
            ha="center",
            va="bottom",
            fontsize=FONT,
            fontweight="bold",
            linespacing=1.05,
        )
    values = []
    for i, case in enumerate(cases):
        y = top - (i + 1) * row_h
        if i == 2:
            ax.plot([0.06, label_w + 3 * col_w], [y + row_h + 0.004] * 2, color=BLACK, linewidth=0.8)
        ax.text(0.06, y + row_h / 2, CASE_LABELS[case], ha="left", va="center", fontsize=FONT - 0.5)
        for j, w in enumerate(workflows):
            r = rows[(case, w)]
            sym, color = OUTCOME_STYLE[r["outcome"]]
            x = label_w + j * col_w
            ax.add_patch(
                Rectangle(
                    (x + 0.03, y + 0.022),
                    col_w - 0.06,
                    row_h - 0.044,
                    facecolor=color,
                    alpha=0.16,
                    edgecolor="none",
                )
            )
            ax.text(
                x + 0.15,
                y + row_h / 2,
                sym,
                ha="center",
                va="center",
                fontsize=FONT + 0.5,
                color=color,
                fontweight="bold",
            )
            ax.text(x + 0.29, y + row_h / 2, cell_text(r), ha="left", va="center", fontsize=FONT - 0.5)
            values.append(
                {
                    "case": case,
                    "workflow": w,
                    "outcome": r["outcome"],
                    "exit_code": r["exit_code"],
                    "episodes_executed": r["episodes_executed"],
                    "verdict": r["verdict"],
                }
            )
    legend = [
        ("✓", GREEN, "accepted as specified (C0: replay exact; C1: permitted numerical difference)"),
        ("✗", BLUE, "rejected through the named targeted check, before any episode ran"),
        ("—", "#999999", "not attempted; the policy was still evaluated on all 100 test seeds"),
    ]
    yb = top - n * row_h - 0.2
    for k, (sym, color, text) in enumerate(legend):
        ax.text(
            0.16,
            yb - k * 0.24,
            sym,
            ha="center",
            va="center",
            fontsize=FONT + 0.5,
            color=color,
            fontweight="bold",
        )
        ax.text(0.32, yb - k * 0.24, text, ha="left", va="center", fontsize=FONT - 0.5)
    save(
        fig,
        "workflow_comparison",
        {"cases": cases, "cells": values},
        [summary_path, inventory_path],
        manifest,
    )


# --------------------------------------------------------------------------- #
# Figure 4: CartPole study
# --------------------------------------------------------------------------- #


def figure_cartpole(manifest: dict) -> None:
    path = EVIDENCE / "cartpole-study" / "results" / "results.json"
    results = json.loads(path.read_text(encoding="utf-8"))
    designs = ["original", "upright-potential", "failure-bonus"]
    labels = {
        "original": "Original reward",
        "upright-potential": "Upright potential",
        "failure-bonus": "Failure bonus\n(flawed)",
    }
    colors = {"original": BLUE, "upright-potential": GREEN, "failure-bonus": VERMILLION}
    panels = [
        ("mean_original_return", "(a) Original return (mean of 100 test episodes)", (-15, 520), 1.0),
        (
            "horizon_completion_rate",
            "(b) Horizon completion (500-step limit reached)",
            (-0.03, 1.04),
            1.0,
        ),
        (
            "mean_training_return_own_design",
            "(c) Training return under the policy's own reward",
            (-25, 1100),
            1.0,
        ),
    ]
    fig, axes = plt.subplots(3, 1, figsize=(WIDTH, 6.3), gridspec_kw={"hspace": 0.75})
    values = {}
    offsets = np.array([-0.36, -0.2, -0.04, 0.12, 0.28])  # one lane per policy (seed order), as in Figure 2
    for ax, (key, title, xlim, _scale) in zip(axes, panels, strict=True):
        for row, d in enumerate(designs):
            pols = results["selected"]["policies"][d]
            xs = [p[key] for p in pols]
            seeds = [p["training_seed"] for p in pols]
            yrow = len(designs) - 1 - row
            ax.scatter(
                xs, yrow + offsets, s=16, facecolor="white", edgecolor=colors[d], linewidth=1.2, zorder=3
            )
            summ = results["selected"]["by_design"][d][key]
            lo, hi = summ["mean_ci95"]
            ax.plot([lo, hi], [yrow + 0.44] * 2, color=BLACK, linewidth=1.2, zorder=2)
            ax.plot([summ["mean"]], [yrow + 0.44], marker="D", color=BLACK, markersize=4.5, zorder=4)
            values.setdefault(d, {})[key] = {
                "by_seed": dict(zip(seeds, xs, strict=True)),
                "mean": summ["mean"],
                "mean_ci95": [lo, hi],
            }
        ax.set_yticks(range(len(designs)))
        ax.set_yticklabels([labels[d] for d in reversed(designs)])
        ax.set_ylim(-0.5, len(designs) - 0.4)
        ax.set_xlim(*xlim)
        ax.set_title(title, loc="left", pad=6)
        if key == "horizon_completion_rate":
            ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
        ax.tick_params(axis="y", length=0)
        ax.grid(axis="x", color="#DDDDDD", linewidth=0.6)
        ax.set_axisbelow(True)
    fig.subplots_adjust(left=0.27, right=0.97, top=0.96, bottom=0.05)
    save(fig, "cartpole_study", values, [path], manifest)


# --------------------------------------------------------------------------- #
# Supplementary figure: Linux replay of the six learned-reward policies
# --------------------------------------------------------------------------- #

LINUX_RUN = EVIDENCE / "linux-replay" / "run-40545198707-dea292c"
LEARNED = [
    ("20261015-235939-custom-s0-standard-0274", "300 pairs, seed 0"),
    ("20261015-235939-custom-s1-standard-b692", "300 pairs, seed 1"),
    ("20261015-235940-custom-s2-standard-a299", "300 pairs, seed 2"),
    ("20261015-235940-custom-s0-standard-d28b", "3000 pairs, seed 0"),
    ("20261015-235940-custom-s1-standard-ce26", "3000 pairs, seed 1"),
    ("20261015-235940-custom-s2-standard-dbc1", "3000 pairs, seed 2"),
]


def figure_linux_replay(manifest: dict) -> None:
    paths = [LINUX_RUN / f"reproduce-{rid}-linux.json" for rid, _ in LEARNED]
    reports = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    fig, (ax_a, ax_b) = plt.subplots(
        1, 2, figsize=(WIDTH, 3.3), gridspec_kw={"width_ratios": [1.75, 1.0], "wspace": 0.08}, sharey=True
    )
    rng = np.random.default_rng(0)  # vertical jitter only; horizontal values are unchanged
    values = []
    n = len(LEARNED)
    for i, ((rid, label), rep) in enumerate(zip(LEARNED, reports, strict=True)):
        y = n - 1 - i
        rows = rep["comparison"]["episodes"]
        diffs = np.array([r["reproduced_return"] - r["recorded_return"] for r in rows])
        ax_a.scatter(
            diffs,
            y + rng.uniform(-0.28, 0.28, diffs.size),
            s=7,
            color=BLUE,
            alpha=0.55,
            linewidth=0,
            zorder=3,
        )
        ax_a.plot([np.median(diffs)] * 2, [y - 0.36, y + 0.36], color=BLACK, linewidth=1.3, zorder=4)
        rec, repr_ = rep["recorded_pad_landing_rate"], rep["reproduced_pad_landing_rate"]
        ax_b.plot([rec, repr_], [y, y], color="#888888", linewidth=1.0, zorder=2)
        ax_b.scatter(
            [rec], [y + 0.12], marker="o", s=26, facecolor="white", edgecolor=BLACK, linewidth=1.2, zorder=3
        )
        ax_b.scatter([repr_], [y - 0.12], marker="^", s=30, color=VERMILLION, zorder=3)
        values.append(
            {
                "run_id": rid,
                "label": label,
                "status": rep["status"],
                "episodes": len(rows),
                "episodes_differing": int(np.sum(diffs != 0)),
                "median_difference": float(np.median(diffs)),
                "largest_absolute_difference": float(np.max(np.abs(diffs))),
                "outcome_agreement": rep["comparison"]["summary"]["agreement"]["all_outcome_fields"],
                "pad_landing_recorded": rec,
                "pad_landing_linux": repr_,
                "mean_original_return_recorded": rep["recorded_mean_original_return"],
                "mean_original_return_linux": rep["reproduced_mean_original_return"],
            }
        )
    ax_a.set_xscale("symlog", linthresh=1e-3, linscale=0.6)
    ax_a.set_xlim(-30, 30)
    ax_a.set_xticks([-10, -0.1, 0, 0.1, 10])
    ax_a.set_xticklabels(["−10", "−0.1", "0", "0.1", "10"])
    ax_a.axvline(0, color="#999999", linewidth=0.8, zorder=1)
    ax_a.set_yticks(range(n))
    ax_a.set_yticklabels([label for _, label in reversed(LEARNED)])
    ax_a.set_ylim(-0.6, n - 0.4)
    ax_a.set_title(
        "(a) Linux − recorded original return,\nevery episode (symmetric log scale)",
        loc="left",
        fontsize=FONT,
    )
    ax_b.set_xlim(-0.05, 0.8)
    ax_b.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax_b.set_xticks([0, 0.25, 0.5, 0.75])
    ax_b.set_title("(b) Pad landing\n○ recorded  ▲ Linux", loc="left", fontsize=FONT)
    ax_b.tick_params(axis="y", length=0)
    for ax in (ax_a, ax_b):
        ax.grid(axis="x", color="#DDDDDD", linewidth=0.6)
        ax.set_axisbelow(True)
    fig.subplots_adjust(left=0.265, right=0.98, top=0.83, bottom=0.1)
    save(
        fig, "linux_replay", {"ci_run": 40545198707, "commit": "dea292c", "policies": values}, paths, manifest
    )


def main() -> int:
    manifest: dict = {}
    figure_historical(manifest)
    figure_architecture(manifest)
    figure_workflows(manifest)
    figure_cartpole(manifest)
    figure_linux_replay(manifest)
    import matplotlib as mpl

    manifest["environment"] = {
        "matplotlib": mpl.__version__,
        "numpy": np.__version__,
        "python": sys.version.split()[0],
    }
    (HERE / "MANIFEST.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("figures written:", ", ".join(k for k in manifest if k != "environment"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
