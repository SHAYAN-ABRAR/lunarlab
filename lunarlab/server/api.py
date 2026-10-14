"""HTTP API (``/api``). Every handler is short: long work is submitted as a job."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any

import psutil
import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import ValidationError

from lunarlab import __version__
from lunarlab.compare import compare_runs, run_summary, training_curve
from lunarlab.config import PROFILES, EvalProtocol, PPOConfig, actual_budget, training_for_profile
from lunarlab.db import Database
from lunarlab.env import ACTIONS, OBSERVATION_FIELDS, environment_record
from lunarlab.evaluation import list_evaluations
from lunarlab.experiments import create_experiment, list_experiments, load_experiment, plan_suite
from lunarlab.jobs import JobConflict, JobManager, JobNotFound, job_dir, tail
from lunarlab.recording import find_recording, list_recordings
from lunarlab.rescoring import rescore
from lunarlab.rewards.analysis import hover_incentive, time_penalty_effect
from lunarlab.rewards.config import RewardConfig, all_presets, preset
from lunarlab.runs import RunError, create_run, load_config, load_metadata, read_manifest
from lunarlab.server import schemas as S
from lunarlab.storage import (
    RunPaths,
    data_dir,
    list_run_ids,
    new_id,
    read_json,
    read_jsonl,
    reports_dir,
    safe_child,
    validate_run_id,
)
from lunarlab.training import request_stop

router = APIRouter(prefix="/api")


def db(request: Request) -> Database:
    return request.app.state.db


def jobs(request: Request) -> JobManager:
    return request.app.state.jobs


def _run_or_404(run_id: str) -> RunPaths:
    try:
        paths = RunPaths(run_id)
    except ValueError as exc:
        raise HTTPException(400, "invalid run id") from exc
    if not paths.exists():
        raise HTTPException(404, f"unknown run {run_id}")
    return paths


def _submit(
    request: Request,
    kind: str,
    *,
    run_id: str | None = None,
    params: dict | None = None,
    key: str | None = None,
) -> dict:
    try:
        return jobs(request).submit(kind, run_id=run_id, params=params, idempotency_key=key)
    except JobConflict as exc:
        raise HTTPException(409, str(exc)) from exc


# --------------------------------------------------------------------------- #
# Cached run summaries (invalidated by file modification times)
# --------------------------------------------------------------------------- #

_summary_cache: dict[str, tuple[tuple, dict]] = {}
_cache_lock = threading.Lock()
_create_lock = threading.Lock()  # serialises "create run + submit job" so double clicks cannot orphan runs


def _signature(paths: RunPaths) -> tuple:
    sig = []
    for p in (
        paths.status,
        paths.checkpoint_manifest,
        paths.metadata,
        paths.validation_history,
        paths.evaluations,
    ):
        try:
            sig.append(p.stat().st_mtime_ns)
        except OSError:
            sig.append(0)
    return tuple(sig)


def cached_summary(run_id: str) -> dict:
    paths = RunPaths(run_id)
    sig = _signature(paths)
    with _cache_lock:
        hit = _summary_cache.get(run_id)
        if hit and hit[0] == sig:
            return hit[1]
    s = run_summary(run_id)
    with _cache_lock:
        _summary_cache[run_id] = (sig, s)
    return s


def light_summary(s: dict) -> dict:
    keep = (
        "run_id",
        "experiment_id",
        "label",
        "created_at",
        "reward_name",
        "reward_preset",
        "reward_hash",
        "reward_revision",
        "active_terms",
        "seed",
        "profile",
        "requested_transitions",
        "planned_transitions",
        "checkpoint_transitions",
        "state",
        "completed",
        "evidence",
        "best_validation",
        "latest_validation",
        "latest_test",
        "frozen_for_test",
        "protocol_hash",
    )
    return {k: s.get(k) for k in keep}


# --------------------------------------------------------------------------- #
# System
# --------------------------------------------------------------------------- #


@router.get("/health")
def health(request: Request) -> dict:
    return {"status": "ok", "version": __version__, "pid": os.getpid(), "home": str(data_dir().parent)}


@router.get("/meta")
def meta() -> dict:
    return {
        "observation_fields": [f.__dict__ for f in OBSERVATION_FIELDS],
        "actions": [a.__dict__ for a in ACTIONS],
        "presets": [p.model_dump(mode="json") | {"hash": p.content_hash()} for p in all_presets()],
        "profiles": {k: {**v} for k, v in PROFILES.items()},
        "ppo_defaults": PPOConfig().model_dump(mode="json"),
        "rollout_size": PPOConfig().rollout_size,
        "eval_protocol": EvalProtocol().model_dump(mode="json") | {"hash": EvalProtocol().protocol_hash()},
        "reward_schema": RewardConfig.model_json_schema(),
    }


_env_record_cache: dict | None = None


@router.get("/system")
def system(request: Request) -> dict:
    global _env_record_cache
    if _env_record_cache is None:
        _env_record_cache = environment_record()
    vm = psutil.virtual_memory()
    du = psutil.disk_usage(str(data_dir()))
    active = jobs(request).db.list_jobs(states=("queued", "starting", "running", "stop_requested"))
    return {
        "time": time.time(),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_count": psutil.cpu_count(logical=True),
        "ram": {
            "used_gb": round(vm.used / 1e9, 2),
            "total_gb": round(vm.total / 1e9, 2),
            "percent": vm.percent,
        },
        "disk": {
            "free_gb": round(du.free / 1e9, 1),
            "total_gb": round(du.total / 1e9, 1),
            "percent": du.percent,
        },
        "jobs": {
            s: sum(1 for j in active if j["state"] == s)
            for s in ("queued", "starting", "running", "stop_requested")
        },
        "queue_paused": jobs(request).queue_paused,
        "readiness": request.app.state.readiness,
        "environment": _env_record_cache,
        "benchmark": read_json(data_dir() / "benchmark.json", default=None),
    }


@router.get("/overview")
def overview(request: Request) -> dict:
    runs = [light_summary(cached_summary(r)) for r in list_run_ids()]
    runs.sort(key=lambda r: r["created_at"], reverse=True)
    active = db(request).list_jobs(states=("queued", "starting", "running", "stop_requested"))
    by_preset: dict[str, dict[str, Any]] = {}
    for r in runs:
        ev = r.get("latest_test") or r.get("latest_validation")
        if r["profile"] == "smoke" or not ev:
            continue
        slot = by_preset.setdefault(r["reward_preset"], {"runs": 0, "evaluations": []})
        slot["runs"] += 1
        slot["evaluations"].append(
            {
                "run_id": r["run_id"],
                "seed": r["seed"],
                "split": "test" if r.get("latest_test") else "validation",
                "mean_original_return": ev["mean_original_return"],
                "pad_landing_rate": ev["pad_landing_rate"],
            }
        )
    return {
        "runs": runs[:12],
        "n_runs": len(runs),
        "active_jobs": active,
        "recordings": len(list_recordings()),
        "experiments": list_experiments()[:6],
        "by_preset": by_preset,
        "readiness": request.app.state.readiness,
        "queue_paused": jobs(request).queue_paused,
    }


# --------------------------------------------------------------------------- #
# Reward configurations
# --------------------------------------------------------------------------- #


def _with_warnings(row: dict) -> dict:
    cfg = RewardConfig.model_validate(row["config"])
    return row | {"warnings": cfg.warnings(), "active_terms": cfg.active_terms()}


@router.get("/reward-configs")
def reward_configs(request: Request) -> list[dict]:
    return [_with_warnings(r) for r in db(request).list_reward_configs()]


@router.get("/reward-configs/{config_id}")
def reward_config(config_id: str, request: Request) -> dict:
    try:
        return _with_warnings(db(request).get_reward_config(config_id))
    except KeyError as exc:
        raise HTTPException(404, "unknown reward configuration") from exc


@router.post("/reward-configs/validate")
def validate_reward(body: S.RewardConfigValidate) -> dict:
    try:
        cfg = RewardConfig.model_validate(body.config)
    except ValidationError as exc:
        return {"valid": False, "errors": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]}
    return {
        "valid": True,
        "errors": [],
        "warnings": cfg.warnings(),
        "hash": cfg.content_hash(),
        "active_terms": cfg.active_terms(),
    }


@router.post("/reward-configs", status_code=201)
def create_reward(body: S.RewardConfigCreate, request: Request) -> dict:
    try:
        return _with_warnings(db(request).create_reward_config(body.config, parent_id=body.parent_id))
    except KeyError as exc:
        raise HTTPException(404, "parent configuration not found") from exc


@router.post("/reward-configs/import", status_code=201)
def import_reward(body: S.RewardImport, request: Request) -> dict:
    try:
        data = yaml.safe_load(body.yaml)
        cfg = RewardConfig.model_validate(data)
    except yaml.YAMLError as exc:
        raise HTTPException(400, f"not valid YAML: {exc}") from exc
    except ValidationError as exc:
        raise HTTPException(422, [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]) from exc
    return _with_warnings(db(request).create_reward_config(cfg, parent_id=body.parent_id))


@router.get("/reward-configs/{config_id}/export")
def export_reward(config_id: str, request: Request) -> PlainTextResponse:
    try:
        row = db(request).get_reward_config(config_id)
    except KeyError as exc:
        raise HTTPException(404, "unknown reward configuration") from exc
    text = yaml.safe_dump(row["config"], sort_keys=False)
    return PlainTextResponse(
        text,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{row["id"]}.yaml"'},
    )


@router.post("/reward-analysis/hover")
def analysis_hover(body: S.HoverAnalysisRequest) -> dict:
    return hover_incentive(**body.model_dump())


@router.get("/reward-analysis/time-penalty")
def analysis_time(cost: float = 0.01, gamma: float = 0.999, steps: int = 1000) -> dict:
    if not (0 <= cost <= 1 and 0 < gamma <= 1 and 1 <= steps <= 100_000):
        raise HTTPException(400, "out of range")
    return time_penalty_effect(cost=cost, gamma=gamma, steps=steps)


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #


@router.get("/runs")
def runs() -> list[dict]:
    out = [light_summary(cached_summary(r)) for r in list_run_ids()]
    return sorted(out, key=lambda r: r["created_at"], reverse=True)


@router.post("/runs", status_code=201)
def create_run_endpoint(body: S.RunCreate, request: Request) -> dict:
    if body.reward_config_id:
        try:
            row = db(request).get_reward_config(body.reward_config_id)
        except KeyError as exc:
            raise HTTPException(404, "unknown reward configuration") from exc
        reward = RewardConfig.model_validate(row["config"])
        ref_id, rev = row["id"], row["revision"]
    elif body.preset:
        reward, ref_id, rev = preset(body.preset), f"preset-{body.preset}-r1", 1
    else:
        raise HTTPException(400, "choose a reward configuration or a preset")
    if body.profile == "extended" and not body.confirm_extended:
        raise HTTPException(400, "EXTENDED runs need explicit confirmation (confirm_extended=true)")
    training = training_for_profile(
        body.profile, total_transitions=body.total_transitions, vec_env=body.vec_env
    )
    ppo = PPOConfig(**({"n_envs": body.n_envs} if body.n_envs else {}))
    with _create_lock:
        if body.idempotency_key:
            existing = db(request).job_by_idempotency_key(body.idempotency_key)
            if existing and existing.get("run_id"):
                return {"run": light_summary(cached_summary(existing["run_id"])), "job": existing}
        cfg = create_run(
            reward=reward,
            training=training,
            seed=body.seed,
            ppo=ppo,
            label=body.label,
            experiment_id=body.experiment_id,
            reward_config_id=ref_id,
            reward_revision=rev,
        )
        job = _submit(request, "train", run_id=cfg.run_id, key=body.idempotency_key) if body.start else None
    return {"run": light_summary(cached_summary(cfg.run_id)), "job": job}


@router.get("/runs/{run_id}")
def run_detail(run_id: str, request: Request) -> dict:
    paths = _run_or_404(run_id)
    cfg = load_config(run_id)
    meta = load_metadata(run_id)
    run_jobs = [j for j in db(request).list_jobs(limit=500) if j["run_id"] == run_id][:20]
    recs = [r for r in list_recordings() if r.get("run_id") == run_id]
    return {
        "summary": cached_summary(run_id),
        "config": cfg.model_dump(mode="json"),
        "config_hash": cfg.config_hash(),
        "rollout_size": cfg.ppo.rollout_size,
        "metadata": meta,
        "status": read_json(paths.status, default={}),
        "manifest": read_manifest(paths),
        "evaluations": list_evaluations(run_id),
        "jobs": run_jobs,
        "recordings": recs,
    }


@router.get("/runs/{run_id}/curve")
def run_curve(run_id: str, window: int = 100) -> dict:
    _run_or_404(run_id)
    return training_curve(run_id, window=max(1, min(window, 1000)))


@router.get("/runs/{run_id}/metrics")
def run_metrics(run_id: str) -> list[dict]:
    paths = _run_or_404(run_id)
    rows = read_jsonl(paths.metrics)
    step = max(1, len(rows) // 500)
    return rows[::step] if step > 1 else rows


@router.get("/runs/{run_id}/validation")
def run_validation(run_id: str) -> list[dict]:
    return read_jsonl(_run_or_404(run_id).validation_history)


@router.get("/runs/{run_id}/events")
def run_events(run_id: str, limit: int = 200) -> list[dict]:
    return read_jsonl(_run_or_404(run_id).events, limit=max(1, min(limit, 2000)))


@router.get("/runs/{run_id}/evaluations/{name}")
def run_evaluation(run_id: str, name: str) -> dict:
    paths = _run_or_404(run_id)
    try:
        p = safe_child(paths.evaluations, name)
    except ValueError as exc:
        raise HTTPException(400, "invalid file name") from exc
    data = read_json(p)
    if not data or p.suffix != ".json":
        raise HTTPException(404, "evaluation not found")
    return data


@router.get("/runs/{run_id}/config.yaml")
def run_config_file(run_id: str) -> FileResponse:
    paths = _run_or_404(run_id)
    return FileResponse(paths.config, media_type="application/x-yaml", filename=f"{run_id}-config.yaml")


@router.post("/runs/{run_id}/train")
def run_train(run_id: str, request: Request, body: S.ResumeRequest | None = None) -> dict:
    _run_or_404(run_id)
    if read_manifest(RunPaths(run_id))["checkpoints"]:
        raise HTTPException(409, "run already has checkpoints; use resume")
    return _submit(request, "train", run_id=run_id, key=body.idempotency_key if body else None)


@router.post("/runs/{run_id}/resume")
def run_resume(run_id: str, body: S.ResumeRequest, request: Request) -> dict:
    _run_or_404(run_id)
    try:
        from lunarlab.runs import resolve_checkpoint

        _, entry = resolve_checkpoint(run_id, body.checkpoint)
    except RunError as exc:
        raise HTTPException(409, str(exc)) from exc
    if any(c["kind"] == "final" for c in read_manifest(RunPaths(run_id))["checkpoints"]):
        raise HTTPException(409, "run already completed")
    return _submit(
        request, "resume", run_id=run_id, params={"checkpoint": entry["name"]}, key=body.idempotency_key
    )


@router.post("/runs/{run_id}/stop")
def run_stop(run_id: str, request: Request) -> dict:
    paths = _run_or_404(run_id)
    active = [
        j
        for j in db(request).list_jobs(states=("queued", "starting", "running", "stop_requested"))
        if j["run_id"] == run_id
    ]
    if active:
        return {"job": jobs(request).request_stop(active[0]["id"])}
    st = read_json(paths.status, default={}) or {}
    if st.get("state") == "running":
        request_stop(paths, reason="user", source="api")  # e.g. a training started from the CLI
        return {"external": True, "pid": st.get("pid")}
    raise HTTPException(409, "nothing is running for this run")


@router.post("/runs/{run_id}/evaluate")
def run_evaluate(run_id: str, body: S.EvaluateRequest, request: Request) -> dict:
    _run_or_404(run_id)
    if body.split == "test" and not body.confirm_test:
        raise HTTPException(
            400, "final-test evaluation must be confirmed (it freezes the selected checkpoint)"
        )
    meta = load_metadata(run_id)
    if (
        body.split == "test"
        and meta.get("frozen_for_test")
        and body.checkpoint not in ("best", meta["frozen_for_test"]["checkpoint"])
    ):
        raise HTTPException(409, "this run is frozen for the final test with a different checkpoint")
    return _submit(
        request,
        "evaluate",
        run_id=run_id,
        params={"split": body.split, "checkpoint": body.checkpoint},
        key=body.idempotency_key,
    )


@router.post("/runs/{run_id}/record")
def run_record(run_id: str, body: S.RecordRequest, request: Request) -> dict:
    _run_or_404(run_id)
    return _submit(
        request,
        "record",
        run_id=run_id,
        params={"episode_seed": body.episode_seed, "checkpoint": body.checkpoint},
        key=body.idempotency_key,
    )


@router.get("/runs/{run_id}/files/{kind}/{name}")
def run_file(run_id: str, kind: str, name: str) -> FileResponse:
    paths = _run_or_404(run_id)
    bases = {"figures": paths.figures, "reports": paths.reports}
    if kind not in bases:
        raise HTTPException(404)
    try:
        p = safe_child(bases[kind], name)
    except ValueError as exc:
        raise HTTPException(400, "invalid file name") from exc
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(p)


# --------------------------------------------------------------------------- #
# Jobs, demos, queue
# --------------------------------------------------------------------------- #


@router.get("/jobs")
def list_jobs(request: Request, active: bool = False, limit: int = 50) -> list[dict]:
    states = ("queued", "starting", "running", "stop_requested") if active else None
    return db(request).list_jobs(states=states, limit=max(1, min(limit, 500)))


@router.get("/jobs/{job_id}")
def get_job(job_id: str, request: Request) -> dict:
    j = db(request).get_job(job_id)
    if not j:
        raise HTTPException(404, "unknown job")
    return j


@router.get("/jobs/{job_id}/log")
def job_log(job_id: str, request: Request, lines: int = 80) -> PlainTextResponse:
    j = db(request).get_job(job_id)
    if not j:
        raise HTTPException(404, "unknown job")
    return PlainTextResponse(tail(job_dir(job_id) / "worker.log", max(1, min(lines, 400))))


@router.post("/jobs/{job_id}/stop")
def stop_job(job_id: str, request: Request) -> dict:
    try:
        return jobs(request).request_stop(job_id)
    except JobNotFound as exc:
        raise HTTPException(404, "unknown job") from exc


@router.post("/jobs/{job_id}/terminate")
def terminate_job(job_id: str, request: Request) -> dict:
    try:
        return jobs(request).force_terminate(job_id)
    except JobNotFound as exc:
        raise HTTPException(404, "unknown job") from exc
    except JobConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/queue")
def set_queue(body: S.QueueRequest, request: Request) -> dict:
    jobs(request).set_queue_paused(body.paused)
    return {"queue_paused": jobs(request).queue_paused}


@router.post("/demos")
def demo(body: S.DemoRequest, request: Request) -> dict:
    return _submit(
        request, "record_demo", params=body.model_dump(exclude={"idempotency_key"}), key=body.idempotency_key
    )


@router.post("/benchmark")
def benchmark(body: S.BenchmarkRequest, request: Request) -> dict:
    return _submit(
        request, "benchmark", params={"n_envs": body.n_envs, "ppo": body.ppo}, key=body.idempotency_key
    )


# --------------------------------------------------------------------------- #
# Recordings and the Reward Stress Test
# --------------------------------------------------------------------------- #


@router.get("/recordings")
def recordings() -> list[dict]:
    return list_recordings()


def _recording(recording_id: str) -> tuple[Path, Path, dict]:
    try:
        tpath, vdir = find_recording(recording_id)
    except KeyError as exc:
        raise HTTPException(404, "unknown recording") from exc
    data = read_json(tpath)
    if not data:
        raise HTTPException(404, "recording telemetry unreadable")
    return tpath, vdir, data


@router.get("/recordings/{recording_id}")
def recording(recording_id: str) -> dict:
    return _recording(recording_id)[2]


@router.get("/recordings/{recording_id}/video")
def recording_video(recording_id: str) -> FileResponse:
    _, vdir, data = _recording(recording_id)
    if data["video"]["format"] != "mp4-h264":
        raise HTTPException(404, "this recording was saved as JPEG frames")
    p = safe_child(vdir, data["video"]["file"])
    if not p.is_file():
        raise HTTPException(404, "video file missing")
    return FileResponse(p, media_type="video/mp4")


@router.get("/recordings/{recording_id}/frames/{index}")
def recording_frame(recording_id: str, index: int) -> FileResponse:
    _, vdir, data = _recording(recording_id)
    if data["video"]["format"] != "jpeg-frames" or not (0 <= index < data["n_frames"]):
        raise HTTPException(404)
    p = safe_child(safe_child(vdir, data["video"]["file"]), f"{index:06d}.jpg")
    return FileResponse(p, media_type="image/jpeg")


@router.post("/recordings/{recording_id}/rescore")
def recording_rescore(recording_id: str, body: S.RescoreRequest, request: Request) -> dict:
    _, _, data = _recording(recording_id)
    configs = [preset(p) for p in body.presets]
    for cid in body.config_ids:
        try:
            configs.append(RewardConfig.model_validate(db(request).get_reward_config(cid)["config"]))
        except KeyError as exc:
            raise HTTPException(404, f"unknown reward configuration {cid}") from exc
    if not configs:
        raise HTTPException(400, "choose at least one reward configuration")
    return rescore(data, configs, gamma=body.gamma, detector=EvalProtocol().hover_detector)


# --------------------------------------------------------------------------- #
# Experiments, comparison, reports
# --------------------------------------------------------------------------- #


@router.get("/experiments")
def experiments() -> list[dict]:
    return list_experiments()


@router.get("/experiments/{experiment_id}")
def experiment(experiment_id: str) -> dict:
    try:
        exp = load_experiment(experiment_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(404, "unknown experiment") from exc
    exp["runs"] = [light_summary(cached_summary(r)) for r in exp["run_ids"] if RunPaths(r).exists()]
    return exp


def _suite_rewards(body: S.SuitePlan, request: Request) -> list[RewardConfig]:
    out = [preset(p) for p in body.presets]
    for cid in body.config_ids:
        try:
            out.append(RewardConfig.model_validate(db(request).get_reward_config(cid)["config"]))
        except KeyError as exc:
            raise HTTPException(404, f"unknown reward configuration {cid}") from exc
    if not out:
        raise HTTPException(400, "choose at least one reward configuration")
    return out


@router.post("/experiments/plan")
def experiment_plan(body: S.SuitePlan, request: Request) -> dict:
    rewards = _suite_rewards(body, request)
    bench = read_json(data_dir() / "benchmark.json", default={}) or {}
    tps = (bench.get("default_config") or {}).get("ppo_tps")
    plan = plan_suite([r.preset for r in rewards], body.seeds, body.profile, throughput_tps=tps)
    plan["throughput_source"] = "data/benchmark.json" if tps else None
    return plan


@router.post("/experiments", status_code=201)
def experiment_create(body: S.SuiteCreate, request: Request) -> dict:
    rewards = _suite_rewards(body, request)
    plan = plan_suite([r.preset for r in rewards], body.seeds, body.profile)
    if plan["n_runs"] > 6 and not body.confirm_large:
        raise HTTPException(400, f"this creates {plan['n_runs']} runs; confirm_large=true is required")
    if body.profile == "extended" and not body.confirm_large:
        raise HTTPException(400, "EXTENDED suites need explicit confirmation")
    exp = create_experiment(
        name=body.name, rewards=rewards, seeds=body.seeds, profile=body.profile, description=body.description
    )
    submitted = []
    if body.start:
        for rid in exp["run_ids"]:
            submitted.append(_submit(request, "train", run_id=rid))
    return exp | {"jobs": submitted}


@router.post("/compare")
def compare(body: S.CompareRequest) -> dict:
    for r in body.run_ids:
        _run_or_404(r)
    data = compare_runs(body.run_ids, split=body.split)
    data["curves"] = {r: training_curve(r, max_points=250) for r in body.run_ids}
    return data


@router.post("/reports")
def report(body: S.ReportRequest, request: Request) -> dict:
    run_ids = list(body.run_ids)
    if body.experiment_id:
        try:
            run_ids += load_experiment(body.experiment_id)["run_ids"]
        except (KeyError, ValueError) as exc:
            raise HTTPException(404, "unknown experiment") from exc
    run_ids = [r for r in dict.fromkeys(run_ids) if RunPaths(r).exists()]
    if not run_ids:
        raise HTTPException(400, "no runs selected")
    report_id = new_id("report", body.experiment_id or "")
    return _submit(
        request,
        "report",
        params={"run_ids": run_ids, "title": body.title, "report_id": report_id, "split": body.split},
        key=body.idempotency_key,
    )


@router.get("/reports")
def reports() -> list[dict]:
    out = []
    root = reports_dir()
    for d in sorted(root.iterdir(), reverse=True) if root.exists() else []:
        if d.is_dir() and (d / "report.html").exists():
            out.append(
                {
                    "report_id": d.name,
                    "files": sorted(p.name for p in d.iterdir() if p.is_file()),
                    "modified": (d / "report.html").stat().st_mtime,
                }
            )
    return out


@router.get("/reports/{report_id}/{name}")
def report_file(report_id: str, name: str) -> FileResponse:
    try:
        validate_run_id(report_id)
        p = safe_child(safe_child(reports_dir(), report_id), name)
    except ValueError as exc:
        raise HTTPException(400, "invalid path") from exc
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(p)


# --------------------------------------------------------------------------- #
# Shutdown (used by scripts/stop.ps1)
# --------------------------------------------------------------------------- #


@router.post("/shutdown")
def shutdown(request: Request) -> dict:
    server = getattr(request.app.state, "uvicorn_server", None)
    if server is None:
        raise HTTPException(409, "not running under the LunarLab launcher")
    server.should_exit = True
    return {"status": "shutting down", "note": "running jobs are asked to stop at a safe boundary first"}


@router.get("/runs/{run_id}/estimate")
def run_estimate(run_id: str) -> dict:
    cfg = load_config(run_id)
    bench = read_json(data_dir() / "benchmark.json", default={}) or {}
    tps = (bench.get("default_config") or {}).get("ppo_tps")
    planned = actual_budget(cfg.training.total_transitions, cfg.ppo.rollout_size)
    return {
        "planned_transitions": planned,
        "throughput_tps": tps,
        "hours": (planned / tps / 3600) if tps else None,
    }
