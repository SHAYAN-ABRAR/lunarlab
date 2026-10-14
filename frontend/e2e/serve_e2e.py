"""Start a LunarLab backend for browser tests on port 8766 with a fresh, disposable home.

The home lives in frontend/.e2e-home (git-ignored) and is wiped on every run, so browser
tests never read or modify real experiment data.
"""

import os
import shutil
import sys
from pathlib import Path

home = Path(__file__).resolve().parent.parent / ".e2e-home"
shutil.rmtree(home, ignore_errors=True)
home.mkdir(parents=True)
os.environ["LUNARLAB_HOME"] = str(home)

from lunarlab.server.main import serve  # noqa: E402

sys.exit(serve(port=8766))
