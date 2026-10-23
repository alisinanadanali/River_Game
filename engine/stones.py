"""Stones that change during a game (MODEL.md S-07; TICK.md steps 2(d) and 6).

Permanent stones keep their map height h_i (World) and gain a decaying raise r_i; temporary stones are made by
ROCK on water, sink every tick and vanish. Both live in one Stones value, like the waves in Water.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from engine.config import Config, ShrekConfig
from engine.events import RaiseTarget, TempStoneRaised, TempStoneSpawned, TempStoneVanished
from engine.evolve import evolve

if TYPE_CHECKING:  # engine/tick.py imports engine/state.py, which imports this module
    from engine.tick import Tick

__all__ = ["RaiseTarget", "Stones", "TempStone"]  # RaiseTarget lives in engine.events (event field)


@dataclass(frozen=True, kw_only=True)
class TempStone:
    """ENTITIES.md TempStone. Its stiffness is shrek.rock_stiffness_kg_per_cm (read from the config, not stored)."""

    id: int
    row: int
    col: int
    h: float          # cm, the stone's current height (D-01 uses it instead of h_i + r_i)
    spawned_at: int   # tick


@dataclass(frozen=True, kw_only=True, eq=False)
class Stones:
    """ENTITIES.md Stones. `raise_h` is r_i per cell, read-only, 0 on water."""

    raise_h: np.ndarray               # float[R, C], cm
    temp: tuple[TempStone, ...]       # in id order
    next_temp_id: int

    def __eq__(self, other):
        if not isinstance(other, Stones):
            return NotImplemented
        return (self.temp, self.next_temp_id) == (other.temp, other.next_temp_id) and np.array_equal(
            self.raise_h, other.raise_h
        )

    __hash__ = None  # equal by content, and numpy arrays are not hashable


def initial_stones(config: Config) -> Stones:
    """S-07: no raise anywhere and no temporary stone."""
    return Stones(raise_h=_read_only(np.zeros((config.map.rows, config.map.cols))), temp=(), next_temp_id=0)


def temp_at(stones: Stones, row: int, col: int) -> TempStone | None:
    """The temporary stone at (row, col), if any (at most one per cell: a second ROCK raises it)."""
    for stone in stones.temp:
        if stone.row == row and stone.col == col:
            return stone
    return None


def throw_rock(tick: Tick, row: int, col: int) -> Tick:
    """S-07 (TICK.md step 2d): raise a temporary or permanent stone, or make a temporary stone on water.

    Step 1 has already refused a spawn beyond rock_max_active, so a water cell here always gets its stone.
    """
    state = tick.state
    stones, shrek_cfg = state.stones, state.config.shrek
    delta = shrek_cfg.rock_raise_cm
    existing = temp_at(stones, row, col)
    if existing is not None:
        raised = evolve(existing, h=existing.h + delta)
        stones = evolve(stones, temp=tuple(raised if s is existing else s for s in stones.temp))
        return _set(tick, stones).emit(TempStoneRaised, row=row, col=col, delta_cm=delta, target=RaiseTarget.TEMP_STONE)
    if state.world.is_stone[row, col]:
        raise_h = stones.raise_h.copy()
        raise_h[row, col] += delta
        stones = evolve(stones, raise_h=_read_only(raise_h))
        return _set(tick, stones).emit(TempStoneRaised, row=row, col=col, delta_cm=delta, target=RaiseTarget.STONE)
    stone = TempStone(id=stones.next_temp_id, row=row, col=col, h=shrek_cfg.rock_initial_h_cm, spawned_at=tick.t)
    stones = evolve(stones, temp=stones.temp + (stone,), next_temp_id=stone.id + 1)
    return _set(tick, stones).emit(TempStoneSpawned, stone_id=stone.id, row=row, col=col, h=stone.h)


def sink_and_decay(stones: Stones, shrek_cfg: ShrekConfig) -> tuple[Stones, tuple[TempStone, ...]]:
    """S-07 (TICK.md step 6): temporary stones sink, those below rock_vanish_h_cm go; r_i decays to 0.

    Returns (new stones, vanished stones as they were last seen).
    """
    sunk = tuple(evolve(s, h=s.h - shrek_cfg.rock_sink_cm_per_tick) for s in stones.temp)
    kept = tuple(s for s in sunk if s.h >= shrek_cfg.rock_vanish_h_cm)
    gone = tuple(s for s in sunk if s.h < shrek_cfg.rock_vanish_h_cm)
    raise_h = stones.raise_h
    if raise_h.any():
        raise_h = _read_only(np.maximum(raise_h - shrek_cfg.rock_raise_decay_cm_per_tick, 0.0))
    return evolve(stones, temp=kept, raise_h=raise_h), gone


def stones_stage(tick: Tick) -> Tick:
    """TICK.md step 6: sink and decay, then TempStoneVanished per vanished stone (the donkey is swept in step 7)."""
    state = tick.state
    if not state.stones.temp and not state.stones.raise_h.any():
        return tick  # most ticks: nothing to do
    stones, gone = sink_and_decay(state.stones, state.config.shrek)
    tick = _set(tick, stones)
    donkey = state.donkey
    for s in gone:
        under = (donkey.row, donkey.col) == (s.row, s.col)
        tick = tick.emit(TempStoneVanished, stone_id=s.id, row=s.row, col=s.col, under_donkey=under)
    return tick


def _set(tick: Tick, stones: Stones) -> Tick:
    return evolve(tick, state=evolve(tick.state, stones=stones))


def _read_only(array: np.ndarray) -> np.ndarray:
    array.flags.writeable = False
    return array
