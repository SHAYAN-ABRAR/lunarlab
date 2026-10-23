# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Command-line interface: ``python -m lunarlab <command>``.

Every command calls the same core functions as the web application.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lunarlab.config import PROFILES, PPOConfig, actual_budget, training_for_profile
from lunarlab.rewards.config import PRESET_NAMES, RewardConfig, preset


def _ints(s: str) -> list[int]:
    return [int(x) for x in s.split(",") if x.strip()]


def _strs(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def _confirm(msg: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print(f"{msg}\nRefusing without --yes in a non-interactive shell.")
        return False
    return input(f"{msg} [y/N] ").strip().lower() in ("y", "yes")


def _load_reward(args) -> RewardConfig:
    if getattr(args, "reward_config", None):
        from lunarlab.storage import read_yaml

        path = Path(args.reward_config)
        data = (
            read_yaml(path)
            if path.suffix in (".yaml", ".yml")
            else json.loads(path.read_text(encoding="utf-8"))
        )
        return RewardConfig.model_validate(data)
    return preset(args.preset)


def _fmt(v, nd=1, pct=False):
    if v is None:
        return "—"
    return f"{100 * v:.0f}%" if pct else f"{v:.{nd}f}"


class _VersionAction(argparse.Action):
    """``--version``: computed only when asked (it reads the git revision), then exits."""

    def __init__(self, option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, help=None):
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        from lunarlab.sysinfo import version_line

        print(version_line())
        parser.exit()


def cmd_version(args) -> int:
    from lunarlab.sysinfo import version_info, version_line

    info = version_info()
    print(json.dumps(info, indent=2) if args.json else version_line(info))
    return 0


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def cmd_doctor(args) -> int:
    from lunarlab.doctor import print_report, run_doctor

    return print_report(run_doctor())


def cmd_demo(args) -> int:
    from lunarlab.recording import record_demo

    kind = "random" if args.command == "random-demo" else "heuristic"
    print(f"Recording one {kind.upper()} episode (episode seed {args.episode_seed}) ...", flush=True)
    meta = record_demo(kind, episode_seed=args.episode_seed, action_seed=getattr(args, "action_seed", 0))
    _print_recording(meta)
    return 0


def _print_recording(meta: dict) -> None:
    from lunarlab.recording import find_recording

    tpath, vdir = find_recording(meta["recording_id"])
    print(f"  policy        {meta['policy']['label']}")
    print(f"  outcome       {meta['env_outcome']}  (strict pad landing: {meta['pad_landing']})")
    print(f"  return        original {meta['original_return']:.1f} over {meta['length']} steps")
    print(
        f"  video         {vdir / meta['video']['file']}  [{meta['video']['format']}, {meta['video']['frames']} frames, verified={meta['video']['verified']}]"
    )
    print(f"  telemetry     {tpath}")


def _floats_pair(text: str, name: str) -> tuple[float, float]:
    parts = [float(x) for x in text.split(",")]
    if len(parts) != 2:
        raise SystemExit(f"--{name} needs two numbers, low,high (for negative values: --{name}=-11,-9)")
    return parts[0], parts[1]


def _physics_config(args):
    """Training-physics ranges from the command line (defaults: PhysicsRandomization's)."""
    from lunarlab.config import PhysicsRandomization

    fields = {}
    if args.wind_probability is not None:
        fields["wind_probability"] = args.wind_probability
    for flag, key in (
        ("wind_power", "wind_power"),
        ("turbulence", "turbulence_power"),
        ("gravity", "gravity"),
    ):
        if getattr(args, flag):
            fields[key] = _floats_pair(getattr(args, flag), flag.replace("_", "-"))
    try:
        return PhysicsRandomization(enabled=True, **fields)
    except ValueError as exc:
        raise SystemExit(f"invalid physics ranges: {exc}") from exc


def _add_physics_args(parser, *, choices: list[str]) -> None:
    parser.add_argument(
        "--physics",
        choices=choices,
        default="fixed",
        help="training physics: fixed (default) or randomized wind/turbulence/gravity per episode",
    )
    parser.add_argument("--wind-probability", type=float, help="share of training episodes with wind (0-1)")
    parser.add_argument("--wind-power", help="uniform range low,high (0-20)")
    parser.add_argument("--turbulence", help="uniform range low,high (0-2)")
    parser.add_argument("--gravity", help="uniform range low,high in (-12, 0), e.g. --gravity=-11,-9")


def cmd_train(args) -> int:
    from lunarlab.runs import create_run
    from lunarlab.training import train

    reward = _load_reward(args)
    training = training_for_profile(
        args.profile,
        total_transitions=args.total_transitions,
        vec_env=args.vec_env,
        device=args.device,
        torch_threads=args.threads,
    )
    from lunarlab.config import DQNConfig, PhysicsRandomization

    gamma = {"gamma": args.gamma} if args.gamma is not None else {}
    ppo = PPOConfig(
        **({"n_envs": args.n_envs} if args.n_envs else {}), **(gamma if args.algo == "ppo" else {})
    )
    dqn = DQNConfig(**gamma) if args.algo == "dqn" else None
    physics = _physics_config(args) if args.physics == "randomized" else PhysicsRandomization()
    planned = actual_budget(training.total_transitions, dqn.rollout_size if dqn else ppo.rollout_size)
    print(PROFILES.get(args.profile, {}).get("label", args.profile))
    print(f"Training physics: {physics.describe()}")
    print(
        f"Reward: {reward.name} [{reward.content_hash()}]  terms: {', '.join(reward.active_terms()) or 'none'}"
    )
    print(
        f"Budget: requested {training.total_transitions:,} transitions → actual {planned:,} "
        f"(whole rollouts of {(dqn or ppo).rollout_size:,})"
    )
    if args.profile == "extended" and not _confirm("EXTENDED runs are long. Start?", args.yes):
        return 1
    cfg = create_run(
        reward=reward,
        training=training,
        seed=args.seed,
        ppo=ppo,
        algo=args.algo,
        dqn=dqn,
        physics=physics,
        label=args.label or "",
        experiment_id=args.experiment_id,
    )
    print(f"Run id: {cfg.run_id}")
    print("Press Ctrl+C once to stop at the next safe boundary (a checkpoint is written).", flush=True)
    return train(cfg.run_id)


def cmd_resume(args) -> int:
    from lunarlab.training import train

    return train(args.run_id, resume=True, checkpoint=args.checkpoint)


def cmd_stop(args) -> int:
    from lunarlab.storage import RunPaths
    from lunarlab.training import request_stop

    paths = RunPaths(args.run_id)
    if not paths.exists():
        print(f"unknown run {args.run_id}")
        return 1
    request_stop(paths, reason="user", source="cli")
    print("Stop requested. The worker stops at its next safe boundary and writes a checkpoint.")
    return 0


def cmd_evaluate(args) -> int:
    from lunarlab.evaluation import evaluate_run, summarize_for_index

    if args.split == "test":
        print(
            "FINAL TEST: the selected checkpoint of this run is frozen at first use; later test evaluations are "
            "flagged as repeats. Do not tune reward or PPO settings on these results."
        )
    res = evaluate_run(
        args.run_id,
        args.split,
        checkpoint=args.checkpoint,
        progress=lambda i, n: print(f"\r  episode {i}/{n}", end="", flush=True),
    )
    print()
    s = summarize_for_index(res)
    ci = s["ci"]
    print(
        f"{args.split} · {res['checkpoint']['name']} ({res['checkpoint']['transitions']:,} transitions) · "
        f"{s['n_episodes']} episodes · deterministic={res['deterministic']}"
    )
    print(
        f"  mean original return  {s['mean_original_return']:.1f}  (sd {s['std_original_return']:.1f}, median "
        f"{s['median_original_return']:.1f}, 95% CI {_fmt(ci[0]) if ci else '—'}..{_fmt(ci[1]) if ci else '—'})"
    )
    print(f"  return >= 200         {_fmt(s['score_rate'], pct=True)}")
    print(f"  env success (at rest) {_fmt(s['env_success_rate'], pct=True)}")
    print(f"  strict pad landing    {_fmt(s['pad_landing_rate'], pct=True)}")
    print(
        f"  crash / OOB / limit   {_fmt(s['crash_rate'], pct=True)} / {_fmt(s['out_of_bounds_rate'], pct=True)} / {_fmt(s['timeout_rate'], pct=True)}"
    )
    print(
        f"  hover fraction        {_fmt(s['hover_fraction_mean'], 3)}   sustained hover {_fmt(s['sustained_hover_rate'], pct=True)}"
    )
    if res.get("repeat_index"):
        print(f"  NOTE: repeat test evaluation #{res['repeat_index'] + 1} of this run")
    print(f"  saved: evaluations/{res['file']}")
    return 0


def cmd_record(args) -> int:
    from lunarlab.recording import record_run

    meta = record_run(args.run_id, episode_seed=args.episode_seed, checkpoint=args.checkpoint)
    _print_recording(meta)
    return 0


def _resolve_run_ids(args) -> list[str]:
    from lunarlab.compare import experiment_run_ids

    if getattr(args, "experiment_id", None):
        ids = experiment_run_ids(args.experiment_id)
        if not ids:
            raise SystemExit(f"no runs found for experiment {args.experiment_id}")
        return ids
    if getattr(args, "run_ids", None):
        return _strs(args.run_ids)
    raise SystemExit("pass --experiment-id or --run-ids")


def cmd_compare(args) -> int:
    from lunarlab.compare import compare_runs

    data = compare_runs(_resolve_run_ids(args), split=args.split)
    if args.json:
        print(json.dumps(data, indent=1, default=str))
        return 0
    comp = data["compatibility"]
    print(
        "Compatible: yes"
        if comp["compatible"]
        else "Compatibility issues:\n  - " + "\n  - ".join(comp["issues"])
    )
    print(f"\nPer training seed ({args.split} split, original reward):")
    print(
        f"{'reward':<26}{'seed':>5}{'eps':>5}{'mean':>9}{'≥200':>7}{'rest':>7}{'pad':>7}{'crash':>7}{'oob':>6}{'limit':>7}{'hover':>7}"
    )
    for g in data["groups"]:
        for ps in g["per_seed"]:
            e = ps["evaluation"]
            if not e:
                print(f"{g['reward_name'][:25]:<26}{ps['seed']:>5}   not evaluated on this split")
                continue
            print(
                f"{g['reward_name'][:25]:<26}{ps['seed']:>5}{e['n_episodes']:>5}{_fmt(e['mean_original_return']):>9}"
                f"{_fmt(e['score_rate'], pct=True):>7}{_fmt(e['env_success_rate'], pct=True):>7}{_fmt(e['pad_landing_rate'], pct=True):>7}"
                f"{_fmt(e['crash_rate'], pct=True):>7}{_fmt(e['out_of_bounds_rate'], pct=True):>6}{_fmt(e['timeout_rate'], pct=True):>7}"
                f"{_fmt(e['hover_fraction_mean'], 2):>7}"
            )
        a = g["across_seeds"]["mean_original_return"]
        print(
            f"{'':<26}  across seeds: mean {_fmt(a['mean'])}, sd {_fmt(a['std'])}, n={a['n']} — {g['evidence_note']}"
        )
    print("\nReward-exploitation assessment:")
    for d in data["diagnostics"]:
        print(f"  {d['reward_name']} · seed {d['seed']}: {d['flag']}")
    _print_gamma_ablation(data["gamma_ablation"])
    return 0


def _ci(ci, nd=0) -> str:
    return "" if not ci else f"[{ci[0]:+.{nd}f}, {ci[1]:+.{nd}f}]"


def _print_gamma_ablation(blocks: list[dict]) -> None:
    for b in blocks:
        print(f"\nDiscount-factor ablation: {b['reward_name']} (training physics: {b['physics_label']})")
        print("  final-test mean original return, mean over training seeds [95% bootstrap CI]")
        for c in b["cells"]:
            ci = "" if not c["mean_ci"] else f"[{c['mean_ci'][0]:.0f}, {c['mean_ci'][1]:.0f}]"
            ref = "  (reference gamma)" if c["reference"] else ""
            print(
                f"  {c['algo'].upper():<5} gamma {c['gamma']:<7g} n={c['n_seeds']:<3}{_fmt(c['mean'], 0):>7} {ci}{ref}"
            )
        rows = [
            (f"{e['algo'].upper()}: gamma {e['gamma']:g} - gamma {e['vs_gamma']:g}", e)
            for e in b["gamma_effects"]
        ]
        rows += [(f"PPO - DQN at gamma {e['gamma']:g}", e) for e in b["algorithm_effects"]]
        if b["reference_setups"]:
            r = b["reference_setups"]
            rows.append((f"PPO (gamma {r['ppo_gamma']:g}) - DQN (gamma {r['dqn_gamma']:g}), both differ", r))
        for label, e in rows:
            p = "" if e["p_improvement"] is None else f"  P(first higher) {e['p_improvement']:.2f}"
            d = "—" if e["difference"] is None else f"{e['difference']:+.0f}"
            print(f"  {label:<52}{d:>7} {_ci(e['ci'])}{p}")
        for note in b["caveats"]:
            print(f"  note: {note}")


def cmd_report(args) -> int:
    from lunarlab.report import build_report
    from lunarlab.storage import new_id

    ids = _resolve_run_ids(args)
    rid = args.experiment_id or new_id("report")
    out = build_report(ids, title=args.title or f"LunarLab report — {rid}", report_id=rid, split=args.split)
    print(f"Report written to {out['dir']}  (report.md, report.html, {len(out['figures'])} figures)")
    return 0


def _holdout_protocol(spec: str | None):
    """``START:COUNT`` -> an evaluation protocol whose final-test seeds are START..START+COUNT-1."""
    if not spec:
        return None
    from lunarlab.config import EvalProtocol

    try:
        start, count = (int(x) for x in spec.split(":"))
    except ValueError as exc:
        raise SystemExit("--holdout-seeds takes START:COUNT, e.g. 30000:100") from exc
    if count < 1:
        raise SystemExit("--holdout-seeds needs COUNT >= 1")
    protocol = EvalProtocol(test_seeds=list(range(start, start + count)))
    protocol.require_valid()
    return protocol


def _exposure_note(protocol) -> None:
    from lunarlab.config import EvalProtocol
    from lunarlab.lineage import first_test_exposure

    exposure = first_test_exposure(protocol or EvalProtocol())
    if exposure:
        print(
            "  note: these final-test seeds were already used for a final test (first by run "
            f"{exposure.get('run_id')}). If this design was chosen after seeing such results, treat its final test "
            "as exploratory, or define an untouched holdout with --holdout-seeds START:COUNT."
        )


def cmd_suite(args) -> int:
    from lunarlab.benchmark import run_benchmark  # noqa: F401  (documented alternative for estimates)
    from lunarlab.evaluation import evaluate_run
    from lunarlab.experiments import create_experiment, plan_suite
    from lunarlab.storage import data_dir, read_json
    from lunarlab.training import EXIT_COMPLETED, train

    presets = _strs(args.presets)
    bad = [p for p in presets if p not in PRESET_NAMES]
    if bad:
        raise SystemExit(f"unknown preset(s): {bad}")
    seeds = _ints(args.seeds)
    bench = read_json(data_dir() / "benchmark.json", default={}) or {}
    tps = (bench.get("default_config") or {}).get("ppo_tps")
    overrides = {
        k: v
        for k, v in {
            "total_transitions": args.total_transitions,
            "checkpoint_every": args.checkpoint_every,
            "validation_every": args.validation_every,
        }.items()
        if v
    }
    from lunarlab.experiments import build_variants

    algos = _strs(args.algos) if args.algos else [args.algo]
    variants = build_variants(
        algos=algos,
        physics=args.physics,
        physics_config=_physics_config(args) if args.physics != "fixed" else None,
        gammas=[float(g) for g in _strs(args.gammas)] if args.gammas else None,
    )
    plan = plan_suite(
        presets,
        seeds,
        args.profile,
        throughput_tps=tps,
        training_overrides=overrides,
        variants=variants,
    )
    print(
        f"Suite: {len(presets)} reward(s) × {len(variants)} variant(s) × {len(seeds)} seed(s) = "
        f"{plan['n_runs']} runs, {plan['transitions_per_run']:,} transitions each "
        f"({plan['total_transitions']:,} total)."
    )
    if len(variants) > 1:
        for v in plan["variants"]:
            print(f"  variant: {v['name']} ({v['transitions_per_run']:,} transitions)")
    if plan["estimated_hours"]:
        print(f"Estimated training time: ~{plan['estimated_hours']:.1f} h (from data/benchmark.json).")
    else:
        print("No throughput benchmark yet: run `python -m lunarlab benchmark` for a time estimate.")
    for w in plan["warnings"]:
        print(f"  ! {w}")
    if not _confirm("Create and run this suite now?", args.yes):
        return 1
    holdout = _holdout_protocol(args.holdout_seeds)
    _exposure_note(holdout)
    exp = create_experiment(
        name=args.name,
        presets=presets,
        seeds=seeds,
        profile=args.profile,
        training_overrides=overrides,
        variants=variants,
        protocol=holdout,
    )
    print(f"Experiment {exp['experiment_id']} with runs:\n  " + "\n  ".join(exp["run_ids"]))
    if args.create_only:
        return 0
    if args.parallel > 1:
        return _run_experiment_parallel(exp["experiment_id"], args.parallel, test=not args.no_test)
    for rid in exp["run_ids"]:
        code = train(rid)
        if code != EXIT_COMPLETED:
            print(
                f"Run {rid} ended with code {code}; stopping the suite. Resume it with "
                f"`python -m lunarlab resume --run-id {rid}` and rerun the remaining runs."
            )
            return code
    if not args.no_test:
        for rid in exp["run_ids"]:
            print(f"Final test evaluation (validation-selected checkpoint) for {rid} ...", flush=True)
            evaluate_run(rid, "test", checkpoint="best")
    print(f"\nDone. Compare with: python -m lunarlab compare --experiment-id {exp['experiment_id']}")
    return 0


def _run_experiment_parallel(experiment_id: str, workers: int, *, test: bool) -> int:
    """Train every unfinished run of an experiment (fresh runs train, interrupted ones resume),
    then evaluate each completed run once on the final-test seeds."""
    from lunarlab.experiments import load_experiment
    from lunarlab.parallel import run_parallel
    from lunarlab.runs import read_manifest
    from lunarlab.storage import RunPaths

    exp = load_experiment(experiment_id)
    jobs = []
    for rid in exp["run_ids"]:
        ckpts = read_manifest(RunPaths(rid))["checkpoints"]
        if any(c["kind"] == "final" for c in ckpts):
            continue
        jobs.append(("resume" if ckpts else "train", rid))
    print(f"Training {len(jobs)} run(s) with up to {workers} in parallel ...", flush=True)
    codes = run_parallel(jobs, workers=workers)
    failed = [rid for rid, c in codes.items() if c != 0]
    if failed:
        print(
            f"{len(failed)} run(s) did not complete: {failed}. Rerun `python -m lunarlab run-experiment "
            f"--experiment-id {experiment_id}` to resume them."
        )
        return 1
    if test:
        from lunarlab.freeze import pending_final_tests

        # A freeze alone is not a completed test: interrupted or failed attempts are retried on the
        # same frozen checkpoint.
        todo = [("test", rid) for rid in pending_final_tests(exp["run_ids"])]
        print(f"Final-test evaluation of {len(todo)} run(s) ...", flush=True)
        test_codes = run_parallel(todo, workers=workers)
        if any(c != 0 for c in test_codes.values()):
            return 1
    print(f"\nDone. Compare with: python -m lunarlab compare --experiment-id {experiment_id}")
    return 0


def cmd_run_experiment(args) -> int:
    return _run_experiment_parallel(args.experiment_id, args.parallel, test=not args.no_test)


def cmd_train_run(args) -> int:
    """Train an existing, never-started run (e.g. one created with --create-only)."""
    from lunarlab.training import train

    return train(args.run_id)


def cmd_robustness(args) -> int:
    """Evaluate frozen checkpoints under wind / heavy gravity (separate from the calm final test)."""
    from lunarlab.parallel import run_parallel
    from lunarlab.robustness import CONDITIONS

    ids = _resolve_run_ids(args)
    conds = _strs(args.conditions) if args.conditions else list(CONDITIONS)
    bad = [c for c in conds if c not in CONDITIONS]
    if bad:
        raise SystemExit(f"unknown condition(s): {bad}; choose from {', '.join(CONDITIONS)}")
    print(f"Robustness: {len(ids)} run(s) x {len(conds)} condition(s), {args.episodes} episodes each")
    jobs = [("robustness", rid) for rid in ids]
    codes = run_parallel(
        jobs,
        workers=args.parallel,
        extra_args=["--conditions", ",".join(conds), "--episodes", str(args.episodes)],
    )
    return 0 if all(c == 0 for c in codes.values()) else 1


def cmd_robustness_run(args) -> int:
    from lunarlab.evaluation import summarize_for_index
    from lunarlab.robustness import evaluate_robustness

    for cond in _strs(args.conditions):
        r = evaluate_robustness(args.run_id, cond, episodes=args.episodes)
        s = summarize_for_index(r)
        print(
            f"{cond}: mean original return {s['mean_original_return']:.1f}, pad landing {s['pad_landing_rate']:.2f}",
            flush=True,
        )
    return 0


def _stage_checkpoints(run_id: str, targets: list[int]) -> list[dict]:
    """Checkpoints of a run nearest to the target transition counts (plus its final one)."""
    from lunarlab.runs import read_manifest
    from lunarlab.storage import RunPaths

    ckpts = [c for c in read_manifest(RunPaths(run_id))["checkpoints"] if c["kind"] in ("periodic", "final")]
    chosen: dict[str, dict] = {}
    for t in targets:
        if ckpts:
            c = min(ckpts, key=lambda c: abs(c["transitions"] - t))
            chosen[c["name"]] = c
    final = next((c for c in ckpts if c["kind"] == "final"), None)
    if final:
        chosen[final["name"]] = final
    return sorted(chosen.values(), key=lambda c: c["transitions"])


def _rlhf_dataset(from_experiment: str | None, source_seeds: str, episodes: int) -> str:
    """Collect preference segments from random, heuristic and (optionally) PPO checkpoints."""
    from lunarlab.compare import experiment_run_ids
    from lunarlab.env import make_env
    from lunarlab.policies import HeuristicPolicy, RandomPolicy
    from lunarlab.preferences.data import create_dataset
    from lunarlab.runs import load_config, load_policy

    policies = [
        ("random-0", RandomPolicy(0)),
        ("random-1", RandomPolicy(1)),
        ("heuristic", HeuristicPolicy(make_env())),
    ]
    if from_experiment:
        seeds_used = set(_ints(source_seeds))
        for rid in experiment_run_ids(from_experiment):
            cfg = load_config(rid)
            if cfg.reward.preset not in ("baseline", "hover-bonus") or cfg.seed not in seeds_used:
                continue
            for c in _stage_checkpoints(rid, [100_000, 300_000, 600_000]):
                pol, _ = load_policy(rid, c["name"], deterministic=False)
                policies.append((f"PPO {cfg.reward.name} s{cfg.seed} @{c['transitions'] // 1000}k", pol))
    print(f"Collecting segments from {len(policies)} policies x {episodes} episodes ...", flush=True)
    dataset_id = create_dataset(policies, episodes_per_policy=episodes, name="rlhf")
    print(f"Dataset {dataset_id}", flush=True)
    return dataset_id


def _rlhf_reward_model(
    dataset_id: str, pairs: int, *, seed: int, include_human: bool, members: int = 1
) -> dict:
    from lunarlab.preferences.train import train_reward_model

    meta = train_reward_model(
        dataset_id,
        n_pairs=pairs,
        seed=seed,
        include_human=include_human,
        name=f"rm-{pairs}" + (f"-x{members}" if members > 1 else ""),
        members=members,
    )
    m = meta["metrics"]
    print(
        f"Reward model {meta['model_id']}: {meta['n_train_pairs']} training pairs ({meta['n_human_labels']} human), "
        f"accuracy vs true order {m['val_accuracy_vs_true_order']:.3f}, segment-return correlation "
        f"{m['segment_return_correlation']:.3f}, step-reward correlation {m['step_reward_correlation']:.3f}",
        flush=True,
    )
    return meta


def cmd_rlhf_dataset(args) -> int:
    _rlhf_dataset(args.from_experiment, args.source_seeds, args.episodes)
    return 0


def cmd_reward_model(args) -> int:
    _rlhf_reward_model(
        args.dataset_id, args.pairs, seed=args.seed, include_human=args.include_human, members=args.members
    )
    return 0


def cmd_rlhf_study(args) -> int:
    """RLHF in miniature: preferences -> reward models -> PPO on the learned reward -> true evaluation."""
    from lunarlab.experiments import create_experiment

    if args.reward_models:  # train PPO on reward models that already exist (e.g. from rlhf-active)
        from lunarlab.preferences.model import load_reward_model, model_path
        from lunarlab.storage import read_json

        rewards = []
        for mid in _strs(args.reward_models):
            load_reward_model(mid)  # validates the id and the recorded SHA-256
            meta = read_json(model_path(mid) / "meta.json", default={}) or {}
            label = meta.get("strategy") or (
                f"{meta['n_train_pairs']} labels" if "n_train_pairs" in meta else mid
            )
            rewards.append(
                RewardConfig.model_validate(
                    {
                        "name": f"Learned reward ({label})"[:80],
                        "preset": "custom",
                        "description": f"RLHF: PPO trained only on reward model {mid}. The environment reward has weight 0.",
                        "original_weight": 0.0,
                        "learned": {"enabled": True, "model_id": mid, "scale": 1.0},
                    }
                )
            )
        exp = create_experiment(
            name=args.name,
            rewards=rewards,
            seeds=_ints(args.seeds),
            profile=args.profile,
            description="Learned-reward (RLHF) study on existing reward models: "
            + ", ".join(_strs(args.reward_models)),
        )
        print(f"Experiment {exp['experiment_id']}: {len(exp['run_ids'])} runs", flush=True)
        if args.create_only:
            return 0
        return _run_experiment_parallel(exp["experiment_id"], args.parallel, test=True)
    dataset_id = args.dataset_id or _rlhf_dataset(args.from_experiment, args.source_seeds, args.episodes)
    rewards = []
    for n in _ints(args.pairs):
        meta = _rlhf_reward_model(
            dataset_id, n, seed=args.rm_seed, include_human=args.include_human, members=args.members
        )
        rewards.append(
            RewardConfig.model_validate(
                {
                    "name": f"Learned reward {n} pairs",
                    "preset": "custom",
                    "description": (
                        f"RLHF: PPO trained only on reward model {meta['model_id']} (fitted to {meta['n_train_pairs']} "
                        "preference labels). The environment reward has weight 0."
                    ),
                    "original_weight": 0.0,
                    "learned": {"enabled": True, "model_id": meta["model_id"], "scale": 1.0},
                }
            )
        )
    exp = create_experiment(
        name=args.name,
        rewards=rewards,
        seeds=_ints(args.seeds),
        profile=args.profile,
        description=f"Learned-reward (RLHF) study on dataset {dataset_id}.",
    )
    print(f"Experiment {exp['experiment_id']}: {len(exp['run_ids'])} runs", flush=True)
    if args.create_only:
        return 0
    return _run_experiment_parallel(exp["experiment_id"], args.parallel, test=True)


def cmd_rlhf_active(args) -> int:
    """Active vs random preference selection, simulated: learning curves of reward-model accuracy."""
    from lunarlab.preferences.active import run_active_study

    strategies = _strs(args.strategies)
    study = run_active_study(
        args.dataset_id,
        strategies=strategies,
        seeds=_ints(args.seeds),
        budget=args.budget,
        initial=args.initial,
        batch=args.batch,
        members=args.members,
        candidates=args.candidates,
        register=args.register,
    )
    print(
        f"\nStudy {study['study_id']} (saved with the dataset). Validation accuracy vs true order, mean [min, max] over seeds:"
    )
    labels = [p["labels"] for p in study["summary"][strategies[0]]]
    print("labels  " + "  ".join(f"{s:>24}" for s in strategies))
    for k, n in enumerate(labels):
        cells = []
        for s in strategies:
            q = study["summary"][s][k]
            cells.append(f"{q['mean']:.3f} [{q['min']:.3f}, {q['max']:.3f}]".rjust(24))
        print(f"{n:>6}  " + "  ".join(cells))
    if args.register:
        ids = [r["model"]["model_id"] for r in study["runs"] if "model" in r]
        print("\nFinal ensembles registered: " + ", ".join(ids))
        print(
            "Train PPO on them with: python -m lunarlab rlhf-study --reward-models <ids> --seeds 0,1,2 --parallel 6"
        )
    return 0


def _print_tuning(summary: dict) -> None:
    st = summary.get("status") or {}
    c = summary["counts"]
    print(
        f"Study {summary['study_id']} ({summary['algo'].upper()}, {summary['preset']}): {st.get('state', '?')}; "
        f"{summary['finished']}/{summary['n_trials']} trials finished ({c.get('complete', 0)} complete, "
        f"{c.get('pruned', 0)} pruned, {c.get('fail', 0)} failed)"
    )
    print(f"Objective: {summary['objective']}")
    for t in summary["trials"]:
        val = f"{t['value']:.1f}" if t["value"] is not None else "—"
        extra = (
            f" (pruned at {t['pruned_at']:,})"
            if t["pruned_at"]
            else (" (cancelled)" if t["cancelled"] else "")
        )
        params = ", ".join(
            f"{k.split('.')[-1]}={v:.4g}" if isinstance(v, float) else f"{k.split('.')[-1]}={v}"
            for k, v in t["params"].items()
        )
        print(f"  #{t['number']:<3} {t['state']:<8} {val:>8}  {params}{extra}")
    if summary["best"]:
        b = summary["best"]
        print(f"Best: trial {b['number']} with {b['value']:.1f} (run {b['run_id']})")


def cmd_tune(args) -> int:
    from lunarlab.tuning import TuningError, create_study, run_study

    try:
        spec = create_study(
            name=args.name,
            algo=args.algo,
            preset_name=args.preset,
            params=_strs(args.params) if args.params else None,
            n_trials=args.trials,
            trial_transitions=args.transitions,
            validation_every=args.validation_every,
            warmup_transitions=args.warmup,
            startup_trials=args.startup_trials,
            sampler_seed=args.seed,
        )
    except TuningError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Study {spec['study_id']}: tuning {', '.join(spec['params'])}")
    print(
        f"Budget: {spec['n_trials']} trials x {spec['trial_transitions']:,} transitions, validation every "
        f"{spec['validation_every']:,}, pruning after {spec['warmup_transitions']:,} transitions "
        f"and {spec['startup_trials']} trials. Final-test seeds are never used."
    )
    if args.create_only:
        return 0
    _print_tuning(run_study(spec["study_id"], timeout_s=args.timeout))
    return 0


def cmd_tune_resume(args) -> int:
    from lunarlab.tuning import run_study

    _print_tuning(run_study(args.study_id, n_trials=args.trials, timeout_s=args.timeout))
    return 0


def cmd_tune_status(args) -> int:
    from lunarlab.tuning import list_studies, study_summary

    if args.study_id:
        _print_tuning(study_summary(args.study_id))
    else:
        for st in list_studies():
            best = st["best"]["value"] if st["best"] else None
            print(
                f"{st['study_id']}  {st['algo'].upper()} {st['preset']:<13} {(st.get('status') or {}).get('state', '?'):<9} "
                f"{st['finished']}/{st['n_trials']} trials  best {best if best is None else round(best, 1)}"
            )
    return 0


def cmd_tune_cancel(args) -> int:
    from lunarlab.tuning import request_cancel

    request_cancel(args.study_id)
    print("Cancel requested: the running trial stops at its next safe boundary. Resume with tune-resume.")
    return 0


def cmd_tune_apply(args) -> int:
    from lunarlab.tuning import TuningError, apply_best

    try:
        exp = apply_best(
            args.study_id,
            seeds=_ints(args.seeds),
            profile=args.profile,
            experiment_name=args.name,
            protocol=_holdout_protocol(args.holdout_seeds),
        )
    except TuningError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Experiment {exp['experiment_id']}: {len(exp['run_ids'])} normal run(s) with the best settings")
    print(f"  {exp['description']}")
    if exp["test_set_previously_exposed"]:
        print(
            "  These runs are EXPLORATORY: their final-test seeds were already used for a final test, so "
            "selecting settings and then testing on them is not a held-out test. For a confirmatory result, "
            "apply again with --holdout-seeds START:COUNT (seeds never used before)."
        )
    if args.create_only:
        return 0
    return _run_experiment_parallel(exp["experiment_id"], args.parallel, test=True)


def cmd_record_showcase(args) -> int:
    """Side-by-side replays: one policy per reward group (and the heuristic/random references),
    all flying the same episode seeds."""
    from lunarlab.compare import experiment_run_ids
    from lunarlab.recording import list_recordings, record_demo, record_run
    from lunarlab.runs import load_config

    seeds = _ints(args.seeds)
    have = {(m.get("run_id"), m["policy"]["kind"], m["episode_seed"]) for m in list_recordings()}
    for rid in experiment_run_ids(args.experiment_id):
        cfg = load_config(rid)
        if cfg.seed != args.training_seed:
            continue
        for s in seeds:
            if (rid, cfg.algo, s) in have:
                continue
            meta = record_run(rid, episode_seed=s, checkpoint="final-test")
            print(
                f"{cfg.algo.upper()} {cfg.reward.name} seed {cfg.seed} on episode {s}: return "
                f"{meta['original_return']:.1f}, {meta['env_outcome']}",
                flush=True,
            )
    if args.references:
        for kind in ("heuristic", "random"):
            for s in seeds:
                if (None, kind, s) not in have:
                    meta = record_demo(kind, episode_seed=s)
                    print(f"{kind} on episode {s}: return {meta['original_return']:.1f}", flush=True)
    return 0


def cmd_warm_restart(args) -> int:
    """A NEW run initialised from a checkpoint's weights (never presented as a resume)."""
    from lunarlab.lineage import create_warm_restart
    from lunarlab.runs import load_metadata

    child = create_warm_restart(args.run_id, args.checkpoint, confirm=args.confirm, label=args.label)
    lineage = load_metadata(child.run_id)["lineage"]
    print(f"Created warm restart {child.run_id} from {args.run_id} ({lineage['parent_checkpoint']}).")
    print("  preserved: " + "; ".join(lineage["preserved"]))
    print("  reset:     " + "; ".join(lineage["reset"]))
    print("  note:      " + lineage["note"])
    if args.train:
        from lunarlab.training import train

        return train(child.run_id)
    print(f"Train it with: python -m lunarlab train-run --run-id {child.run_id}")
    return 0


def cmd_test_status(args) -> int:
    from lunarlab.freeze import test_status
    from lunarlab.runs import load_config

    load_config(args.run_id)  # an unknown run is an error, not "0 completed final tests"
    s = test_status(args.run_id)
    f = s["frozen_for_test"] or {}
    print(
        f"frozen:     {'yes' if s['frozen'] else 'no'}"
        + (f" ({f.get('checkpoint')}, {f.get('frozen_at')})" if f else "")
    )
    if s["frozen"]:
        print(
            f"artifact:   {f.get('artifact') or 'legacy record (no immutable copy yet: see freeze-migrate)'}"
        )
    print(f"completed:  {'yes' if s['completed'] else 'no'} ({s['completed_count']} completed final test(s))")
    for a in s["attempts"]:
        print(
            f"  attempt {a['attempt']}: {a['state']} {a.get('started_at', '')} {a.get('file') or a.get('error') or ''}"
        )
    if s["needs_retry"]:
        print(
            f"Retry with: python -m lunarlab evaluate --run-id {args.run_id} --split test (same frozen checkpoint)"
        )
    return 0


def cmd_freeze_migrate(args) -> int:
    """Explicit, logged migration of legacy freeze records to immutable artifacts (or a dry run)."""
    from lunarlab.freeze import migrate_legacy_freeze, resolve_frozen_checkpoint
    from lunarlab.runs import RunError, load_metadata
    from lunarlab.storage import list_run_ids

    ids = list_run_ids() if args.all else _resolve_run_ids(args)
    bad = 0
    for rid in ids:
        frozen = load_metadata(rid).get("frozen_for_test")
        if not frozen or frozen.get("artifact"):
            continue
        if args.dry_run:
            try:
                resolve_frozen_checkpoint(rid)
                print(f"{rid}: migratable (tested bytes intact: {frozen['checkpoint']})")
            except RunError as exc:
                bad += 1
                print(f"{rid}: NOT migratable: {exc}")
            continue
        report = migrate_legacy_freeze(rid)
        bad += not report["migrated"]
        print(
            f"{rid}: {'migrated -> ' + report['artifact'] if report['migrated'] else 'not migrated: ' + report['reason']}"
        )
    return 1 if bad else 0


def cmd_reclassify_outcomes(args) -> int:
    from lunarlab.reclassify import reclassification_report, write_report

    run_ids = (
        [r for e in _strs(args.experiment_ids) for r in _experiment_runs(e)] if args.experiment_ids else []
    )
    if args.experiment_id:
        run_ids += _experiment_runs(args.experiment_id)
    if args.run_ids:
        run_ids += _strs(args.run_ids)
    if not run_ids:
        raise SystemExit("pass --experiment-ids, --experiment-id or --run-ids")
    report = reclassification_report(list(dict.fromkeys(run_ids)))
    s = report["summary"]
    print(
        f"{s['evaluation_files']} version-1 evaluation file(s), {s['episodes']:,} episodes: "
        f"v1 'landed_off_pad' {s['v1_landed_off_pad']}, v2 landed not within the pad "
        f"{s['v2_landed_not_within_pad']}, v2 on the pad but not strict {s['v2_on_pad_not_strict']}, "
        f"relabelled {s['relabelled_episodes']} (strict pad landings unchanged: {s['pad_landings']})."
    )
    if args.out:
        for p in write_report(report, Path(args.out)):
            print(f"wrote {p}")
    else:
        print("Dry run: nothing written (pass --out DIR to write the derived report).")
    return 0


def _experiment_runs(experiment_id: str) -> list[str]:
    from lunarlab.compare import experiment_run_ids

    return experiment_run_ids(experiment_id)


def cmd_results(args) -> int:
    from lunarlab.results import build_results

    build_results(_strs(args.experiment_ids), Path(args.out))
    return 0


def cmd_showcase(args) -> int:
    from lunarlab.results import make_showcase

    ids, labels = _strs(args.recordings), [x.strip() for x in args.labels.split("|")]
    if len(ids) != len(labels):
        raise SystemExit("give one label per recording (labels are separated by '|')")
    r = make_showcase(
        ids,
        labels,
        Path(args.out),
        frames_dir=Path(args.frames_dir) if args.frames_dir else None,
        tile=(args.tile_width, args.tile_width * 2 // 3),
        max_steps=args.max_steps,
        colors=args.colors,
        quality=args.quality,
    )
    print(f"{r['file']}: {r['frames']} frames, {r['bytes'] / 1e6:.1f} MB")
    return 0


def _write_report(report: dict, path: str | None) -> None:
    if path:
        Path(path).write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
        print(f"report written to {path}")


def cmd_reproduce_smoke(args) -> int:
    from lunarlab.reproduce import run_smoke

    print(
        f"Reproducibility smoke test: {args.algo.upper()}, preset {args.preset}, {args.transitions:,} transitions, "
        f"seed {args.seed}{', training twice' if args.training_determinism else ''} (isolated temporary home)"
    )
    report = run_smoke(
        Path(args.workdir) if args.workdir else None,
        transitions=args.transitions,
        seed=args.seed,
        preset_name=args.preset,
        algo=args.algo,
        training_determinism=args.training_determinism,
        keep=args.keep,
    )
    print(
        f"{'PASSED' if report['ok'] else 'FAILED'}: {sum(c['ok'] for c in report['checks'])}/{len(report['checks'])} checks in {report['elapsed_s']} s"
    )
    _write_report(report, args.report)
    return 0 if report["ok"] else 1


def cmd_export_artifact(args) -> int:
    from lunarlab.reproduce import export_artifact

    m = export_artifact(args.run_id, Path(args.out))
    d = m["documented_metric"]
    print(
        f"exported {args.run_id} to {args.out}: checkpoint {m['files']['checkpoint.zip']['sha256'][:16]}, "
        f"final test {d['n_episodes']} episodes, mean original return {d['mean_original_return']:.2f}, "
        f"pad landing {d['pad_landing_rate']:.0%}"
    )
    return 0


def cmd_reproduce_artifact(args) -> int:
    from lunarlab.reproduce import reproduce_artifact

    if not _is_artifact(args.artifact):
        return 2
    report = reproduce_artifact(Path(args.artifact), episodes=args.episodes, tolerance=args.tolerance)
    print(
        f"{report['status'].upper()}{' (blocking)' if report['blocking'] else ''}: {report['artifact']}, "
        f"{report['episodes']} episodes; mean original return recorded {report['recorded_mean_original_return']:.4f}, "
        f"reproduced {report['reproduced_mean_original_return']:.4f}; pad landing recorded "
        f"{report['recorded_pad_landing_rate']:.0%}, reproduced {report['reproduced_pad_landing_rate']:.0%}\n"
        f"  {report['status_reason']}"
    )
    _write_report(report, args.report)
    return report["exit_code"]


def _is_artifact(folder: str) -> bool:
    if (Path(folder) / "artifact.json").is_file():
        return True
    print(
        f"error: {folder} is not a reproduction package (no artifact.json); see export-artifact",
        file=sys.stderr,
    )
    return False


def cmd_trace_artifact(args) -> int:
    from lunarlab.divergence import diagnose, record_traces

    if not _is_artifact(args.artifact):
        return 2
    if args.compare and not (
        Path(args.compare).is_file() and Path(args.compare).with_suffix(".json").is_file()
    ):
        print(f"error: no trace pair {args.compare} (+ .json); record one with --out", file=sys.stderr)
        return 2
    if args.compare:
        report = diagnose(Path(args.artifact), Path(args.compare))
        for e in report["episodes"]:
            c = e["closed_loop"]
            print(
                f"  seed {e['seed']}: {e['source']}; first output difference at step "
                f"{e['inference']['first_output_difference_step']} ({e['inference']['action_flips']} action flips), "
                f"first open-loop observation difference at step {e['dynamics']['first_observation_difference_step']}; "
                f"closed loop parts at step {c['first_observation_difference_step']}, return "
                f"{c['reference_return']:.4f} -> {c['return']:.4f}"
            )
        verdict = "IDENTICAL" if report["identical"] else "DIFFERENT"
        print(
            f"{verdict}: {report['artifact']} against {report['reference']['file']}; sources: {', '.join(report['sources'])}"
        )
        _write_report(report, args.report)
        if "unexplained" in report["sources"]:
            return 1  # the closed loop differs although inference and dynamics do not: nondeterminism
        return 0 if report["identical"] else 3
    meta = record_traces(Path(args.artifact), [int(s) for s in args.seeds.split(",")], Path(args.out))
    for e in meta["episodes"]:
        print(
            f"  seed {e['seed']}: {e['steps']} steps, return {e['original_return']:.4f}"
            f"{'' if e['matches_recorded_return'] else ' (differs from the recorded evaluation)'}"
        )
    print(f"traces written to {args.out} and {Path(args.out).with_suffix('.json')}")
    return 0 if all(e["matches_recorded_return"] for e in meta["episodes"]) else 1


def cmd_overhead_benchmark(args) -> int:
    from lunarlab.overhead import PROFILES, run_benchmark

    p = PROFILES[args.profile]
    transitions = args.transitions or p["transitions"]
    repeats = args.repeats or p["repeats"]
    runs = 3 * repeats
    if args.profile == "comprehensive" and not _confirm(
        f"The comprehensive benchmark trains {runs} PPO runs of {transitions:,} transitions (hours of CPU time). Continue?",
        args.yes,
    ):
        return 1
    print(
        f"Overhead benchmark ({args.profile}): {runs} runs of {transitions:,} transitions, each in a fresh process"
    )
    res = run_benchmark(
        args.profile,
        transitions=transitions,
        repeats=repeats,
        out=Path(args.out) if args.out else None,
        torch_threads=args.torch_threads,
    )
    print((Path(res["out"]) / "table.md").read_text(encoding="utf-8"))
    print(f"raw measurements, summary, table and figures: {res['out']}")
    return 0


def cmd_export_demo(args) -> int:
    from lunarlab.demo import export_demo

    manifest = export_demo(
        Path(args.out),
        experiment_ids=_strs(args.experiment_ids),
        extra_run_ids=_strs(args.run_ids) if args.run_ids else None,
        draft=args.draft,
    )
    print(
        f"{manifest['kind']} export of revision {manifest['export_revision'] or 'unknown'}"
        + ("" if manifest["export_source_clean"] else " (with uncommitted changes: labelled draft)")
    )
    return 0


def cmd_sweep(args) -> int:
    """Explicit development sweep over hover-bonus weights (validation-only selection)."""
    from lunarlab.experiments import create_experiment
    from lunarlab.training import EXIT_COMPLETED, train

    rewards = []
    for b in [float(x) for x in _strs(args.bonus)]:
        r = preset("hover-bonus")
        r.name = f"Hover bonus {b:g}"
        r.preset = "custom"
        r.hover_bonus.bonus_per_step = b
        rewards.append(RewardConfig.model_validate(r.model_dump()))
    seeds = _ints(args.seeds)
    n = len(rewards) * len(seeds)
    print(
        f"DEVELOPMENT SWEEP: {n} run(s). Selection uses validation episodes only; test seeds are not touched."
    )
    if not _confirm("Create and run the sweep?", args.yes):
        return 1
    exp = create_experiment(
        name=args.name,
        rewards=rewards,
        seeds=seeds,
        profile=args.profile,
        description="Development sweep over hover-bonus weight. All trials kept.",
    )
    print(f"Experiment {exp['experiment_id']}")
    if args.create_only:
        return 0
    for rid in exp["run_ids"]:
        if train(rid) != EXIT_COMPLETED:
            return 1
    print(
        f"Compare on validation: python -m lunarlab compare --experiment-id {exp['experiment_id']} --split validation"
    )
    return 0


def cmd_runs(args) -> int:
    from lunarlab.compare import run_summary
    from lunarlab.storage import list_run_ids

    ids = list_run_ids()
    if not ids:
        print("No runs yet. Start with: python -m lunarlab train --preset baseline --profile smoke")
        return 0
    print(
        f"{'run id':<52}{'reward':<24}{'seed':>5} {'profile':<9}{'state':<12}{'ckpt transitions':>17}  evidence"
    )
    for rid in ids:
        s = run_summary(rid)
        print(
            f"{rid:<52}{s['reward_name'][:23]:<24}{s['seed']:>5} {s['profile']:<9}{s['state']:<12}"
            f"{s['checkpoint_transitions']:>17,}  {s['evidence']}"
        )
    return 0


def cmd_rescore(args) -> int:
    from lunarlab.config import EvalProtocol
    from lunarlab.recording import find_recording
    from lunarlab.rescoring import rescore
    from lunarlab.storage import read_json

    tpath, _ = find_recording(args.recording_id)
    telemetry = read_json(tpath)
    configs = [preset(p) for p in _strs(args.presets)]
    res = rescore(telemetry, configs, gamma=args.gamma, detector=EvalProtocol().hover_detector)
    print(res["disclaimer"])
    print(
        f"Trajectory {res['recording_id']} ({res['steps']} steps, outcome {res['outcome']}, policy "
        f"{res['policy']['kind']}). Phase steps: {res['phase_steps']}"
    )
    print(f"{'reward':<28}{'undiscounted':>14}{'discounted':>12}")
    for c in res["configs"]:
        print(f"{c['name']:<28}{c['undiscounted']['training']:>14.2f}{c['discounted']['training']:>12.2f}")
        for e in c["explanations"]:
            print(f"    {e}")
    return 0


def cmd_benchmark(args) -> int:
    from lunarlab.benchmark import run_benchmark

    print("Measuring throughput (bounded: a few seconds per configuration) ...")
    res = run_benchmark(
        n_envs_list=tuple(_ints(args.n_envs)),
        env_seconds=args.seconds,
        ppo=not args.no_ppo,
        torch_threads=args.threads,
    )
    if res["best"]:
        print(
            f"Fastest: {res['best']['vec_env']} with n_envs={res['best']['n_envs']}. "
            "Primary experiments keep n_envs=4 so PPO settings stay identical; saved to data/benchmark.json"
        )
    return 0


def cmd_reward(args) -> int:
    from lunarlab.storage import read_yaml

    if args.action == "export":
        import yaml

        text = yaml.safe_dump(preset(args.preset).model_dump(mode="json"), sort_keys=False)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"wrote {args.output}")
        else:
            print(text)
        return 0
    cfg = RewardConfig.model_validate(read_yaml(Path(args.file)))
    print(f"valid: {cfg.name} [{cfg.content_hash()}], terms: {', '.join(cfg.active_terms()) or 'none'}")
    for w in cfg.warnings():
        print(f"  ! {w}")
    return 0


def cmd_processes(args) -> int:
    from lunarlab.procs import find_lunarlab_processes, terminate

    procs = find_lunarlab_processes()
    if not procs:
        print("No LunarLab processes from this project are running.")
        return 0
    for p in procs:
        print(f"pid {p['pid']:>7}  {p['role']:<7} {p['cmdline']}")
    if args.terminate:
        for pid, outcome in terminate(procs):
            print(f"pid {pid}: {outcome}")
    return 0


def cmd_serve(args) -> int:
    from lunarlab.server.main import serve

    return serve(host=args.host, port=args.port)


def cmd_worker(args) -> int:
    from lunarlab.jobs import run_worker

    return run_worker(args.job_id)


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m lunarlab", description="LunarLab — Reward Shaping Mission Control"
    )
    p.add_argument(
        "--version", action=_VersionAction, help="print the version, source revision and key dependencies"
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check the installation").set_defaults(fn=cmd_doctor)
    v = sub.add_parser("version", help="software identity: version, source revision, Python, dependencies")
    v.add_argument("--json", action="store_true", help="machine-readable output")
    v.set_defaults(fn=cmd_version)

    d = sub.add_parser("random-demo", help="record one RANDOM-policy episode")
    d.add_argument("--episode-seed", type=int, default=20_000)
    d.add_argument("--action-seed", type=int, default=0)
    d.set_defaults(fn=cmd_demo)
    d = sub.add_parser("heuristic-demo", help="record one episode of Gymnasium's HEURISTIC controller")
    d.add_argument("--episode-seed", type=int, default=20_000)
    d.set_defaults(fn=cmd_demo)

    t = sub.add_parser("train", help="create a run and train it in this terminal")
    g = t.add_mutually_exclusive_group(required=True)
    g.add_argument("--preset", choices=PRESET_NAMES)
    g.add_argument("--reward-config", help="YAML/JSON reward configuration file")
    t.add_argument("--profile", choices=list(PROFILES), default="smoke")
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--total-transitions", type=int)
    t.add_argument("--n-envs", type=int)
    t.add_argument("--vec-env", choices=["dummy", "subproc"])
    t.add_argument("--device", choices=["cpu", "cuda", "auto"])
    t.add_argument("--threads", type=int)
    t.add_argument("--experiment-id")
    t.add_argument("--label")
    t.add_argument("--yes", action="store_true", help="skip confirmation for EXTENDED")
    t.add_argument(
        "--algo", choices=["ppo", "dqn"], default="ppo", help="PPO (default) or DQN (Zoo settings)"
    )
    t.add_argument("--gamma", type=float, help="discount factor (default: the algorithm's reference value)")
    _add_physics_args(t, choices=["fixed", "randomized"])
    t.set_defaults(fn=cmd_train)

    r = sub.add_parser("resume", help="continue a stopped/interrupted run from a checkpoint")
    r.add_argument("--run-id", required=True)
    r.add_argument("--checkpoint", default="latest")
    r.set_defaults(fn=cmd_resume)

    s = sub.add_parser("stop", help="ask a running training to stop at the next safe boundary")
    s.add_argument("--run-id", required=True)
    s.set_defaults(fn=cmd_stop)

    e = sub.add_parser("evaluate", help="evaluate a checkpoint with the original reward")
    e.add_argument("--run-id", required=True)
    e.add_argument("--split", choices=["validation", "test"], required=True)
    e.add_argument("--checkpoint", default="best", help="best | final | latest | <file name>")
    e.set_defaults(fn=cmd_evaluate)

    rec = sub.add_parser("record", help="record one episode of a run's checkpoint")
    rec.add_argument("--run-id", required=True)
    rec.add_argument("--episode-seed", type=int, required=True)
    rec.add_argument("--checkpoint", default="best")
    rec.set_defaults(fn=cmd_record)

    for name, fn, help_ in (
        ("compare", cmd_compare, "compare runs"),
        ("report", cmd_report, "write a Markdown/HTML report"),
    ):
        c = sub.add_parser(name, help=help_)
        c.add_argument("--experiment-id")
        c.add_argument("--run-ids", help="comma-separated run ids")
        c.add_argument("--split", choices=["validation", "test"], default="test")
        if name == "compare":
            c.add_argument("--json", action="store_true")
        else:
            c.add_argument("--title")
        c.set_defaults(fn=fn)

    su = sub.add_parser("suite", help="multi-seed suite: presets × seeds, then final test evaluation")
    su.add_argument("--presets", default="baseline,time-penalty,hover-bonus,potential")
    su.add_argument("--seeds", default="0,1,2")
    su.add_argument("--profile", choices=list(PROFILES), default="standard")
    su.add_argument("--name", default="reward-shaping-suite")
    su.add_argument("--yes", action="store_true")
    su.add_argument(
        "--create-only", action="store_true", help="create the runs; train them later (e.g. from the UI)"
    )
    su.add_argument("--no-test", action="store_true", help="skip the final test evaluation")
    su.add_argument("--parallel", type=int, default=1, help="train up to N runs at once (one CPU core each)")
    su.add_argument("--algo", choices=["ppo", "dqn"], default="ppo")
    su.add_argument(
        "--algos", help="several algorithms, e.g. ppo,dqn: one variant each, with exactly matched budgets"
    )
    su.add_argument("--gammas", help="discount-factor ablation, e.g. 0.99,0.999: one variant per value")
    su.add_argument(
        "--holdout-seeds",
        help="START:COUNT final-test seeds never used before (an untouched holdout for confirmatory claims)",
    )
    _add_physics_args(su, choices=["fixed", "randomized", "both"])
    su.add_argument("--total-transitions", type=int, help="override the profile's budget (labelled 'custom')")
    su.add_argument("--checkpoint-every", type=int)
    su.add_argument("--validation-every", type=int)
    su.set_defaults(fn=cmd_suite)

    re_ = sub.add_parser(
        "run-experiment", help="train/resume the unfinished runs of an experiment, then final-test them"
    )
    re_.add_argument("--experiment-id", required=True)
    re_.add_argument("--parallel", type=int, default=1)
    re_.add_argument("--no-test", action="store_true")
    re_.set_defaults(fn=cmd_run_experiment)

    rd = sub.add_parser("rlhf-dataset", help="collect flight segments for preference labelling")
    rd.add_argument(
        "--from-experiment", help="also use checkpoints of this experiment's baseline/hover-bonus runs"
    )
    rd.add_argument("--source-seeds", default="0,1")
    rd.add_argument("--episodes", type=int, default=20, help="episodes per source policy")
    rd.set_defaults(fn=cmd_rlhf_dataset)

    rm = sub.add_parser("reward-model", help="fit a reward model to a dataset's preferences")
    rm.add_argument("--dataset-id", required=True)
    rm.add_argument("--pairs", type=int, default=3000, help="simulated-human comparisons")
    rm.add_argument("--include-human", action="store_true", help="also use the labels given in the UI")
    rm.add_argument("--seed", type=int, default=0)
    rm.add_argument(
        "--members", type=int, default=1, help="ensemble size (bootstrap resamples; 1 = one network)"
    )
    rm.set_defaults(fn=cmd_reward_model)

    ra = sub.add_parser("rlhf-active", help="active vs random preference selection (simulated labeller)")
    ra.add_argument("--dataset-id", required=True)
    ra.add_argument("--strategies", default="random,disagreement")
    ra.add_argument("--seeds", default="0,1,2")
    ra.add_argument("--budget", type=int, default=1000, help="labels per run")
    ra.add_argument("--initial", type=int, default=100, help="random labels before the first selection")
    ra.add_argument("--batch", type=int, default=100, help="labels selected per round")
    ra.add_argument("--members", type=int, default=5, help="ensemble size")
    ra.add_argument("--candidates", type=int, default=2000, help="random candidate pairs scored per round")
    ra.add_argument("--register", action="store_true", help="register each final ensemble as a reward model")
    ra.set_defaults(fn=cmd_rlhf_active)

    rl = sub.add_parser("rlhf-study", help="preferences -> reward models -> PPO on the learned reward")
    rl.add_argument("--dataset-id", help="reuse an existing dataset instead of collecting a new one")
    rl.add_argument(
        "--from-experiment",
        help="use checkpoints of this experiment's baseline/hover-bonus runs as data sources",
    )
    rl.add_argument("--source-seeds", default="0,1")
    rl.add_argument("--episodes", type=int, default=20, help="episodes per source policy")
    rl.add_argument("--pairs", default="300,3000", help="comparison counts, one reward model each")
    rl.add_argument("--include-human", action="store_true", help="also use the labels given in the UI")
    rl.add_argument("--rm-seed", type=int, default=0)
    rl.add_argument("--members", type=int, default=1, help="reward-model ensemble size")
    rl.add_argument(
        "--reward-models", help="train on these existing reward models instead (comma-separated ids)"
    )
    rl.add_argument("--seeds", default="0,1,2", help="PPO training seeds per reward model")
    rl.add_argument("--profile", choices=list(PROFILES), default="standard")
    rl.add_argument("--name", default="rlhf-study")
    rl.add_argument("--parallel", type=int, default=1)
    rl.add_argument("--create-only", action="store_true")
    rl.set_defaults(fn=cmd_rlhf_study)

    tu = sub.add_parser("tune", help="Optuna study: tune algorithm settings and reward weights on validation")
    tu.add_argument("--name", default="study")
    tu.add_argument("--algo", choices=["ppo", "dqn"], default="ppo")
    tu.add_argument("--preset", choices=PRESET_NAMES, default="baseline")
    tu.add_argument(
        "--params",
        help="comma-separated, e.g. ppo.learning_rate,reward.potential.alpha (default: a small set)",
    )
    tu.add_argument("--trials", type=int, default=20)
    tu.add_argument("--transitions", type=int, default=200_000, help="training budget of each trial")
    tu.add_argument("--validation-every", type=int, default=25_000)
    tu.add_argument(
        "--warmup", type=int, help="no pruning before this many transitions (default: 2 validations)"
    )
    tu.add_argument(
        "--startup-trials", type=int, default=4, help="trials before the sampler and pruner kick in"
    )
    tu.add_argument("--seed", type=int, default=0, help="sampler seed")
    tu.add_argument("--timeout", type=float, help="start no new trial after N seconds (resumable)")
    tu.add_argument("--create-only", action="store_true")
    tu.set_defaults(fn=cmd_tune)

    tr2 = sub.add_parser("tune-resume", help="continue a tuning study (after a cancel, timeout or crash)")
    tr2.add_argument("--study-id", required=True)
    tr2.add_argument("--trials", type=int, help="at most this many more trials in this session")
    tr2.add_argument("--timeout", type=float)
    tr2.set_defaults(fn=cmd_tune_resume)

    ts = sub.add_parser("tune-status", help="list tuning studies, or show one study's trials")
    ts.add_argument("--study-id")
    ts.set_defaults(fn=cmd_tune_status)

    tc = sub.add_parser("tune-cancel", help="stop a running tuning study at the next safe boundary")
    tc.add_argument("--study-id", required=True)
    tc.set_defaults(fn=cmd_tune_cancel)

    ta = sub.add_parser(
        "tune-apply", help="create normal runs from a study's best settings (then train + test)"
    )
    ta.add_argument("--study-id", required=True)
    ta.add_argument("--seeds", default="0,1,2")
    ta.add_argument("--profile", choices=list(PROFILES), default="standard")
    ta.add_argument("--name")
    ta.add_argument("--parallel", type=int, default=1)
    ta.add_argument("--create-only", action="store_true")
    ta.add_argument(
        "--holdout-seeds",
        help="START:COUNT final-test seeds never used before (keeps the new runs confirmatory)",
    )
    ta.set_defaults(fn=cmd_tune_apply)

    sc = sub.add_parser(
        "record-showcase", help="record every reward group's policy on the same episode seeds"
    )
    sc.add_argument("--experiment-id", required=True)
    sc.add_argument("--seeds", default="20000,20001", help="episode seeds (final-test seeds start at 20000)")
    sc.add_argument(
        "--training-seed", type=int, default=0, help="which training seed's policy to record per group"
    )
    sc.add_argument("--references", action="store_true", help="also record the heuristic and random policies")
    sc.set_defaults(fn=cmd_record_showcase)

    rr = sub.add_parser("results", help="figures and tables for the results write-up (final-test data only)")
    rr.add_argument("--experiment-ids", required=True)
    rr.add_argument("--out", default="docs/results")
    rr.set_defaults(fn=cmd_results)

    sg = sub.add_parser("showcase", help="compose recorded flights side by side (GIF or animated WebP)")
    sg.add_argument("--recordings", required=True, help="comma-separated recording ids")
    sg.add_argument("--labels", required=True, help="one label per recording, separated by '|'")
    sg.add_argument(
        "--frames-dir", help="3-D frames from frontend/tools/capture3d.mjs (default: simulator footage)"
    )
    sg.add_argument("--out", required=True, help=".gif or .webp")
    sg.add_argument("--tile-width", type=int, default=360)
    sg.add_argument("--max-steps", type=int, default=600, help="footage only: cut long episodes here")
    sg.add_argument("--colors", type=int, default=96, help="GIF palette size")
    sg.add_argument("--quality", type=int, default=70, help="WebP quality (0-100)")
    sg.set_defaults(fn=cmd_showcase)

    wr = sub.add_parser(
        "warm-restart",
        help="create a NEW run initialised from a checkpoint's weights (not a resume; lineage recorded)",
    )
    wr.add_argument("--run-id", required=True)
    wr.add_argument("--checkpoint", default="latest", help="manifest name, latest, final, best or frozen")
    wr.add_argument("--confirm", action="store_true", help="required: confirms this is a new run")
    wr.add_argument("--label")
    wr.add_argument("--train", action="store_true", help="start training the new run right away")
    wr.set_defaults(fn=cmd_warm_restart)

    ts = sub.add_parser("test-status", help="frozen checkpoint, final-test attempts and completion of a run")
    ts.add_argument("--run-id", required=True)
    ts.set_defaults(fn=cmd_test_status)

    fm = sub.add_parser(
        "freeze-migrate",
        help="give legacy freeze records an immutable artifact (only if the bytes are intact)",
    )
    fm.add_argument("--experiment-id")
    fm.add_argument("--run-ids")
    fm.add_argument("--all", action="store_true")
    fm.add_argument("--dry-run", action="store_true", help="report what would happen; change nothing")
    fm.set_defaults(fn=cmd_freeze_migrate)

    rc = sub.add_parser(
        "reclassify-outcomes",
        help="derived outcome-classifier-v2 report for version-1 evaluations (files are never modified)",
    )
    rc.add_argument("--experiment-ids")
    rc.add_argument("--experiment-id")
    rc.add_argument("--run-ids")
    rc.add_argument("--out", help="directory for the derived report; without it nothing is written")
    rc.set_defaults(fn=cmd_reclassify_outcomes)

    ed = sub.add_parser(
        "export-demo", help="write a static, read-only snapshot of results for the hosted demo"
    )
    ed.add_argument("--experiment-ids", required=True)
    ed.add_argument("--run-ids", help="additional runs to include")
    ed.add_argument("--out", default="demo/api")
    ed.add_argument(
        "--draft",
        action="store_true",
        help="allow uncommitted source changes; the snapshot is labelled a draft (a release export refuses them)",
    )
    ed.set_defaults(fn=cmd_export_demo)

    rs = sub.add_parser(
        "reproduce-smoke",
        help="bounded end-to-end reproducibility check in an isolated temporary home (no web UI needed)",
    )
    rs.add_argument("--transitions", type=int, default=4096)
    rs.add_argument("--seed", type=int, default=0)
    rs.add_argument("--preset", choices=PRESET_NAMES, default="potential")
    rs.add_argument("--algo", choices=["ppo", "dqn"], default="ppo")
    rs.add_argument(
        "--training-determinism",
        action="store_true",
        help="train the same configuration twice and compare weights and episodes",
    )
    rs.add_argument("--workdir", help="use this (new) folder instead of a temporary one")
    rs.add_argument("--keep", action="store_true", help="keep the working folder for inspection")
    rs.add_argument("--report", help="write the JSON report to this file")
    rs.set_defaults(fn=cmd_reproduce_smoke)

    ea = sub.add_parser(
        "export-artifact",
        help="copy a run's tested checkpoint, config and recorded final test into a reproduction package",
    )
    ea.add_argument("--run-id", required=True)
    ea.add_argument("--out", required=True, help="new folder to create")
    ea.set_defaults(fn=cmd_export_artifact)

    ra = sub.add_parser(
        "reproduce-artifact",
        help="verify a reproduction package and re-evaluate its checkpoint on the recorded test seeds",
        description="Exit status: 0 = selected episode-summary fields match (or returns within --tolerance); 3 = numerical "
        "differences on a different platform with integrity intact and no aggregate differing significantly from "
        "the record in paired tests (reported, not failed); 1 = integrity failure, a difference on the recording "
        "platform, or a significant aggregate difference; 2 = invalid arguments (or no artifact.json in the folder).",
    )
    ra.add_argument("--artifact", required=True, help="folder written by export-artifact")
    ra.add_argument("--episodes", type=int, help="only the first N recorded seeds (default: all)")
    ra.add_argument(
        "--tolerance",
        type=float,
        default=0.0,
        help="absolute tolerance on returns (default 0: exact numeric equality of compared fields)",
    )
    ra.add_argument("--report", help="write the JSON report to this file")
    ra.set_defaults(fn=cmd_reproduce_artifact)

    ta = sub.add_parser(
        "trace-artifact",
        help="record per-step traces of an artifact's test episodes, or locate where this machine departs from them",
        description="--out records traces (observations, network outputs, actions, rewards) on this machine. "
        "--compare re-flies the traced episodes here and separates policy-inference from simulator-dynamics "
        "differences. Exit status for --compare: 0 = identical, 3 = differences located (reported, not failed), "
        "1 = the closed loop differs although neither inference nor dynamics does; 2 = invalid arguments.",
    )
    ta.add_argument("--artifact", required=True, help="folder written by export-artifact")
    tmode = ta.add_mutually_exclusive_group(required=True)
    tmode.add_argument("--out", help="record: write the traces to this .npz (metadata next to it as .json)")
    tmode.add_argument("--compare", help="compare: a .npz written by --out")
    ta.add_argument("--seeds", default="20000,20001,20002", help="record: comma-separated test seeds")
    ta.add_argument("--report", help="compare: write the JSON report to this file")
    ta.set_defaults(fn=cmd_trace_artifact)

    ob = sub.add_parser(
        "overhead-benchmark",
        help="measure LunarLab's instrumentation overhead against plain SB3 (time, memory, artifacts)",
    )
    ob.add_argument("--profile", choices=["smoke", "standard", "comprehensive"], default="smoke")
    ob.add_argument("--transitions", type=int, help="override the profile's transitions per run")
    ob.add_argument("--repeats", type=int, help="override the profile's repetitions per configuration")
    ob.add_argument("--torch-threads", type=int, default=1)
    ob.add_argument("--out", help="new output folder (default reports/jmlr/benchmarks/<profile>-<time>)")
    ob.add_argument("--yes", action="store_true", help="required for the comprehensive profile")
    ob.set_defaults(fn=cmd_overhead_benchmark)

    rb = sub.add_parser(
        "robustness", help="evaluate frozen checkpoints under wind/gravity they never trained on"
    )
    rb.add_argument("--experiment-id")
    rb.add_argument("--run-ids")
    rb.add_argument("--conditions", help="comma-separated; default: all")
    rb.add_argument("--episodes", type=int, default=50)
    rb.add_argument("--parallel", type=int, default=1)
    rb.set_defaults(fn=cmd_robustness)

    rbr = sub.add_parser("robustness-run", help=argparse.SUPPRESS)
    rbr.add_argument("--run-id", required=True)
    rbr.add_argument("--conditions", required=True)
    rbr.add_argument("--episodes", type=int, default=50)
    rbr.set_defaults(fn=cmd_robustness_run)

    tr_ = sub.add_parser("train-run", help="train an existing run that has not been started yet")
    tr_.add_argument("--run-id", required=True)
    tr_.set_defaults(fn=cmd_train_run)

    sw = sub.add_parser("sweep", help="explicit development sweep over hover-bonus weights")
    sw.add_argument("--bonus", default="0.25,0.5,1,2")
    sw.add_argument("--seeds", default="0")
    sw.add_argument("--profile", choices=list(PROFILES), default="standard")
    sw.add_argument("--name", default="hover-bonus-sweep")
    sw.add_argument("--yes", action="store_true")
    sw.add_argument("--create-only", action="store_true")
    sw.set_defaults(fn=cmd_sweep)

    sub.add_parser("runs", help="list runs").set_defaults(fn=cmd_runs)

    rs = sub.add_parser("rescore", help="Reward Stress Test: re-score a recorded trajectory")
    rs.add_argument("--recording-id", required=True)
    rs.add_argument("--presets", default=",".join(PRESET_NAMES))
    rs.add_argument("--gamma", type=float, default=PPOConfig().gamma)
    rs.set_defaults(fn=cmd_rescore)

    b = sub.add_parser("benchmark", help="measure throughput before changing worker counts")
    b.add_argument("--n-envs", default="1,2,4,8")
    b.add_argument("--seconds", type=float, default=3.0)
    b.add_argument("--threads", type=int, default=1)
    b.add_argument("--no-ppo", action="store_true")
    b.set_defaults(fn=cmd_benchmark)

    rw = sub.add_parser("reward", help="export a preset or validate a reward configuration file")
    rw.add_argument("action", choices=["export", "validate"])
    rw.add_argument("--preset", choices=PRESET_NAMES, default="baseline")
    rw.add_argument("--file")
    rw.add_argument("--output", "-o")
    rw.set_defaults(fn=cmd_reward)

    sv = sub.add_parser("serve", help="run the web application (loopback only by default)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8765)
    sv.set_defaults(fn=cmd_serve)

    pr = sub.add_parser("processes", help="list (or terminate) this project's backend/worker processes")
    pr.add_argument("--terminate", action="store_true", help="terminate them (no stop checkpoint is written)")
    pr.set_defaults(fn=cmd_processes)

    w = sub.add_parser("worker", help=argparse.SUPPRESS)
    w.add_argument("--job-id", required=True)
    w.set_defaults(fn=cmd_worker)
    return p


# Single-id arguments, validated before any command runs (the ids LunarLab generates always pass).
ID_ARGUMENTS = ("run_id", "experiment_id", "recording_id", "study_id", "dataset_id")


def main(argv: list[str] | None = None) -> int:
    # When output is piped on Windows, Python uses the ANSI code page; never crash on
    # characters such as "≥" or "—" that it cannot encode.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = build_parser().parse_args(argv)
    from lunarlab.config import ProtocolError
    from lunarlab.runs import RunError
    from lunarlab.storage import validate_run_id

    ids = {name: v for name in ID_ARGUMENTS if isinstance(v := getattr(args, name, None), str)}
    for name, value in ids.items():
        try:
            validate_run_id(value)
        except ValueError:
            print(
                f"error: --{name.replace('_', '-')} {value!r} is not a valid id "
                "(letters, digits, '-' and '_'; at most 96 characters)",
                file=sys.stderr,
                flush=True,
            )
            return 2
    try:
        return int(args.fn(args) or 0)
    except (RunError, ProtocolError) as exc:
        print(f"error: {exc}", file=sys.stderr, flush=True)
        return 1
    except KeyError as exc:
        # The stores raise KeyError(<id>) for an id that does not exist; any other KeyError is a bug.
        name = next((n for n, v in ids.items() if exc.args and exc.args[0] == v), None)
        if name is None:
            raise
        print(f"error: unknown {name.removesuffix('_id')}: {exc.args[0]}", file=sys.stderr, flush=True)
        return 1
