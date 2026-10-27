# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Generate the API reference in docs/api/ from the code itself.

    python tools/gen_api_docs.py           # (re)write docs/api/
    python tools/gen_api_docs.py --check   # exit 1 if docs/api/ is out of date

* ``docs/api/<module>.md``: the Python research API -- signatures, docstrings, pydantic fields with their
  types, defaults and descriptions -- for every module in RESEARCH_MODULES (public names: ``__all__`` when a
  module defines it, else every name not starting with ``_`` that the module defines);
* ``docs/api/cli.md``: every ``python -m lunarlab`` command with its arguments, from the real parser;
* ``docs/api/openapi.json`` and ``docs/api/http.md``: the local HTTP API, from the FastAPI application;
* ``docs/api/README.md``: the index, with docstring coverage per module.

The output is deterministic (sorted, no timestamps, no memory addresses), so ``--check`` can run in CI.
"""

from __future__ import annotations

import argparse
import enum
import importlib
import inspect
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "api"
# argparse wraps help text to the terminal width; a fixed width keeps the output identical everywhere.
os.environ["COLUMNS"] = "100"
sys.path.insert(0, str(ROOT))

RESEARCH_MODULES = {
    "Reward design and accounting": [
        "lunarlab.rewards.config",
        "lunarlab.rewards.terms",
        "lunarlab.rewards.accounting",
        "lunarlab.rewards.wrapper",
        "lunarlab.rewards.analysis",
        "lunarlab.rescoring",
    ],
    "Task-independent auditing": [
        "lunarlab.audit.core",
        "lunarlab.audit.contracts",
        "lunarlab.audit.provenance",
        "lunarlab.audit.adapters",
        "lunarlab.audit.evaluate",
    ],
    "Environment, outcomes and diagnostics": [
        "lunarlab.env",
        "lunarlab.outcomes",
        "lunarlab.hover",
        "lunarlab.physics",
        "lunarlab.policies",
    ],
    "Configuration, runs and provenance": [
        "lunarlab.config",
        "lunarlab.runs",
        "lunarlab.storage",
        "lunarlab.freeze",
        "lunarlab.continuation",
        "lunarlab.lineage",
        "lunarlab.sysinfo",
    ],
    "Training and evaluation": [
        "lunarlab.training",
        "lunarlab.evaluation",
        "lunarlab.robustness",
        "lunarlab.recording",
        "lunarlab.experiments",
        "lunarlab.tuning",
    ],
    "Learned rewards from preferences": [
        "lunarlab.preferences.data",
        "lunarlab.preferences.model",
        "lunarlab.preferences.train",
        "lunarlab.preferences.active",
    ],
    "Statistics, comparison and reports": [
        "lunarlab.stats",
        "lunarlab.rl_stats",
        "lunarlab.compare",
        "lunarlab.results",
        "lunarlab.report",
    ],
    "Reproducibility and benchmarking": [
        "lunarlab.reproduce",
        "lunarlab.divergence",
        "lunarlab.overhead",
        "lunarlab.benchmark",
    ],
}
ADDRESS = re.compile(r" at 0x[0-9A-Fa-f]+")


def _clean(text: str) -> str:
    return ADDRESS.sub("", text)


def _stable_repr(obj) -> str:
    """repr() with set elements sorted: set order depends on hash randomisation."""
    if isinstance(obj, (set, frozenset)):
        return f"{type(obj).__name__}({{{', '.join(sorted(map(repr, obj)))}}})"
    return _clean(repr(obj))


def _doc(obj) -> str:
    return inspect.cleandoc(obj.__doc__) if obj.__doc__ else ""


def _signature(obj) -> str:
    try:
        return _clean(str(inspect.signature(obj)))
    except (TypeError, ValueError):
        return "(...)"


def _public_names(mod) -> list[str]:
    if hasattr(mod, "__all__"):
        return sorted(mod.__all__)
    names = []
    for name, obj in vars(mod).items():
        if name.startswith("_"):
            continue
        if inspect.isclass(obj) or inspect.isfunction(obj):
            if getattr(obj, "__module__", None) == mod.__name__:
                names.append(name)
        elif name.isupper() and not inspect.ismodule(obj):
            names.append(name)
    return sorted(names)


def _is_pydantic(cls) -> bool:
    return hasattr(cls, "model_fields") and hasattr(cls, "model_validate")


def _type_name(t) -> str:
    s = getattr(t, "__name__", None) if isinstance(t, type) else None
    return _clean(s or str(t).replace("typing.", ""))


def _render_class(name: str, cls, lines: list[str]) -> tuple[int, int]:
    documented, total = (1 if _doc(cls) else 0), 1
    bases = [b.__name__ for b in cls.__bases__ if b is not object]
    lines.append(f"### class `{name}`" + (f"({', '.join(bases)})" if bases else ""))
    lines.append("")
    if _doc(cls):
        lines += [_doc(cls), ""]
    if _is_pydantic(cls):
        own = cls.model_fields
        if own:
            lines += ["| Field | Type | Default | Description |", "|---|---|---|---|"]
            for fname, f in own.items():
                default = (
                    "required" if f.is_required() else _clean(repr(f.get_default(call_default_factory=False)))
                )
                if f.default_factory is not None:
                    default = "factory"
                desc = (f.description or "").replace("|", "\\|")
                lines.append(f"| `{fname}` | `{_type_name(f.annotation)}` | `{default}` | {desc} |")
            lines.append("")
    elif issubclass(cls, enum.Enum):
        lines += ["Members: " + ", ".join(f"`{m.name}`" for m in cls), ""]
    else:
        lines += [f"`{name}{_signature(cls)}`", ""]
    for mname, member in sorted(vars(cls).items()):
        if mname.startswith("_") or not (
            inspect.isfunction(member) or isinstance(member, (property, classmethod, staticmethod))
        ):
            continue
        func = member.fget if isinstance(member, property) else getattr(member, "__func__", member)
        total += 1
        documented += 1 if _doc(func) else 0
        kind = "property" if isinstance(member, property) else "method"
        sig = "" if kind == "property" else _signature(func)
        lines.append(f"- {kind} `{mname}{sig}`" + (f": {_doc(func).splitlines()[0]}" if _doc(func) else ""))
    lines.append("")
    return documented, total


def render_module(modname: str) -> tuple[str, int, int]:
    mod = importlib.import_module(modname)
    lines = [
        f"# `{modname}`",
        "",
        f"Source: [`{modname.replace('.', '/')}.py`](../../{modname.replace('.', '/')}.py)",
        "",
    ]
    if _doc(mod):
        lines += [_doc(mod), ""]
    documented = total = 0
    constants = []
    for name in _public_names(mod):
        obj = getattr(mod, name)
        if inspect.isclass(obj):
            d, t = _render_class(name, obj, lines)
            documented += d
            total += t
        elif inspect.isfunction(obj):
            total += 1
            documented += 1 if _doc(obj) else 0
            lines += [f"### `{name}{_signature(obj)}`", ""]
            if _doc(obj):
                lines += [_doc(obj), ""]
        else:
            value = _stable_repr(obj)
            constants.append(f"- `{name}` = `{value[:120] + ('…' if len(value) > 120 else '')}`")
    if constants:
        lines += ["## Constants", "", *constants, ""]
    return "\n".join(lines).rstrip() + "\n", documented, total


def render_cli() -> str:
    from lunarlab.cli import build_parser

    parser = build_parser()
    lines = [
        "# Command-line reference",
        "",
        "Generated from the parser in `lunarlab/cli.py`. Run any command with `--help` for the same text.",
        "",
        "```text",
        parser.format_usage().strip(),
        "```",
        "",
    ]
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    helps = {a.dest: a.help for a in sub._choices_actions}
    for name in sorted(sub.choices):
        p = sub.choices[name]
        lines += [
            f"## `{name}`",
            "",
            (helps.get(name) or "").strip(),
            "",
            "```text",
            p.format_usage().strip(),
            "```",
            "",
        ]
        rows = []
        for a in p._actions:
            if isinstance(a, argparse._HelpAction):
                continue
            flags = ", ".join(a.option_strings) or a.dest
            default = "" if a.default in (None, argparse.SUPPRESS, False) else f" (default: `{a.default}`)"
            choices = f" Choices: {', '.join(map(str, a.choices))}." if a.choices else ""
            rows.append(
                f"| `{flags}` | {('required. ' if a.required else '')}{(a.help or '').strip()}{choices}{default} |"
            )
        if rows:
            lines += ["| Argument | Description |", "|---|---|", *rows, ""]
    return "\n".join(lines).rstrip() + "\n"


def render_http() -> tuple[str, str]:
    from lunarlab.server.main import create_app

    spec = create_app(start_jobs=False, testing=True).openapi()
    lines = [
        "# HTTP API (local)",
        "",
        "The web interface talks to this API. It binds to 127.0.0.1 only, has no authentication (single local user), "
        "and every state-changing request must carry the `X-LunarLab: 1` header (a CSRF guard). The machine-readable "
        "schema is [openapi.json](openapi.json).",
        "",
        "| Method | Path | Summary |",
        "|---|---|---|",
    ]
    for path in sorted(spec.get("paths", {})):
        for method, op in sorted(spec["paths"][path].items()):
            lines.append(f"| {method.upper()} | `{path}` | {(op.get('summary') or '').strip()} |")
    return "\n".join(lines) + "\n", json.dumps(spec, indent=1, sort_keys=True) + "\n"


def render_all() -> dict[str, str]:
    files: dict[str, str] = {}
    index = [
        "# LunarLab API reference",
        "",
        "Generated by `python tools/gen_api_docs.py` from the code (signatures, docstrings, pydantic field "
        "descriptions); `--check` verifies it is current. Narrative documentation: [../DEVELOPER.md](../DEVELOPER.md), "
        "[../TUTORIAL.md](../TUTORIAL.md), [../ARCHITECTURE.md](../ARCHITECTURE.md).",
        "",
        "- [Command-line reference](cli.md)",
        "- [HTTP API](http.md) ([OpenAPI schema](openapi.json))",
        "",
        "Modules not listed here (`cli`, `server`, `jobs`, `db`, `procs`, `parallel`, `locks`, `play`, `doctor`, `demo`) "
        "are application internals: the job supervisor, persistence and the web server.",
        "",
        "| Module | Public objects documented |",
        "|---|---|",
    ]
    total_doc = total_all = 0
    for section, modules in RESEARCH_MODULES.items():
        index.append(f"| **{section}** | |")
        for modname in modules:
            text, d, t = render_module(modname)
            files[f"{modname}.md"] = text
            total_doc += d
            total_all += t
            summary = (_doc(importlib.import_module(modname)).splitlines() or [""])[0]
            index.append(f"| [`{modname}`]({modname}.md) — {summary} | {d} / {t} |")
    index += [
        "",
        f"Docstrings: {total_doc} of {total_all} public classes, functions and methods in these modules.",
        "",
    ]
    files["README.md"] = "\n".join(index)
    files["cli.md"] = render_cli()
    files["http.md"], files["openapi.json"] = render_http()
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if docs/api/ is out of date")
    args = ap.parse_args()
    files = render_all()
    if args.check:
        stale = sorted(
            n
            for n, text in files.items()
            if not (OUT / n).exists() or (OUT / n).read_text(encoding="utf-8") != text
        )
        extra = sorted(p.name for p in OUT.glob("*") if p.name not in files) if OUT.exists() else []
        if stale or extra:
            print(
                f"docs/api is out of date (stale: {stale}, unexpected: {extra}); run python tools/gen_api_docs.py"
            )
            return 1
        print("docs/api is current")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        if old.name not in files:
            old.unlink()
    for name, text in files.items():
        (OUT / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(files)} files to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
