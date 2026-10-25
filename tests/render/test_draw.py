"""VISUALS §2, §4.1: the frame, drawn on SDL's dummy driver and read back pixel by pixel.

The boards are hand-made (tests/render/boards.py: water at level 0 everywhere, stones where asked), so every
pixel can be worked out from §2. The characters are the fallback shapes (VISUALS §9.4), so the pixels do not
depend on the local images.
"""

import dataclasses
import os
from collections import Counter
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from engine.events import ProjectileKind, Role  # noqa: E402
from engine.observe import Observation, ProjectileView  # noqa: E402
from engine.stones import TempStone  # noqa: E402
from render.board import life_share, stand_z  # noqa: E402
from render.characters.animator import Look  # noqa: E402
from render.characters.pose import Clip, pose  # noqa: E402
from render.characters.sprites import load_character  # noqa: E402
from render.draw import FONT_PX, LIFE_BAR_MARGIN_PX, LIFE_BAR_PX, Assets, draw_scene  # noqa: E402
from render.hud import hud  # noqa: E402
from render.hud_layout import FONT_PX as HUD_FONT_PX  # noqa: E402
from render.hud_layout import top_rects  # noqa: E402
from render.fonts import load_font  # noqa: E402
from render.layout import board_rect, cell_center, cell_rect, feet, map_area  # noqa: E402
from render.scene import Ghost, Scene  # noqa: E402
from tests.render.boards import CFG, an_obs  # noqa: E402

PALETTE, LAY = CFG.render.palette, CFG.render.layout
ROWS = CFG.map.rows
ALPHA = round(255 * LAY.water_alpha)
TOLERANCE = 2  # per channel: SDL's alpha blending rounds


@pytest.fixture(scope="module")
def assets():
    pygame.init()
    no_images = Path(__file__).parent / "no_such_dir"
    yield Assets(load_font(CFG, FONT_PX), load_font(CFG, HUD_FONT_PX),
                 {role: load_character(role, CFG, root=no_images) for role in Role})
    pygame.quit()


