# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Release metadata stays consistent: license, version, citation, dependencies, notices, file headers."""

from __future__ import annotations

import importlib.metadata as md
import importlib.util
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

import lunarlab

ROOT = Path(__file__).resolve().parent.parent


def _tool(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def test_license_file_and_every_declaration_agree():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("MIT License") and "Permission is hereby granted, free of charge" in text
    assert re.search(r"^Copyright \(c\) \d{4} \S", text, re.M)
    project = _pyproject()["project"]
    assert project["license"] == "MIT"
    assert "LICENSE" in project["license-files"]
    assert md.metadata("lunarlab").get("License-Expression") == "MIT"
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert pkg["license"] == "MIT"
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    assert lock["packages"][""]["license"] == "MIT"
    cff = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert cff["license"] == "MIT"


def test_every_source_file_carries_the_spdx_header():
    spdx = _tool("spdx_headers")
    files = spdx.source_files()
    assert len(files) > 100  # Python, TypeScript, PowerShell, workflows, CSS, HTML
    missing = [p.relative_to(ROOT).as_posix() for p in files if not spdx.has_header(p)]
    assert missing == [], f"run python tools/spdx_headers.py --fix: {missing}"


def test_one_authoritative_version_everywhere():
    v = lunarlab.__version__
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?", v)
    project = _pyproject()
    assert "version" in project["project"]["dynamic"] and "version" not in project["project"]
    assert project["tool"]["setuptools"]["dynamic"]["version"] == {"attr": "lunarlab.__version__"}
    assert md.version("lunarlab") == v, "installed metadata is stale: reinstall with pip install -e ."
    assert json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))["version"] == v
    assert str(yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))["version"]) == v


def test_cli_reports_version_and_source_revision():
    out = subprocess.run(
        [sys.executable, "-m", "lunarlab", "--version"], capture_output=True, text=True, check=True
    ).stdout
    assert out.startswith(f"lunarlab {lunarlab.__version__} (source ")
    info = json.loads(
        subprocess.run(
            [sys.executable, "-m", "lunarlab", "version", "--json"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    assert info["lunarlab"] == lunarlab.__version__
    assert info["python"] == sys.version.split()[0]
    assert {"gymnasium", "stable-baselines3", "torch", "optuna"} <= set(info["packages"])
    assert "available" in info["git"]


def test_package_metadata_declares_every_top_level_requirement():
    """requirements.in (what the lock is resolved from) and pyproject.toml must name the same packages."""
    req_in = set()
    for line in (ROOT / "requirements.in").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            req_in.add(_norm(re.split(r"[<>=!~\[ ;]", line, maxsplit=1)[0]))
    project = _pyproject()["project"]
    declared = {
        _norm(re.split(r"[<>=!~\[ ;]", d, maxsplit=1)[0])
        for d in project["dependencies"] + project["optional-dependencies"]["dev"]
    }
    assert req_in == declared, (
        f"only in requirements.in: {req_in - declared}; only in pyproject: {declared - req_in}"
    )


def test_third_party_notices_cover_every_locked_package():
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    listed = {_norm(m.group(1)) for m in re.finditer(r"^\| ([^ |]+) \| ", notices, re.M)}
    pins = {
        _norm(m.group(1))
        for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines()
        if (m := re.match(r"^([A-Za-z0-9][A-Za-z0-9_.\-]*)==", line))
    }
    assert pins <= listed, f"missing from THIRD_PARTY_NOTICES.md: {sorted(pins - listed)}"
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    frontend = {
        _norm(path.split("node_modules/")[-1])
        for path, info in lock["packages"].items()
        if path and not info.get("dev") and not info.get("devOptional")
    }
    assert frontend <= listed, f"missing from THIRD_PARTY_NOTICES.md: {sorted(frontend - listed)}"


@pytest.mark.parametrize("name", ["bug_report.yml", "feature_request.yml", "reproducibility_report.yml"])
def test_issue_forms_are_valid_yaml_with_a_body(name):
    form = yaml.safe_load((ROOT / ".github" / "ISSUE_TEMPLATE" / name).read_text(encoding="utf-8"))
    assert form["name"] and form["description"] and form["body"]
    assert all("type" in item for item in form["body"])


def test_provenance_outside_a_git_checkout_says_so(tmp_path, monkeypatch):
    """An installed source archive has no .git: provenance must say "no git revision", not fail."""
    from lunarlab import sysinfo

    monkeypatch.setattr(sysinfo, "project_root", lambda: tmp_path)
    state = sysinfo.git_state()
    assert state == {"available": False, "reason": "not a git repository"}
    info = sysinfo.version_info()
    assert info["git"] == state and "no git revision" in sysinfo.version_line(info)


def test_a_missing_tracked_package_is_reported_as_none(monkeypatch):
    from lunarlab import sysinfo

    monkeypatch.setattr(sysinfo, "TRACKED_PACKAGES", ("numpy", "no-such-package-lunarlab"))
    versions = sysinfo.package_versions()
    assert versions["numpy"] == md.version("numpy") and versions["no-such-package-lunarlab"] is None
