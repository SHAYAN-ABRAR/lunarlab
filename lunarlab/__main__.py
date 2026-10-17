# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""``python -m lunarlab``. The guard matters on Windows: SubprocVecEnv uses spawn."""

import sys

from lunarlab.cli import main

if __name__ == "__main__":
    sys.exit(main())
