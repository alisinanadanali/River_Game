"""ADR-005 (2026-10-25 update): render/ depends on the engine and pygame, never on the outer layers; the pure
modules do not import pygame or read the clock, so they are tested without a window and with time passed in.
Static, like INV-07: every import in render/**/*.py is read with `ast`.
"""

import sys
from pathlib import Path

import pytest

from tests.imports import imported_modules

ROOT = Path(__file__).resolve().parents[2]
RENDER_DIR = ROOT / "render"

ALLOWED = frozenset(sys.stdlib_module_names) | {"numpy", "pygame", "engine", "render"}  # not controllers/tools/…
PURE = ("render/interpolation.py", "render/characters/pose.py", "render/characters/animator.py", "render/layout.py",
        "render/scene.py")
NOT_IN_PURE = frozenset({"pygame", "time", "datetime"})  # no window, no wall clock: time is an argument


def render_files() -> list[Path]:
    return sorted(RENDER_DIR.rglob("*.py"))


def imports_of(path: Path) -> list[tuple[int, str]]:
    rel = path.relative_to(ROOT)
    return imported_modules(path.read_text(encoding="utf-8"), ".".join(rel.with_suffix("").parts[:-1]))


def test_render_has_files():
    assert render_files(), f"no .py files under {RENDER_DIR}"  # zero files scanned would pass vacuously


def test_render_imports_only_the_engine_and_pygame():
    found = [
        f"{path.relative_to(ROOT).as_posix()}:{line} imports {module}"
        for path in render_files()
        for line, module in imports_of(path)
        if module.split(".")[0] not in ALLOWED
    ]
    assert not found, "render/ crosses the ADR-005 boundary:\n" + "\n".join(found)


@pytest.mark.parametrize("rel", PURE)
def test_pure_modules_need_no_window_and_no_clock(rel):
    path = ROOT / rel
    assert path.is_file(), f"{rel} is listed as pure but does not exist"
    found = [f"{rel}:{line} imports {module}" for line, module in imports_of(path) if module.split(".")[0] in NOT_IN_PURE]
    assert not found, "\n".join(found)


@pytest.mark.parametrize(
    ("source", "bad"),
    [("import tools.bench", "tools"), ("from controllers import keyboard", "controllers"), ("from ... import logs", "logs")],
)
def test_the_check_sees_outer_layers(source, bad):
    modules = [m.split(".")[0] for _, m in imported_modules(source, "render.characters")]
    assert bad in modules and bad not in ALLOWED
