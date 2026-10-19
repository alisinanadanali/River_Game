"""M-02: every river cell is a stone with probability p, drawn as U_stone < p from a fixed per-cell block."""

import numpy as np
import pytest

from engine.config import load_config
from engine.rng import make_rngs
from engine.world import build_world, draw_world_block

from tests.support import config_with

CFG = load_config()
STONE, HEIGHT, MOSS = 0, 1, 2  # block layers, MODEL.md M-02


def map_with(p: float):
    return config_with({"map": {"stone_density": p, "path_guarantee": "none"}}).map


def test_stone_is_uniform_below_p():
    block = np.full((3, 3, 3), 0.5)
    block[STONE] = [[0.1, 0.57, 0.58], [0.59, 0.0, 0.99], [0.3, 0.6, 0.2]]
    world = build_world(block, map_with(0.58), seed=0, attempt=0)
    assert world.is_stone.tolist() == [[True, True, False], [False, True, False], [True, False, True]]


def test_density_zero_and_one():
    block, _ = draw_world_block(make_rngs(42), CFG.map)
    assert not build_world(block, map_with(0.0), seed=42, attempt=0).is_stone.any()
    assert build_world(block, map_with(1.0), seed=42, attempt=0).is_stone.all()


@pytest.mark.parametrize("seed", range(20))
def test_more_density_only_adds_stones(seed):
    # Monotone coupling: same numbers, larger p -> a superset of stones with unchanged properties.
    block, _ = draw_world_block(make_rngs(seed), CFG.map)
    sparse = build_world(block, map_with(0.50), seed=seed, attempt=0)
    dense = build_world(block, map_with(0.72), seed=seed, attempt=0)
    assert np.all(dense.is_stone[sparse.is_stone])
    both = sparse.is_stone
    assert np.array_equal(sparse.base_h[both], dense.base_h[both])
    assert np.array_equal(sparse.mossy[both], dense.mossy[both])


@pytest.mark.parametrize("p", [0.30, 0.58, 0.72])
def test_density_matches_p(p):
    # 200 maps x 81 cells; deterministic seeds, so this never flakes. Tolerance: 4 standard errors.
    cfg = map_with(p)
    stones = []
    rngs = make_rngs(2026)
    for _ in range(200):
        block, rngs = draw_world_block(rngs, cfg)
        stones.append(build_world(block, cfg, seed=2026, attempt=0).is_stone)
    n = 200 * cfg.rows * cfg.cols
    assert abs(np.mean(stones) - p) < 4 * np.sqrt(p * (1 - p) / n)


def test_cells_are_independent_of_their_neighbours():
    # Bernoulli per cell: a stone's right-hand neighbour is a stone with probability p, not more.
    cfg = map_with(0.58)
    pairs = []
    rngs = make_rngs(7)
    for _ in range(300):
        block, rngs = draw_world_block(rngs, cfg)
        s = build_world(block, cfg, seed=7, attempt=0).is_stone
        pairs.append(s[:, 1:][s[:, :-1]])
    joined = np.concatenate(pairs)
    assert abs(joined.mean() - 0.58) < 4 * np.sqrt(0.58 * 0.42 / joined.size)
