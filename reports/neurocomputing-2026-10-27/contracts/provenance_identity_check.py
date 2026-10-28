# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Can the reward-provenance record tell apart two terms that declare the same description?

    python reports/neurocomputing-2026-10-27/contracts/provenance_identity_check.py

Prints, for three pairs of terms with equal descriptions that pay 1 and 1,000, whether the definition
digests are equal and whether the per-term implementation records differ. The first pair is the candidate
reproduced on 27 October (two lambdas in one class body, ``reproduce_candidates.py``). Run it with
``PYTHONPATH`` pointing at another source tree to check that tree's ``lunarlab``.
"""

from __future__ import annotations

import json
from pathlib import Path

import lunarlab
from lunarlab.audit import RewardTerm
from lunarlab.audit.provenance import PROVENANCE_SCHEMA, reward_provenance

DESC = {"type": "custom", "id": "bonus"}


class Custom:
    """As in reproduce_candidates.py: identical declared descriptions, different behaviour."""

    a = RewardTerm("bonus", lambda t: 1.0, {"type": "custom", "id": "bonus"})
    b = RewardTerm("bonus", lambda t: 1000.0, {"type": "custom", "id": "bonus"})


def paying(value: float):
    return lambda t: value


def pays_1(t):
    return 1.0


def pays_1000(t):
    return 1000.0


PAIRS = {
    "two lambdas in one class body (the reproduced candidate)": (Custom.a, Custom.b),
    "two closures of one factory": (
        RewardTerm("bonus", paying(1.0), DESC),
        RewardTerm("bonus", paying(1000.0), DESC),
    ),
    "two named functions": (RewardTerm("bonus", pays_1, DESC), RewardTerm("bonus", pays_1000, DESC)),
}

if __name__ == "__main__":
    origin = Path(lunarlab.__file__).resolve().parent
    print(f"lunarlab imported from a tree whose last two path parts are {'/'.join(origin.parts[-2:])}")
    print(f"schema {PROVENANCE_SCHEMA}")
    for label, (a, b) in PAIRS.items():
        ra, rb = reward_provenance({"bonus": a}, 1.0), reward_provenance({"bonus": b}, 1.0)
        same_definition = ra["definition_sha256"] == rb["definition_sha256"]
        ia = json.dumps(ra["terms"]["bonus"]["implementation"], sort_keys=True)
        ib = json.dumps(rb["terms"]["bonus"]["implementation"], sort_keys=True)
        verdict = "told apart" if ia != ib else "NOT told apart"
        print(f"{label}: definition digests equal: {same_definition}; implementation records {verdict}")
