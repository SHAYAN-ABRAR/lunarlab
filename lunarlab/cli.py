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
    ppo = PPOConfig(**({"n_envs": args.n_envs} if args.n_envs else {}))
    planned = actual_budget(training.total_transitions, ppo.rollout_size)
    print(PROFILES.get(args.profile, {}).get("label", args.profile))
    print(
        f"Reward: {reward.name} [{reward.content_hash()}]  terms: {', '.join(reward.active_terms()) or 'none'}"
    )
    print(
        f"Budget: requested {training.total_transitions:,} transitions → actual {planned:,} "
        f"(whole rollouts of {ppo.rollout_size:,})"
    )
    if args.profile == "extended" and not _confirm("EXTENDED runs are long. Start?", args.yes):
        return 1
    cfg = create_run(
        reward=reward,
        training=training,
        seed=args.seed,
        ppo=ppo,
        algo=args.algo,
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
    return 0


def cmd_report(args) -> int:
    from lunarlab.report import build_report
    from lunarlab.storage import new_id

    ids = _resolve_run_ids(args)
    rid = args.experiment_id or new_id("report")
    out = build_report(ids, title=args.title or f"LunarLab report — {rid}", report_id=rid, split=args.split)
    print(f"Report written to {out['dir']}  (report.md, report.html, {len(out['figures'])} figures)")
    return 0


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
    plan = plan_suite(
        presets,
        seeds,
        args.profile,
        throughput_tps=tps if args.algo == "ppo" else None,
        algo=args.algo,
        training_overrides=overrides,
    )
    print(
        f"Suite: {len(presets)} reward(s) × {len(seeds)} seed(s) = {plan['n_runs']} runs, "
        f"{plan['transitions_per_run']:,} transitions each ({plan['total_transitions']:,} total)."
    )
    if plan["estimated_hours"]:
        print(f"Estimated training time: ~{plan['estimated_hours']:.1f} h (from data/benchmark.json).")
    else:
        print("No throughput benchmark yet: run `python -m lunarlab benchmark` for a time estimate.")
    for w in plan["warnings"]:
        print(f"  ! {w}")
    if not _confirm("Create and run this suite now?", args.yes):
        return 1
    exp = create_experiment(
        name=args.name,
        presets=presets,
        seeds=seeds,
        profile=args.profile,
        algo=args.algo,
        training_overrides=overrides,
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
        from lunarlab.runs import load_metadata

        todo = [("test", rid) for rid in exp["run_ids"] if not load_metadata(rid).get("frozen_for_test")]
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


def _rlhf_reward_model(dataset_id: str, pairs: int, *, seed: int, include_human: bool) -> dict:
    from lunarlab.preferences.train import train_reward_model

    meta = train_reward_model(
        dataset_id, n_pairs=pairs, seed=seed, include_human=include_human, name=f"rm-{pairs}"
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
    _rlhf_reward_model(args.dataset_id, args.pairs, seed=args.seed, include_human=args.include_human)
    return 0


def cmd_rlhf_study(args) -> int:
    """RLHF in miniature: preferences -> reward models -> PPO on the learned reward -> true evaluation."""
    from lunarlab.experiments import create_experiment

    dataset_id = args.dataset_id or _rlhf_dataset(args.from_experiment, args.source_seeds, args.episodes)
    rewards = []
    for n in _ints(args.pairs):
        meta = _rlhf_reward_model(dataset_id, n, seed=args.rm_seed, include_human=args.include_human)
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


def cmd_record_showcase(args) -> int:
    """Side-by-side replays: one policy per reward group (and the heuristic/random references),
    all flying the same episode seeds."""
    from lunarlab.compare import experiment_run_ids
    from lunarlab.recording import list_recordings, record_demo, record_run
    from lunarlab.runs import load_config, load_metadata

    seeds = _ints(args.seeds)
    have = {(m.get("run_id"), m["policy"]["kind"], m["episode_seed"]) for m in list_recordings()}
    for rid in experiment_run_ids(args.experiment_id):
        cfg = load_config(rid)
        if cfg.seed != args.training_seed:
            continue
        frozen = load_metadata(rid).get("frozen_for_test")
        for s in seeds:
            if (rid, cfg.algo, s) in have:
                continue
            meta = record_run(rid, episode_seed=s, checkpoint=frozen["checkpoint"] if frozen else "best")
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


def cmd_results(args) -> int:
    from lunarlab.results import build_results

    build_results(_strs(args.experiment_ids), Path(args.out))
    return 0


def cmd_export_demo(args) -> int:
    from lunarlab.demo import export_demo

    export_demo(
        Path(args.out),
        experiment_ids=_strs(args.experiment_ids),
        extra_run_ids=_strs(args.run_ids) if args.run_ids else None,
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
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check the installation").set_defaults(fn=cmd_doctor)

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
    rm.set_defaults(fn=cmd_reward_model)

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
    rl.add_argument("--seeds", default="0,1,2", help="PPO training seeds per reward model")
    rl.add_argument("--profile", choices=list(PROFILES), default="standard")
    rl.add_argument("--name", default="rlhf-study")
    rl.add_argument("--parallel", type=int, default=1)
    rl.add_argument("--create-only", action="store_true")
    rl.set_defaults(fn=cmd_rlhf_study)

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

    ed = sub.add_parser(
        "export-demo", help="write a static, read-only snapshot of results for the hosted demo"
    )
    ed.add_argument("--experiment-ids", required=True)
    ed.add_argument("--run-ids", help="additional runs to include")
    ed.add_argument("--out", default="demo/api")
    ed.set_defaults(fn=cmd_export_demo)

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


def main(argv: list[str] | None = None) -> int:
    # When output is piped on Windows, Python uses the ANSI code page; never crash on
    # characters such as "≥" or "—" that it cannot encode.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = build_parser().parse_args(argv)
    return int(args.fn(args) or 0)
