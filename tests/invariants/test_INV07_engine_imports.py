"""INV-07: engine/ imports only the allow-list from ADR-005 (static test, nothing is executed).

Every import in engine/**/*.py is read with `ast` and its top-level module checked against ALLOWED.
Known limit: dynamic imports (importlib.import_module("pygame")) are invisible to a static test.
"""

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = ROOT / "engine"

FORBIDDEN_STDLIB = frozenset({"random", "time", "datetime"})  # ADR-006 RNG streams; no wall-clock in engine
THIRD_PARTY = frozenset({"numpy", "pydantic", "yaml"})
ALLOWED = (frozenset(sys.stdlib_module_names) - FORBIDDEN_STDLIB) | THIRD_PARTY | {"engine"}


def engine_import_violations(source: str, package: str) -> list[tuple[int, str]]:
    """INV-07: (line, imported module) for every import in `source` outside ALLOWED.

    `package` is the dotted package the file lives in ("engine" for engine/step.py), needed to resolve
    relative imports such as `from ..tools import x`.
    """
    imported: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = package.split(".")[: len(package.split(".")) - (node.level - 1)] if node.level else []
            if node.module:
                imported.append((node.lineno, ".".join(base + [node.module])))
            else:  # `from . import rng` / `from .. import logs`: each name is a module
                imported += [(node.lineno, ".".join(base + [alias.name])) for alias in node.names]
    return sorted((line, module) for line, module in imported if module.split(".")[0] not in ALLOWED)


# --- the checker itself, on in-memory snippets -----------------------------------

@pytest.mark.parametrize(
    "source",
    [
        "import numpy as np",
        "import numpy.random",
        "from pydantic import BaseModel",
        "import yaml",
        "from __future__ import annotations",
        "import dataclasses, math",
        "from engine import rng",
        "from engine.rng import spawn",
        "from . import rng",
        "from .rng import spawn",
        "# import render",
        "x = 'import pygame'",
    ],
)
def test_allowed(source):
    assert engine_import_violations(source, "engine") == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import pygame", [(1, "pygame")]),
        ("from render.board import draw", [(1, "render.board")]),
        ("import os, pygame", [(1, "pygame")]),
        ("import controllers.keyboard", [(1, "controllers.keyboard")]),
        ("from tools import ghosting", [(1, "tools")]),
        ("from ..tools import ghosting", [(1, "tools")]),
        ("from .. import logs", [(1, "logs")]),
        ("import random", [(1, "random")]),
        ("from time import perf_counter", [(1, "time")]),
        ("import numpy\n\ndef f():\n    import gymnasium\n", [(4, "gymnasium")]),
    ],
)
def test_violations(source, expected):
    assert engine_import_violations(source, "engine") == expected


def test_relative_import_in_subpackage_stays_inside():
    # engine/rules/water.py: `from .. import rng` is engine.rng
    assert engine_import_violations("from .. import rng", "engine.rules") == []


# --- the real engine/ package ------------------------------------------------------

def engine_files() -> list[Path]:
    return sorted(ENGINE_DIR.rglob("*.py"))


def test_engine_has_files():
    # Guard against a vacuous pass: zero files scanned would mean zero violations.
    assert engine_files(), f"no .py files under {ENGINE_DIR}"


def test_engine_imports_only_allowed_modules():
    found = []
    for path in engine_files():
        rel = path.relative_to(ROOT)
        package = ".".join(rel.with_suffix("").parts[:-1])
        for line, module in engine_import_violations(path.read_text(encoding="utf-8"), package):
            found.append(f"{rel.as_posix()}:{line} imports {module}")
    assert not found, "engine/ crosses the ADR-005 boundary:\n" + "\n".join(found)
