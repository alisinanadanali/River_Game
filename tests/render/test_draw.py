"""VISUALS §4.1: the skeleton frame, drawn on SDL's dummy driver and read back pixel by pixel.

The characters are the fallback shapes (VISUALS §9.4), so the pixels do not depend on the local images.
"""

import dataclasses
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from engine.events import ProjectileKind, Role  # noqa: E402
from engine.observe import ProjectileView, observe  # noqa: E402
from engine.state import new_game  # noqa: E402
from engine.stones import TempStone  # noqa: E402
from render.characters.animator import Look  # noqa: E402
from render.characters.pose import Clip, pose  # noqa: E402
from render.characters.sprites import load_character  # noqa: E402
from render.draw import FONT_PX, Assets, draw_scene  # noqa: E402
from render.fonts import load_font  # noqa: E402
from render.layout import board_rect, cell_center, cell_rect, feet, map_area  # noqa: E402
from render.scene import Scene  # noqa: E402
from tests.support import config_with  # noqa: E402

CFG = config_with({})
SEED = 7
PALETTE = CFG.render.palette


@pytest.fixture(scope="module")
def assets():
    pygame.init()
    no_images = Path(__file__).parent / "no_such_dir"
    yield Assets(load_font(CFG, FONT_PX), {role: load_character(role, CFG, root=no_images) for role in Role})
    pygame.quit()


def a_scene(**obs_changes) -> Scene:
    state = new_game(CFG, SEED)[0]
    obs = dataclasses.replace(observe(state, Role.DONKEY), **obs_changes)
    cells = {Role.SHREK: (-1, state.shrek.col), Role.DONKEY: (state.donkey.row, state.donkey.col)}
    looks = {role: Look(Clip.IDLE, pose(Clip.IDLE, 0.0, CFG), True) for role in Role}
    return Scene(obs, feet={role: feet(CFG, role, cells[role]) for role in Role}, looks=looks, mode="realtime",
                 paused=False, seed=SEED)


def drawn(assets, scene: Scene) -> pygame.Surface:
    screen = pygame.Surface(CFG.render.window_px)
    draw_scene(screen, assets, scene)
    return screen


def at(screen, point) -> pygame.Color:
    return screen.get_at((round(point[0]), round(point[1])))


def far_cell(scene: Scene, stone: bool) -> tuple[int, int]:
    """A river cell of the kind asked for, away from the characters (they stand by the middle of the south bank)."""
    w = scene.obs.world
    return next((r, c) for r in range(w.rows - 1, 1, -1) for c in range(2) if bool(w.is_stone[r, c]) is stone)


def test_cells_have_the_bank_stone_and_water_colours(assets):
    sc = a_scene()
    screen = drawn(assets, sc)
    assert at(screen, cell_center(CFG, CFG.map.rows, 0)) == pygame.Color(PALETTE.bank)
    assert at(screen, cell_center(CFG, *far_cell(sc, stone=True))) == pygame.Color(PALETTE.dry)
    assert at(screen, cell_center(CFG, *far_cell(sc, stone=False))) == pygame.Color(PALETTE.water)


def test_outside_the_board_is_the_background(assets):
    screen = drawn(assets, a_scene())
    ax, ay, _, _ = map_area(CFG)
    bx, by, _, _ = board_rect(CFG)
    assert (bx, by) > (ax, ay)
    assert at(screen, (ax, ay)) == pygame.Color(PALETTE.background)


def test_the_aim_frame_is_drawn_over_the_characters(assets):
    sc = a_scene()
    x, y, w, h = cell_rect(CFG, sc.obs.shrek.aim_row, sc.obs.shrek.col)
    bottom = (x + w / 2, y + h - 1)                                   # the frame's south line, over the donkey
    away = a_scene(shrek=dataclasses.replace(sc.obs.shrek, aim_row=CFG.map.rows - 1))
    assert at(drawn(assets, away), bottom) == pygame.Color(CFG.render.characters.donkey.fallback_color)
    assert at(drawn(assets, sc), bottom) == pygame.Color(PALETTE.text)
    assert at(drawn(assets, sc), (x, y)) == pygame.Color(PALETTE.text)


def test_a_temporary_stone_is_a_stone(assets):
    sc = a_scene()
    r, c = far_cell(sc, stone=False)
    rock = TempStone(id=0, row=r, col=c, h=CFG.shrek.rock_initial_h_cm, spawned_at=0)
    stones = dataclasses.replace(sc.obs.stones, temp=(rock,), next_temp_id=1)
    assert at(drawn(assets, a_scene(stones=stones)), cell_center(CFG, r, c)) == pygame.Color(PALETTE.dry)


def test_a_flying_item_shows_a_shadow_on_its_target_cell(assets):
    sc = a_scene()
    target = far_cell(sc, stone=False)
    flying = ProjectileView(item_id=0, kind=ProjectileKind.THROW, target=target, sigma=1.0, ticks_left=1, thrown_at=0)
    screen = drawn(assets, a_scene(projectiles=(flying,)))
    assert at(screen, cell_center(CFG, *target)) == pygame.Color(PALETTE.background)


def test_the_top_bar_has_text_and_the_pause_shows_a_banner(assets):
    sc = a_scene()
    playing, paused = drawn(assets, sc), drawn(assets, dataclasses.replace(sc, paused=True))
    bar = pygame.Rect(0, 0, CFG.render.window_px[0], CFG.render.layout.top_bar_px)
    background = pygame.Color(PALETTE.background)
    assert any(playing.get_at((x, y)) != background for x in range(bar.width) for y in range(bar.height))
    assert pygame.image.tobytes(playing, "RGB") != pygame.image.tobytes(paused, "RGB")


def test_drawing_reads_nothing_but_the_scene(assets):
    """The same scene twice gives the same pixels: no hidden state between frames."""
    sc = a_scene()
    assert pygame.image.tobytes(drawn(assets, sc), "RGB") == pygame.image.tobytes(drawn(assets, sc), "RGB")
