# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Draw manuscript Figure 1 from docs/results/results.json; never changes source data.

    python paper/jmlr-mloss/build_audit_figure.py

Two stacked, full-width panels for the four primary PPO reward designs: (a) each policy's mean original return
with the group interquartile mean (IQM) and its stored 95% training-run bootstrap interval, (b) each policy's
strict pad-landing rate with the group mean. Horizontal positions are the stored values exactly (rates are
plotted on their stored 0-1 scale with percent tick labels). A policy is lifted into a higher lane only where
its marker would otherwise touch another one in the same row (deterministic first fit, in order of value, then
seed); the group summary has its own lane below the policies. Before saving, the script checks the plotted
values against the input, marker separation, text sizes and the canvas bounds. Writes
figures/final_test_audit.{pdf,svg,png} and final_test_audit.source.json (input digest, plotted values, lanes
and layout). The figure is drawn at the JMLR text width so that its text prints at the stated sizes.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.markers import MarkerStyle
from matplotlib.ticker import FixedLocator, PercentFormatter

# Embed real TrueType subsets in the PDF (not Type 3) and keep SVG text as outlines.
plt.rcParams.update(
    {"pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "path", "font.family": "DejaVu Sans"}
)
HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / "docs" / "results" / "results.json"
OUT = HERE / "figures"
DESIGNS = [  # results.json group name, row label, colour
    ("Original baseline", "Original reward", "#246085"),
    ("Time-penalty ablation", "Time penalty", "#497f77"),
    ("Potential-based shaping", "Potential shaping", "#7570a4"),
    ("Flawed hover bonus", "Hover bonus", "#b33f32"),
]
PANELS = [
    {
        "key": "return",
        "title": "(a) Original environment return",
        "xlim": (-75.0, 295.0),
        "ticks": [-50, 0, 50, 100, 150, 200, 250],
        "percent": False,
        # Legend: left edge in data units, centred on these rows (all their data lie right of 228).
        "legend_x": -68.0,
        "legend_rows": [0, 1, 2],
        "summary_label": "IQM, 95% bootstrap CI",
    },
    {
        "key": "landing",
        "title": "(b) Strict pad-landing rate",
        "xlim": (-0.04, 1.04),
        "ticks": [0.0, 0.25, 0.5, 0.75, 1.0],
        "percent": True,
        "legend_x": 0.1,  # empty between 0% and 75% in every row
        "legend_rows": [0, 1, 2, 3],
        "summary_label": "Mean landing rate",
    },
]
WIDTH_PT = 6.0 * 72  # JMLR text width; included at natural size
FONT_PT = 10.0  # smallest text in the figure
TITLE_PT = 10.5
DOT_PT = 4.4  # policy marker diameter
LANE_PT = 5.2  # lane pitch, and the smallest centre distance between two policies in one lane
DIAMOND_MS = 5.0  # summary marker size (a "D" of this size spans about 7.1 pt corner to corner)
CAP_PT = 2.5  # half-height of interval caps
ROW_GAP_PT = 7.0  # free space between neighbouring rows
EDGE_PAD_PT = 2.0  # free space above the top row and below the bottom row
TOP_PT, TITLE_BAND_PT, TICK_BAND_PT, PANEL_GAP_PT, BOTTOM_PT = 0.5, 15.0, 15.0, 8.0, 0.5
INK, GRID, RULE = "#1f1f1f", "#e3e3e3", "#d0d0d0"


def half_extent(marker: str, size: float) -> float:
    """Half the width/height, in points, of a matplotlib marker drawn at ``size``."""
    m = MarkerStyle(marker)
    e = m.get_path().transformed(m.get_transform()).get_extents()
    return size * max(abs(e.x0), abs(e.x1), abs(e.y0), abs(e.y1))


DOT_R = half_extent("o", DOT_PT)
DIAMOND_R = half_extent("D", DIAMOND_MS)
FIRST_LANE_PT = max(DIAMOND_R, CAP_PT) + 1.4 + DOT_R  # summary lane to first policy lane


def load() -> tuple[bytes, list[dict]]:
    raw = SOURCE.read_bytes()
    d = json.loads(raw)
    rows = []
    for group, label, color in DESIGNS:
        stats = d["robust_stats"]["groups"][group]
        records = next(x for x in d["groups"] if x["reward_name"] == group)["per_seed"]
        returns = [r["evaluation"]["mean_original_return"] for r in records]
        if returns != stats["run_scores"]:
            raise SystemExit(f"{group}: per-policy returns disagree with robust_stats.run_scores")
        rows.append(
            {
                "group": group,
                "label": label,
                "color": color,
                "seeds": [r["seed"] for r in records],
                "run_ids": [r["run_id"] for r in records],
                "return": returns,
                "landing": [r["evaluation"]["pad_landing_rate"] for r in records],
                "iqm": stats["iqm"],
                "iqm_ci": list(stats["iqm_ci"]),
                "landing_mean": stats["pad_rate_mean"],
            }
        )
    return raw, rows


def assign_lanes(values: list[float], pt_per_unit: float) -> list[int]:
    """Lowest lane (1, 2, ...) in which a marker keeps LANE_PT from every marker already placed there."""
    placed: dict[int, list[float]] = {}
    lanes = [0] * len(values)
    for i in sorted(range(len(values)), key=lambda i: (values[i], i)):
        x, lane = values[i] * pt_per_unit, 1
        while any(abs(x - other) < LANE_PT for other in placed.get(lane, [])):
            lane += 1
        placed.setdefault(lane, []).append(x)
        lanes[i] = lane
    return lanes


def text_width_pt(text: str, size: float) -> float:
    fig = plt.figure()
    t = fig.text(0, 0, text, fontsize=size)
    w = t.get_window_extent(fig.canvas.get_renderer()).width * 72 / fig.dpi
    plt.close(fig)
    return w


def overlaps(a, b) -> bool:
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


def build() -> dict:
    raw, rows = load()
    left = max(text_width_pt(r["label"], FONT_PT) for r in rows) + 4.0 + 2.0  # labels, tick pad, margin
    right = 4.0
    axis_w = WIDTH_PT - left - right
    layout = []
    for panel in PANELS:
        lo, hi = panel["xlim"]
        lanes = [assign_lanes(r[panel["key"]], axis_w / (hi - lo)) for r in rows]
        heights = [FIRST_LANE_PT + (max(ln) - 1) * LANE_PT + DOT_R + max(DIAMOND_R, CAP_PT) for ln in lanes]
        layout.append(
            {
                "lanes": lanes,
                "row_heights": heights,
                "height": sum(heights) + ROW_GAP_PT * (len(rows) - 1) + 2 * EDGE_PAD_PT,
            }
        )
    height_pt = (
        TOP_PT + BOTTOM_PT + PANEL_GAP_PT + sum(TITLE_BAND_PT + TICK_BAND_PT + p["height"] for p in layout)
    )

    fig = plt.figure(figsize=(WIDTH_PT / 72, height_pt / 72))
    top = height_pt - TOP_PT
    axes = []
    for panel, lay in zip(PANELS, layout, strict=True):
        top -= TITLE_BAND_PT
        bottom = top - lay["height"]
        ax = fig.add_axes((left / WIDTH_PT, bottom / height_pt, axis_w / WIDTH_PT, lay["height"] / height_pt))
        ax.set_xlim(*panel["xlim"])
        ax.set_ylim(0, lay["height"])  # one y unit is one point
        top = bottom - TICK_BAND_PT - PANEL_GAP_PT
        lay["axes"], lay["centres"], lay["summary_y"], lay["policy_y"] = ax, [], [], []
        y = lay["height"] - EDGE_PAD_PT
        for i, (row, lanes, h) in enumerate(zip(rows, lay["lanes"], lay["row_heights"], strict=True)):
            summary_y = y - h + max(DIAMOND_R, CAP_PT)
            policy_y = [summary_y + FIRST_LANE_PT + (k - 1) * LANE_PT for k in lanes]
            values = row[panel["key"]]
            ax.plot(
                values,
                policy_y,
                ls="none",
                marker="o",
                ms=DOT_PT,
                mfc=row["color"],
                mec="white",
                mew=0.6,
                zorder=3,
                clip_on=False,
                gid=f"{panel['key']}-policies-{i}",
            )
            if panel["key"] == "return":
                # The interval is drawn from its stored endpoints (errorbar would recompute them as IQM +/- a
                # difference, which can move them in the last floating-point digit).
                m, (ci_lo, ci_hi) = row["iqm"], row["iqm_ci"]
                ink = {"color": INK, "lw": 1.1, "solid_capstyle": "butt", "zorder": 4}
                ax.plot([ci_lo, ci_hi], [summary_y, summary_y], gid=f"return-ci-{i}", **ink)
                for end in (ci_lo, ci_hi):
                    ax.plot([end, end], [summary_y - CAP_PT, summary_y + CAP_PT], **ink)
                ax.plot(
                    [m],
                    [summary_y],
                    ls="none",
                    marker="D",
                    ms=DIAMOND_MS,
                    mfc=row["color"],
                    mec=INK,
                    mew=0.8,
                    zorder=5,
                    gid=f"return-iqm-{i}",
                )
            else:
                ax.plot(
                    [row["landing_mean"]],
                    [summary_y],
                    ls="none",
                    marker="D",
                    ms=DIAMOND_MS,
                    mfc=row["color"],
                    mec=INK,
                    mew=0.8,
                    zorder=4,
                    gid=f"landing-mean-{i}",
                )
            lay["centres"].append((y - h + y) / 2)
            lay["summary_y"].append(summary_y)
            lay["policy_y"].append(policy_y)
            if i < len(rows) - 1:
                ax.axhline(y - h - ROW_GAP_PT / 2, color=RULE, lw=0.6, zorder=0)
            y -= h + ROW_GAP_PT
        ax.set_yticks(lay["centres"], [r["label"] for r in rows], fontsize=FONT_PT)
        ax.xaxis.set_major_locator(FixedLocator(panel["ticks"]))
        if panel["percent"]:
            ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
        ax.tick_params(axis="x", labelsize=FONT_PT, length=3, width=0.8, color="#555555", pad=2.5)
        ax.tick_params(axis="y", length=0, pad=4)
        for x in panel["ticks"]:
            ax.axvline(x, color=GRID, lw=0.6, zorder=0)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color("#555555")
        ax.spines["bottom"].set_linewidth(0.8)
        ax.set_title(panel["title"], loc="left", fontsize=TITLE_PT, pad=5, color=INK)
        handles = [
            Line2D([], [], ls="none", marker="o", ms=DOT_PT, mfc="#8a8a8a", mec="white", mew=0.6),
            Line2D([], [], color=INK, lw=1.1, marker="D", ms=DIAMOND_MS, mfc="#8a8a8a", mec=INK, mew=0.8)
            if panel["key"] == "return"
            else Line2D([], [], ls="none", marker="D", ms=DIAMOND_MS, mfc="#8a8a8a", mec=INK, mew=0.8),
        ]
        lx = (panel["legend_x"] - panel["xlim"][0]) / (panel["xlim"][1] - panel["xlim"][0])
        ly = sum(lay["centres"][i] for i in panel["legend_rows"]) / len(panel["legend_rows"]) / lay["height"]
        lay["legend"] = ax.legend(
            handles,
            ["Policy (one training seed)", panel["summary_label"]],
            loc="center left",
            bbox_to_anchor=(lx, ly),
            fontsize=FONT_PT,
            frameon=True,
            framealpha=1.0,
            edgecolor=RULE,
            fancybox=False,
            borderpad=0.45,
            labelspacing=0.4,
            handlelength=1.8,
            handletextpad=0.6,
            borderaxespad=0.0,
        )
        axes.append(ax)

    checks = verify(fig, rows, layout)
    geometry = {
        panel["key"]: {
            "axes_pt": [round(v * 72 / fig.dpi, 6) for v in lay["axes"].get_window_extent().extents],
            "xlim": list(panel["xlim"]),
        }
        for panel, lay in zip(PANELS, layout, strict=True)
    }
    OUT.mkdir(exist_ok=True)
    plt.rcParams["svg.hashsalt"] = "lunarlab-figure-1"
    fig.savefig(
        OUT / "final_test_audit.pdf", metadata={"Title": "LunarLab final-test audit", "CreationDate": None}
    )
    fig.savefig(OUT / "final_test_audit.svg", metadata={"Title": "LunarLab final-test audit", "Date": None})
    fig.savefig(OUT / "final_test_audit.png", dpi=300)
    plt.close(fig)
    manifest = {
        "source": "docs/results/results.json",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "groups": [r["group"] for r in rows],
        "layout": {
            "width_in": WIDTH_PT / 72,
            "height_in": round(height_pt / 72, 4),
            "panels": "two stacked full-width panels: (a) original return, (b) strict pad-landing rate",
            "min_font_pt": FONT_PT,
            "policy_marker_diameter_pt": DOT_PT,
            "lane_pitch_pt": LANE_PT,
            "lanes": "first fit by value then seed; vertical offsets only, horizontal positions exact",
            "revision": "2026-10-21 stacked redesign",
        },
        "plotted": [
            {
                "group": r["group"],
                "policies": [
                    {
                        "seed": s,
                        "run_id": rid,
                        "mean_original_return": ret,
                        "pad_landing_rate": rate,
                        "lane_a": la,
                        "lane_b": lb,
                    }
                    for s, rid, ret, rate, la, lb in zip(
                        r["seeds"],
                        r["run_ids"],
                        r["return"],
                        r["landing"],
                        layout[0]["lanes"][i],
                        layout[1]["lanes"][i],
                        strict=True,
                    )
                ],
                "iqm": r["iqm"],
                "iqm_ci": r["iqm_ci"],
                "pad_landing_rate_mean": r["landing_mean"],
            }
            for i, r in enumerate(rows)
        ],
        "checks": checks,
        "axes_geometry": geometry,
        "description": "Circles are per-policy mean original returns (a) and strict pad-landing rates (b) at "
        "their stored values; diamonds are the stored group IQM (a, with the stored 95% training-run bootstrap "
        "interval) and mean landing rate (b). No raw episode reconstruction, smoothing or new data.",
    }
    (OUT / "final_test_audit.source.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


def verify(fig, rows: list[dict], layout: list[dict]) -> dict:
    """Fail unless the drawing shows exactly the input values, legibly and inside the canvas."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    px = fig.dpi / 72  # pixels per point
    canvas = fig.bbox
    problems = []
    texts = [t for t in fig.findobj(plt.Text) if t.get_visible() and t.get_text().strip()]
    for t in texts:
        if t.get_fontsize() < FONT_PT:
            problems.append(f"text below {FONT_PT} pt: {t.get_text()!r}")
        e = t.get_window_extent(renderer)
        if e.x0 < canvas.x0 or e.y0 < canvas.y0 or e.x1 > canvas.x1 or e.y1 > canvas.y1:
            problems.append(f"text outside the canvas: {t.get_text()!r}")
    # A legend's own entries lie inside its frame; everything else must be disjoint.
    owner = {id(t): i for i, lay in enumerate(layout) for t in lay["legend"].get_texts()}
    boxes = [(t.get_text(), owner.get(id(t)), t.get_window_extent(renderer)) for t in texts]
    boxes += [(f"legend {i}", i, lay["legend"].get_window_extent(renderer)) for i, lay in enumerate(layout)]
    for (na, ga, a), (nb, gb, b) in itertools.combinations(boxes, 2):
        if overlaps(a, b) and not (ga is not None and ga == gb):
            problems.append(f"overlapping text: {na!r} / {nb!r}")
    for panel, lay in zip(PANELS, layout, strict=True):
        ax = lay["axes"]
        frame = ax.get_window_extent(renderer)
        legend = lay["legend"].get_window_extent(renderer)
        for i, row in enumerate(rows):
            values = row[panel["key"]]
            line = next(a for a in ax.get_lines() if a.get_gid() == f"{panel['key']}-policies-{i}")
            if list(line.get_xdata()) != values:
                problems.append(f"{panel['key']} {row['group']}: plotted x differs from the input")
            pts = ax.transData.transform(list(zip(values, lay["policy_y"][i], strict=True)))
            for (xa, ya), (xb, yb) in itertools.combinations(pts, 2):
                if ((xa - xb) ** 2 + (ya - yb) ** 2) ** 0.5 < DOT_PT * px - 1e-6:
                    problems.append(f"{panel['key']} {row['group']}: two policy markers touch")
            for x, y in pts:
                r = DOT_R * px
                if x - r < frame.x0 - 1e-6 or x + r > frame.x1 + 1e-6 or y - r < frame.y0 or y + r > frame.y1:
                    problems.append(f"{panel['key']} {row['group']}: a policy marker leaves the axes")
                if legend.x0 - r < x < legend.x1 + r and legend.y0 - r < y < legend.y1 + r:
                    problems.append(f"{panel['key']} {row['group']}: a policy marker meets the legend")
            gap = min(lay["policy_y"][i]) - lay["summary_y"][i] - DOT_R - max(DIAMOND_R, CAP_PT)
            if gap < 1.0:
                problems.append(f"{panel['key']} {row['group']}: policies too close to the summary lane")
            lines = {a.get_gid(): a for a in ax.get_lines() if a.get_gid()}
            if panel["key"] == "return":
                if list(lines[f"return-iqm-{i}"].get_xdata()) != [row["iqm"]]:
                    problems.append(f"return {row['group']}: plotted IQM differs from the input")
                if list(lines[f"return-ci-{i}"].get_xdata()) != row["iqm_ci"]:
                    problems.append(f"return {row['group']}: plotted interval differs from the input")
                xs = [min(row["iqm_ci"][0], row["iqm"]), max(row["iqm_ci"][1], row["iqm"])]
            else:
                if list(lines[f"landing-mean-{i}"].get_xdata()) != [row["landing_mean"]]:
                    problems.append(f"landing {row['group']}: plotted mean differs from the input")
                xs = [row["landing_mean"], row["landing_mean"]]
            # The summary lane's whole horizontal extent (interval and diamond) must stay clear of the legend.
            (x0, y0), (x1, _) = ax.transData.transform(
                [(xs[0], lay["summary_y"][i]), (xs[1], lay["summary_y"][i])]
            )
            r = max(DIAMOND_R, CAP_PT) * px
            if legend.x0 - r < x1 and x0 < legend.x1 + r and legend.y0 - r < y0 < legend.y1 + r:
                problems.append(f"{panel['key']} {row['group']}: a summary mark meets the legend")
    tight = fig.get_tightbbox(renderer)
    w, h = fig.get_figwidth(), fig.get_figheight()
    if tight.x0 < -1e-6 or tight.y0 < -1e-6 or tight.x1 > w + 1e-6 or tight.y1 > h + 1e-6:
        problems.append(f"artists extend beyond the canvas: {tight}")
    if problems:
        raise SystemExit("figure checks failed:\n  " + "\n  ".join(problems))
    return {
        "plotted_values_equal_input": True,
        "policy_markers_disjoint": True,
        "summary_lane_separate": True,
        "legends_clear_of_data": True,
        "all_text_at_least_pt": FONT_PT,
        "all_artists_inside_canvas": True,
        "texts_checked": len(texts),
    }


if __name__ == "__main__":
    m = build()
    lanes = {p["group"]: [(q["lane_a"], q["lane_b"]) for q in p["policies"]] for p in m["plotted"]}
    print(
        f"wrote figures/final_test_audit.{{pdf,svg,png}}: {m['layout']['width_in']} x {m['layout']['height_in']} in"
    )
    print(f"lanes (a, b) by seed: {lanes}")
