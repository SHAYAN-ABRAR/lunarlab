"""Independent read-only verification of the supplied LunarLab review return."""

import argparse
import ast
import hashlib
import json
import math
import statistics as S
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from lunarlab.config import RunConfig
from lunarlab.storage import read_yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--return-dir",
    type=Path,
    required=True,
    help="Extracted original return folder containing SUMMARY.md",
)
parser.add_argument(
    "--source-dir",
    type=Path,
    required=True,
    help="Source reconstructed from base 67440c6 plus the ORIGINAL followup.patch, before this review patch",
)
parser.add_argument(
    "--out",
    type=Path,
    required=True,
    help="New analysis output directory; input files are not modified",
)
parser.add_argument(
    "--prior-review-source",
    type=Path,
    help="Optional preceding reviewer source for syntax-only formatting comparison",
)
args = parser.parse_args()
R = args.return_dir.resolve()
W = args.source_dir.resolve()
V = args.out.resolve()
V.mkdir(parents=True, exist_ok=True)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def close(x, y):
    assert math.isclose(x, y, rel_tol=0, abs_tol=1e-9), (x, y)


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


results = read(W / "docs/results/results.json")
arts = {}
originals = {}
deps = []
payloads = 0
accounting = 0
for p in (R / "study-artifacts").glob("*/*/artifact.json"):
    m = read(p)
    d = p.parent
    cfg = RunConfig.model_validate(read_yaml(d / "config.yaml"))
    e = read(d / "evaluation.json")
    rid = m["source_run_id"]
    arts[rid] = (d, cfg, e)
    for name, info in m["files"].items():
        assert sha(d / name) == info["sha256"]
        payloads += 1
        originals[info["source"]] = d / name
    frozen = read(d / "provenance/metadata.json")["frozen_for_test"]
    assert (
        m["files"]["checkpoint.zip"]["sha256"]
        == e["checkpoint"]["sha256"]
        == frozen["checkpoint_sha256"]
    )
    assert m["files"]["checkpoint.zip"]["checkpoint_name"] == frozen["checkpoint"]
    assert cfg.config_hash() == m["config_hash"]
    assert cfg.reward.content_hash() == m["reward"]["hash"] == e["reward_hash"]
    assert cfg.eval_protocol.protocol_hash() == m["protocol_hash"] == e["protocol_hash"]
    eps = e["episodes"]
    seeds = [x["seed"] for x in eps]
    assert len(eps) == len(set(seeds)) == 100
    assert sorted(seeds) == sorted(e["seeds"]) == sorted(cfg.eval_protocol.test_seeds)
    assert not set(seeds) & set(cfg.eval_protocol.validation_seeds)
    close(
        S.mean(x["original_return"] for x in eps),
        e["aggregate"]["original_return"]["mean"],
    )
    close(
        S.mean(x["training_return"] for x in eps),
        e["aggregate"]["training_reward_rescored"]["return"]["mean"],
    )
    for x in eps:
        close(
            x["training_return"],
            cfg.reward.original_weight * x["original_return"]
            + sum(x["term_returns"].values()),
        )
        accounting += 1
    if cfg.reward.learned.enabled:
        deps.append(
            {
                "run_id": rid,
                "model_id": cfg.reward.learned.model_id,
                "bundled": (d / "reward_model/model.npz").exists(),
            }
        )
    for f in (d / "provenance").rglob("*"):
        if f.is_file():
            originals[f"runs/{rid}/{f.relative_to(d / 'provenance').as_posix()}"] = f
rows = []
for g in results["groups"]:
    scores = []
    lands = 0
    timeouts = 0
    train = []
    for r in g["per_seed"]:
        d, cfg, e = arts[r["run_id"]]
        eps = e["episodes"]
        p = r["evaluation"]
        scores.append(S.mean(x["original_return"] for x in eps))
        n = len(eps)
        close(scores[-1], p["mean_original_return"])
        close(
            S.mean(x["training_return"] for x in eps),
            p["training_return_rescored_mean"],
        )
        l = sum(bool(x["pad_landing"]) for x in eps)
        t = sum(x["env_outcome"] == "timeout" for x in eps)
        lands += l
        timeouts += t
        close(l / n, p["pad_landing_rate"])
        close(t / n, p["timeout_rate"])
        train.extend(x["training_return"] for x in eps)
    ordered = sorted(scores)
    k = len(scores) // 4
    iqm = S.mean(ordered[k : len(scores) - k])
    close(iqm, results["robust_stats"]["groups"][g["reward_name"]]["iqm"])
    rows.append(
        {
            "group": g["reward_name"],
            "policies": len(scores),
            "episodes": 100 * len(scores),
            "iqm": iqm,
            "landings": lands,
            "timeouts": timeouts,
            "mean_training_return": S.mean(train),
        }
    )
assert len(arts) == 38 and accounting == 3800 and len(rows) == 10
# Compare the nested study ZIP to its supplied extracted files.
inner = next(R.glob("lunarlab-study-artifacts-*.zip"))
count = 0
with zipfile.ZipFile(inner) as z:
    assert z.testzip() is None
    for n in z.namelist():
        if n.endswith("/"):
            continue
        parts = Path(n).parts
        options = [
            R / n,
            R / "study-artifacts" / Path(*parts[1:]),
            R / "study-artifacts" / n,
        ]
        targets = [p for p in options if p.is_file()]
        assert targets, n
        assert any(z.read(n) == p.read_bytes() for p in targets)
        count += 1
