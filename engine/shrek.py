"""Shrek (MODEL.md §5, S-01 … S-08; TICK.md step 2).

Shrek walks the south bank (row −1), aims at a river row and uses at most one ability per tick. Each rule is a
small pure function; shrek_stage chains them in the TICK.md step 2 sub-order and emits the events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from engine.actions import Ability, Aim, ShrekMove
from engine.config import Config, ShrekConfig
from engine.events import DamStarted, ItemStatus, ItemThrown, ProjectileKind, ReleaseReason, ShrekAimed, ShrekMoved, Side
from engine.evolve import evolve
from engine.items import Bank, Projectile, item_type, landing_point, set_item
from engine.stones import throw_rock
from engine.water import release_dam, start_dam

if TYPE_CHECKING:  # engine/tick.py imports engine/state.py, which imports this module
    from engine.donkey import Donkey
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
    return evolve(
        shrek, throw_cooldown=max(shrek.throw_cooldown - 1, 0), rock_cooldown=max(shrek.rock_cooldown - 1, 0)
    )


def throw_sigma(aim_row: int, mass: float, shrek_cfg: ShrekConfig) -> float:
    """S-04: σ = σ₀ + σ₁·(aim_row + 1) + σ₂·m, in cells; aim_row + 1 is the distance from Shrek in rows."""
    return (
        shrek_cfg.throw_sigma0_cells
        + shrek_cfg.throw_sigma_per_row_cells * (aim_row + 1)
        + shrek_cfg.throw_sigma_per_kg_cells * mass
    )


def is_handoff(donkey: Donkey, shrek: Shrek) -> bool:
    """S-06: a throw now would be a handoff: the donkey in a stance on the south bank, in Shrek's column."""
    return donkey.row == -1 and donkey.col == shrek.col and donkey.stance is not Side.NONE


def aim_cell(shrek: Shrek) -> tuple[int, int]:
    """S-02: the cell Shrek aims at, (aim_row, col)."""
    return shrek.aim_row, shrek.col


def shrek_stage(tick: Tick) -> Tick:
    """TICK.md step 2: (a) dam, (b) walk, (c) aim, (d) ability. THROW arrives with S-04."""
    tick = dam_stage(tick)
    cfg, shrek, action = tick.state.config, tick.state.shrek, tick.actions.shrek
    col = walk(shrek.col, action.move, cfg.map.cols)
    row = aim(shrek.aim_row, action.aim, cfg.map.rows)
    if (col, row) != (shrek.col, shrek.aim_row):  # most ticks: nothing to copy
        tick = _set_shrek(tick, evolve(shrek, col=col, aim_row=row))
        if col != shrek.col:
            tick = tick.emit(ShrekMoved, from_col=shrek.col, to_col=col)
        if row != shrek.aim_row:
            tick = tick.emit(ShrekAimed, row=row)
    return ability_stage(tick)


def ability_stage(tick: Tick) -> Tick:
    """TICK.md step 2(d): THROW (S-04, S-06) or ROCK (S-07), each starting its cooldown (S-03)."""
    shrek, cfg = tick.state.shrek, tick.state.config
    ability = tick.actions.shrek.ability
    if ability is Ability.ROCK:
        tick = throw_rock(tick, *aim_cell(shrek))
        return _set_shrek(tick, evolve(shrek, rock_cooldown=cfg.shrek.rock_cooldown_ticks))
    if ability is Ability.THROW:
        tick = throw(tick)
        return _set_shrek(tick, evolve(shrek, throw_cooldown=cfg.shrek.throw_cooldown_ticks))
    return tick


def throw(tick: Tick) -> Tick:
    """S-04 / S-06: the head of the queue becomes a projectile. Step 1 has made sure the queue is not empty.

    With the donkey in stance on the south bank in Shrek's column it is a noise-free HANDOFF to (−1, col);
    otherwise a THROW at the aim cell, landing where this tick's u_throw puts it.
    """
    state = tick.state
    shrek, donkey, cfg = state.shrek, state.donkey, state.config.shrek
    item_id = state.bank.queue[0]
    item = state.items[item_id]
    if is_handoff(donkey, shrek):
        kind, target, sigma, flight = ProjectileKind.HANDOFF, (-1, shrek.col), 0.0, cfg.bank_load_ticks
        landing = (float(target[0]), float(target[1]))
    else:
        kind, target, flight = ProjectileKind.THROW, aim_cell(shrek), cfg.throw_flight_ticks
        sigma = throw_sigma(shrek.aim_row, item_type(state.config.items, item.kind).mass_kg, cfg)
        landing = landing_point(target, sigma, tick.u_throw)
    p = Projectile(item_id=item_id, kind=kind, target=target, landing=landing, sigma=sigma, ticks_left=flight,
                   thrown_at=tick.t)
    tick = evolve(tick, state=evolve(state, bank=Bank(queue=state.bank.queue[1:]), projectiles=state.projectiles + (p,)))
    tick = set_item(tick, evolve(item, status=ItemStatus.IN_FLIGHT, pos=(float(target[0]), float(target[1]))))
    return tick.emit(ItemThrown, item_id=item_id, kind=kind, from_col=shrek.col, target=target, sigma=sigma,
                     flight_ticks=flight)


def dam_stage(tick: Tick) -> Tick:
    """S-08 (TICK.md step 2a): any ability but DAM lets an active dam go (W-05); DAM on an idle dam starts one."""
    state, ability = tick.state, tick.actions.shrek.ability
    if state.dam.active and ability is not Ability.DAM:
        return release_dam(tick, ReleaseReason.MANUAL)
    if not state.dam.active and ability is Ability.DAM:
        dam = start_dam(state.dam, state.shrek.col, tick.t)
        tick = evolve(tick, state=evolve(state, dam=dam))
        return tick.emit(DamStarted, col=dam.col)
    return tick


def _set_shrek(tick: Tick, shrek: Shrek) -> Tick:
    return evolve(tick, state=evolve(tick.state, shrek=shrek))
