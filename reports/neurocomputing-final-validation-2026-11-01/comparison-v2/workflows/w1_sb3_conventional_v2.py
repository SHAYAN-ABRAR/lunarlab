# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""W1: the conventional Stable-Baselines3 evaluation of a neutral audit case, with no custom audit checks.

    python w1_sb3_conventional_v2.py CASE_DIR

This is what a competent SB3 user writes to evaluate a saved policy. It loads the model with ``PPO.load``,
which validates the archive and prints the saved and the current system information. It reads the
environment and test seeds from the saved configuration. It evaluates the deterministic policy once per
test seed in a ``Monitor``-wrapped environment. ``Monitor`` is innermost, so it records the original
episode reward and length. Results are the mean and standard deviation of the return and the time-limit
completion rate. Seeds go to ``reset(seed=int(seed))``, as is common.

The specification's checks (digests, dependencies, recorded-evaluation consistency, the seed contract,
finite parameters, reward channels, the accounting identity, the potential convention, the outcome
schema, replay comparison) are not part of SB3's evaluation tools. They are reported as unsupported.
Prints one JSON object on stdout; exit status 4 ("unchecked").

Follow-up version 2 (1 November 2026) of the hashed ``workflows/w1_sb3_conventional.py``, which is unchanged.
The only change is the optional process-memory telemetry: where the operating system does not expose
this process to psutil, ``peak_rss_bytes_self`` is null and ``peak_rss_status`` gives the reason, instead
of the program ending before it prints its result. See ``../CHANGES.diff``.
"""

from __future__ import annotations

import contextlib
import json
import sys
import time
from pathlib import Path

import gymnasium as gym
import numpy as np
import psutil
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor

UNSUPPORTED = {
    "S1": "SB3 neither records nor verifies a checkpoint digest; PPO.load only validated and loaded the archive",
    "S2": "no dependency or record files are verified",
    "S3": "the saved configuration is used for evaluation, not compared with a recorded evaluation",
    "S4": "seeds are passed to reset(seed=int(seed)); int() converts floats and numeric strings without notice",
    "S5": "reward parameters are not read: the evaluation uses the original reward only",
    "S6": "the recorded evaluation is not read",
    "S7": "the recorded evaluation is not read",
    "S8": "reward terms are not re-scored",
    "S9": "no outcome schema is compared",
    "S10": "results are not compared with the recorded evaluation",
}


def peak_rss() -> tuple[int | None, str]:
    """This process's peak working set (Windows) or resident set (elsewhere) at exit, in bytes, and its status.

    When memory is available, the value is the one the hashed program reports. It is optional telemetry: where
    the operating system does not expose this process to psutil (``NoSuchProcess``, ``AccessDenied``), the value
    is None and the status gives the reason. It is never replaced by zero. Other errors are not caught.
    """
    try:
        info = psutil.Process().memory_info()
    except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
        return None, f"unavailable: {type(exc).__name__}: {exc}"
    for field in ("peak_wset", "rss"):
        value = getattr(info, field, None)
        if value:
            return int(value), f"measured: {field}"
    return None, "unavailable: psutil reported neither peak_wset nor rss"


def main() -> int:
    t0 = time.perf_counter()
    torch.set_num_threads(1)
    case_dir = Path(sys.argv[1])
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    with contextlib.redirect_stdout(sys.stderr):  # SB3 prints the saved and the current system information
        model = PPO.load(case_dir / case["policy"]["file"], device="cpu", print_system_info=True)
    env = Monitor(gym.make(case["environment"]["id"], **case["environment"]["kwargs"]))
    returns, lengths, completed = [], [], 0
    for seed in case["protocol"]["test_seeds"]:
        obs, _ = env.reset(seed=int(seed))
        while True:
            action, _ = model.predict(obs, deterministic=True)
            obs, _reward, terminated, truncated, info = env.step(action)
            if terminated or truncated:
                break
        returns.append(float(info["episode"]["r"]))
        lengths.append(int(info["episode"]["l"]))
        completed += bool(truncated and not terminated)
    env.close()
    seconds = time.perf_counter() - t0
    rss, rss_status = peak_rss()
    result = {
        "workflow": "W1",
        "case": case.get("case"),
        "checks": {k: {"status": "unsupported", "detail": v} for k, v in UNSUPPORTED.items()},
        "verdict": "unchecked",
        "episodes_executed": len(returns),
        "execution_started_before_failure": None,
        "mean_original_return": float(np.mean(returns)),
        "std_original_return": float(np.std(returns)),
        "mean_length": float(np.mean(lengths)),
        "completion_rate": completed / len(returns),
        "seconds": seconds,
        "peak_rss_bytes_self": rss,
        "peak_rss_status": rss_status,
    }
    print(json.dumps(result))
    return 4


if __name__ == "__main__":
    sys.exit(main())
