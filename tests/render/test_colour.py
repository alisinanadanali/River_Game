"""VISUALS §3: the safety-margin colours and patterns stay distinguishable for colour-blind players.

Colour science is checked against reference values; the thresholds and the palette are read from VISUALS §3
(the doc is the oracle). The pattern part draws each tier's pattern on SDL's dummy driver.
"""

import itertools
import os
import re
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np  # noqa: E402
import pygame  # noqa: E402
import pytest  # noqa: E402

from engine.config import load_config  # noqa: E402
from engine.events import DepthState  # noqa: E402
from render.colour import (  # noqa: E402
    MACHADO_2009,
    MIN_DELTA_E,
    TIERS,
    Vision,
    blend,
    delta_e,
    lab,
    rgb,
    simulate,
    tier_colour,
    to_linear,
    to_srgb,
)
from render.patterns import MARK_STROKE_PX, draw_pattern  # noqa: E402

CFG = load_config()
PALETTE, LAY = CFG.render.palette, CFG.render.layout
VISUALS = (Path(__file__).resolve().parents[2] / "docs" / "VISUALS.md").read_text(encoding="utf-8")
ORDER = (DepthState.DRY, DepthState.ANKLE, DepthState.KNEE, DepthState.SWEPT)   # by danger


def seen(colour, vision, under_water=False):
    c = rgb(colour) if isinstance(colour, str) else colour
    if under_water:
        c = blend(rgb(PALETTE.water), c, LAY.water_alpha)
    return simulate(c, vision)


# --- colour science ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("hex_colour", "expected"), [
    ("#FFFFFF", (100.0, 0.0, 0.0)),
    ("#000000", (0.0, 0.0, 0.0)),
    ("#FF0000", (53.2408, 80.0925, 67.2032)),        # sRGB primaries in CIELAB (D65), standard reference values
    ("#00FF00", (87.7347, -86.1827, 83.1793)),
])
def test_cielab_reference_values(hex_colour, expected):
    assert lab(rgb(hex_colour)) == pytest.approx(expected, abs=0.05)


def test_srgb_and_linear_round_trip():
    c = np.linspace(0, 1, 101)
    assert to_srgb(to_linear(c)) == pytest.approx(c, abs=1e-12)
    assert to_linear(np.array([0.04045]))[0] == pytest.approx(0.04045 / 12.92)


@pytest.mark.parametrize("vision", list(Vision))
def test_greys_stay_grey(vision):
    """Machado 2009: a dichromat sees achromatic colours unchanged (each matrix row sums to 1)."""
    for v in (0.0, 0.2, 0.5, 1.0):
        assert simulate(np.array([v, v, v]), vision) == pytest.approx([v, v, v], abs=1e-3)


def test_normal_vision_changes_nothing_and_dichromats_confuse_red_and_green():
    red, green = rgb("#CC3333"), rgb("#669933")                  # a red and an olive green that dichromats mix up
    assert simulate(red, Vision.NORMAL) == pytest.approx(red)
    normal = delta_e(red, green)
    for vision in (Vision.PROTAN, Vision.DEUTAN):
        assert delta_e(simulate(red, vision), simulate(green, vision)) < normal / 2


def test_the_simulation_works_on_whole_images():
    image = np.random.default_rng(0).random((4, 5, 3))
    out = simulate(image, Vision.DEUTAN)
    assert out.shape == image.shape and out[2, 3] == pytest.approx(simulate(image[2, 3], Vision.DEUTAN))


def test_the_matrices_are_machado_2009_at_full_severity():
    assert set(MACHADO_2009) == {Vision.PROTAN, Vision.DEUTAN, Vision.TRITAN}
    assert MACHADO_2009[Vision.DEUTAN][0] == pytest.approx([0.367322, 0.860646, -0.227968])


# --- the palette (§3) --------------------------------------------------------------------------------------------

def test_the_threshold_is_the_documented_one():
    assert float(re.search(r"ΔE₇₆ ≥ (\d+)\*\*", VISUALS).group(1)) == MIN_DELTA_E


