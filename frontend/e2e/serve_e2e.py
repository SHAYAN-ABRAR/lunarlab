# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Start a LunarLab backend for browser tests on port 8766 with a fresh, disposable home.

The home lives in frontend/.e2e-home (git-ignored) and is wiped on every run, so browser
tests never read or modify real experiment data.
"""

import os
import shutil
import stat
import sys
from pathlib import Path


def _remove_read_only(func, path, _exc):
    """Frozen final-test artifacts are read-only; clear the flag so the disposable home can be removed."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


home = Path(__file__).resolve().parent.parent / ".e2e-home"
if home.exists():
    shutil.rmtree(home, onexc=_remove_read_only)
home.mkdir(parents=True)
os.environ["LUNARLAB_HOME"] = str(home)

from lunarlab.server.main import serve  # noqa: E402

sys.exit(serve(port=8766))