def a_scene(obs: Observation, levels=None, before: Observation | None = None, u: float = 1.0) -> Scene:
    cells = {Role.SHREK: (-1, obs.shrek.col), Role.DONKEY: (obs.donkey.row, obs.donkey.col)}
    looks = {role: Look(Clip.IDLE, pose(Clip.IDLE, 0.0, CFG), True) for role in Role}
    return Scene(obs, before=obs if before is None else before, u=u, levels=tuple(obs.water.level) if levels is None else tuple(levels),
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
    screen = drawn(assets, a_scene(an_obs({(5, 3): -10.0})))                # loaded e = −14: DİZ
    assert close(dominant(face(screen, 5, 3, -10.0)), water_over(colour(PALETTE.knee)))


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


def test_the_hud_is_drawn_when_the_scene_has_one(assets):
    sc = a_scene(an_obs({}))
    x, y, w, h = top_rects(CFG).hearts[0]
    centre = (x + w / 2, y + h / 2)
    assert at(drawn(assets, sc), centre) == pygame.Color(PALETTE.background)
    with_hud = dataclasses.replace(sc, hud=hud(sc.obs, sc.mode, 0.0))
    assert at(drawn(assets, with_hud), centre) == pygame.Color(PALETTE.danger)


def test_the_bottom_bar_shows_the_feed(assets):
    sc = a_scene(an_obs({}))
    w, h = CFG.render.window_px
    strip = [(x, y) for x in range(0, w, 2) for y in range(h - LAY.bottom_bar_px, h)]
    quiet = drawn(assets, sc)
    assert all(quiet.get_at(p) == pygame.Color(PALETTE.background) for p in strip)
    speaking = drawn(assets, dataclasses.replace(sc, feed=("Eşek sürüklendi!", "Can gitti, 2 kaldı")))
    assert any(speaking.get_at(p) != pygame.Color(PALETTE.background) for p in strip)


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


# --- the characters in the water (§4.1, §9.1, §9.3) ------------------------------------------------------------

DONKEY_COLOUR = pygame.Color(CFG.render.characters.donkey.fallback_color)
SHREK_COLOUR = pygame.Color(CFG.render.characters.shrek.fallback_color)
DEPTH_CM = 6.0
UNDER, OVER = 3, 20     # px above the feet: under the water line DEPTH_CM up, and over it (the shape is 44 px)


def unseen(sc: Scene) -> Scene:
    """The same scene with the donkey invisible: the board as it is under the donkey."""
    invisible = Look(Clip.IDLE, dataclasses.replace(pose(Clip.IDLE, 0.0, CFG), alpha=0.0), True)
    return dataclasses.replace(sc, looks={**sc.looks, Role.DONKEY: invisible})


def test_the_donkey_is_not_drawn_under_its_water_line(assets):
    sc = a_scene(an_obs({(5, 7): 0.0}, donkey_at=(5, 7), level=DEPTH_CM))
    fx, fy = sc.feet[Role.DONKEY]
    cropped = dataclasses.replace(sc, water_y=fy - DEPTH_CM * LAY.px_per_cm)
    assert at(drawn(assets, sc), (fx, fy - UNDER)) == DONKEY_COLOUR                 # no line: all of it
    screen = drawn(assets, cropped)
    assert at(screen, (fx, fy - UNDER)) == at(drawn(assets, unseen(sc)), (fx, fy - UNDER)) != DONKEY_COLOUR
    assert at(screen, (fx, fy - OVER)) == DONKEY_COLOUR


def test_shrek_is_never_cropped(assets):
    sc = a_scene(an_obs({}))
    fx, fy = sc.feet[Role.SHREK]
    assert at(drawn(assets, dataclasses.replace(sc, water_y=fy - OVER)), (fx, fy - UNDER)) == SHREK_COLOUR


def a_ghost(r, c, top_z, water_y=None):
    look = Look(Clip.SWEPT, pose(Clip.SWEPT, 0.0, CFG), True)                       # t = 0: in place, opaque
    return Ghost(look, feet(CFG, Role.DONKEY, (r, c), top_z), r, water_y)


def test_the_ghost_is_drawn_on_its_cell_and_cropped_at_the_water(assets):
    sc = a_scene(an_obs({(5, 7): 0.0}, level=DEPTH_CM))
    ghost = a_ghost(5, 7, 0.0)
    fx, fy = ghost.feet
    assert at(drawn(assets, sc), (fx, fy - OVER)) != DONKEY_COLOUR                   # no ghost, no donkey there
    whole = drawn(assets, dataclasses.replace(sc, ghost=ghost))
    assert at(whole, (fx, fy - UNDER)) == at(whole, (fx, fy - OVER)) == DONKEY_COLOUR
    cropped = drawn(assets, dataclasses.replace(sc, ghost=dataclasses.replace(ghost, water_y=fy - DEPTH_CM * LAY.px_per_cm)))
    assert at(cropped, (fx, fy - UNDER)) == at(drawn(assets, sc), (fx, fy - UNDER))
    assert at(cropped, (fx, fy - OVER)) == DONKEY_COLOUR


def test_the_ghost_is_drawn_with_its_row(assets):
    """A tall stone in the row in front hides the ghost's feet, as it hides the donkey's."""
    ghost = a_ghost(5, 7, 0.0)
    fx, fy = ghost.feet
    sc = a_scene(an_obs({(5, 7): 0.0, (4, 7): 20.0}))
    assert at(drawn(assets, dataclasses.replace(sc, ghost=ghost)), (fx, fy - UNDER)) == pygame.Color(PALETTE.dry)


# --- the safety margin (§3) --------------------------------------------------------------------------------------

def face(screen, r, c, top_z):
    """The colours of a stone's top face, inside its edges and above the next row's water (pygame Colors)."""
    x, y, w, h = (round(v) for v in cell_rect(CFG, r, c, top_z))
    row_bottom = round(cell_rect(CFG, r, c)[1] + LAY.tile_h_px)            # below: the next row's water
    return [screen.get_at((px, py)) for px in range(x + 1, x + w - 1) for py in range(y + 1, min(y + h, row_bottom) - 1)]


def dominant(pixels) -> tuple[int, int, int]:
    return Counter(tuple(p)[:3] for p in pixels).most_common(1)[0][0]


def ink_share(pixels) -> float:
    main = dominant(pixels)
    return sum(tuple(p)[:3] != main for p in pixels) / len(pixels)


TIER_STONES = [  # base height → (tier colour, seen under water?); level 0, the donkey's 200 kg sink 4 cm
    (15.0, PALETTE.dry, False), (2.0, PALETTE.ankle, False), (-6.0, PALETTE.knee, True), (-20.0, PALETTE.danger, True),
]


@pytest.mark.parametrize(("base_h", "tier_colour", "under"), TIER_STONES)
def test_each_tier_has_its_colour(assets, base_h, tier_colour, under):
    pixels = face(drawn(assets, a_scene(an_obs({(5, 1): base_h}))), 5, 1, base_h)
    expected = water_over(colour(tier_colour)) if under else colour(tier_colour)
    assert close(dominant(pixels), expected)


def test_the_pattern_ink_grows_with_the_danger(assets):
    shares = [ink_share(face(drawn(assets, a_scene(an_obs({(5, 1): h}))), 5, 1, h)) for h, _, _ in TIER_STONES]
    assert shares[0] == 0 and shares == sorted(shares) and len(set(shares)) == len(shares), shares


def test_between_ticks_the_colour_blends_and_the_pattern_follows_the_drawn_water(assets):
    """Base 2 cm, loaded e = −2: L = −10 → DRY (previous tick), L = 0 → ANKLE (this tick)."""
    before, now = an_obs({(5, 1): 2.0}, level=-10.0), an_obs({(5, 1): 2.0}, level=0.0)
    for u, inked in ((0.5, False), (0.9, True)):
        levels = [-10.0 * (1 - u)] * CFG.map.cols                          # m = −2 + 5 = 3 > 0; m = −2 + 1 = −1
        pixels = face(drawn(assets, a_scene(now, levels, before=before, u=u)), 5, 1, 2.0)
        mix = tuple(d + u * (a - d) for d, a in zip(colour(PALETTE.dry), colour(PALETTE.ankle)))
        assert close(dominant(pixels), mix), u
        assert (ink_share(pixels) > 0) is inked, u


def test_a_mossy_stone_has_a_dark_contour_and_a_wave_mark(assets):
    plain = drawn(assets, a_scene(an_obs({(5, 1): 15.0})))
    mossy = drawn(assets, a_scene(an_obs({(5, 1): 15.0}, mossy=[(5, 1)])))
    x, y, _, _ = cell_rect(CFG, 5, 1, 15.0)
    assert at(mossy, (x, y)) == pygame.Color(PALETTE.background) != at(plain, (x, y))
    assert ink_share(face(plain, 5, 1, 15.0)) == 0 < ink_share(face(mossy, 5, 1, 15.0))


def test_a_temporary_stone_has_a_dashed_contour_and_a_life_bar(assets):
    shrek = CFG.shrek
    for h in (shrek.rock_initial_h_cm, (shrek.rock_initial_h_cm + shrek.rock_vanish_h_cm) / 2):
        rock = TempStone(id=0, row=6, col=1, h=h, spawned_at=0)
        screen = drawn(assets, a_scene(an_obs({}, temp=(rock,), level=-30.0)))   # high and dry: no water over it
        x, y, w, hh = (round(v) for v in cell_rect(CFG, 6, 1, h))
        edge = [at(screen, (px, y)) == pygame.Color(PALETTE.background) for px in range(x, x + w)]
        assert 0 < sum(edge) < len(edge)                                          # dashed
        bar_y = y + hh - LIFE_BAR_MARGIN_PX - LIFE_BAR_PX // 2 - 1
        bar_w = w - 2 * LIFE_BAR_MARGIN_PX
        filled = sum(at(screen, (px, bar_y)) == pygame.Color(PALETTE.text) for px in range(x, x + w))
        assert filled == pytest.approx(life_share(h, CFG) * bar_w, abs=1)
