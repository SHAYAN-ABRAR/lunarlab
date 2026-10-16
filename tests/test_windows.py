"""Windows-relevant robustness: locked files, cross-process locks, atomic replacement, paths with spaces.

Windows refuses to replace or delete a file that another process holds open without
FILE_SHARE_DELETE (Python's default ``open``), which real-time antivirus scanners also do for a
moment with fresh files. A checkpoint save that meets such a lock must never corrupt the previous
valid checkpoint, register an incomplete artifact, or let a newer file pass for an older frozen one.
Most tests inject the failure (any OS); the ``real_process`` tests use a second Windows process.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from lunarlab.config import DQNConfig, EvalProtocol, PPOConfig, TrainingConfig
from lunarlab.rewards import preset
from lunarlab.runs import RunError, create_run, read_manifest, resolve_checkpoint
from lunarlab.storage import RunPaths, atomic_write_json, read_json, sha256_file

TINY_PROTOCOL = EvalProtocol(validation_seeds=[10_000], test_seeds=[20_000])
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows file-sharing semantics")


def _run(algo="ppo", total=512):
    return create_run(
        reward=preset("baseline"),
        seed=0,
        algo=algo,
        ppo=PPOConfig(n_envs=2, n_steps=64, batch_size=32),
        dqn=DQNConfig(buffer_size=1000, batch_size=32, net_arch=[32]) if algo == "dqn" else None,
        protocol=TINY_PROTOCOL,
        training=TrainingConfig(
            profile="custom", total_transitions=total, checkpoint_every=256, validation_every=256
        ),
    )


def _model(cfg):
    import lunarlab.training as tr

    venv = tr.build_vec_env(cfg)
    return tr, venv, tr.build_model(cfg, venv, "cpu")


def _hold_open(path: Path) -> subprocess.Popen:
    """A second process that opens ``path`` and keeps it open (no FILE_SHARE_DELETE on Windows)."""
    code = "import sys, time; f = open(sys.argv[1], 'rb'); print('ready', flush=True); time.sleep(60)"
    p = subprocess.Popen([sys.executable, "-c", code, str(path)], stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "ready"
    return p


@pytest.mark.slow
def test_a_locked_destination_never_corrupts_the_previous_checkpoint(monkeypatch):
    cfg = _run()
    tr, venv, model = _model(cfg)
    paths = RunPaths(cfg.run_id)
    try:
        first = tr.save_model_atomic(
            model,
            paths,
            "ckpt_0000000128.zip",
            kind="periodic",
            transitions=128,
            segment=0,
            config_hash=cfg.config_hash(),
            continuation="ppo",
        )
        before = sha256_file(paths.checkpoints / first["name"])

        def locked(*_a, **_k):
            raise PermissionError(5, "Access is denied")

        monkeypatch.setattr(tr, "replace_file", locked)
        second = tr.save_model_atomic(
            model,
            paths,
            "stop_0000000256.zip",
            kind="stop",
            transitions=256,
            segment=0,
            config_hash=cfg.config_hash(),
            continuation="ppo",
        )
    finally:
        venv.close()
    assert second["name"].startswith("stop_0000000256-") and second["name"] != "stop_0000000256.zip"
    assert sha256_file(paths.checkpoints / first["name"]) == before  # previous checkpoint untouched
    assert {c["name"] for c in read_manifest(paths)["checkpoints"]} == {first["name"], second["name"]}
    assert not list(paths.checkpoints.glob("*.tmp"))
    assert resolve_checkpoint(cfg.run_id, second["name"])[1]["sha256"] == second["sha256"]


@pytest.mark.slow
def test_a_failed_bundle_save_registers_nothing_and_leaves_no_partial_files(monkeypatch):
    import shutil

    cfg = _run(algo="dqn")
    tr, venv, model = _model(cfg)
    paths = RunPaths(cfg.run_id)
    try:
        model.learn(64)
        good = tr.save_model_atomic(
            model,
            paths,
            "ckpt_0000000064.zip",
            kind="periodic",
            transitions=64,
            segment=0,
            config_hash=cfg.config_hash(),
            continuation="dqn",
            total_timesteps_basis=cfg.planned_transitions,
        )
        manifest = read_manifest(paths)

        def locked(*_a, **_k):
            raise PermissionError(5, "Access is denied")

        def disk_full(*_a, **_k):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(tr, "replace_file", locked)
        monkeypatch.setattr(shutil, "copyfile", disk_full)
        with pytest.raises(OSError):
            tr.save_model_atomic(
                model,
                paths,
                "stop_0000000068.zip",
                kind="stop",
                transitions=68,
                segment=0,
                config_hash=cfg.config_hash(),
                continuation="dqn",
                total_timesteps_basis=cfg.planned_transitions,
            )
    finally:
        venv.close()
    assert read_manifest(paths) == manifest  # nothing new was published
    assert not list(paths.checkpoints.glob("*.tmp"))
    from lunarlab.continuation import read_continuation

    state, _ = read_continuation(paths, good)  # the previous bundle is still complete and valid
    assert state["num_timesteps"] == 64


@windows_only
@pytest.mark.slow
def test_real_process_holding_a_destination_file(monkeypatch):
    cfg = _run()
    tr, venv, model = _model(cfg)
    paths = RunPaths(cfg.run_id)
    orphan = paths.checkpoints / "stop_0000000256.zip"  # e.g. left behind by a crash, not in the manifest
    orphan.write_bytes(b"orphan")
    holder = _hold_open(orphan)
    monkeypatch.setattr(tr, "REPLACE_TIMEOUT_S", 0.5)
    try:
        entry = tr.save_model_atomic(
            model,
            paths,
            "stop_0000000256.zip",
            kind="stop",
            transitions=256,
            segment=0,
            config_hash=cfg.config_hash(),
            continuation="ppo",
        )
    finally:
        holder.kill()
        holder.wait()
        venv.close()
    assert entry["name"] != orphan.name and orphan.read_bytes() == b"orphan"
    assert sha256_file(paths.checkpoints / entry["name"]) == entry["sha256"]


@pytest.mark.slow
def test_the_frozen_artifact_is_read_only_and_never_overwritten():
    from lunarlab.evaluation import evaluate_run
    from lunarlab.freeze import _write_immutable_copy, resolve_frozen_checkpoint
    from lunarlab.training import EXIT_COMPLETED, train

    cfg = _run()
    paths = RunPaths(cfg.run_id)
    assert train(cfg.run_id, quiet=True) == EXIT_COMPLETED
    evaluate_run(cfg.run_id, "test")
    path, info = resolve_frozen_checkpoint(cfg.run_id)
    sha = info["checkpoint_sha256"]
    assert not os.access(path, os.W_OK)  # read-only on disk
    other = next(p for p in paths.checkpoints.glob("*.zip") if sha256_file(p) != sha)
    if sys.platform == "win32":
        # Windows refuses to replace a read-only file: a newer checkpoint cannot take its place.
        tmp = path.with_name("incoming.tmp")
        tmp.write_bytes(other.read_bytes())
        with pytest.raises(PermissionError):
            os.replace(tmp, path)
        tmp.unlink()
    assert sha256_file(path) == sha
    # Even if something does change the bytes, they are detected and never trusted or re-frozen.
    path.chmod(0o644)
    path.write_bytes(other.read_bytes())
    with pytest.raises(RunError, match="does not match"):
        resolve_frozen_checkpoint(cfg.run_id)
    with pytest.raises(RunError, match="refusing to overwrite"):
        _write_immutable_copy(other, paths, sha)
    with pytest.raises(RunError, match="does not match"):
        evaluate_run(cfg.run_id, "test")


@pytest.mark.slow
def test_another_process_holding_the_run_lock_blocks_training_and_final_tests():
    from lunarlab.evaluation import evaluate_run
    from lunarlab.training import EXIT_BUSY, EXIT_COMPLETED, train

    cfg = _run()
    assert train(cfg.run_id, quiet=True) == EXIT_COMPLETED
    lock_path = RunPaths(cfg.run_id).lock
    code = (
        "import sys, time; from pathlib import Path; from lunarlab.locks import FileLock; "
        "held = FileLock(Path(sys.argv[1])).acquire(); print('locked', flush=True); time.sleep(60)"
    )
    holder = subprocess.Popen([sys.executable, "-c", code, str(lock_path)], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "locked"
        with pytest.raises(RunError, match="busy"):
            evaluate_run(cfg.run_id, "test")
        assert train(cfg.run_id, quiet=True) == EXIT_BUSY
        other = _run()
        assert train(other.run_id, quiet=True) == EXIT_COMPLETED  # other runs are unaffected
    finally:
        holder.kill()
        holder.wait()
    time.sleep(0.2)  # the OS releases the lock with the process
    assert evaluate_run(cfg.run_id, "test")["split"] == "test"
    with pytest.raises(RunError, match="frozen"):  # and once tested, it never trains again
        train(cfg.run_id, quiet=True)


def test_atomic_json_write_keeps_the_old_file_when_the_replace_fails(tmp_path, monkeypatch):
    import lunarlab.storage as storage

    path = tmp_path / "meta.json"
    atomic_write_json(path, {"version": 1})

    def locked(*_a, **_k):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(storage, "_replace_with_retry", locked)
    with pytest.raises(PermissionError):
        atomic_write_json(path, {"version": 2})
    assert read_json(path) == {"version": 1}
    assert not [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]  # no partial file left


@windows_only
def test_powershell_scripts_parse():
    root = Path(__file__).resolve().parent.parent
    # Windows PowerShell 5.1, and PowerShell 7 when it is installed (CI parses with 7 as well).
    shells = ["powershell"] + (["pwsh"] if shutil.which("pwsh") else [])
    for shell in shells:
        for script in sorted((root / "scripts").glob("*.ps1")):
            cmd = (
                "$errs = $null; [System.Management.Automation.Language.Parser]::ParseFile("
                f"'{script}', [ref]$null, [ref]$errs) | Out-Null; if ($errs.Count) {{ $errs | ForEach-Object {{ $_.Message }}; exit 1 }}"
            )
            res = subprocess.run(
                [shell, "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True, text=True
            )
            assert res.returncode == 0, f"{shell} {script.name}: {res.stdout} {res.stderr}"


@windows_only
def test_powershell_scripts_avoid_escapes_that_powershell_7_reads_differently():
    # Windows PowerShell 5.1 reads `u and `e in double-quoted strings as plain letters; PowerShell 7 reads them as
    # Unicode and escape-character sequences, and a malformed `u is a parse error there (the whole script fails).
    root = Path(__file__).resolve().parent.parent
    for script in sorted((root / "scripts").glob("*.ps1")):
        cmd = (
            "$tokens = $null; $errs = $null; [System.Management.Automation.Language.Parser]::ParseFile("
            f"'{script}', [ref]$tokens, [ref]$errs) | Out-Null; "
            "$tokens | Where-Object { $_.Kind -like '*Expandable' -and $_.Text -cmatch '`[ue]' } | "
            "ForEach-Object { 'line ' + $_.Extent.StartLineNumber + ': ' + $_.Text }"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True, text=True
        )
        assert res.returncode == 0, f"{script.name}: {res.stderr}"
        assert res.stdout.strip() == "", f"{script.name}: {res.stdout}"


@pytest.mark.slow
def test_stop_resume_and_final_test_in_a_home_whose_path_has_spaces(tmp_path, monkeypatch):
    from lunarlab.evaluation import evaluate_run
    from lunarlab.training import EXIT_COMPLETED, EXIT_STOPPED, train

    home = tmp_path / "Lunar Lab home with spaces"
    home.mkdir()
    monkeypatch.setenv("LUNARLAB_HOME", str(home))
    for algo in ("ppo", "dqn"):
        cfg = _run(algo=algo, total=768)
        assert " " in str(RunPaths(cfg.run_id).root)
        assert train(cfg.run_id, quiet=True, on_validation=lambda n, _m: n >= 256) == EXIT_STOPPED
        assert train(cfg.run_id, resume=True, quiet=True) == EXIT_COMPLETED
        res = evaluate_run(cfg.run_id, "test")
        assert res["checkpoint"]["frozen"] is True
