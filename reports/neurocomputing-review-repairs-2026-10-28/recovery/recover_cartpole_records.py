# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Inventory of the CartPole run records that the repository and the review package omitted.

    python reports/neurocomputing-review-repairs-2026-10-28/recovery/recover_cartpole_records.py EVIDENCE_DIR OUT_DIR

Every file a study index (``records/{main,pilot}/study.json``) names is checked, in two candidate locations:

- **the repository copy:** ``reports/neurocomputing-2026-10-27/cartpole-study/records/<part>/runs/<run>/``. It is
  present on the recording machine but was ignored by Git.
- **the original output:** ``EVIDENCE_DIR/cartpole-study/<part>/runs/<run>/``, the study runner's own output
  directory, kept outside the repository with the checkpoints.

Each copy's SHA-256 is compared with every digest recorded for that file before the omission was found:

- the study index;
- the analysis output (``results.json`` ``inputs_sha256``);
- the exported artifact's manifest. Its ``evaluation.json`` is a byte copy of ``test-selected.json``.

Nothing is copied, normalised or rewritten here. The script only reads and reports.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "reports/neurocomputing-2026-10-27/cartpole-study"
RESULTS = {"main": STUDY / "results/results.json", "pilot": STUDY / "pilot-results/results.json"}
ARTIFACT_NAME = {
    "run.json": "run.json",
    "protocol.json": "protocol.json",
    "test-selected.json": "evaluation.json",
}


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(evidence: Path, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for part in ("main", "pilot"):
        index = json.loads((STUDY / f"records/{part}/study.json").read_text(encoding="utf-8"))
        analysed = {}
        if RESULTS[part].is_file():
            analysed = json.loads(RESULTS[part].read_text(encoding="utf-8")).get("inputs_sha256", {})
        for run in index["runs"]:
            name = run["run"]
            manifest_path = STUDY / f"records/{part}/artifacts/{name}/manifest.json"
            manifest = (
                json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
            )
            for fname, expected in sorted(run["files"].items()):
                rel = f"records/{part}/runs/{name}/{fname}"
                recorded = {"study.json": expected}
                if f"runs/{name}/{fname}" in analysed:
                    recorded["results.json inputs_sha256"] = analysed[f"runs/{name}/{fname}"]
                art = manifest.get("files", {}).get(ARTIFACT_NAME.get(fname, ""), {})
                if art:
                    recorded[f"artifact manifest ({ARTIFACT_NAME[fname]})"] = art["sha256"]
                repo_copy = sha256(STUDY / rel)
                original = sha256(evidence / f"cartpole-study/{part}/runs/{name}/{fname}")
                records_agree = len(set(recorded.values())) == 1
                status = (
                    "recovered"
                    if records_agree and repo_copy == expected and original == expected
                    else "recovered (repository copy only)"
                    if records_agree and repo_copy == expected
                    else "recovered (original output only)"
                    if records_agree and original == expected
                    else "UNRESOLVED"
                )
                rows.append(
                    {
                        "file": rel,
                        "expected_sha256": expected,
                        "recorded_digests": recorded,
                        "recorded_digests_agree": records_agree,
                        "repository_copy_sha256": repo_copy,
                        "original_output_sha256": original,
                        "status": status,
                    }
                )
    summary = {
        "expected": len(rows),
        "recovered_both_copies_match": sum(r["status"] == "recovered" for r in rows),
        "recovered_one_copy": sum(r["status"].startswith("recovered (") for r in rows),
        "unresolved": [r["file"] for r in rows if r["status"] == "UNRESOLVED"],
        "recorded_digest_disagreements": [r["file"] for r in rows if not r["recorded_digests_agree"]],
    }
    (out / "inventory.json").write_text(
        json.dumps({"summary": summary, "files": rows}, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    lines = [
        "# CartPole run records: recovery inventory",
        "",
        f"Expected files (named by the two study indexes): {summary['expected']}. Both copies match every recorded "
        f"digest: {summary['recovered_both_copies_match']}. One copy matches: {summary['recovered_one_copy']}. "
        f"Unresolved: {len(summary['unresolved'])}. Recorded digests disagreeing with each other: "
        f"{len(summary['recorded_digest_disagreements'])}.",
        "",
        "| File | Recorded digest | Records agreeing | Repository copy | Original output | Status |",
        "|---|---|---:|---|---|---|",
    ]
    for r in rows:
        mark = lambda h, e=r["expected_sha256"]: (
            "missing" if h is None else ("match" if h == e else f"DIFFERS {h[:12]}")
        )  # noqa: E731
        lines.append(
            f"| `{r['file']}` | `{r['expected_sha256'][:16]}…` | {len(r['recorded_digests'])} | "
            f"{mark(r['repository_copy_sha256'])} | {mark(r['original_output_sha256'])} | {r['status']} |"
        )
    (out / "INVENTORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=1))
    return 0 if not summary["unresolved"] and not summary["recorded_digest_disagreements"] else 1


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
