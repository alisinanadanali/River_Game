"""Shrek (MODEL.md §5, S-01 … S-08; TICK.md step 2).

Shrek walks the south bank (row −1), aims at a river row and uses at most one ability per tick. Each rule is a
small pure function; shrek_stage chains them in the TICK.md step 2 sub-order and emits the events.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING

from engine.actions import Ability, Aim, ShrekMove
from engine.config import Config
from engine.events import DamStarted, ReleaseReason, ShrekAimed, ShrekMoved
from engine.water import release_dam, start_dam

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


def cool_down(shrek: Shrek) -> Shrek:
    """S-03 (TICK.md step 11): each cooldown drops by one tick, not below 0."""
    if shrek.throw_cooldown == 0 and shrek.rock_cooldown == 0:
        return shrek
    return dataclasses.replace(
        shrek, throw_cooldown=max(shrek.throw_cooldown - 1, 0), rock_cooldown=max(shrek.rock_cooldown - 1, 0)
    )


def aim_cell(shrek: Shrek) -> tuple[int, int]:
    """S-02: the cell Shrek aims at, (aim_row, col)."""
    return shrek.aim_row, shrek.col


def shrek_stage(tick: Tick) -> Tick:
    """TICK.md step 2: (a) dam, (b) walk, (c) aim. (d) abilities arrive with S-04 and S-07."""
    tick = dam_stage(tick)
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


def dam_stage(tick: Tick) -> Tick:
    """S-08 (TICK.md step 2a): any ability but DAM lets an active dam go (W-05); DAM on an idle dam starts one."""
    state, ability = tick.state, tick.actions.shrek.ability
    if state.dam.active and ability is not Ability.DAM:
        return release_dam(tick, ReleaseReason.MANUAL)
    if not state.dam.active and ability is Ability.DAM:
        dam = start_dam(state.dam, state.shrek.col, tick.t)
        tick = dataclasses.replace(tick, state=dataclasses.replace(state, dam=dam))
        return tick.emit(DamStarted, col=dam.col)
    return tick


def _set_shrek(tick: Tick, shrek: Shrek) -> Tick:
    return dataclasses.replace(tick, state=dataclasses.replace(tick.state, shrek=shrek))
