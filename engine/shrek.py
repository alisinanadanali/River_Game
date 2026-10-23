"""Shrek (MODEL.md §5, S-01 … S-08; TICK.md step 2).

Shrek walks the south bank (row −1), aims at a river row and uses at most one ability per tick. Each rule is a
small pure function; shrek_stage chains them in the TICK.md step 2 sub-order and emits the events.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING

from engine.actions import Aim, ShrekMove
from engine.config import Config
from engine.events import ShrekAimed, ShrekMoved

if TYPE_CHECKING:  # engine/tick.py imports engine/state.py, which imports this module
    from engine.tick import Tick


@dataclass(frozen=True, kw_only=True)
class Shrek:
    """ENTITIES.md Shrek. He always stands on the south bank, row −1."""

    col: int
    aim_row: int
    throw_cooldown: int = 0   # ticks, S-03
    rock_cooldown: int = 0    # ticks, S-03


def initial_shrek(config: Config) -> Shrek:
    """S-01, S-02: Shrek starts in column ⌊C/2⌋, aiming at row 0."""
    return Shrek(col=config.map.cols // 2, aim_row=0)


def walk(col: int, move: ShrekMove, cols: int) -> int:
    """S-01: one column west or east, clipped to [0, cols − 1]."""
    step = {ShrekMove.NONE: 0, ShrekMove.W: -1, ShrekMove.E: 1}[move]
    return min(max(col + step, 0), cols - 1)


def aim(aim_row: int, direction: Aim, rows: int) -> int:
    """S-02: one row up (north) or down, clipped to [0, rows − 1]."""
    step = {Aim.NONE: 0, Aim.UP: 1, Aim.DOWN: -1}[direction]
    return min(max(aim_row + step, 0), rows - 1)


def aim_cell(shrek: Shrek) -> tuple[int, int]:
    """S-02: the cell Shrek aims at, (aim_row, col)."""
    return shrek.aim_row, shrek.col


def shrek_stage(tick: Tick) -> Tick:
    """TICK.md step 2, sub-steps (b) walk and (c) aim. (a) dam and (d) abilities arrive with S-08, S-04, S-07."""
    cfg, shrek, action = tick.state.config, tick.state.shrek, tick.actions.shrek
    col = walk(shrek.col, action.move, cfg.map.cols)
    row = aim(shrek.aim_row, action.aim, cfg.map.rows)
    if (col, row) == (shrek.col, shrek.aim_row):
        return tick  # most ticks: nothing to copy
    tick = _set_shrek(tick, dataclasses.replace(shrek, col=col, aim_row=row))
    if col != shrek.col:
        tick = tick.emit(ShrekMoved, from_col=shrek.col, to_col=col)
    if row != shrek.aim_row:
        tick = tick.emit(ShrekAimed, row=row)
    return tick


def _set_shrek(tick: Tick, shrek: Shrek) -> Tick:
    return dataclasses.replace(tick, state=dataclasses.replace(tick.state, shrek=shrek))
