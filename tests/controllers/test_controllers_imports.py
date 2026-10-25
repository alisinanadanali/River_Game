"""ADR-005 (Phase 1.1 update): controllers/ depends on the engine only; no pygame and no wall clock, so the
keyboard buffer is tested without a window and without waiting. Static, like INV-07."""

import sys
from pathlib import Path

import pytest

from tests.imports import imported_modules

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = frozenset(sys.stdlib_module_names) | {"numpy", "engine", "controllers"}
FORBIDDEN = frozenset({"pygame", "time", "datetime"})


def controller_files() -> list[Path]:
    return sorted((ROOT / "controllers").rglob("*.py"))


def test_controllers_has_files():
    assert any(path.name == "keyboard.py" for path in controller_files())


@pytest.mark.parametrize("path", controller_files(), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_controllers_import_only_the_engine(path):
    package = ".".join(path.relative_to(ROOT).with_suffix("").parts[:-1])
    for line, module in imported_modules(path.read_text(encoding="utf-8"), package):
        top = module.split(".")[0]
        assert top in ALLOWED and top not in FORBIDDEN, f"{path.name}:{line} imports {module}"
