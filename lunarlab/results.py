"""Figures and tables for the results write-up (docs/RESULTS.md), generated only from stored data.

    python -m lunarlab results --experiment-ids <main>,<dqn>,<rlhf> --out docs/results

Everything is computed from the final-test evaluations (100 held-out episode seeds per
policy, frozen validation-selected checkpoints, original reward) via ``compare_runs``:
the same numbers the Compare page shows. Nothing is typed in by hand.
"""

from __future__ import annotations

import functools
import json
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from lunarlab.compare import compare_runs, experiment_run_ids, training_curve  # noqa: E402
from lunarlab.report import PRESET_COLORS, PRESET_LINESTYLES, PRESET_MARKERS  # noqa: E402
from lunarlab.robustness import CONDITIONS  # noqa: E402
from lunarlab.storage import atomic_write_text, utc_now  # noqa: E402

LEARNED_COLORS = ["#8a63d2", "#4d4d4d", "#b07aa1"]  # learned-reward groups (custom preset)
ALGO_COLORS = {"ppo": "#3987e5", "dqn": "#d95926"}
# Variants of one reward and algorithm (discount factor, training physics) keep the reward's colour.
VARIANT_LINESTYLES = ["-", (0, (6, 3)), (0, (2, 2)), (0, (8, 3, 2, 3))]
plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold", "figure.dpi": 100})


def _style(ax) -> None:
    ax.grid(alpha=0.25, lw=0.6)
    ax.spines[["top", "right"]].set_visible(False)


def _is_learned(g: dict) -> bool:
    return "learned_reward" in g.get("active_terms", [])


def _group_style(g: dict, groups: list[dict]) -> dict[str, Any]:
    if _is_learned(g):
        learned = [x for x in groups if _is_learned(x)]
        color = LEARNED_COLORS[learned.index(g) % len(LEARNED_COLORS)]
        return {"color": color, "ls": "-", "marker": "P", "hollow": False}
    preset = g["reward_preset"]
    siblings = [
        x
        for x in groups
        if not _is_learned(x) and x["reward_hash"] == g["reward_hash"] and x["algo"] == g["algo"]
    ]
    ls = PRESET_LINESTYLES.get(preset, "-")
    if len(siblings) > 1:
        ls = VARIANT_LINESTYLES[siblings.index(g) % len(VARIANT_LINESTYLES)]
    return {
        "color": PRESET_COLORS.get(preset, "#888"),
        "ls": ls,
        "marker": PRESET_MARKERS.get(preset, "o"),
        "hollow": g.get("algo", "ppo") != "ppo",
    }


def _evaluated(groups: list[dict]) -> list[dict]:
    return [g for g in groups if g["n_evaluated_seeds"]]


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #


def _panels(groups: list[dict]) -> list[tuple[str, list[dict]]]:
    """PPO groups (reward designs and learned rewards) and DQN groups, each in its own panel."""
    ppo = [g for g in groups if g.get("algo", "ppo") == "ppo"]
    dqn = [g for g in groups if g.get("algo", "ppo") == "dqn"]
    return [(t, gs) for t, gs in (("PPO", ppo), ("DQN", dqn)) if gs]


def fig_headline(data: dict, out: Path) -> bool:
    groups = _evaluated(data["groups"])
    rs = data["robust_stats"]["groups"]
    if not groups:
        return False
    fig, ax = plt.subplots(figsize=(8.6, 0.48 * len(groups) + 1.5))
    rng = np.random.default_rng(0)
    labels = []
    for row, g in enumerate(groups):
        y = len(groups) - 1 - row
        st = _group_style(g, groups)
        vals = [ps["evaluation"]["mean_original_return"] for ps in g["per_seed"] if ps["evaluation"]]
        r = rs.get(g["reward_name"], {})
        if r.get("iqm_ci"):
            lo, hi = r["iqm_ci"]
            ax.plot([lo, hi], [y, y], color=st["color"], lw=7, alpha=0.28, solid_capstyle="butt", zorder=1)
        if r.get("iqm") is not None:
            ax.plot([r["iqm"]], [y], marker="|", ms=17, mew=2.6, color=st["color"], zorder=3)
        ax.scatter(
            vals,
            y + rng.uniform(-0.13, 0.13, len(vals)),
            s=26,
            marker=st["marker"],
            zorder=4,
            facecolors="white" if st["hollow"] else st["color"],
            edgecolors=st["color"],
            linewidths=1.2,
        )
        labels.append(f"{g['reward_name']}  (n={len(vals)})")
    ax.set_yticks(range(len(groups)), labels[::-1])
    ax.axvline(200, color="#777", ls="--", lw=1)
    ax.set_ylim(-0.9, len(groups) - 0.5)
    ax.text(203, -0.62, "solved (200)", color="#555", fontsize=8, va="center")
    ax.set_xlabel("mean original return of each trained policy on 100 held-out test episodes")
    ax.set_title("Final test · marker = one trained policy · bar = IQM with 95% bootstrap CI", loc="left")
    _style(ax)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return True


