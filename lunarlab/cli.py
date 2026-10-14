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
    plan = plan_suite(presets, seeds, args.profile, throughput_tps=tps)
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
    exp = create_experiment(name=args.name, presets=presets, seeds=seeds, profile=args.profile)
    print(f"Experiment {exp['experiment_id']} with runs:\n  " + "\n  ".join(exp["run_ids"]))
    if args.create_only:
        return 0
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
    su.set_defaults(fn=cmd_suite)

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
