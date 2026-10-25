"""Hand-made boards for the drawing tests: water everywhere except the stones asked for (VISUALS §2)."""

import dataclasses

import numpy as np

from engine.events import Role
from engine.observe import Observation, observe
from engine.state import new_game
from tests.support import config_with

CFG = config_with({})
ROWS, COLS = CFG.map.rows, CFG.map.cols


def an_obs(stones: dict[tuple[int, int], float], raise_h=None, temp=(), donkey_at=None, mossy=(),
           level: float | None = None) -> Observation:
    """A world of water with stones of the given base heights; the donkey on the south bank unless donkey_at;
    `mossy` cells are mossy (same stiffness, so only the look changes); `level`: L in every column."""
    state = new_game(CFG, 7)[0]
    is_stone = np.zeros((ROWS, COLS), dtype=bool)
    base_h = np.zeros((ROWS, COLS))
    for (r, c), h in stones.items():
        is_stone[r, c], base_h[r, c] = True, h
    world = dataclasses.replace(state.world, is_stone=is_stone, base_h=base_h, mossy=np.isin(np.arange(ROWS * COLS), [r * COLS + c for r, c in mossy]).reshape(ROWS, COLS),
                                stiffness=np.full((ROWS, COLS), CFG.map.stiffness_kg_per_cm))
    r_h = np.zeros((ROWS, COLS)) if raise_h is None else raise_h
    s_stones = dataclasses.replace(state.stones, raise_h=r_h, temp=tuple(temp), next_temp_id=len(temp))
    donkey = state.donkey if donkey_at is None else dataclasses.replace(state.donkey, row=donkey_at[0],
                                                                         col=donkey_at[1])
    water = state.water if level is None else dataclasses.replace(state.water, level=np.full(COLS, float(level)))
    return observe(dataclasses.replace(state, world=world, stones=s_stones, donkey=donkey, water=water), Role.DONKEY)
