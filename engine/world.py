"""The immutable map (MODEL.md §2, M-01 … M-05).

A generation attempt draws one fixed block of uniforms from rng_world, WORLD_LAYERS x R x C, and build_world
turns it into a World without further randomness. Fixed per-cell numbers give the monotone coupling of M-02.
"""

import dataclasses
from collections import deque
from dataclasses import dataclass

import numpy as np

from engine.config import MapConfig
from engine.rng import Rngs, draw

WORLD_LAYERS = 3                         # M-02: uniforms per cell and attempt (stone, height, moss)
_STONE, _HEIGHT, _MOSS = range(WORLD_LAYERS)
_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))  # M-01: 4-neighbourhood


@dataclass(frozen=True, kw_only=True, eq=False)
class World:
    """ENTITIES.md World. Grids are read-only, indexed [row, col]; float grids hold NaN on water cells (M-03)."""

    rows: int
    cols: int
    is_stone: np.ndarray    # bool[R, C]   M-02
    base_h: np.ndarray      # float[R, C]  cm, M-03
    stiffness: np.ndarray   # float[R, C]  kg/cm, M-03
    mossy: np.ndarray       # bool[R, C]   M-03
    rocks_to_solve: int     # M-04
    seed: int               # the game's master seed (R-01)
    regen_attempt: int      # M-05

    def __eq__(self, other):
        if not isinstance(other, World):
            return NotImplemented
        return all(_same(getattr(self, f.name), getattr(other, f.name)) for f in dataclasses.fields(self))

    __hash__ = None  # equal by content, and numpy arrays are not hashable

    def __repr__(self):
        return (
            f"World({self.rows}x{self.cols}, stones={int(self.is_stone.sum())}, "
            f"rocks_to_solve={self.rocks_to_solve}, seed={self.seed}, regen_attempt={self.regen_attempt})"
        )


def _same(a, b) -> bool:
    if isinstance(a, np.ndarray):
        return a.dtype == b.dtype and np.array_equal(a, b, equal_nan=a.dtype.kind == "f")
    return a == b


def walkable(world: World, row: int, col: int) -> bool:
    """M-01: banks (rows -1 and R) in every column, and permanent stones. Temporary stones join with S-07."""
    if not 0 <= col < world.cols:
        return False
    if row in (-1, world.rows):
        return True
    return 0 <= row < world.rows and bool(world.is_stone[row, col])


def draw_world_block(rngs: Rngs, map_cfg: MapConfig) -> tuple[np.ndarray, Rngs]:
    """M-02, M-05: one attempt's uniforms, shape (WORLD_LAYERS, rows, cols), from rng_world."""
    return draw(rngs, "world", lambda g: g.random((WORLD_LAYERS, map_cfg.rows, map_cfg.cols)))


def build_world(block: np.ndarray, map_cfg: MapConfig, *, seed: int, attempt: int) -> World:
    """M-02, M-03, M-04: the World these uniforms describe. Pure; the grid size is the block's."""
    if block.ndim != 3 or block.shape[0] != WORLD_LAYERS:
        raise ValueError(f"expected a ({WORLD_LAYERS}, rows, cols) block, got {block.shape}")
    is_stone = block[_STONE] < map_cfg.stone_density
    lo, hi = map_cfg.stone_base_h_cm
    base_h = np.where(is_stone, lo + (hi - lo) * block[_HEIGHT], np.nan)
    mossy = is_stone & (block[_MOSS] < map_cfg.mossy_prob)
    stiffness = np.where(mossy, map_cfg.mossy_stiffness_kg_per_cm, map_cfg.stiffness_kg_per_cm)
    stiffness = np.where(is_stone, stiffness, np.nan)
    for grid in (is_stone, base_h, stiffness, mossy):
        grid.flags.writeable = False
    return World(
        rows=block.shape[1],
        cols=block.shape[2],
        is_stone=is_stone,
        base_h=base_h,
        stiffness=stiffness,
        mossy=mossy,
        rocks_to_solve=rocks_to_solve(is_stone),
        seed=seed,
        regen_attempt=attempt,
    )


def rocks_to_solve(is_stone: np.ndarray) -> int:
    """M-04: fewest temporary stones for a south -> north crossing (0-1 BFS; stone costs 0, water 1).

    Both banks are walkable along their whole length, so the crossing may start at any cell of row 0 and end
    at any cell of row R-1. Water level and time are ignored: this is a topological measure.
    """
    if is_stone.ndim != 2 or is_stone.dtype != np.bool_ or 0 in is_stone.shape:
        raise ValueError(f"expected a non-empty 2-D bool grid, got {is_stone.dtype} {is_stone.shape}")
    stone = is_stone.tolist()  # plain lists: much faster to index than numpy scalars in this loop
    rows, cols = is_stone.shape
    cost = [[rows * cols + 1] * cols for _ in range(rows)]  # larger than any real cost
    queue: deque[tuple[int, int, int]] = deque()
    for c in range(cols):
        d = 0 if stone[0][c] else 1
        cost[0][c] = d
        queue.appendleft((d, 0, c)) if d == 0 else queue.append((d, 0, c))
    while queue:
        d, r, c = queue.popleft()
        if d > cost[r][c]:
            continue  # a cheaper way here was found after this entry was queued
        if r == rows - 1:
            return d  # costs leave the deque in non-decreasing order: the first north cell is the cheapest
        for dr, dc in _NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                step = 0 if stone[nr][nc] else 1
                if d + step < cost[nr][nc]:
                    cost[nr][nc] = d + step
                    queue.appendleft((d, nr, nc)) if step == 0 else queue.append((d + 1, nr, nc))
    raise AssertionError("unreachable: every river cell can be entered, so row R-1 is always reached")


def meets_guarantee(map_cfg: MapConfig, n_rock: int) -> bool:
    """M-04: does a map needing `n_rock` temporary stones satisfy the profile's path_guarantee?"""
    match map_cfg.path_guarantee:
        case "none":
            return True
        case "path":
            return n_rock == 0
        case "max_rocks":
            return n_rock <= map_cfg.max_rocks_to_solve


class MapGenerationError(ValueError):
    """M-05: no attempt within max_regen_attempts met the profile's path_guarantee for this seed."""


def generate_world(map_cfg: MapConfig, seed: int, rngs: Rngs) -> tuple[World, Rngs]:
    """M-05: the first attempt whose map meets M-04; returns it with rng_world advanced past its block."""
    for attempt in range(map_cfg.max_regen_attempts):
        block, rngs = draw_world_block(rngs, map_cfg)
        world = build_world(block, map_cfg, seed=seed, attempt=attempt)
        if meets_guarantee(map_cfg, world.rocks_to_solve):
            return world, rngs
    raise MapGenerationError(
        f"seed {seed}: no map met path_guarantee={map_cfg.path_guarantee!r} "
        f"(max_rocks_to_solve={map_cfg.max_rocks_to_solve}) in {map_cfg.max_regen_attempts} attempts"
    )
