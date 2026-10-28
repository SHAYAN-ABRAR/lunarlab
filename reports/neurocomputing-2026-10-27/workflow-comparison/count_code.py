# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Count the custom source lines of each workflow program, under the prespecified rule.

    python count_code.py OUT.json

A counted line holds at least one token that is not a comment, a newline or indentation, and is not part
of a module, class or function docstring (found with ``ast``). Imports and the JSON output code count.
The library code a program calls (SB3, Gymnasium, LunarLab) does not count. The figure indicates the
setup a user writes; it is not a measure of productivity.
"""

from __future__ import annotations

import ast
import io
import json
import sys
import tokenize
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRAMS = {
    "W1": HERE / "workflows" / "w1_sb3_conventional.py",
    "W2": HERE / "workflows" / "w2_sb3_reference.py",
    "W3": HERE / "workflows" / "w3_lunarlab.py",
}
SKIP = {
    tokenize.COMMENT,
    tokenize.NL,
    tokenize.NEWLINE,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENCODING,
    tokenize.ENDMARKER,
}


def docstring_lines(source: str) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                lines.update(range(first.lineno, first.end_lineno + 1))
    return lines


def count(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    doc = docstring_lines(source)
    code = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type in SKIP:
            continue
        for line in range(tok.start[0], tok.end[0] + 1):
            if line not in doc:
                code.add(line)
    imports = sorted(
        {n.module or "" for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ImportFrom)}
        | {a.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Import) for a in n.names}
    )
    return {
        "file": path.name,
        "counted_lines": len(code),
        "physical_lines": source.count("\n"),
        "imports": imports,
    }


def main() -> int:
    result = {k: count(p) for k, p in PROGRAMS.items()}
    result["rule"] = __doc__.split("\n\n")[1].replace("\n", " ")
    Path(sys.argv[1]).write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
    for k in PROGRAMS:
        print(k, result[k]["counted_lines"], "counted of", result[k]["physical_lines"], "physical lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
