"""The immutable map (MODEL.md §2, M-01 … M-05)."""

from collections import deque

import numpy as np

from engine.config import MapConfig

_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))  # M-01: 4-neighbourhood


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
