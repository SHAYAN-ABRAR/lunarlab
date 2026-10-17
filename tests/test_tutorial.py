# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""The tutorial is executable: every LunarLab command in docs/TUTORIAL.md runs, in order, in a fresh home.

Placeholders (<run_id>, <recording_id>, <experiment_id>) are filled with the IDs the earlier commands created,
exactly as a reader would copy them.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TUTORIAL = ROOT / "docs" / "TUTORIAL.md"
COMMAND = re.compile(r"\.venv[\\/](?:Scripts[\\/]python\.exe|bin[\\/]python) -m lunarlab (.+)$")


def tutorial_commands() -> list[str]:
    fenced, out = False, []
    for line in TUTORIAL.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        m = COMMAND.search(line) if fenced else None
        if m:
            out.append(m.group(1).split(" #")[0].strip())
    return out


def test_tutorial_has_the_documented_steps():
    cmds = tutorial_commands()
    assert len(cmds) >= 20
    for needed in ("doctor", "reproduce-smoke", "train", "evaluate", "reward export", "record", "rescore",
                   "suite", "compare", "report", "results", "export-artifact", "reproduce-artifact"):  # fmt: skip
        assert any(c.startswith(needed) for c in cmds), needed


@pytest.mark.slow
def test_every_tutorial_command_runs_in_order(tmp_path, monkeypatch):
    from lunarlab.cli import main
    from lunarlab.experiments import list_experiments
    from lunarlab.recording import list_recordings
    from lunarlab.storage import list_run_ids

    monkeypatch.chdir(tmp_path)  # files the tutorial writes (my-reward.yaml, my-results, …) land here
    artifacts = (ROOT / "examples" / "artifacts").as_posix() + "/"
    state: dict[str, str] = {}
    ran = []
    for cmd in tutorial_commands():
        cmd = cmd.replace("\\", "/").replace("examples/artifacts/", artifacts)
        for key, value in state.items():
            cmd = cmd.replace(f"<{key}>", value)
        assert "<" not in cmd, f"unresolved placeholder in `{cmd}` (known: {state})"
        runs = set(list_run_ids())
        recordings = {r["recording_id"] for r in list_recordings()}
        experiments = {e["experiment_id"] for e in list_experiments()}
        try:
            code = main(shlex.split(cmd))
        except SystemExit as exc:  # argparse handles --version itself
            code = exc.code
        # The supplied artifacts were recorded on Windows: elsewhere `reproduce-artifact` may report (exit 1)
        # that episodes differ, which is a result, not a failure of the command. Exact cross-platform
        # agreement is not claimed; CI records it separately.
        allowed = (
            (0, None, 1)
            if cmd.startswith("reproduce-artifact --artifact ") and "examples/" in cmd
            else (0, None)
        )
        assert code in allowed, f"`python -m lunarlab {cmd}` exited with {code}"
        ran.append(cmd)
        new_runs = sorted(set(list_run_ids()) - runs)
        if new_runs and "run_id" not in state:
            state["run_id"] = new_runs[0]
        new_recordings = sorted({r["recording_id"] for r in list_recordings()} - recordings)
        if new_recordings:
            state["recording_id"] = new_recordings[-1]
        new_experiments = sorted({e["experiment_id"] for e in list_experiments()} - experiments)
        if new_experiments:
            state["experiment_id"] = new_experiments[-1]
    assert len(ran) == len(tutorial_commands())
    assert (tmp_path / "my-reward.yaml").exists() and (tmp_path / "my-artifact" / "artifact.json").exists()
    assert any((tmp_path / "my-results").iterdir())
