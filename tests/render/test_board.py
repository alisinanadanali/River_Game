"""VISUALS §2: heights and shapes of the board from an observation. Pure: no pygame."""

import dataclasses

import numpy as np
import pytest

from engine.donkey import classify_depth, effective_height, load_kg
from engine.events import DepthState
from engine.stones import TempStone
from render.board import (
    front_face,
    life_share,
    margin,
    stand_z,
    stone_top_z,
    surface_z,
    tier_of,
    water_polygon,
    water_profile,
)
from render.layout import cell_rect
from tests.render.boards import an_obs
from tests.support import config_with

CFG = config_with({})
LAY = CFG.render.layout
ROWS, COLS = CFG.map.rows, CFG.map.cols


# --- heights -----------------------------------------------------------------------------------------------------

def test_an_empty_permanent_stone_is_its_height_plus_its_raise():
    raise_h = np.zeros((ROWS, COLS))
    raise_h[3, 2] = 6.0
    assert stone_top_z(an_obs({(3, 2): 11.0}, raise_h=raise_h), 3, 2) == 17.0


def test_the_donkeys_stone_sinks_under_its_load():
    obs = an_obs({(3, 2): 11.0}, donkey_at=(3, 2))
    k = CFG.map.stiffness_kg_per_cm
    assert stone_top_z(obs, 3, 2) == pytest.approx(effective_height(11.0, load_kg(obs.donkey, CFG), k))


def test_a_temporary_stone_is_its_current_height():
    rock = TempStone(id=0, row=4, col=5, h=13.5, spawned_at=0)
    assert stone_top_z(an_obs({}, temp=(rock,)), 4, 5) == 13.5


def test_water_and_banks_have_no_stone_top():
    obs = an_obs({(3, 2): 11.0})
    assert stone_top_z(obs, 3, 3) is None
    assert stone_top_z(obs, -1, 2) is None and stone_top_z(obs, ROWS, 2) is None


def test_the_surface_is_the_higher_of_stone_and_water_and_the_bank_top_on_a_bank():
    obs = an_obs({(3, 2): 11.0, (3, 4): -6.0})
    levels = [2.0] * COLS
    assert surface_z(obs, levels, 3, 2) == 11.0
    assert surface_z(obs, levels, 3, 4) == 2.0
    assert surface_z(obs, levels, 3, 3) == 2.0
    assert surface_z(obs, levels, -1, 3) == surface_z(obs, levels, ROWS, 3) == LAY.bank_z_cm


def test_characters_stand_on_the_bank_top_or_on_their_stone():
    obs = an_obs({(3, 2): 11.0}, donkey_at=(3, 2))
    assert stand_z(obs, 3, 2) == stone_top_z(obs, 3, 2)
    assert stand_z(an_obs({}), -1, 4) == stand_z(an_obs({}), ROWS, 4) == LAY.bank_z_cm
    water = an_obs({}, donkey_at=(3, 3))                                  # no stone under it: on the water
    assert stand_z(water, 3, 3) == float(water.water.level[3])


def test_on_water_the_feet_follow_the_level():
    obs = an_obs({}, donkey_at=(3, 3))
    level = np.arange(COLS, dtype=float) + 5.0
    obs = dataclasses.replace(obs, water=dataclasses.replace(obs.water, level=level))
    assert stand_z(obs, 3, 3) == 8.0


# --- water -------------------------------------------------------------------------------------------------------

def test_the_water_profile_is_linear_between_column_centres_and_flat_at_the_ends():
    levels = [0.0, 10.0, 30.0] + [4.0] * (COLS - 3)
    assert water_profile(levels, 1) == (5.0, 10.0, 20.0)
    assert water_profile(levels, 0) == (0.0, 0.0, 5.0)
    assert water_profile(levels, COLS - 1) == (4.0, 4.0, 4.0)


def test_the_water_polygon_follows_the_profile_one_tile_deep():
    levels = [0.0, 10.0, 30.0] + [4.0] * (COLS - 3)
    x, y, w, h = cell_rect(CFG, 2, 1)
    px = LAY.px_per_cm
    west, mid, east = water_profile(levels, 1)
    assert water_polygon(CFG, levels, 2, 1) == pytest.approx([
        (x, y - west * px), (x + w / 2, y - mid * px), (x + w, y - east * px),
        (x + w, y + h - east * px), (x + w / 2, y + h - mid * px), (x, y + h - west * px),
    ])


# --- the prism ---------------------------------------------------------------------------------------------------

def test_a_stone_above_the_water_has_a_front_face_down_to_the_water():
    x, y, w, h = cell_rect(CFG, 3, 2)
    px = LAY.px_per_cm
    assert front_face(CFG, 3, 2, top_z=15.0, level=-5.0) == pytest.approx((x, y + h - 15.0 * px, w, 20.0 * px))


def test_a_stone_under_the_water_has_no_front_face():
    assert front_face(CFG, 3, 2, top_z=-5.0, level=-5.0) is None
    assert front_face(CFG, 3, 2, top_z=-6.0, level=-5.0) is None


# --- the safety margin (§3) --------------------------------------------------------------------------------------

def test_the_margin_of_an_empty_stone_is_for_the_donkeys_current_load():
    """§3: "if the donkey stepped here now": e under its current load, also on stones it does not stand on."""
    obs = an_obs({(3, 2): 11.0})
    levels = [2.0] * COLS
    e = effective_height(11.0, load_kg(obs.donkey, CFG), CFG.map.stiffness_kg_per_cm)
    assert margin(obs, levels, 3, 2) == pytest.approx(e - 2.0)
    assert margin(obs, levels, 3, 3) is None and margin(obs, levels, -1, 3) is None


def test_the_margin_reads_the_drawn_level():
    obs = an_obs({(3, 2): 11.0})
    assert margin(obs, [0.0] * COLS, 3, 2) - margin(obs, [5.0] * COLS, 3, 2) == pytest.approx(5.0)


@pytest.mark.parametrize(("base_h", "tier"), [
    (15.0, DepthState.DRY), (2.0, DepthState.ANKLE), (-6.0, DepthState.KNEE), (-20.0, DepthState.SWEPT),
])
def test_the_tier_is_d04s_class_of_the_depth(base_h, tier):
    obs = an_obs({(3, 2): base_h})
    levels = [0.0] * COLS
    assert tier_of(obs, levels, 3, 2) is tier is classify_depth(-margin(obs, levels, 3, 2), CFG.donkey)
    assert tier_of(obs, levels, 3, 3) is None


@pytest.mark.parametrize(("h", "share"), [
    (CFG.shrek.rock_initial_h_cm, 1.0), (CFG.shrek.rock_vanish_h_cm, 0.0),
    ((CFG.shrek.rock_initial_h_cm + CFG.shrek.rock_vanish_h_cm) / 2, 0.5),
    (CFG.shrek.rock_initial_h_cm + CFG.shrek.rock_raise_cm, 1.0), (CFG.shrek.rock_vanish_h_cm - 1, 0.0),
])
def test_a_temporary_stones_life_is_its_height_between_spawn_and_vanish(h, share):
    assert life_share(h, CFG) == pytest.approx(share)
