"""VISUALS §2, §4.1: the frame, drawn on SDL's dummy driver and read back pixel by pixel.

The boards are hand-made (tests/render/boards.py: water at level 0 everywhere, stones where asked), so every
pixel can be worked out from §2. The characters are the fallback shapes (VISUALS §9.4), so the pixels do not
depend on the local images.
"""

import dataclasses
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from engine.events import ProjectileKind, Role  # noqa: E402
from engine.observe import Observation, ProjectileView  # noqa: E402
from engine.stones import TempStone  # noqa: E402
from render.board import stand_z  # noqa: E402
from render.characters.animator import Look  # noqa: E402
from render.characters.pose import Clip, pose  # noqa: E402
from render.characters.sprites import load_character  # noqa: E402
from render.draw import FONT_PX, Assets, draw_scene  # noqa: E402
from render.fonts import load_font  # noqa: E402
from render.layout import board_rect, cell_center, cell_rect, feet, map_area  # noqa: E402
from render.scene import Scene  # noqa: E402
from tests.render.boards import CFG, an_obs  # noqa: E402

PALETTE, LAY = CFG.render.palette, CFG.render.layout
ROWS = CFG.map.rows
ALPHA = round(255 * LAY.water_alpha)
TOLERANCE = 2  # per channel: SDL's alpha blending rounds


@pytest.fixture(scope="module")
def assets():
    pygame.init()
    no_images = Path(__file__).parent / "no_such_dir"
    yield Assets(load_font(CFG, FONT_PX), {role: load_character(role, CFG, root=no_images) for role in Role})
    pygame.quit()


def a_scene(obs: Observation, levels=None) -> Scene:
    cells = {Role.SHREK: (-1, obs.shrek.col), Role.DONKEY: (obs.donkey.row, obs.donkey.col)}
    looks = {role: Look(Clip.IDLE, pose(Clip.IDLE, 0.0, CFG), True) for role in Role}
    return Scene(obs, levels=tuple(obs.water.level) if levels is None else tuple(levels),
                 feet={role: feet(CFG, role, cell, stand_z(obs, *cell)) for role, cell in cells.items()},
                 rows={role: cell[0] for role, cell in cells.items()}, looks=looks, mode="realtime", paused=False,
                 seed=7)


def drawn(assets, scene: Scene) -> pygame.Surface:
    screen = pygame.Surface(CFG.render.window_px)
    draw_scene(screen, assets, scene)
    return screen


def at(screen, point) -> pygame.Color:
    return screen.get_at((round(point[0]), round(point[1])))


def colour(hex_or_rgb) -> tuple[int, int, int]:
    return tuple(pygame.Color(hex_or_rgb))[:3]


def shaded(hex_colour) -> tuple[int, int, int]:
    return tuple(round(v * LAY.front_shade) for v in colour(hex_colour))


def water_over(below) -> tuple[int, int, int]:
    return tuple(round(w * ALPHA / 255 + b * (1 - ALPHA / 255)) for w, b in zip(colour(PALETTE.water), below))


def close(got: pygame.Color, expected) -> bool:
    return all(abs(g - e) <= TOLERANCE for g, e in zip(tuple(got)[:3], expected))


def front_middle(r, c, top_z, level=0.0):
    """The middle of a front face from top_z down to level, on the cell's south edge."""
    x, y, w, h = cell_rect(CFG, r, c)
    return (x + w / 2, y + h - (top_z + level) / 2 * LAY.px_per_cm)


# --- the board ---------------------------------------------------------------------------------------------------

def test_the_banks_have_a_top_at_their_height_and_a_darker_front(assets):
    screen = drawn(assets, a_scene(an_obs({})))
    assert at(screen, cell_center(CFG, ROWS, 0, LAY.bank_z_cm)) == pygame.Color(PALETTE.bank)
    assert close(at(screen, front_middle(ROWS, 0, LAY.bank_z_cm)), shaded(PALETTE.bank))


def test_a_stone_above_the_water_is_a_prism(assets):
    screen = drawn(assets, a_scene(an_obs({(5, 1): 15.0})))
    assert at(screen, cell_center(CFG, 5, 1, 15.0)) == pygame.Color(PALETTE.dry)
    assert close(at(screen, front_middle(5, 1, 15.0)), shaded(PALETTE.dry))


def test_a_stone_under_the_water_shows_through_it(assets):
    screen = drawn(assets, a_scene(an_obs({(5, 3): -10.0})))
    assert close(at(screen, cell_center(CFG, 5, 3, -10.0)), water_over(colour(PALETTE.dry)))


def test_open_water_lies_over_the_background(assets):
    screen = drawn(assets, a_scene(an_obs({})))
    assert close(at(screen, cell_center(CFG, 6, 1)), water_over(colour(PALETTE.background)))


def test_a_wave_lifts_the_water_in_front_of_the_north_bank(assets):
    obs = an_obs({})
    x, y, w, _ = cell_rect(CFG, ROWS - 1, 1)
    point = (x + w / 2, y - 10)                                     # on the north bank's front face at level 0
    levels = [0.0] * CFG.map.cols
    assert close(at(drawn(assets, a_scene(obs, levels)), point), shaded(PALETTE.bank))
    levels[1] = 30.0
    assert close(at(drawn(assets, a_scene(obs, levels)), point), water_over(shaded(PALETTE.bank)))


