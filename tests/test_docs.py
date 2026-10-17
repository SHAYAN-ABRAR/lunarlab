# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Documentation stays executable: every documented CLI command parses with the real parser."""

from __future__ import annotations

import contextlib
import io
import re
import shlex
from pathlib import Path

import pytest

from lunarlab.cli import build_parser

ROOT = Path(__file__).resolve().parent.parent
# docs/api/ is generated from the parser itself (usage syntax such as "[-h]" is not a command line).
DOCS = sorted(
    p
    for p in {*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md"), *(ROOT / "paper").rglob("*.md")}
    if p != ROOT / "THIRD_PARTY_NOTICES.md" and "api" not in p.relative_to(ROOT).parts
)
COMMAND = re.compile(
    r"(?:python(?:\.exe)?|\.venv[\\/](?:Scripts[\\/]python\.exe|bin[\\/]python)|\$py|\$PY) -m lunarlab(?: (.*))?$"
)


def documented_commands() -> list[tuple[str, str]]:
    """Command lines inside fenced code blocks (prose mentions of a command name are not checked)."""
    found = []
    for doc in DOCS:
        fenced = False
        for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("```"):
                fenced = not fenced
                continue
            m = COMMAND.search(line) if fenced else None
            if not m:
                continue
            cmd = (m.group(1) or "").split(" #")[0]
            cmd = re.split(r"\s{2,}|\s\|\s|\s;\s|\s&&\s", cmd.strip())[0]  # comments, pipes, chained commands
            if "…" in cmd:
                continue
            cmd = re.sub(r"\s\.\.\.(?=\s|$)", "", cmd)  # "suite ... --parallel 5": elided options
            cmd = re.sub(r"<[^>]+>", "x1", cmd).strip().rstrip("`")
            found.append((f"{doc.relative_to(ROOT).as_posix()}:{lineno}", cmd))
    return found


COMMANDS = documented_commands()


def test_the_documentation_contains_commands():
    assert len(COMMANDS) > 60


@pytest.mark.parametrize(("where", "cmd"), COMMANDS, ids=[w for w, _ in COMMANDS])
def test_documented_command_parses(where, cmd):
    parser = build_parser()
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            parser.parse_args(shlex.split(cmd, posix=True))
    except SystemExit as exc:  # argparse exits 0 for --help / --version, 2 for errors
        assert exc.code in (0, None), f"{where}: `python -m lunarlab {cmd}` -> {err.getvalue().strip()}"
