# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Derive the version-2 workflow programs from the hashed originals, by exact and listed replacements.

    python derive_v2_programs.py [--check]

The originals are ``workflows/*.py`` of ``reports/neurocomputing-2026-10-27/workflow-comparison/``. They are
fixed by that comparison's ``protocol/HASHES.sha256``, and this script refuses to run unless they still match
it. It never writes to them. Each replacement below must match exactly once.

The only change is the optional process-memory telemetry. The originals read ``psutil.Process().memory_info()``
when they finish; where the operating system does not expose the process to psutil, this raises
``NoSuchProcess`` and the program ends before it prints its result. In version 2 the value is null and a status
gives the reason; it is never replaced by zero. When memory is available, the value is the one the original
reports. Other errors are not caught, and no check, threshold, input or exit status changes. The docstrings
name the new files and say what changed.

Writes ``workflows/*_v2.py`` and ``CHANGES.diff``. With ``--check``, it writes nothing and exits 1 if either
differs from what the derivation produces.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parents[1] / "neurocomputing-2026-10-27" / "workflow-comparison"
PROGRAMS = ("w1_sb3_conventional", "w2_sb3_reference", "w3_lunarlab")

ORIGINAL_TELEMETRY = """def peak_rss() -> int:
    info = psutil.Process().memory_info()
    return int(getattr(info, "peak_wset", 0) or getattr(info, "rss", 0))
"""
V2_TELEMETRY = '''def peak_rss() -> tuple[int | None, str]:
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
'''


def note(program: str) -> str:
    return (
        f"\n\nFollow-up version 2 (1 November 2026) of the hashed ``workflows/{program}.py``, which is unchanged."
        "\nThe only change is the optional process-memory telemetry: where the operating system does not expose"
        "\nthis process to psutil, ``peak_rss_bytes_self`` is null and ``peak_rss_status`` gives the reason, instead"
        "\nof the program ending before it prints its result. See ``../CHANGES.diff``.\n"
    )


REPLACEMENTS: dict[str, list[tuple[str, str]]] = {
    "w1_sb3_conventional": [
        ("    python w1_sb3_conventional.py CASE_DIR\n", "    python w1_sb3_conventional_v2.py CASE_DIR\n"),
        (
            'Prints one JSON object on stdout; exit status 4 ("unchecked").\n"""',
            'Prints one JSON object on stdout; exit status 4 ("unchecked").'
            + note("w1_sb3_conventional")
            + '"""',
        ),
        (ORIGINAL_TELEMETRY, V2_TELEMETRY),
        (
            "    env.close()\n    result = {\n",
            "    env.close()\n    seconds = time.perf_counter() - t0\n    rss, rss_status = peak_rss()\n    result = {\n",
        ),
        (
            '        "seconds": time.perf_counter() - t0,\n        "peak_rss_bytes_self": peak_rss(),\n',
            '        "seconds": seconds,\n        "peak_rss_bytes_self": rss,\n        "peak_rss_status": rss_status,\n',
        ),
    ],
    "w2_sb3_reference": [
        ("    python w2_sb3_reference.py CASE_DIR\n", "    python w2_sb3_reference_v2.py CASE_DIR\n"),
        ('\n1 rejected.\n"""', "\n1 rejected." + note("w2_sb3_reference") + '"""'),
        (ORIGINAL_TELEMETRY, V2_TELEMETRY),
    ],
    "w3_lunarlab": [
        ("    python w3_lunarlab.py CASE_DIR\n", "    python w3_lunarlab_v2.py CASE_DIR\n"),
        (
            '3 permitted numerical difference, 1 rejected.\n"""',
            "3 permitted numerical difference, 1 rejected." + note("w3_lunarlab") + '"""',
        ),
        (ORIGINAL_TELEMETRY, V2_TELEMETRY),
    ],
}
FINAL_UPDATE = (
    "    result.update(seconds=time.perf_counter() - t0, peak_rss_bytes_self=peak_rss())\n",
    "    seconds = time.perf_counter() - t0\n"
    "    rss, rss_status = peak_rss()\n"
    "    result.update(seconds=seconds, peak_rss_bytes_self=rss, peak_rss_status=rss_status)\n",
)
REPLACEMENTS["w2_sb3_reference"].append(FINAL_UPDATE)
REPLACEMENTS["w3_lunarlab"].append(FINAL_UPDATE)

DIGEST_LINE = re.compile(r"^([0-9a-f]{64}) [ *](.+)$")


def recorded_digests() -> dict[str, str]:
    rows = {}
    for line in (FROZEN / "protocol" / "HASHES.sha256").read_text(encoding="utf-8").splitlines():
        m = DIGEST_LINE.match(line.strip())
        if m:
            rows[m.group(2).strip()] = m.group(1)
    return rows


def derive() -> tuple[dict[str, str], str]:
    """The version-2 program texts and the unified diff from the originals."""
    recorded = recorded_digests()
    programs, diff = {}, []
    for name in PROGRAMS:
        path = FROZEN / "workflows" / f"{name}.py"
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != recorded.get(f"workflows/{name}.py"):
            raise SystemExit(f"{path} does not match protocol/HASHES.sha256; refusing to derive from it")
        text = data.decode("utf-8")
        new = text
        for old, replacement in REPLACEMENTS[name]:
            if new.count(old) != 1:
                raise SystemExit(f"{name}: a replacement matches {new.count(old)} times, not once:\n{old}")
            new = new.replace(old, replacement)
        programs[f"{name}_v2.py"] = new
        diff += difflib.unified_diff(
            text.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"neurocomputing-2026-10-27/workflow-comparison/workflows/{name}.py",
            tofile=f"neurocomputing-final-validation-2026-11-01/comparison-v2/workflows/{name}_v2.py",
        )
    return programs, "".join(diff)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="verify the committed files; write nothing")
    a = ap.parse_args()
    programs, diff = derive()
    wanted = {HERE / "workflows" / n: t for n, t in programs.items()} | {HERE / "CHANGES.diff": diff}
    if a.check:
        stale = [p.name for p, t in wanted.items() if not p.is_file() or p.read_bytes() != t.encode("utf-8")]
        print(
            f"differs from the derivation: {stale}"
            if stale
            else "the version-2 programs and CHANGES.diff are current"
        )
        return 1 if stale else 0
    for path, text in wanted.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    print(f"wrote {', '.join(p.name for p in wanted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
