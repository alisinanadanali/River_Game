"""Catching (MODEL.md S-05, S-06, I-05; TICK.md steps 4 and 8): items meeting the donkey's bags.

Kept apart from items.py and donkey.py because catching needs both, while the donkey (dropping items when it
slips or is swept) already needs items.py; this way the imports stay one-way: items ← donkey ← catching.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from engine.donkey import bag_of, fits, in_river, push, stance_ready, with_bag
from engine.events import (
    CatchSource, ItemBounced, ItemCaught, ItemMissed, ItemStatus, LostReason, MissReason, ProjectileKind, ReturnCause,
    Side,
)
from engine.evolve import evolve
from engine.items import (
    Projectile, drift, drop_into_water, item_type, landing_cell, lose, return_to_bank, round_half_up, set_item,
)

if TYPE_CHECKING:  # engine/tick.py imports engine/state.py, which imports engine/donkey.py
    from engine.tick import Tick


def try_bag(tick: Tick, item_id: int, side: Side) -> tuple[Tick, bool]:
    """D-09: put the item into the `side` bag if it fits; (tick, whether it went in). No event."""
    state = tick.state
    t = item_type(state.config.items, state.items[item_id].kind)
    bag = bag_of(state.donkey, side)
    if not fits(bag, t.mass_kg, t.volume, state.config.donkey):
        return tick, False
    donkey = with_bag(state.donkey, side, push(bag, item_id, t.mass_kg, t.volume))
    tick = evolve(tick, state=evolve(state, donkey=donkey))
    return set_item(tick, evolve(state.items[item_id], status=ItemStatus.IN_BAG, pos=None)), True


def projectiles_stage(tick: Tick) -> Tick:
    """TICK.md step 4: every projectile not thrown this tick counts down; those reaching 0 land, in id order."""
    projectiles = tick.state.projectiles
    if not projectiles:
        return tick
    flying, landing = [], []
    for p in projectiles:
        if p.thrown_at == tick.t:
            flying.append(p)  # S-04: not moved in its throw tick
        elif p.ticks_left > 1:
            flying.append(evolve(p, ticks_left=p.ticks_left - 1))
        else:
            landing.append(p)
    tick = evolve(tick, state=evolve(tick.state, projectiles=tuple(flying)))
    for p in sorted(landing, key=lambda p: p.item_id):
        tick = _land_handoff(tick, p) if p.kind is ProjectileKind.HANDOFF else _land_throw(tick, p)
    return tick


def _land_handoff(tick: Tick, p: Projectile) -> Tick:
    """S-06: into the stance-side bag if the donkey is still there in stance, else back to the queue."""
    donkey = tick.state.donkey
    if (donkey.row, donkey.col) == p.target and donkey.stance is not Side.NONE:
        tick, ok = try_bag(tick, p.item_id, donkey.stance)
        if ok:
            return tick.emit(ItemCaught, item_id=p.item_id, side=donkey.stance, source=CatchSource.HANDOFF,
                             miss_distance=0.0)
    return return_to_bank(tick, p.item_id, ReturnCause.HANDOFF_CANCELLED)


def _land_throw(tick: Tick, p: Projectile) -> Tick:
    """S-05: caught, bounced off a full bag, or missed (then the landing cell decides)."""
    state = tick.state
    donkey, rows, cols = state.donkey, state.config.map.rows, state.config.map.cols
    distance = math.hypot(p.landing[0] - donkey.row, p.landing[1] - donkey.col)
    if not in_river(donkey, rows):
        reason = MissReason.DONKEY_ON_BANK
    elif donkey.stance is Side.NONE:
        reason = MissReason.NO_STANCE
    elif not stance_ready(donkey, tick.t):
        reason = MissReason.STANCE_TOO_LATE
    elif distance > state.config.shrek.catch_radius_cells:
        reason = MissReason.OUT_OF_RADIUS
    else:
        tick, ok = try_bag(tick, p.item_id, donkey.stance)
        if ok:
            return tick.emit(ItemCaught, item_id=p.item_id, side=donkey.stance, source=CatchSource.FLIGHT,
                             miss_distance=distance)
        tick = tick.emit(ItemBounced, item_id=p.item_id, side=donkey.stance)
        return drop_into_water(tick, p.item_id, donkey.row, float(donkey.col))
    tick = tick.emit(ItemMissed, item_id=p.item_id, landing=p.landing, miss_distance=distance, reason=reason)
    row, col = landing_cell(p.landing)
    if row < 0:
        return return_to_bank(tick, p.item_id, ReturnCause.LANDED_ON_BANK)
    if row > rows - 1 or not 0 <= col < cols:
        return lose(tick, p.item_id, LostReason.OFF_MAP)
    return drop_into_water(tick, p.item_id, row, p.landing[1])


def floating_stage(tick: Tick) -> Tick:
    """TICK.md step 8: for each floating item in id order, first the I-05 catch, then the I-04 drift."""
    floating = [i for i in tick.state.items if i.status is ItemStatus.FLOATING]
    for item in floating:
        tick, ok = _catch_floating(tick, item)
        if not ok:
            tick = drift(tick, tick.state.items[item.id])
    return tick


def _catch_floating(tick: Tick, item) -> tuple[Tick, bool]:
    """I-05: the donkey in the item's cell (r, round(x)), in a valid stance, with room in the stance bag."""
    donkey = tick.state.donkey
    row, x = item.pos
    if (donkey.row, donkey.col) != (row, round_half_up(x)) or not stance_ready(donkey, tick.t):
        return tick, False
    tick, ok = try_bag(tick, item.id, donkey.stance)
    if ok:
        tick = tick.emit(ItemCaught, item_id=item.id, side=donkey.stance, source=CatchSource.FLOATING,
                         miss_distance=abs(x - donkey.col))
    return tick, ok
