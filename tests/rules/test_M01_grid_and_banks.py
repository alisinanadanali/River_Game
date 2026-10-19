"""M-01: R x C river grid between two banks; the donkey's graph is bank cells ∪ stone cells, 4-neighbourhood."""

import dataclasses

import numpy as np
import pytest

from engine.config import load_config
from engine.rng import make_rngs
from engine.world import WORLD_LAYERS, World, build_world, draw_world_block, walkable

from tests.support import config_with

CFG = load_config()


def world_of(map_cfg, seed: int = 42) -> World:
    block, _ = draw_world_block(make_rngs(seed), map_cfg)
    return build_world(block, map_cfg, seed=seed, attempt=0)


def test_block_shape_is_layers_rows_cols():
    block, _ = draw_world_block(make_rngs(42), CFG.map)
    assert WORLD_LAYERS == 3
    assert block.shape == (WORLD_LAYERS, CFG.map.rows, CFG.map.cols)


@pytest.mark.parametrize("rows, cols", [(9, 9), (5, 7), (3, 12)])
def test_grid_shape_follows_config(rows, cols):
    world = world_of(config_with({"map": {"rows": rows, "cols": cols}}).map)
    assert (world.rows, world.cols) == (rows, cols)
    for grid in (world.is_stone, world.base_h, world.stiffness, world.mossy):
        assert grid.shape == (rows, cols)


def test_banks_are_walkable_in_every_column():
    world = world_of(CFG.map)
    assert all(walkable(world, -1, c) and walkable(world, world.rows, c) for c in range(world.cols))


def test_river_cell_is_walkable_exactly_when_it_is_a_stone():
    world = world_of(CFG.map)
    assert all(
        walkable(world, r, c) == bool(world.is_stone[r, c]) for r in range(world.rows) for c in range(world.cols)
    )


@pytest.mark.parametrize("row, col", [(-2, 0), (9, -1), (10, 0), (0, -1), (0, 9), (-1, 9)])
def test_outside_the_map_is_not_walkable(row, col):
    assert not walkable(world_of(CFG.map), row, col)


def test_arrays_are_read_only():
    world = world_of(CFG.map)
    for grid in (world.is_stone, world.base_h, world.stiffness, world.mossy):
        with pytest.raises(ValueError):
            grid[0, 0] = grid[0, 0]


def test_world_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        world_of(CFG.map).seed = 1


def test_does_not_keep_the_callers_block():
    # Changing the block afterwards must not reach into the world.
    block, _ = draw_world_block(make_rngs(42), CFG.map)
    world = build_world(block, CFG.map, seed=42, attempt=0)
    before = world.is_stone.copy()
    block[:] = 0.0
    assert np.array_equal(world.is_stone, before)


# --- equality (INV-02 compares states, and states hold a world) --------------------------------

def test_same_numbers_equal_worlds_despite_nan():
    # Water cells hold NaN, and NaN != NaN; worlds must still compare equal by content.
    a, b = world_of(CFG.map), world_of(CFG.map)
    assert a is not b and np.isnan(a.base_h).any()
    assert a == b


def test_other_seed_other_world():
    assert world_of(CFG.map, 1) != world_of(CFG.map, 2)


def test_other_attempt_number_other_world():
    block, _ = draw_world_block(make_rngs(42), CFG.map)
    assert build_world(block, CFG.map, seed=42, attempt=0) != build_world(block, CFG.map, seed=42, attempt=1)


def test_not_equal_to_other_types():
    assert world_of(CFG.map) != "world"


def test_repr_is_one_short_line():
    text = repr(world_of(CFG.map))
    assert "\n" not in text and len(text) < 120 and text.startswith("World(9x9")