def test_rows_are_drawn_back_to_front(assets):
    """A tall stone hides the lower part of the water cell north of it."""
    x, y, w, _ = cell_rect(CFG, 5, 6)
    screen = drawn(assets, a_scene(an_obs({(4, 6): 20.0})))
    assert at(screen, (x + w / 2, y + 20)) == pygame.Color(PALETTE.dry)


def test_a_character_is_hidden_by_the_stone_in_front_of_it(assets):
    behind = an_obs({(5, 7): 0.0}, donkey_at=(5, 7))
    fx, fy = a_scene(behind).feet[Role.DONKEY]
    above_feet = (fx, fy - 3)
    assert at(drawn(assets, a_scene(behind)), above_feet) == pygame.Color(CFG.render.characters.donkey.fallback_color)
    hidden = an_obs({(5, 7): 0.0, (4, 7): 20.0}, donkey_at=(5, 7))
    assert at(drawn(assets, a_scene(hidden)), above_feet) == pygame.Color(PALETTE.dry)


def test_a_temporary_stone_is_a_stone(assets):
    rock = TempStone(id=0, row=6, col=1, h=12.0, spawned_at=0)
    screen = drawn(assets, a_scene(an_obs({}, temp=(rock,))))
    assert at(screen, cell_center(CFG, 6, 1, 12.0)) == pygame.Color(PALETTE.dry)


def test_outside_the_board_is_the_background(assets):
    screen = drawn(assets, a_scene(an_obs({})))
    ax, ay, _, _ = map_area(CFG)
    bx, by, _, _ = board_rect(CFG)
    assert (bx, by) >= (ax, ay)
    assert at(screen, (ax, ay)) == pygame.Color(PALETTE.background)


# --- on top ------------------------------------------------------------------------------------------------------

def test_the_aim_frame_lies_on_the_cells_surface(assets):
    obs = an_obs({(5, 1): 15.0})
    obs = dataclasses.replace(obs, shrek=dataclasses.replace(obs.shrek, col=1, aim_row=5))
    x, y, _, _ = cell_rect(CFG, 5, 1, 15.0)
    assert at(drawn(assets, a_scene(obs)), (x, y)) == pygame.Color(PALETTE.text)


def test_the_aim_frame_is_drawn_over_the_characters(assets):
    obs = an_obs({})
    x, y, w, _ = cell_rect(CFG, 0, obs.shrek.col)                 # aim_row 0: water at level 0
    top = (x + w / 2, y)                                          # the frame's north line, over the donkey
    away = dataclasses.replace(obs, shrek=dataclasses.replace(obs.shrek, aim_row=ROWS - 1))
    assert at(drawn(assets, a_scene(away)), top) == pygame.Color(CFG.render.characters.donkey.fallback_color)
    assert at(drawn(assets, a_scene(obs)), top) == pygame.Color(PALETTE.text)


def test_a_flying_item_shows_a_shadow_on_its_target_surface(assets):
    flying = ProjectileView(item_id=0, kind=ProjectileKind.THROW, target=(6, 1), sigma=1.0, ticks_left=1,
                            thrown_at=0)
    obs = dataclasses.replace(an_obs({(6, 1): 15.0}), projectiles=(flying,))
    assert at(drawn(assets, a_scene(obs)), cell_center(CFG, 6, 1, 15.0)) == pygame.Color(PALETTE.background)


def test_the_top_bar_has_text_and_the_pause_shows_a_banner(assets):
    sc = a_scene(an_obs({}))
    playing, paused = drawn(assets, sc), drawn(assets, dataclasses.replace(sc, paused=True))
    bar = pygame.Rect(0, 0, CFG.render.window_px[0], LAY.top_bar_px)
    background = pygame.Color(PALETTE.background)
    assert any(playing.get_at((x, y)) != background for x in range(bar.width) for y in range(bar.height))
    assert pygame.image.tobytes(playing, "RGB") != pygame.image.tobytes(paused, "RGB")


def test_drawing_reads_nothing_but_the_scene(assets):
    """The same scene twice gives the same pixels: no hidden state between frames."""
    sc = a_scene(an_obs({(5, 1): 15.0}))
    assert pygame.image.tobytes(drawn(assets, sc), "RGB") == pygame.image.tobytes(drawn(assets, sc), "RGB")


def test_water_has_no_seams_between_rows_and_stays_on_the_board(assets):
    """pygame fills a polygon's edges too: two rows' shared edge must not be blended twice."""
    screen = drawn(assets, a_scene(an_obs({})))
    x, y, w, _ = cell_rect(CFG, 5, 1)
    expected = water_over(colour(PALETTE.background))
    assert all(close(at(screen, (x + w / 2, y + dy)), expected) for dy in (-1, 0, 1))   # row 6 | row 5 boundary
    bx, _, bw, _ = board_rect(CFG)
    assert at(screen, (bx + bw, cell_center(CFG, 5, 1)[1])) == pygame.Color(PALETTE.background)
