"""ADR-005 (Phase 1.3 update): game/ is the outermost layer. It may use the engine, controllers and render;
no package imports game/ (only main.py does), and game/session.py is pure: no pygame, no wall clock."""

import sys
from pathlib import Path

import pytest

from tests.imports import imported_modules

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = frozenset(sys.stdlib_module_names) | {"numpy", "pygame", "engine", "controllers", "render", "game"}
PURE = ("game/session.py", "game/view.py")
NOT_IN_PURE = frozenset({"pygame", "time", "datetime"})
INNER = ("engine", "render", "controllers", "tools", "envs", "logs")


def imports_of(path: Path) -> list[tuple[int, str]]:
    package = ".".join(path.relative_to(ROOT).with_suffix("").parts[:-1])
    return imported_modules(path.read_text(encoding="utf-8"), package)


def files_in(*packages: str) -> list[Path]:
    return sorted(path for package in packages for path in (ROOT / package).rglob("*.py"))


def test_game_has_the_session():
    assert ROOT / "game" / "session.py" in files_in("game")


@pytest.mark.parametrize("path", files_in("game"), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_game_imports_only_inner_layers(path):
    for line, module in imports_of(path):
        assert module.split(".")[0] in ALLOWED, f"{path.name}:{line} imports {module}"


@pytest.mark.parametrize("name", PURE)
def test_the_session_is_pure(name):
    for line, module in imports_of(ROOT / name):
        assert module.split(".")[0] not in NOT_IN_PURE, f"{name}:{line} imports {module}"


@pytest.mark.parametrize("path", files_in(*INNER), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_nothing_imports_game(path):
    for line, module in imports_of(path):
        assert module.split(".")[0] != "game", f"{path.name}:{line} imports {module}"
