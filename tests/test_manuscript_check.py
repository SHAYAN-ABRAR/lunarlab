# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""The manuscript check: ``--draft`` lets a review build carry marked author items, ``--final`` never does.

The AI declaration and the CRediT statement wait for the author. A review draft may show them as "AUTHOR TO
CONFIRM" items, but only while every page carries the working-draft footer; the submission check
(``--final``) fails on any such item and on the footer itself.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "paper/neurocomputing/check_manuscript.py"
FIXED = r"""\author{Shayan Abrar}\ead{shayanabrar7@gmail.com}
\affiliation{organization={American International University-Bangladesh (AIUB)},
addressline={408/1 (Old KA 66/1), Kuratoli, Khilkhet},postcode={1229}}
The author declares no competing interests.
This research was self-funded. It received no specific grant from funding agencies in the public, commercial or not-for-profit sectors.
The author thanks American International University-Bangladesh (AIUB) for its institutional support.
"""


def manuscript(tmp_path: Path, *, footer: bool, declaration: str, body: str = "") -> Path:
    """A minimal manuscript directory beside a copy of the check, which reads the files next to itself."""
    folder = tmp_path / "neurocomputing"
    (folder / "figures").mkdir(parents=True)
    shutil.copy2(CHECK, folder / "check_manuscript.py")
    (folder / "figures/MANIFEST.json").write_text(json.dumps({}), encoding="utf-8")
    (folder / "references.bib").write_text("", encoding="utf-8")
    (folder / "declaration.tex").write_text(declaration, encoding="utf-8")
    style = r"\def\@oddfoot{Working draft, not submitted (\today)}" if footer else ""
    (folder / "main.tex").write_text(
        style
        + "\n\\begin{abstract}A short abstract.\\end{abstract}\n\\begin{keyword}one \\sep two\\end{keyword}\n"
        + FIXED
        + body
        + "\n\\input{declaration}\n",
        encoding="utf-8",
    )
    return folder


def check(folder: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(folder / "check_manuscript.py"), *flags], capture_output=True, text=True
    )


PENDING = "[AUTHOR TO CONFIRM: the review sentence]"


@pytest.mark.parametrize(
    ("footer", "declaration", "flag", "passes"),
    [
        (True, PENDING, "--draft", True),
        (False, PENDING, "--draft", False),
        (True, PENDING, "--final", False),
        (True, "Confirmed text.", "--final", False),
        (False, "Confirmed text.", "--final", True),
        (False, "% AUTHOR TO CONFIRM in a comment only\nConfirmed text.", "--final", True),
    ],
)
def test_pending_author_items_pass_only_as_a_marked_working_draft(
    tmp_path, footer, declaration, flag, passes
):
    result = check(manuscript(tmp_path, footer=footer, declaration=declaration), flag)
    assert (result.returncode == 0) is passes, result.stdout
    if "AUTHOR TO CONFIRM:" in declaration:
        assert "declaration.tex: 1 AUTHOR TO CONFIRM item(s) awaiting the author" in result.stdout


def test_an_item_in_main_tex_itself_is_counted(tmp_path):
    folder = manuscript(tmp_path, footer=False, declaration="Confirmed.", body=f"\nCRediT: {PENDING}\n")
    result = check(folder, "--final")
    assert result.returncode == 1 and "main.tex: 1 AUTHOR TO CONFIRM item(s)" in result.stdout


def test_an_escaped_percent_does_not_hide_an_item(tmp_path):
    folder = manuscript(tmp_path, footer=False, declaration=f"97.6\\% of episodes {PENDING}")
    assert check(folder, "--final").returncode == 1
