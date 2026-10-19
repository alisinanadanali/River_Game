"""M-03: h ~ U[lo, hi], mossy ~ Bernoulli(p_moss), k = k_moss or k_normal; water cells hold NaN / False."""

import numpy as np

from engine.config import load_config
from engine.rng import make_rngs
from engine.world import build_world, draw_world_block

from tests.support import config_with

CFG = load_config()
STONE, HEIGHT, MOSS = 0, 1, 2  # block layers, MODEL.md M-02


def hand_block(stone, height, moss) -> np.ndarray:
    return np.array([stone, height, moss], dtype=float)


MAP = config_with({
    "map": {"stone_density": 0.5, "path_guarantee": "none", "stone_base_h_cm": [0, 20], "mossy_prob": 0.15,
            "stiffness_kg_per_cm": 50, "mossy_stiffness_kg_per_cm": 25},
}).map

#            stone   water   stone            (row 0)
BLOCK = hand_block(
    stone=[[0.1, 0.9, 0.2]],
    height=[[0.25, 0.5, 1 - 2**-53]],
    moss=[[0.10, 0.01, 0.15]],
)


def test_height_is_lo_plus_range_times_uniform():
    world = build_world(BLOCK, MAP, seed=0, attempt=0)
    assert world.base_h[0, 0] == 5.0
    assert world.base_h[0, 2] < 20.0  # U < 1, so h < hi


def test_mossy_is_uniform_below_p_moss_on_stones_only():
    world = build_world(BLOCK, MAP, seed=0, attempt=0)
    # (0,0): 0.10 < 0.15 mossy; (0,1): water, never mossy; (0,2): 0.15 is not < 0.15.
    assert world.mossy.tolist() == [[True, False, False]]


def test_stiffness_follows_moss():
    world = build_world(BLOCK, MAP, seed=0, attempt=0)
    assert world.stiffness[0, 0] == 25.0 and world.stiffness[0, 2] == 50.0


def test_water_cells_hold_nan():
    world = build_world(BLOCK, MAP, seed=0, attempt=0)
    assert np.isnan(world.base_h[0, 1]) and np.isnan(world.stiffness[0, 1])


def test_nan_exactly_where_there_is_no_stone():
    block, _ = draw_world_block(make_rngs(42), CFG.map)
    world = build_world(block, CFG.map, seed=42, attempt=0)
    assert np.array_equal(np.isnan(world.base_h), ~world.is_stone)
    assert np.array_equal(np.isnan(world.stiffness), ~world.is_stone)
    assert not world.mossy[~world.is_stone].any()


def test_fixed_height_when_lo_equals_hi():
    cfg = config_with({"map": {"stone_base_h_cm": [7, 7]}}).map
    block, _ = draw_world_block(make_rngs(42), cfg)
    world = build_world(block, cfg, seed=42, attempt=0)
    assert np.all(world.base_h[world.is_stone] == 7.0)


def many_stones(cfg, maps: int = 300):
    rngs = make_rngs(99)
    heights, moss = [], []
    for _ in range(maps):
        block, rngs = draw_world_block(rngs, cfg)
        world = build_world(block, cfg, seed=99, attempt=0)
        heights.append(world.base_h[world.is_stone])
        moss.append(world.mossy[world.is_stone])
    return np.concatenate(heights), np.concatenate(moss)


def test_heights_fill_the_range_uniformly():
    heights, _ = many_stones(CFG.map)
    lo, hi = CFG.map.stone_base_h_cm
    assert heights.min() >= lo and heights.max() < hi
    # U[lo, hi]: mean (lo+hi)/2, sd (hi-lo)/√12. Tolerance: 4 standard errors of the mean.
    assert abs(heights.mean() - (lo + hi) / 2) < 4 * (hi - lo) / np.sqrt(12 * heights.size)


def test_moss_fraction_matches_p_moss():
    _, moss = many_stones(CFG.map)
    p = CFG.map.mossy_prob
    assert abs(moss.mean() - p) < 4 * np.sqrt(p * (1 - p) / moss.size)


def test_moss_does_not_depend_on_height():
    # Independent draws: mossy stones are not systematically higher or lower.
    heights, moss = many_stones(CFG.map)
    lo, hi = CFG.map.stone_base_h_cm
    sd = (hi - lo) / np.sqrt(12)
    assert abs(heights[moss].mean() - heights[~moss].mean()) < 4 * sd * np.sqrt(1 / moss.sum() + 1 / (~moss).sum())
