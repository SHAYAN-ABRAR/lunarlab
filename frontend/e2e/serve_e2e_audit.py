"""Backend for the audit-repair browser tests (port 8767) with a disposable, pre-built home.

The home lives in frontend/.e2e-audit-home (git-ignored) and is rebuilt on every run, so these tests
never read or modify real experiment data. Fixture runs (tiny budgets, technical tests only) are
found by the tests through their labels:

* ``fixture: ppo resumable``          stopped at a safe boundary; a genuine resume is available
* ``fixture: dqn resumable``          the same for DQN (replay buffer and state stored)
* ``fixture: dqn legacy``             a DQN stop checkpoint without replay state, as older versions wrote
* ``fixture: dqn corrupt replay``     a DQN stop checkpoint whose replay archive was altered afterwards
* ``fixture: frozen, test interrupted``  frozen for the final test; its only attempt was interrupted
* ``fixture: legacy evaluation``      a tested run whose result is in the outcome-classifier-v1 format
"""

import contextlib
import os
import shutil
import stat
import sys
from pathlib import Path


def _remove_read_only(func, path, _exc):
    """Frozen final-test artifacts are read-only; clear the flag so the disposable home can be removed."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


home = Path(__file__).resolve().parent.parent / ".e2e-audit-home"
if home.exists():
    shutil.rmtree(home, onexc=_remove_read_only)
home.mkdir(parents=True)
os.environ["LUNARLAB_HOME"] = str(home)

from lunarlab.config import DQNConfig, EvalProtocol, PPOConfig, TrainingConfig  # noqa: E402
from lunarlab.evaluation import EvaluationAborted, evaluate_run  # noqa: E402
from lunarlab.recording import record_run  # noqa: E402
from lunarlab.rewards import preset  # noqa: E402
from lunarlab.runs import create_run, mutate_manifest, read_manifest  # noqa: E402
from lunarlab.storage import RunPaths, atomic_write_json, read_json  # noqa: E402
from lunarlab.training import train  # noqa: E402

PROTOCOL = EvalProtocol(validation_seeds=[10_000], test_seeds=[20_000, 20_001])


def run(label: str, algo: str = "ppo", total: int = 768):
    return create_run(
        reward=preset("baseline"),
        seed=0,
        algo=algo,
        label=label,
        ppo=PPOConfig(n_envs=2, n_steps=64, batch_size=32),
        dqn=DQNConfig(buffer_size=1000, batch_size=32, net_arch=[32]) if algo == "dqn" else None,
        protocol=PROTOCOL,
        training=TrainingConfig(
            profile="custom", total_transitions=total, checkpoint_every=256, validation_every=256
        ),
    )


def stopped(label: str, algo: str = "ppo"):
    cfg = run(label, algo)
    train(cfg.run_id, quiet=True, on_validation=lambda n, _m: n >= 256)
    return cfg


stopped("fixture: ppo resumable")
dqn_ok = stopped("fixture: dqn resumable", "dqn")
record_run(dqn_ok.run_id, episode_seed=20_000, checkpoint="best")

legacy = stopped("fixture: dqn legacy", "dqn")


def strip(manifest: dict) -> None:
    for c in manifest["checkpoints"]:
        for k in ("resumable", "continuation", "role"):
            c.pop(k, None)


mutate_manifest(RunPaths(legacy.run_id), strip)

corrupt = stopped("fixture: dqn corrupt replay", "dqn")
stop = next(c for c in read_manifest(RunPaths(corrupt.run_id))["checkpoints"] if c["kind"] == "stop")
replay = RunPaths(corrupt.run_id).checkpoints / stop["continuation"]["replay_file"]
data = replay.read_bytes()
replay.write_bytes(data[:-4] + b"XXXX")

frozen = run("fixture: frozen, test interrupted", total=256)
train(frozen.run_id, quiet=True)
with contextlib.suppress(EvaluationAborted):  # a final test interrupted after the freeze
    evaluate_run(frozen.run_id, "test", should_stop=lambda: True)

old = run("fixture: legacy evaluation", total=256)
train(old.run_id, quiet=True)
res = evaluate_run(old.run_id, "test")
path = RunPaths(old.run_id).evaluations / res["file"]
r = read_json(path)
r.pop("outcome_classifier_version", None)
r["aggregate"].pop("outcome_classifier_version", None)
r["aggregate"].pop("landing_categories", None)
for ep in r["episodes"]:
    for k in (
        "landing_category",
        "pad_geography",
        "strict_failures",
        "on_pad_not_strict",
        "leg_x_world",
        "helipad_x_world",
        "outcome_classifier_version",
    ):
        ep.pop(k, None)
atomic_write_json(path, r)

from lunarlab.server.main import serve  # noqa: E402

sys.exit(serve(port=8767))
