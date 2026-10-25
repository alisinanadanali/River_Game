"""VISUALS §5: the HUD drawn on SDL's dummy driver and read back. Where to look comes from render/hud_layout.py,
what to expect from the pure model (render/hud.py), so these tests check only the drawing."""

import dataclasses
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from engine.donkey import Bag  # noqa: E402
from engine.events import DepthState, Role, Side  # noqa: E402
from engine.items import Bank, Item, ItemStatus  # noqa: E402
from engine.observe import observe  # noqa: E402
from engine.water import Dam  # noqa: E402
from render.colour import tier_colour  # noqa: E402
from render.fonts import load_font  # noqa: E402
from render.hud import hud  # noqa: E402
from render.hud_layout import FONT_PX, donkey_rects, shrek_rects, top_rects  # noqa: E402
from render.panels import draw_hud  # noqa: E402
from tests.support import set_up, still  # noqa: E402

CFG = still({"map": {"rows": 3, "cols": 5}})
LINE = ["..#m.", "..#..", "..#.."]
PALETTE = CFG.render.palette
ITEMS = (
    Item(id=0, kind="watermelon", status=ItemStatus.IN_BAG),
    Item(id=1, kind="apple_crate", status=ItemStatus.IN_BAG),
    Item(id=2, kind="potato_sack", status=ItemStatus.ON_BANK),
    Item(id=3, kind="apple_crate", status=ItemStatus.ON_BANK),
)
D, S, T = donkey_rects(CFG), shrek_rects(CFG), top_rects(CFG)


@pytest.fixture(scope="module")
def font():
    pygame.init()
    yield load_font(CFG, FONT_PX)
    pygame.quit()


def drawn(font, now_s=0.0, **fields):
    state, _ = set_up(CFG, LINE, items=ITEMS, **fields)
    obs = observe(state, Role.DONKEY)
    screen = pygame.Surface(CFG.render.window_px)
    screen.fill(PALETTE.background)
    model = hud(obs, "realtime", now_s)
    draw_hud(screen, font, model, CFG)
    return screen, model


def at(screen, x, y) -> tuple[int, int, int]:
    return tuple(screen.get_at((round(x), round(y))))[:3]


def colour(hex_colour) -> tuple[int, int, int]:
    return tuple(pygame.Color(hex_colour))[:3]


def count_in_row(screen, rect, rgb) -> int:
    x, y, w, h = rect
    row = round(y + h / 2)
    return sum(at(screen, px, row) == rgb for px in range(round(x), round(x + w)))


def count_in_column(screen, rect, rgb) -> int:
    x, y, w, h = rect
    column = round(x + w / 2)
    return sum(at(screen, column, py) == rgb for py in range(round(y), round(y + h)))


BG, TEXT, BANK = colour(PALETTE.background), colour(PALETTE.text), colour(PALETTE.bank)


# --- the top bar -------------------------------------------------------------------------------------------------

def test_the_time_bar_shows_the_share_left(font):
    state, _ = set_up(CFG, LINE, items=ITEMS)
    length = CFG.time.game_length_ticks
    obs = dataclasses.replace(observe(state, Role.DONKEY), t=length // 4)
    screen = pygame.Surface(CFG.render.window_px)
    screen.fill(PALETTE.background)
    model = hud(obs, "realtime", 0.0)
    draw_hud(screen, font, model, CFG)
    filled = count_in_row(screen, T.time_bar, TEXT)
    assert filled == pytest.approx(model.top.time_share * T.time_bar[2], abs=1)


def test_a_full_heart_per_life_left(font):
    screen, _ = drawn(font, donkey={"lives": CFG.time.lives - 1})
    centres = [at(screen, x + w / 2, y + h / 2) for x, y, w, h in T.hearts]
    assert centres[:-1] == [colour(PALETTE.danger)] * (CFG.time.lives - 1) and centres[-1] == BG


# --- the donkey's panel ------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("bags", "heavy_left"), [
    ({"bag_left": Bag(items=(0,), mass=50.0, volume=3)}, True),
    ({"bag_right": Bag(items=(0,), mass=50.0, volume=3)}, False),
])
def test_the_balance_bar_fills_from_the_middle_towards_the_heavy_side(font, bags, heavy_left):
    screen, model = drawn(font, donkey={"row": 0, "col": 2, **bags})
    x, y, w, h = D.balance_bar
    tier = colour(tier_colour(PALETTE, model.donkey.balance.tier))
    reach = abs(model.donkey.balance.delta) / model.donkey.balance.limit * w / 2
    left, right = at(screen, x + w / 2 - reach / 2, y + h / 2), at(screen, x + w / 2 + reach / 2, y + h / 2)
    assert (left, right) == ((tier, BG) if heavy_left else (BG, tier))
    sign = -1 if heavy_left else 1                                               # where the fill ends
    assert at(screen, x + w / 2 + sign * (reach - 2), y + h / 2) == tier
    assert at(screen, x + w / 2 + sign * (reach + 2), y + h / 2) == BG
    assert model.donkey.balance.tier is not DepthState.DRY                       # p₀ + κδ² with 50 kg: not the lowest


def test_bag_squares_fill_bottom_up_and_the_top_item_is_framed(font):
    screen, model = drawn(font, donkey={"bag_left": Bag(items=(0, 1), mass=60.0, volume=4)})
    squares = D.squares[0]                                                       # watermelon 3, apple 1: all four
    corner = [at(screen, x + 3, y + h - 3) for x, y, w, h in squares]
    assert corner == [BANK] * 4
    edge = [at(screen, x + w / 2, y) for x, y, w, h in squares]
    assert edge[3] == TEXT and edge[0] == BANK                                    # the apple on top is framed
    empty = [at(screen, x + 3, y + h - 3) for x, y, w, h in D.squares[1]]
    assert empty == [BG] * len(empty)