# Source archive is independently matched to reconstructed source, not merely its own manifest.
folder = R / "source/candidate"
manifest = read(folder / "lunarlab-0.1.0-src.manifest.json")
archive = folder / manifest["archive"]["file"]
assert sha(archive) == manifest["archive"]["sha256"]
with tarfile.open(archive) as t:
    for entry in manifest["files"]:
        name = entry["path"]
        data = t.extractfile("lunarlab-0.1.0/" + name).read()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
        assert data == (W / name).read_bytes(), name
assert len(manifest["files"]) == 425
# Recompute timing ratios using means of durations and sample SD of throughput.
bench = R / "benchmark/standard-2026-10-19T180346+0000"
raw = [json.loads(x) for x in (bench / "raw.jsonl").read_text().splitlines() if x]
assert len(raw) == 9
assert {x["transitions"] for x in raw} == {102400}
assert len({json.dumps(x["hyperparameters"], sort_keys=True) for x in raw}) == 1
meta = read(bench / "summary.json")["meta"]
assert meta["equivalent_hyperparameters"]
baseloop = S.mean(x["loop_s"] for x in raw if x["config"] == "sb3")
basewall = S.mean(x["wall_s"] for x in raw if x["config"] == "sb3")
benchmark = {}
for c in ["sb3", "accounting", "lunarlab"]:
    rr = [x for x in raw if x["config"] == c]
    assert len(rr) == 3
    speed = [x["transitions"] / x["loop_s"] for x in rr]
    benchmark[c] = {
        "n": 3,
        "transitions_per_s": S.mean(speed),
        "sample_sd": S.stdev(speed),
        "loop_ratio": S.mean(x["loop_s"] for x in rr) / baseloop,
        "wall_ratio": S.mean(x["wall_s"] for x in rr) / basewall,
        "peak_MB": S.mean(x["peak_memory_bytes"] / 1e6 for x in rr),
        "memory_scope": sorted({x["peak_memory_scope"] for x in rr}),
    }
# Parse author-machine logs without claiming to have executed them.
windows = {}
for label in ["python", "python-final"]:
    d = R / "validation" / label
    tree = ET.parse(d / "pytest.xml").getroot()
    tests = list(tree.iter("testcase"))
    windows[label] = {
        "tests": len(tests),
        "failures": sum(x.find("failure") is not None for x in tests),
        "errors": sum(x.find("error") is not None for x in tests),
        "skips": sum(x.find("skipped") is not None for x in tests),
        "coverage": read(d / "coverage.json")["totals"],
    }
# Compare supplied historical manifests separately from physical-file availability.
a = read(R / "analysis/earlier-integrity-manifests/corr_integrity_baseline.json")
b = read(R / "analysis/earlier-integrity-manifests/corr_integrity_after.json")
history = {
    "before": len(a),
    "after": len(b),
    "unchanged": sum(k in b and a[k] == b[k] for k in a),
    "changed": sum(k in b and a[k] != b[k] for k in a),
    "removed": len(a.keys() - b.keys()),
    "added": len(b.keys() - a.keys()),
}
expected = [
    {"path": k, "bytes": v[0], "sha256": v[1]}
    for k, v in b.items()
    if k.startswith("data/reward_models/rm-20261015-235")
]
(V / "REQUIRED_REWARD_MODELS.json").write_text(
    json.dumps(
        {
            "source": "supplied historical corr_integrity_after.json; original model bytes are absent",
            "files": expected,
            "total_bytes": sum(x["bytes"] for x in expected),
        },
        indent=2,
    )
    + "\n"
)
old = read(W / "reports/jmlr/artifacts/integrity_baseline.json")
physical = {
    "exact": [],
    "line_endings_only": [],
    "missing": [],
    "other_differences": [],
}
for name, (size, digest) in old.items():
    p = originals.get(name, W / name)
    if not p.is_file():
        physical["missing"].append(name)
        continue
    data = p.read_bytes()
    if sha(p) == digest and len(data) == size:
        physical["exact"].append(name)
    elif (
        hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() == digest
        or hashlib.sha256(
            data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        ).hexdigest()
        == digest
    ):
        physical["line_endings_only"].append(name)
    else:
        physical["other_differences"].append(name)
# Reformatting claim: compare syntax trees, not whitespace.
fmt = {}
for name in [
    "lunarlab/reproduce.py",
    "tests/test_reproduction_report.py",
    "tools/reproduction_summary.py",
]:
    prev = args.prior_review_source / name if args.prior_review_source else None
    fmt[name] = (
        ast.dump(ast.parse(prev.read_text()))
        == ast.dump(ast.parse((W / name).read_text()))
        if prev and prev.is_file()
        else None
    )
figs = {
    p.name: sha(p) == sha(W / "docs/results" / p.name)
    for p in (R / "regenerated-results").glob("*.png")
}
assert all(figs.values())
out = {
    "study": {
        "policies": len(arts),
        "episodes": accounting,
        "groups": rows,
        "all_checked_statistics_match": True,
        "payload_digests": payloads,
    },
    "learned_reward_dependencies": deps,
    "study_archive": {"files_compared": count, "all_match": True},
    "source_archive": {
        "sha256": sha(archive),
        "files_compared": 425,
        "all_match": True,
        "source": manifest["source"],
    },
    "benchmark": benchmark,
    "supplied_windows_logs": windows,
    "historical_manifest_comparison": history,
    "historical_physical_files": physical,
    "reformat_ast_comparison": fmt,
    "historical_figures_unchanged": figs,
}
(V / "independent_verification.json").write_text(json.dumps(out, indent=2) + "\n")
print(
    json.dumps(
        {
            "policies": 38,
            "episodes": 3800,
            "groups": 10,
            "candidate_files": 425,
            "missing_learned_dependencies": len(deps),
            "all_recalculations_match": True,
            "historical_figures": figs,
            "benchmark": benchmark,
        },
        indent=1,
    )
)