@functools.lru_cache(maxsize=1024)
def _curve_points(run_id: str) -> list[dict]:
    return training_curve(run_id)["points"]


def _mean_curve(
    run_ids: list[str],
    key: str,
    grid: np.ndarray,
    *,
    x_key: str = "transitions",
    require_all: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Mean, min and max over runs of ``key`` interpolated on ``grid`` (x = ``x_key``). With
    ``require_all`` a grid point is drawn only while every run has data there, so a mean is never
    carried by the slowest runs alone."""
    ys = []
    for rid in run_ids:
        pts = [p for p in _curve_points(rid) if p.get(x_key) is not None]
        if len(pts) < 2:
            continue
        x = np.array([p[x_key] for p in pts], float)
        y = np.array([p[key] for p in pts], float)
        yi = np.interp(grid, x, y, left=np.nan, right=np.nan)
        ys.append(yi)
    if not ys:
        return None
    a = np.vstack(ys)
    if require_all:
        return a.mean(axis=0), a.min(axis=0), a.max(axis=0)
    with warnings.catch_warnings():  # grid points outside every run's range stay NaN (not drawn)
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(a, axis=0), np.nanmin(a, axis=0), np.nanmax(a, axis=0)


def fig_curves(data: dict, out: Path) -> bool:
    groups = [g for g in data["groups"] if g["per_seed"]]
    algos = [a for a in ("ppo", "dqn") if any(g.get("algo", "ppo") == a for g in groups)]
    if not algos:
        return False
    fig, axes = plt.subplots(1, len(algos), figsize=(5.6 * len(algos), 3.6), squeeze=False)
    for ax, algo in zip(axes[0], algos, strict=True):
        mine = [g for g in groups if g.get("algo", "ppo") == algo]
        budget = max(ps["checkpoint_transitions"] for g in mine for ps in g["per_seed"])
        grid = np.linspace(0, budget, 200)
        for g in mine:
            st = _group_style(g, groups)
            res = _mean_curve([ps["run_id"] for ps in g["per_seed"]], "original_return", grid)
            if res is None:
                continue
            mean, lo, hi = res
            ax.fill_between(grid, lo, hi, color=st["color"], alpha=0.12, lw=0)
            ax.plot(
                grid,
                mean,
                color=st["color"],
                ls=st["ls"],
                lw=1.8,
                label=f"{g['reward_name']} ({len(g['per_seed'])})",
            )
        ax.axhline(200, color="#777", ls="--", lw=1)
        ax.set_xlabel("environment transitions")
        ax.set_ylabel("original return (rolling mean, 100 episodes)")
        ax.set_title(f"{algo.upper()} learning curves: mean and min–max over seeds", loc="left")
        ax.set_ylim(bottom=max(ax.get_ylim()[0], -600))
        ax.legend(fontsize=7, frameon=False, loc="lower right")
        _style(ax)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return True


def algorithm_rows(data: dict) -> list[list[dict]]:
    """Reward designs trained with more than one algorithm at one shared budget (matched-budget
    comparisons), each as its list of groups (algorithm x discount factor x training physics)."""
    budget = {s["run_id"]: s["planned_transitions"] for s in data["runs"]}
    by_reward: dict[str, list[dict]] = defaultdict(list)
    for g in data["groups"]:
        if g["per_seed"]:
            by_reward[g["reward_hash"]].append(g)
    return [
        gs
        for gs in by_reward.values()
        if len({g["algo"] for g in gs}) > 1
        and len({budget.get(ps["run_id"]) for g in gs for ps in g["per_seed"]}) == 1
    ]


def fig_algorithms(data: dict, out: Path) -> bool:
    """Matched-budget algorithm comparison: learning curves against transitions and wall-clock time."""
    rows = algorithm_rows(data)[:5]
    if not rows:
        return False
    names = {s["run_id"]: s["reward_name"] for s in data["runs"]}
    fig, axes = plt.subplots(len(rows), 2, figsize=(11.2, 3.4 * len(rows)), squeeze=False)
    for (ax_t, ax_w), gs in zip(axes, rows, strict=True):
        ids = [[ps["run_id"] for ps in g["per_seed"]] for g in gs]
        budget = max(ps["checkpoint_transitions"] for g in gs for ps in g["per_seed"])
        t_end = max(
            (
                p["elapsed_s"]
                for rs in ids
                for r in rs
                for p in _curve_points(r)
                if p.get("elapsed_s") is not None
            ),
            default=0.0,
        )
        scale, unit = (3600.0, "hours") if t_end > 2 * 3600 else (60.0, "minutes")
        n_variant: dict[str, int] = defaultdict(int)
        for g, rs in zip(gs, ids, strict=True):
            ls = VARIANT_LINESTYLES[n_variant[g["algo"]] % len(VARIANT_LINESTYLES)]
            n_variant[g["algo"]] += 1
            color = ALGO_COLORS.get(g["algo"], "#888")
            label = g["algo"].upper() + (f" · {g['variant']}" if g["variant"] else "") + f" (n={len(rs)})"
            for ax, x_key, grid, xs in (
                (ax_t, "transitions", np.linspace(0, budget, 200), None),
                (ax_w, "elapsed_s", np.linspace(0, t_end, 200), scale),
            ):
                res = _mean_curve(rs, "original_return", grid, x_key=x_key, require_all=x_key == "elapsed_s")
                if res is None:
                    continue
                x = grid / xs if xs else grid
                ax.fill_between(x, res[1], res[2], color=color, alpha=0.10, lw=0)
                ax.plot(x, res[0], color=color, ls=ls, lw=1.8, label=label)
        reward = names.get(ids[0][0], gs[0]["base_name"])
        ax_t.set_title(f"{reward}: against environment transitions", loc="left")
        ax_w.set_title(f"{reward}: against wall-clock training time", loc="left")
        ax_t.set_xlabel("environment transitions (same budget for every run)")
        ax_w.set_xlabel(f"wall-clock training time ({unit})")
        ax_t.set_ylabel("original return\n(rolling mean, 100 episodes)")
        for ax in (ax_t, ax_w):
            ax.axhline(200, color="#777", ls="--", lw=1)
            ax.set_ylim(bottom=max(ax.get_ylim()[0], -600))
            ax.legend(fontsize=7, frameon=False, loc="lower right")
            _style(ax)
    fig.text(
        0.99,
        0.005,
        "line: mean over training seeds, band: min-max · time curves stop when a group's first seed finished · "
        "wall-clock time depends on the machine and on how many runs trained at once",
        ha="right",
        fontsize=7,
        color="#666",
    )
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return True


def fig_profiles(data: dict, out: Path) -> bool:
    rs = data["robust_stats"]["groups"]
    groups = [g for g in _evaluated(data["groups"]) if g["reward_name"] in rs]
    panels = _panels(groups)
    if not panels:
        return False
    fig, axes = plt.subplots(1, len(panels), figsize=(5.4 * len(panels), 3.7), squeeze=False, sharey=True)
    for ax, (title, gs) in zip(axes[0], panels, strict=True):
        for g in gs:
            st = _group_style(g, groups)
            pr = rs[g["reward_name"]]["profile"]
            tau = np.array(pr["tau"])
            ax.fill_between(tau, pr["lo"], pr["hi"], color=st["color"], alpha=0.1, lw=0)
            ax.plot(tau, pr["fraction"], color=st["color"], ls=st["ls"], lw=1.9, label=g["reward_name"])
        ax.axvline(200, color="#777", ls="--", lw=1)
        ax.set_xlabel("original return threshold τ")
        ax.set_title(f"{title}: performance profiles", loc="left")
        ax.set_ylim(0, 1.02)
        ax.legend(fontsize=7, frameon=False, loc="lower left")
        _style(ax)
    axes[0][0].set_ylabel("fraction of test episodes with return > τ")
    fig.text(0.99, 0.01, "band: 95% bootstrap over policies", ha="right", fontsize=7, color="#666")
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return True


def fig_robustness(data: dict, out: Path) -> bool:
    rows = data["robustness"]["rows"]
    if not rows:
        return False
    conds = ["calm", *CONDITIONS]
    by_name = {g["reward_name"]: g for g in data["groups"]}
    panels = [(t, [r for r in rows if (r.get("algo") or "ppo") == t.lower()]) for t in ("PPO", "DQN")]
    panels = [(t, rs) for t, rs in panels if rs]
    fig, axes = plt.subplots(1, len(panels), figsize=(5.6 * len(panels), 3.8), squeeze=False, sharey=True)
    x = np.arange(len(conds))
    for ax, (title, rs) in zip(axes[0], panels, strict=True):
        for r in rs:
            g = by_name.get(r["reward_name"])
            st = (
                _group_style(g, data["groups"])
                if g
                else {"color": "#888", "ls": "-", "marker": "o", "hollow": False}
            )
            ys = [r["conditions"].get(c, {}).get("mean_original_return", np.nan) for c in conds]
            ax.plot(
                x,
                ys,
                color=st["color"],
                ls=st["ls"],
                marker=st["marker"],
                ms=5,
                lw=1.7,
                mfc="white" if st["hollow"] else st["color"],
                label=r["reward_name"],
            )
            for i, c in enumerate(conds):
                for ps in r["conditions"].get(c, {}).get("per_seed", []):
                    ax.scatter(
                        [i], [ps["mean_original_return"]], s=7, color=st["color"], alpha=0.35, zorder=1
                    )
        ax.axhline(200, color="#777", ls="--", lw=1)
        ax.set_xticks(x, ["calm\n(test)", *[c.replace("-", " ") for c in CONDITIONS]])
        ax.set_title(f"{title}: robustness of frozen policies", loc="left")
        ax.legend(fontsize=7, frameon=False, loc="lower left")
        _style(ax)
    axes[0][0].set_ylabel("mean original return (line: mean over policies)")
    fig.text(
        0.99,
        0.01,
        "dots: individual policies · 50 test seeds per condition",
        ha="right",
        fontsize=7,
        color="#666",
    )
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return True


def fig_learned(data: dict, out: Path) -> bool:
    groups = [g for g in data["groups"] if _is_learned(g) and g["per_seed"]]
    if not groups:
        return False
    fig, axes = plt.subplots(1, len(groups), figsize=(5.2 * len(groups), 3.5), squeeze=False)
    for ax, g in zip(axes[0], groups, strict=True):
        budget = max(ps["checkpoint_transitions"] for ps in g["per_seed"])
        grid = np.linspace(0, budget, 200)
        ids = [ps["run_id"] for ps in g["per_seed"]]
        true_c = _mean_curve(ids, "original_return", grid)
        proxy_c = _mean_curve(ids, "training_return", grid)
        if true_c is None or proxy_c is None:
            continue
        ax.fill_between(grid, true_c[1], true_c[2], color="#3987e5", alpha=0.12, lw=0)
        ax.plot(grid, true_c[0], color="#3987e5", lw=1.9, label="true (environment) return")
        ax.axhline(200, color="#777", ls="--", lw=1)
        ax.set_xlabel("environment transitions")
        ax.set_ylabel("true return", color="#3987e5")
        ax2 = ax.twinx()
        ax2.fill_between(grid, proxy_c[1], proxy_c[2], color="#d95926", alpha=0.10, lw=0)
        ax2.plot(grid, proxy_c[0], color="#d95926", lw=1.6, ls=(0, (6, 3)), label="learned (proxy) return")
        ax2.set_ylabel("learned-reward return (arbitrary units)", color="#d95926")
        ax2.spines[["top"]].set_visible(False)
        ax.set_title(f"{g['reward_name']}: proxy vs true", loc="left")
        lines = ax.get_legend_handles_labels()
        lines2 = ax2.get_legend_handles_labels()
        ax.legend(lines[0] + lines2[0], lines[1] + lines2[1], fontsize=7, frameon=False, loc="lower right")
        _style(ax)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return True


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #


def _f(v, d=1) -> str:
    return "—" if v is None else f"{v:.{d}f}"


def _p(v) -> str:
    return "—" if v is None else f"{100 * v:.0f}%"


def _ci(ci, d=0) -> str:
    return "" if not ci else f" [{ci[0]:.{d}f}, {ci[1]:.{d}f}]"


def tables_markdown(data: dict) -> str:
    rs = data["robust_stats"]
    groups = _evaluated(data["groups"])
    L = [
        f"_Generated {utc_now()} by `python -m lunarlab results` from stored final-test evaluations "
        "(100 held-out episode seeds per policy, frozen validation-selected checkpoints, original reward)._",
        "",
        "### Aggregate per group",
        "",
        f"P(improvement) is against **{rs.get('reference')}**: the probability that a randomly chosen policy of the "
        "group scores higher than a randomly chosen reference policy. Intervals: 95% bootstrap over policies.",
        "",
        "| Group | Policies | IQM [95% CI] | Mean [95% CI] | Pad landing | Env. success | Crash | Time limit | P(improvement) [95% CI] |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for g in groups:
        r = rs["groups"].get(g["reward_name"], {})
        a = g["across_seeds"]
        poi = rs["probability_of_improvement"].get(g["reward_name"])
        poi_s = (
            "reference"
            if g["reward_name"] == rs.get("reference")
            else (f"{poi['p']:.2f}{_ci(poi['ci'], 2)}" if poi and poi["p"] is not None else "—")
        )
        L.append(
            f"| {g['reward_name']} | {r.get('n_runs', 0)} | {_f(r.get('iqm'))}{_ci(r.get('iqm_ci'))} | "
            f"{_f(r.get('mean'))}{_ci(r.get('mean_ci'))} | {_p(a['pad_landing_rate']['mean'])} | "
            f"{_p(a['env_success_rate']['mean'])} | {_p(a['crash_rate']['mean'])} | {_p(a['timeout_rate']['mean'])} | {poi_s} |"
        )
    rows = data["robustness"]["rows"]
    if rows:
        conds = ["calm", *CONDITIONS]
        L += [
            "",
            "### Robustness (mean original return over policies · strict pad-landing rate)",
            "",
            "| Group | " + " | ".join(conds) + " |",
            "|---|" + "---:|" * len(conds),
        ]
        for r in rows:
            cells = []
            for c in conds:
                v = r["conditions"].get(c)
                cells.append(
                    "—" if not v else f"{v['mean_original_return']:.0f} · {_p(v['pad_landing_rate'])}"
                )
            L.append(f"| {r['reward_name']} | " + " | ".join(cells) + " |")
        L += [
            "",
            "Conditions: "
            + "; ".join(f"`{k}` = {v}" for k, v in data["robustness"]["conditions"].items())
            + ".",
        ]
    L += [
        "",
        "### Every policy",
        "",
        "| Group | Seed | Run | Checkpoint (transitions) | Mean [95% CI over episodes] | Pad | Success | Crash | Time limit | Hover fraction |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for g in groups:
        for ps in g["per_seed"]:
            e = ps["evaluation"]
            if not e:
                continue
            ckt = e.get("checkpoint_transitions")
            L.append(
                f"| {g['reward_name']} | {ps['seed']} | `{ps['run_id']}` | {f'{ckt:,}' if ckt is not None else '—'} | "
                f"{e['mean_original_return']:.1f}{_ci(e.get('ci'))} | {_p(e['pad_landing_rate'])} | {_p(e['env_success_rate'])} | "
                f"{_p(e['crash_rate'])} | {_p(e['timeout_rate'])} | {_f(e.get('hover_fraction_mean'), 3)} |"
            )
    L += _ablation_markdown(data.get("gamma_ablation") or [])
    if algorithm_rows(data) and data.get("wall_clock", {}).get("notes"):
        L += [
            "",
            "Wall-clock context (algorithm-comparison figure): " + " ".join(data["wall_clock"]["notes"]),
        ]
    if not data["compatibility"]["compatible"]:
        L += ["", "Comparability notes: " + " ".join(data["compatibility"]["issues"])]
    return "\n".join(L) + "\n"


def _signed(v, d=0) -> str:
    return "—" if v is None else f"{v:+.{d}f}"


def _ablation_markdown(blocks: list[dict]) -> list[str]:
    L: list[str] = []
    for b in blocks:
        L += [
            "",
            f"### Discount-factor ablation: {b['reward_name']} (training physics: {b['physics_label']})",
            "",
            "Mean over training seeds of each policy's final-test mean original return, with a 95% bootstrap "
            "interval over seeds. Differences resample each cell's seeds.",
            "",
            "| Algorithm | γ | Policies | Mean [95% CI] | Pad landing |",
            "|---|---:|---:|---:|---:|",
        ]
        for c in b["cells"]:
            ref = " (reference γ)" if c["reference"] else ""
            L.append(
                f"| {c['algo'].upper()}{ref} | {c['gamma']:g} | {c['n_seeds']} | {_f(c['mean'])}{_ci(c['mean_ci'])} | "
                f"{_p(c['pad_landing_rate'])} |"
            )
        rows = [
            (f"{e['algo'].upper()}: γ {e['gamma']:g} − γ {e['vs_gamma']:g}", e) for e in b["gamma_effects"]
        ]
        rows += [(f"PPO − DQN at γ {e['gamma']:g}", e) for e in b["algorithm_effects"]]
        if b["reference_setups"]:
            r = b["reference_setups"]
            rows.append((f"PPO (γ {r['ppo_gamma']:g}) − DQN (γ {r['dqn_gamma']:g}): both differ", r))
        L += ["", "| Contrast | Difference [95% CI] | P(first higher) [95% CI] |", "|---|---:|---:|"]
        for label, e in rows:
            p = (
                "—"
                if e["p_improvement"] is None
                else f"{e['p_improvement']:.2f}{_ci(e['p_improvement_ci'], 2)}"
            )
            L.append(f"| {label} | {_signed(e['difference'])}{_ci(e['ci'])} | {p} |")
        if b["caveats"]:
            L += ["", "Notes: " + " ".join(b["caveats"])]
    return L


def build_results(experiment_ids: list[str], out_dir: Path, echo=print) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    _curve_points.cache_clear()
    run_ids = [r for e in experiment_ids for r in experiment_run_ids(e)]
    data = compare_runs(run_ids, split="test")
    figs = {}
    for name, fn in (
        ("headline", fig_headline),
        ("learning_curves", fig_curves),
        ("algorithm_comparison", fig_algorithms),
        ("performance_profiles", fig_profiles),
        ("robustness", fig_robustness),
        ("learned_reward", fig_learned),
    ):
        path = out_dir / f"{name}.png"
        if fn(data, path):
            figs[name] = path.name
            echo(f"figure {path}")
    atomic_write_text(out_dir / "tables.md", tables_markdown(data))
    slim = {
        k: data[k]
        for k in (
            "split",
            "compatibility",
            "groups",
            "robust_stats",
            "robustness",
            "gamma_ablation",
            "wall_clock",
        )
    }
    atomic_write_text(
        out_dir / "results.json",
        json.dumps({"experiments": experiment_ids, "generated_at": utc_now(), **slim}, indent=1, default=str),
    )
    echo(f"tables {out_dir / 'tables.md'}")
    return {"figures": figs, "dir": str(out_dir)}


# --------------------------------------------------------------------------- #
# Showcase GIF: several recorded flights of the same episode seed, side by side
# --------------------------------------------------------------------------- #


def make_showcase(
    recording_ids: list[str],
    labels: list[str],
    out: Path,
    *,
    frames_dir: Path | None = None,
    cols: int = 2,
    tile: tuple[int, int] = (360, 240),
    step: int = 3,
    max_steps: int = 750,
    frame_ms: int = 60,
    colors: int = 96,
    quality: int = 70,
) -> dict:
    """Compose several recorded flights side by side into one looping animation.

    The format follows ``out``'s extension: ``.gif`` (palette of ``colors``) or ``.webp`` (lossy,
    ``quality``; far smaller for the shaded 3-D frames).

    Frames come from the real simulator footage (each recording's MP4; every ``step``-th frame is kept,
    50 fps → ~16.7 fps), or, with ``frames_dir``, from the 3-D reconstruction captured by
    ``frontend/tools/capture3d.mjs`` (``<frames_dir>/<recording id>/*.jpg`` + ``meta.json``). When a
    flight's episode ends, its tile shows the outcome and the episode's original return.
    """
    import imageio.v2 as imageio
    from PIL import Image, ImageDraw, ImageFont

    from lunarlab.recording import find_recording
    from lunarlab.storage import read_json

    font = ImageFont.load_default(size=15)
    small = ImageFont.load_default(size=13)
    names = {"at_rest": "at rest", "timeout": "time limit", "out_of_bounds": "out of bounds"}
    clips, ends, endings = [], [], []
    for rid in recording_ids:
        tpath, vdir = find_recording(rid)
        tele = read_json(tpath)
        fps = float(tele["fps"])
        ep = tele["episode"]
        frames = []
        if frames_dir is not None:
            meta = read_json(frames_dir / rid / "meta.json")
            for f in sorted((frames_dir / rid).glob("*.jpg")):
                frames.append(Image.open(f).convert("RGB").resize(tile, Image.Resampling.LANCZOS))
            end = meta["episode_end_frame"] if meta.get("episode_end_frame") is not None else len(frames) - 1
            clip_s = (meta["frames"] - 1) * float(meta["dt"])
            cut = meta.get("episode_end_frame") is None
        else:
            reader = imageio.get_reader(str(vdir / tele["video"]["file"]))
            try:
                for i, fr in enumerate(reader):
                    if i > max_steps:
                        break
                    if i % step == 0:
                        frames.append(Image.fromarray(fr).resize(tile, Image.Resampling.LANCZOS))
            finally:
                reader.close()
            end = len(frames) - 1
            clip_s = max_steps / fps
            cut = ep["length"] > max_steps
        outcome = (
            "pad landing"
            if ep.get("pad_landing")
            else names.get(ep.get("env_outcome"), str(ep.get("env_outcome")))
        )
        ending = f"{outcome} · return {ep['original_return']:.0f}"
        if cut:  # the clip stops before the episode does; say how the full episode ended
            ending = f"{outcome} at {ep['length'] / fps:.0f} s · return {ep['original_return']:.0f} · clip: {clip_s:.0f} s"
        clips.append(frames)
        ends.append(end)
        endings.append(ending)
    n = max(len(c) for c in clips)
    rows = (len(clips) + cols - 1) // cols
    W, H = cols * tile[0], rows * tile[1]
    out_frames = []
    for k in range(n):
        canvas = Image.new("RGB", (W, H), (0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        for j, (clip, end, label, ending) in enumerate(zip(clips, ends, labels, endings, strict=True)):
            x0, y0 = (j % cols) * tile[0], (j // cols) * tile[1]
            canvas.paste(clip[min(k, len(clip) - 1)], (x0, y0))
            draw.rectangle([x0, y0, x0 + tile[0], y0 + 24], fill=(8, 12, 18))
            draw.text((x0 + 8, y0 + 4), label, fill=(230, 237, 244), font=font)
            if k >= end:
                draw.rectangle([x0, y0 + tile[1] - 24, x0 + tile[0], y0 + tile[1]], fill=(8, 12, 18))
                draw.text((x0 + 8, y0 + tile[1] - 20), ending, fill=(245, 181, 68), font=small)
            draw.rectangle([x0, y0, x0 + tile[0] - 1, y0 + tile[1] - 1], outline=(40, 52, 68))
        out_frames.append(canvas)
    durations = [frame_ms] * len(out_frames)
    durations[-1] = 2500  # hold the final frame
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".webp":
        out_frames[0].save(
            out,
            format="WEBP",
            save_all=True,
            append_images=out_frames[1:],
            duration=durations,
            loop=0,
            quality=quality,
            method=6,
        )
    else:
        pal = [
            f.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
            for f in out_frames
        ]
        pal[0].save(
            out, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True, disposal=1
        )
    return {"file": str(out), "frames": len(out_frames), "bytes": out.stat().st_size, "endings": endings}