def test_the_palette_is_the_table_of_section_3():
    table = dict(re.findall(r"^\| (KURU|BİLEK|DİZ|TEHLİKE) \|.*?`(#[0-9A-F]{6})`", VISUALS, re.M))
    names = {DepthState.DRY: "KURU", DepthState.ANKLE: "BİLEK", DepthState.KNEE: "DİZ", DepthState.SWEPT: "TEHLİKE"}
    assert {names[t]: tier_colour(PALETTE, t).upper() for t in TIERS} == table


@pytest.mark.parametrize("vision", list(Vision))
def test_tier_colours_above_water_are_told_apart(vision):
    for a, b in itertools.combinations(ORDER, 2):
        d = delta_e(seen(tier_colour(PALETTE, a), vision), seen(tier_colour(PALETTE, b), vision))
        assert d >= MIN_DELTA_E, (vision, a, b, d)


@pytest.mark.parametrize("vision", list(Vision))
@pytest.mark.parametrize("under_water", [False, True])
def test_the_pattern_ink_stands_out_on_every_tier(vision, under_water):
    for tier in ORDER:
        base = seen(tier_colour(PALETTE, tier), vision, under_water)
        ink = seen(PALETTE.background, vision, under_water)
        assert delta_e(base, ink) >= MIN_DELTA_E, (vision, tier)


# --- the patterns ------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def masks():
    """Each tier's pattern drawn on its colour: the set of inked pixels."""
    pygame.init()
    rect = pygame.Rect(0, 0, LAY.tile_w_px, LAY.tile_h_px)
    out = {}
    for tier in ORDER:
        tile = pygame.Surface(rect.size)
        tile.fill(tier_colour(PALETTE, tier))
        draw_pattern(tile, rect, tier, tier_colour(PALETTE, tier), PALETTE.background)
        ink = pygame.Color(PALETTE.background)
        out[tier] = frozenset((x, y) for x in range(rect.width) for y in range(rect.height) if tile.get_at((x, y)) == ink)
    yield out
    pygame.quit()


def test_dry_is_plain_and_the_ink_grows_with_the_danger(masks):
    counts = [len(masks[t]) for t in ORDER]
    assert counts[0] == 0
    assert counts == sorted(counts) and len(set(counts)) == len(counts), counts


def test_every_pattern_differs(masks):
    for a, b in itertools.combinations(ORDER, 2):
        assert masks[a] != masks[b]


def test_srgb_mid_grey_reference():
    """IEC 61966-2-1: sRGB 0.5 is 0.21404 linear; #808080 is L* 53.585."""
    assert to_linear(np.array([0.5]))[0] == pytest.approx(0.214041, abs=1e-6)
    assert lab(rgb("#808080"))[0] == pytest.approx(53.585, abs=0.01)


def test_delta_e_is_the_euclidean_distance_in_cielab():
    assert delta_e(rgb("#FF0000"), rgb("#000000")) == pytest.approx(np.hypot(53.2408, np.hypot(80.0925, 67.2032)),
                                                                     abs=0.05)


def test_blend_puts_the_top_colour_at_alpha():
    assert blend(np.ones(3), np.zeros(3), 0.55) == pytest.approx([0.55] * 3)


def test_danger_is_a_lattice_both_ways(masks):
    """Away from the "!": every rising line of DİZ, plus the falling ones."""
    quarter = LAY.tile_w_px // 4
    left = lambda mask: {(x, y) for x, y in mask if x < quarter}       # noqa: E731
    assert left(masks[DepthState.KNEE]) < left(masks[DepthState.SWEPT])


def test_danger_has_an_exclamation_mark_on_a_clear_patch(masks):
    cx, cy = LAY.tile_w_px // 2, LAY.tile_h_px // 2
    mark = masks[DepthState.SWEPT]
    assert (cx, cy) in mark                                                 # the bar
    side = MARK_STROKE_PX // 2 + 1
    assert (cx - side - 1, cy) not in mark and (cx + side, cy) not in mark  # the patch around it
