"""Markdown + HTML experiment report generated only from stored data.

Figures (matplotlib, Agg backend):

* training curves: original vs training return per run (rolling mean);
* outcomes: stacked outcome rates per run (evaluation split);
* behaviour: hover fraction and main-engine fraction per run;
* seed variability: one dot per training seed, per reward configuration.

Missing data is reported as missing; nothing is filled in.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from lunarlab.compare import compare_runs, training_curve  # noqa: E402
from lunarlab.storage import atomic_write_text, reports_dir, safe_child, utc_now  # noqa: E402

# Same validated assignments as the web UI (frontend/src/lib/reward.ts). The preset set sits in
# the 6-8 CVD band all-pairs, so every preset also gets its own line style and marker.
PRESET_COLORS = {
    "baseline": "#3987e5",
    "time-penalty": "#c98500",
    "hover-bonus": "#d55181",
    "potential": "#008300",
    "custom": "#8494a8",
}
PRESET_LINESTYLES = {
    "baseline": "-",
    "time-penalty": (0, (6, 3)),
    "hover-bonus": (0, (2, 3)),
    "potential": (0, (10, 4)),
    "custom": (0, (1, 3)),
}
PRESET_MARKERS = {"baseline": "o", "time-penalty": "s", "hover-bonus": "^", "potential": "D", "custom": "x"}
# Stack order validated for adjacent CVD separation: blue, aqua, orange, violet, amber.
OUTCOME_COLORS = {
    "pad": "#3987e5",
    "off_pad": "#199e70",
    "crash": "#d95926",
    "oob": "#9085e9",
    "timeout": "#c98500",
}


def _fmt(v, digits=1, pct=False):
    if v is None:
        return "—"
    if pct:
        return f"{100 * v:.0f}%"
    return f"{v:.{digits}f}"


def _style(ax):
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)


def figure_training_curves(data: dict, out: Path) -> bool:
    runs = data["runs"]
    if not runs:
        return False
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharex=True)
    plotted = False
    for s in runs:
        c = training_curve(s["run_id"])
        if not c["points"]:
            continue
        x = [p["transitions"] for p in c["points"]]
        color = PRESET_COLORS.get(s["reward_preset"], "#888")
        ls = PRESET_LINESTYLES.get(s["reward_preset"], "-")
        axes[0].plot(
            x,
            [p["original_return"] for p in c["points"]],
            color=color,
            ls=ls,
            lw=1.4,
            alpha=0.9,
            label=f"{s['reward_name']} · s{s['seed']}",
        )
        axes[1].plot(x, [p["training_return"] for p in c["points"]], color=color, ls=ls, lw=1.4, alpha=0.9)
        plotted = True
    if not plotted:
        plt.close(fig)
        return False
    axes[0].set_title("Original episode return (training episodes, 100-ep mean)")
    axes[1].set_title("Training (shaped) episode return — scales differ by reward")
    for ax in axes:
        ax.set_xlabel("environment transitions")
        _style(ax)
    axes[0].set_ylabel("return")
    axes[0].legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return True


def figure_outcomes(data: dict, out: Path) -> bool:
    rows = [(d, d["evaluation"]) for d in data["diagnostics"] if d["evaluation"]]
    if not rows:
        return False
    labels = [f"{d['reward_name']}\nseed {d['seed']}" for d, _ in rows]
    parts = {
        "pad": [e["pad_landing_rate"] or 0 for _, e in rows],
        "off_pad": [max((e["env_success_rate"] or 0) - (e["pad_landing_rate"] or 0), 0) for _, e in rows],
        "crash": [e["crash_rate"] or 0 for _, e in rows],
        "oob": [e["out_of_bounds_rate"] or 0 for _, e in rows],
        "timeout": [e["timeout_rate"] or 0 for _, e in rows],
    }
    names = {
        "pad": "strict pad landing",
        "off_pad": "at rest, not strict pad",
        "crash": "crash",
        "oob": "out of bounds",
        "timeout": "time limit",
    }
    fig, ax = plt.subplots(figsize=(max(6, 1.1 * len(rows) + 2), 4))
    bottom = [0.0] * len(rows)
    for k, vals in parts.items():
        ax.bar(
            labels, vals, bottom=bottom, color=OUTCOME_COLORS[k], label=names[k], edgecolor="white", lw=0.5
        )
        bottom = [b + v for b, v in zip(bottom, vals, strict=True)]
    ax.set_ylim(0, 1)
    ax.set_ylabel("fraction of evaluation episodes")
    ax.set_title(f"Outcomes on the {data['split']} seeds (original environment)")
    ax.legend(fontsize=7, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.25))
    plt.xticks(fontsize=7)
    _style(ax)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return True


def figure_behaviour(data: dict, out: Path) -> bool:
    rows = [(d, d["evaluation"]) for d in data["diagnostics"] if d["evaluation"]]
    if not rows:
        return False
    labels = [f"{d['reward_name']}\ns{d['seed']}" for d, _ in rows]
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.8))
    colors = [PRESET_COLORS.get(d["reward_preset"], "#888") for d, _ in rows]
    axes[0].bar(labels, [e["hover_fraction_mean"] or 0 for _, e in rows], color=colors)
    axes[0].set_title("Mean hover fraction (detector, same for all agents)")
    axes[1].bar(labels, [e["main_engine_fraction"] or 0 for _, e in rows], color=colors)
    axes[1].set_title("Main-engine action fraction")
    for ax in axes:
        ax.tick_params(axis="x", labelsize=7)
        _style(ax)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return True


def figure_seed_variability(data: dict, out: Path) -> bool:
    groups = [g for g in data["groups"] if g["n_evaluated_seeds"]]
    if not groups:
        return False
    fig, ax = plt.subplots(figsize=(max(5, 1.6 * len(groups) + 2), 3.8))
    for i, g in enumerate(groups):
        vals = [ps["evaluation"]["mean_original_return"] for ps in g["per_seed"] if ps["evaluation"]]
        ax.scatter(
            [i] * len(vals),
            vals,
            color=PRESET_COLORS.get(g["reward_preset"], "#888"),
            marker=PRESET_MARKERS.get(g["reward_preset"], "o"),
            s=46,
            zorder=3,
            edgecolors="white",
            linewidths=1,
        )
        for ps in g["per_seed"]:
            if ps["evaluation"]:
                ax.annotate(
                    f"s{ps['seed']}",
                    (i, ps["evaluation"]["mean_original_return"]),
                    fontsize=7,
                    xytext=(6, -3),
                    textcoords="offset points",
                )
    ax.axhline(200, color="#999", ls="--", lw=1)
    ax.set_xticks(range(len(groups)), [g["reward_name"] for g in groups], fontsize=8)
    ax.set_ylabel("mean original return per policy")
    ax.set_title("Variability across independently trained policies (one dot per training seed)")
    _style(ax)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return True


def build_report(
    run_ids: list[str], *, title: str, report_id: str, split: str = "test", out_root: Path | None = None
) -> dict[str, Any]:
    out_dir = safe_child(out_root or reports_dir(), report_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = compare_runs(run_ids, split=split)
    figs = {}
    for name, fn in (
        ("training_curves", figure_training_curves),
        ("outcomes", figure_outcomes),
        ("behaviour", figure_behaviour),
        ("seed_variability", figure_seed_variability),
    ):
        path = out_dir / f"{name}.png"
        if fn(data, path):
            figs[name] = path.name
    md = render_markdown(data, title=title, figs=figs)
    atomic_write_text(out_dir / "report.md", md)
    atomic_write_text(out_dir / "portfolio_summary.md", render_portfolio(data))
    atomic_write_text(out_dir / "report.html", render_html(md, title))
    atomic_write_text(out_dir / "data.json", json.dumps(data, indent=1, default=str))
    return {
        "report_id": report_id,
        "dir": str(out_dir),
        "figures": figs,
        "markdown": "report.md",
        "html": "report.html",
        "portfolio": "portfolio_summary.md",
    }


def render_markdown(data: dict, *, title: str, figs: dict[str, str]) -> str:
    L: list[str] = [
        f"# {title}",
        "",
        f"_Generated {utc_now()} from stored LunarLab data. Split: **{data['split']}**._",
        "",
    ]
    comp = data["compatibility"]
    L += ["## Comparability", ""]
    L += (
        ["All selected runs share environment, PPO settings, budget and evaluation protocol."]
        if comp["compatible"]
        else [f"- ⚠ {i}" for i in comp["issues"]]
    )
    L += [
        "",
        "## Configurations",
        "",
        "| Run | Reward | Active terms | Seed | Profile | Planned transitions | Trained (ckpt) | State |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in data["runs"]:
        L.append(
            f"| `{s['run_id']}` | {s['reward_name']} | {', '.join(s['active_terms']) or 'none (original)'} | "
            f"{s['seed']} | {s['profile']} | {s['planned_transitions']:,} | {s['checkpoint_transitions']:,} | {s['state']} |"
        )
    L += [
        "",
        "## Original-reward performance (per training seed)",
        "",
        "Every value is from the original, unmodified environment reward on the same fixed episode seeds. "
        "CI = 95% percentile bootstrap over evaluation episodes of that one policy.",
        "",
        "| Reward | Seed | Episodes | Mean return [CI] | Median | ≥200 | Env success (at rest) | Strict pad landing | Crash | Out of bounds | Time limit |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for g in data["groups"]:
        for ps in g["per_seed"]:
            e = ps["evaluation"]
            if not e:
                L.append(
                    f"| {g['reward_name']} | {ps['seed']} | — | not evaluated on this split | | | | | | | |"
                )
                continue
            ci = e.get("ci")
            ci_s = f" [{ci[0]:.1f}, {ci[1]:.1f}]" if ci else ""
            L.append(
                f"| {g['reward_name']} | {ps['seed']} | {e['n_episodes']} | {_fmt(e['mean_original_return'])}{ci_s} | "
                f"{_fmt(e['median_original_return'])} | {_fmt(e['score_rate'], pct=True)} | {_fmt(e['env_success_rate'], pct=True)} | "
                f"{_fmt(e['pad_landing_rate'], pct=True)} | {_fmt(e['crash_rate'], pct=True)} | {_fmt(e['out_of_bounds_rate'], pct=True)} | "
                f"{_fmt(e['timeout_rate'], pct=True)} |"
            )
    L += [
        "",
        "### Across training seeds (descriptive)",
        "",
        "| Reward | Evaluated seeds | Mean of per-seed means | SD across seeds | Min | Max | Note |",
        "|---|---|---|---|---|---|---|",
    ]
    for g in data["groups"]:
        a = g["across_seeds"]["mean_original_return"]
        L.append(
            f"| {g['reward_name']} | {g['n_evaluated_seeds']} | {_fmt(a['mean'])} | {_fmt(a['std'])} | {_fmt(a['min'])} | {_fmt(a['max'])} | {g['evidence_note']} |"
        )
    if "training_curves" in figs:
        L += [
            "",
            "## Training curves",
            "",
            f"![Training curves]({figs['training_curves']})",
            "",
            "Original and training returns are shown separately; shaped returns of different rewards are on different scales.",
        ]
    if "outcomes" in figs:
        L += ["", "## Outcome rates", "", f"![Outcomes]({figs['outcomes']})"]
    L += [
        "",
        "## Hover and engine diagnostics",
        "",
        "| Run | Reward | Hover fraction | Sustained hover | Mean length | Main-engine fraction | Rescored training return | Flag |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in data["diagnostics"]:
        e = d["evaluation"]
        if e:
            L.append(
                f"| `{d['run_id']}` | {d['reward_name']} | {_fmt(e['hover_fraction_mean'], 2)} | {_fmt(e['sustained_hover_rate'], pct=True)} | "
                f"{_fmt(e['mean_length'], 0)} | {_fmt(e['main_engine_fraction'], 2)} | {_fmt(e['training_return_rescored_mean'])} | {d['flag']} |"
            )
        else:
            L.append(f"| `{d['run_id']}` | {d['reward_name']} | — | — | — | — | — | {d['flag']} |")
    if "behaviour" in figs:
        L += ["", f"![Behaviour]({figs['behaviour']})"]
    if "seed_variability" in figs:
        L += ["", "## Seed variability", "", f"![Seed variability]({figs['seed_variability']})"]
    L += [
        "",
        "## Reward-exploitation assessment",
        "",
        "Flag rule: additional terms pay out on evaluation episodes, AND behavioural evidence (sustained hover, "
        "hover fraction or time-limit rate above thresholds), AND pad landing not better than the baseline. "
        "A shaped-vs-original gap alone is not evidence.",
        "",
    ]
    for d in data["diagnostics"]:
        L.append(f"- **{d['reward_name']} · seed {d['seed']}** — {d['flag']}")
        for r in d.get("reasons", []):
            L.append(f"  - {r}")
    L += [
        "",
        "## Example trajectories",
        "",
        "Recorded flights are listed in the Flight Replay view with their episode seeds. Recordings are of single "
        "episodes; consult the outcome rates above before treating any clip as typical.",
        "",
        "## Limitations",
        "",
        "- Results come from a handful of training seeds; differences between reward designs are descriptive.",
        "- PPO hyperparameters were not tuned per reward; a reward may look worse only because of these settings.",
        "- The hover detector and strict pad-landing rule are documented design choices, not ground truth.",
        "- SMOKE runs are pipeline tests and say nothing about landing performance.",
        "- This is a 2-D simulation benchmark, not evidence of real-world rocket-control capability.",
        "",
    ]
    return "\n".join(L)


NOT_MEASURED = "[not yet measured]"


def render_portfolio(data: dict) -> str:
    """Portfolio summary template. Numbers appear only if real final-test evaluations exist.

    SMOKE runs never count. Each figure states its evidence (number of training seeds,
    episodes, split) so it cannot be quoted without context.
    """
    L = [
        "# LunarLab — portfolio summary",
        "",
        "_Generated from stored evaluations. Values marked " + NOT_MEASURED + " have not been run; "
        "do not replace them by hand._",
        "",
        "## Project",
        "",
        "LunarLab is a local reward-design laboratory for Gymnasium `LunarLander-v3` (discrete actions). It trains "
        "PPO agents (Stable-Baselines3) under different reward designs, evaluates every policy with the unmodified "
        "environment reward on fixed episode seeds, and provides a FastAPI + React mission-control interface for "
        "training, flight replay with synchronized telemetry, reward-hacking diagnostics and reproducible reports.",
        "",
        "## Measured results (final test, original reward)",
        "",
    ]
    rows = []
    for g in data["groups"]:
        evaluated = [ps for ps in g["per_seed"] if ps["evaluation"]]
        run_profiles = {r["profile"] for r in data["runs"] if r["reward_hash"] == g["reward_hash"]}
        if data["split"] != "test" or not evaluated or run_profiles == {"smoke"}:
            rows.append(f"- **{g['reward_name']}**: {NOT_MEASURED}")
            continue
        a = g["across_seeds"]
        n_eps = evaluated[0]["evaluation"]["n_episodes"]
        rows.append(
            f"- **{g['reward_name']}** ({len(evaluated)} training seed(s), {n_eps} test episodes each): mean original "
            f"return {_fmt(a['mean_original_return']['mean'])} (SD across seeds {_fmt(a['mean_original_return']['std'])}); "
            f"strict pad-landing rate {_fmt(a['pad_landing_rate']['mean'], pct=True)}; time-limit rate "
            f"{_fmt(a['timeout_rate']['mean'], pct=True)}; mean hover fraction {_fmt(a['hover_fraction_mean']['mean'], 2)}."
        )
    L += rows
    flags = [d for d in data["diagnostics"] if d["flag"] == "possible reward exploitation"]
    L += ["", "## Reward-hacking finding", ""]
    real_runs = {r["run_id"] for r in data["runs"] if r["profile"] != "smoke"}
    assessed = [
        d
        for d in data["diagnostics"]
        if d["evaluation"] and d["run_id"] in real_runs and d["flag"] != "not applicable"
    ]
    if data["split"] != "test" or not assessed:
        L.append(NOT_MEASURED)
    elif flags:
        L.append(
            "Runs meeting the documented exploitation rule: "
            + ", ".join(f"{d['reward_name']} (seed {d['seed']})" for d in flags)
            + "."
        )
    else:
        L.append(
            "No run met the documented exploitation rule on the final test. State this result as measured; "
            "do not claim that reward hacking occurred."
        )
    L += [
        "",
        "## Engineering highlights",
        "",
        "- Reward terms as pure, tested functions; `training = original + Σ terms` verified on every transition.",
        "- Potential-based shaping with the PPO discount, absorbing terminal potential and correct time-limit handling (telescoping identity tested).",
        "- Evaluation on the original reward with disjoint validation/test seed sets, bootstrap and Wilson intervals, strict pad-landing definition.",
        "- Local job supervisor with cooperative stop at safe boundaries, checkpoint resume with lineage, crash reconciliation and verified process ownership.",
        "- Real-frame flight replay with frame-accurate telemetry; reports generated only from stored data.",
        "",
        "## Limitations to state with any number",
        "",
        "- Few training seeds per reward: differences are descriptive, not statistically established.",
        "- PPO hyperparameters were not tuned per reward design.",
        "- A 2-D simulation benchmark; not evidence of real-world rocket-control capability.",
        "",
    ]
    return "\n".join(L)


def render_html(md: str, title: str) -> str:
    """Minimal Markdown → HTML for this report's own constructs (headings, tables, lists, images)."""
    out: list[str] = []
    in_table = in_list = False
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            if not in_table:
                out.append("<table>")
                in_table = True
                out.append("<tr>" + "".join(f"<th>{_inline(c)}</th>" for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        if line.lstrip().startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            indent = "sub" if line.startswith("  ") else ""
            out.append(f"<li class='{indent}'>{_inline(line.lstrip()[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if line.startswith("!["):
            alt, src = line[2:].split("](", 1)
            out.append(
                f"<figure><img src='{html.escape(src.rstrip(')'))}' alt='{html.escape(alt)}'></figure>"
            )
        elif line.startswith("### "):
            out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line:
            out.append(f"<p>{_inline(line)}</p>")
    if in_table:
        out.append("</table>")
    if in_list:
        out.append("</ul>")
    css = (
        "body{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#1b2430}"
        "table{border-collapse:collapse;margin:1rem 0;font-size:13px}th,td{border:1px solid #d5dbe3;padding:4px 8px;text-align:left}"
        "th{background:#eef2f6}code{font-size:12px}img{max-width:100%}li.sub{margin-left:1.5rem;list-style:circle}"
        "h1,h2,h3{color:#0b3d5c}"
    )
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>{css}</style></head><body>{''.join(out)}</body></html>"


def _inline(s: str) -> str:
    import re

    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"_(.+?)_", r"<em>\1</em>", s) if s.startswith("_") else s
    return s
