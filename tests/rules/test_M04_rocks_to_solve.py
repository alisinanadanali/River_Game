"""M-04: n_rock = cheapest south -> north crossing, entering a stone costs 0 and a water cell 1 (0-1 BFS).

Maps are written as seen from above with north on top: the first line is row R-1 (next to the north bank),
the last line row 0 (next to Shrek's south bank). '#' = stone, '.' = water.
"""

import itertools
from collections import deque

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine.world import meets_guarantee, rocks_to_solve

from tests.support import config_with


def grid(*lines: str) -> np.ndarray:
    """A bool stone grid from map lines, north first (see the module docstring)."""
    return np.array([[ch == "#" for ch in line] for line in reversed(lines)], dtype=bool)


# --- hand-made maps ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "lines, expected",
    [
        (("###", "###", "###"), 0),                       # all stone
        (("...", "...", "..."), 3),                       # all water: one rock per row
        ((".#.", ".#.", ".#."), 0),                       # one straight stone column
        (("..#", ".#.", "#.."), 2),                       # diagonal: not 4-connected
        (("###", "...", "###"), 1),                       # a wall of water one cell thick
        (("#..", "..#", "..#"), 1),                       # banks are free to walk along; one gap
        (("#....", "#....", "#####", "....#", "....#"), 0),   # a winding stone path is free
        (("#....", "#....", "##.##", "....#", "....#"), 1),   # same path with one gap
        (("....", "####", "####"), 1),                    # last row water: the north bank still needs a step
    ],
)
def test_hand_made_maps(lines, expected):
    assert rocks_to_solve(grid(*lines)) == expected


def test_prefers_a_long_free_path_over_a_short_costly_one():
    # Every straight column has water in it (cost ≥ 1); the 13-cell zigzag through the stones costs 0.
    lines = (
        "#....",
        "#.###",
        "#.#.#",
        "###.#",
        "....#",
    )
    stones = grid(*lines)
    assert all(not stones[:, c].all() for c in range(stones.shape[1]))
    assert rocks_to_solve(stones) == 0


def test_rectangular_map():
    assert rocks_to_solve(grid("....", "....")) == 2
    assert rocks_to_solve(grid("#", ".", "#", ".")) == 2


def test_input_is_not_changed():
    stones = grid("#..", ".#.", "..#")
    before = stones.copy()
    rocks_to_solve(stones)
    assert np.array_equal(stones, before)


def test_accepts_read_only_arrays():
    stones = grid("#.", ".#")
    stones.flags.writeable = False
    assert rocks_to_solve(stones) == 1


@pytest.mark.parametrize("bad", [np.zeros(3, dtype=bool), np.zeros((2, 2), dtype=int), np.zeros((0, 3), dtype=bool)])
def test_rejects_anything_but_a_non_empty_2d_bool_grid(bad):
    with pytest.raises(ValueError):
        rocks_to_solve(bad)


# --- against a brute-force oracle -------------------------------------------------------

def crossable(stones: np.ndarray) -> bool:
    """Plain BFS: is there a 4-connected stone path from row 0 to the last row?"""
    rows, cols = stones.shape
    seen = {(0, c) for c in range(cols) if stones[0, c]}
    queue = deque(seen)
    while queue:
        r, c = queue.popleft()
        if r == rows - 1:
            return True
        for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if 0 <= nr < rows and 0 <= nc < cols and stones[nr, nc] and (nr, nc) not in seen:
                seen.add((nr, nc))
                queue.append((nr, nc))
    return False


def brute_force_rocks(stones: np.ndarray) -> int:
    """The definition itself: the fewest water cells that, turned to stone, make the river crossable."""
    water = [tuple(cell) for cell in np.argwhere(~stones)]
    for k in range(len(water) + 1):
        for chosen in itertools.combinations(water, k):
            trial = stones.copy()
            for cell in chosen:
                trial[cell] = True
            if crossable(trial):
                return k
    raise AssertionError("an all-stone river is always crossable")


small_grids = st.integers(min_value=1, max_value=4).flatmap(
    lambda rows: st.integers(min_value=1, max_value=4).flatmap(
        lambda cols: st.lists(st.booleans(), min_size=rows * cols, max_size=rows * cols).map(
            lambda cells: np.array(cells, dtype=bool).reshape(rows, cols)
        )
    )
)


@given(stones=small_grids)
def test_matches_brute_force(stones):
    assert rocks_to_solve(stones) == brute_force_rocks(stones)


@given(stones=small_grids)
def test_bounds(stones):
    # 0 ≤ n_rock ≤ R: one rock per row in a straight line always crosses.
    assert 0 <= rocks_to_solve(stones) <= stones.shape[0]


# --- the profile condition -------------------------------------------------------------

def map_cfg(guarantee: str, max_rocks: int = 2):
    return config_with({"map": {"path_guarantee": guarantee, "max_rocks_to_solve": max_rocks}}).map


@pytest.mark.parametrize("n_rock", [0, 1, 5])
def test_none_accepts_every_map(n_rock):
    assert meets_guarantee(map_cfg("none"), n_rock)


def test_path_needs_a_rock_free_crossing():
    assert meets_guarantee(map_cfg("path"), 0)
    assert not meets_guarantee(map_cfg("path"), 1)


def test_max_rocks_is_inclusive():
    cfg = map_cfg("max_rocks", 2)
    assert [meets_guarantee(cfg, n) for n in range(4)] == [True, True, True, False]