def test_the_mass_bar_fills_from_the_bottom(font):
    screen, model = drawn(font, donkey={"bag_left": Bag(items=(0,), mass=30.0, volume=3)})
    bar = D.mass_bars[0]
    assert count_in_column(screen, bar, TEXT) == pytest.approx(30 / CFG.donkey.bag_max_kg_per_side * bar[3], abs=1)
    x, y, w, h = bar
    assert at(screen, x + w / 2, y + h - 1) == TEXT and at(screen, x + w / 2, y + 1) != TEXT


def test_the_depth_badge_has_the_tier_colour(font):
    screen, _ = drawn(font, donkey={"row": 0, "col": 2, "depth_state": DepthState.ANKLE, "depth": 3.0})
    x, y, w, h = D.badge
    pixels = [at(screen, px, py) for px in range(round(x), round(x + w)) for py in range(round(y), round(y + h))]
    assert max(set(pixels), key=pixels.count) == colour(PALETTE.ankle)


def test_the_stance_shows_an_arrow_and_its_time_left(font):
    cfg_max = CFG.donkey.stance_max_ticks
    without, _ = drawn(font)
    x, y, w, h = D.arrow
    assert all(at(without, px, py) == BG for px in range(round(x), round(x + w)) for py in range(round(y), round(y + h)))
    state, _ = set_up(CFG, LINE, items=ITEMS, donkey={"stance": Side.LEFT, "stance_since": 10})
    obs = dataclasses.replace(observe(state, Role.DONKEY), t=12)                  # 3 of stance_max_ticks left
    screen = pygame.Surface(CFG.render.window_px)
    screen.fill(PALETTE.background)
    draw_hud(screen, font, hud(obs, "realtime", 0.0), CFG)
    assert any(at(screen, px, py) == TEXT for px in range(round(x), round(x + w)) for py in range(round(y), round(y + h)))
    left = cfg_max + 11 - 12
    assert count_in_row(screen, D.stance_bar, TEXT) == pytest.approx(left / cfg_max * D.stance_bar[2], abs=1)


def test_the_arrow_points_to_the_stance_side(font):
    def mass_of_arrow(side):
        state, _ = set_up(CFG, LINE, items=ITEMS, donkey={"stance": side, "stance_since": 0})
        obs = dataclasses.replace(observe(state, Role.DONKEY), t=1)
        screen = pygame.Surface(CFG.render.window_px)
        screen.fill(PALETTE.background)
        draw_hud(screen, font, hud(obs, "realtime", 0.0), CFG)
        x, y, w, h = D.arrow
        inked = [px for px in range(round(x), round(x + w)) for py in range(round(y), round(y + h))
                 if at(screen, px, py) == TEXT]
        return sum(inked) / len(inked) - (x + w / 2)                              # the ink's centre, from the middle
    assert mass_of_arrow(Side.RIGHT) < 0 < mass_of_arrow(Side.LEFT)              # heavy at its base, opposite the tip


# --- Shrek's panel -----------------------------------------------------------------------------------------------

def test_queued_items_fill_the_slots_and_a_full_bank_warns(font):
    screen, _ = drawn(font, bank=Bank(queue=(2, 3)))
    corners = [at(screen, x + 3, y + 3) for x, y, w, h in S.slots]
    assert corners[:2] == [BANK, BANK] and corners[2:] == [BG] * (len(S.slots) - 2)
    items = ITEMS + tuple(Item(id=i, kind="apple_crate", status=ItemStatus.ON_BANK) for i in range(4, 7))
    state, _ = set_up(CFG, LINE, items=items, bank=Bank(queue=(2, 3, 4, 5, 6)))
    screen = pygame.Surface(CFG.render.window_px)
    screen.fill(PALETTE.background)
    draw_hud(screen, font, hud(observe(state, Role.DONKEY), "realtime", 0.0), CFG)
    assert all(at(screen, x + 3, y + 3) == colour(PALETTE.danger) for x, y, w, h in S.slots)


@pytest.mark.parametrize(("left", "dry"), [(0, True), (None, False)])
def test_a_dial_is_full_when_ready(font, left, dry):
    total = CFG.shrek.throw_cooldown_ticks
    screen, _ = drawn(font, shrek={"throw_cooldown": total if left is None else left})
    cx, cy, r = S.dials[0]
    ring = [at(screen, cx + r / 2 * dx, cy + r / 2 * dy) for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1))]
    assert (ring == [colour(PALETTE.dry)] * 4) is dry
    assert (colour(PALETTE.dry) in ring) is dry


def test_the_dam_bar_fills_with_water_and_flashes_at_the_share(font):
    q_max = CFG.dam.q_max_cm_cols
    half, _ = drawn(font, dam=Dam(active=True, col=2, volume=0.5 * q_max, started_at=0))
    bar = S.dam_bar
    assert count_in_column(half, bar, colour(PALETTE.water)) == pytest.approx(0.5 * bar[3], abs=1)
    lit, model = drawn(font, now_s=0.0, dam=Dam(active=True, col=2, volume=q_max, started_at=0))
    assert model.shrek.dam.flash_on
    assert count_in_column(lit, bar, colour(PALETTE.danger)) == pytest.approx(bar[3], abs=1)
