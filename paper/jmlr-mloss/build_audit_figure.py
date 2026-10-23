# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Draw the manuscript figure from committed per-policy summaries; never changes source data."""

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / "docs/results/results.json"
d = json.loads(SOURCE.read_text(encoding="utf-8"))
names = ["Original baseline", "Time-penalty ablation", "Potential-based shaping", "Flawed hover bonus"]
labels = ["Original reward", "Time penalty", "Potential shaping", "Hover bonus"]
colors = ["#246085", "#497f77", "#7570a4", "#b33f32"]
plt.rcParams.update(
    {
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "font.family": "DejaVu Sans",
    }
)
fig, axes = plt.subplots(1, 2, figsize=(6, 2.0), gridspec_kw={"width_ratios": [1.3, 1]})
for i, (name, c) in enumerate(zip(names, colors, strict=True)):
    g = d["robust_stats"]["groups"][name]
    records = next(x for x in d["groups"] if x["reward_name"] == name)["per_seed"]
    y = 3 - i
    axes[0].scatter(g["run_scores"], y + np.linspace(-0.13, 0.13, 5), s=14, color=c, alpha=0.55, zorder=3)
    lo, hi = g["iqm_ci"]
    m = g["iqm"]
    axes[0].errorbar(m, y, xerr=[[m - lo], [hi - m]], fmt="D", color=c, capsize=3, ms=4, lw=1.6, zorder=4)
    rates = [r["evaluation"]["pad_landing_rate"] * 100 for r in records]
    axes[1].scatter(rates, y + np.linspace(-0.13, 0.13, 5), s=14, color=c, alpha=0.55, zorder=3)
    axes[1].scatter([g["pad_rate_mean"] * 100], [y], marker="D", s=22, color=c, zorder=4)
for ax in axes:
    ax.set_ylim(-0.5, 3.6)
    ax.set_yticks(range(4))
    ax.set_axisbelow(True)
    ax.grid(axis="x", alpha=0.2)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
axes[0].set_yticklabels(labels[::-1])
axes[1].set_yticklabels([])
axes[0].set_xlim(-85, 310)
axes[0].set_xticks([-50, 50, 150, 250])
axes[0].set_xlabel("Original return")
axes[0].set_title("(a) Per-policy mean and IQM", loc="left")
axes[1].set_xlim(-4, 104)
axes[1].set_xticks([0, 25, 50, 75, 100])
axes[1].set_xlabel("Strict pad landing (%)")
axes[1].set_title("(b) Per-policy rate, mean", loc="left")  # "rate and mean" overran the figure edge
fig.subplots_adjust(left=0.22, right=0.98, bottom=0.25, top=0.86, wspace=0.17)
(HERE / "figures").mkdir(exist_ok=True)
fig.savefig(
    HERE / "figures/final_test_audit.pdf",
    metadata={"Title": "LunarLab final-test audit", "CreationDate": None},
)
fig.savefig(HERE / "figures/final_test_audit.png", dpi=220)
(HERE / "figures/final_test_audit.source.json").write_text(
    json.dumps(
        {
            "source": "docs/results/results.json",
            "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "groups": names,
            "description": "Dots are per-policy means/rates; diamonds are IQM/mean; horizontal bars are stored 95% run-bootstrap IQM intervals. No raw episode reconstruction.",
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
    newline="\n",
)
