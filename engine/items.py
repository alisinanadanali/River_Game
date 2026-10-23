"""Items (MODEL.md §6, I-01 … I-05; TICK.md steps 4, 8 and 9).

Items arrive at the south bank, wait in a FIFO queue, fly, ride in the donkey's bags, float, and end up
DELIVERED or LOST. GameState.items holds every item ever born, in id order (items[i].id == i), so an item is
updated in place by id and conservation (INV-01) can always be counted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from engine.config import ItemsConfig, ItemType
from engine.events import ItemArrived, ItemLost, ItemStatus, LostReason
from engine.evolve import evolve
from engine.rng import Rngs, draw

if TYPE_CHECKING:  # engine/tick.py imports engine/state.py, which imports this module
    from engine.tick import Tick

__all__ = ["Bank", "Item", "ItemStatus", "LostReason"]  # the enums live in engine.events (event fields)


@dataclass(frozen=True, kw_only=True)
class Item:
    """ENTITIES.md Item. mass, volume, points and floats are read from config items.types[kind]."""

    id: int
    kind: str
    status: ItemStatus
    pos: tuple[float, float] | None = None   # FLOATING: (row, x)
    lost_reason: LostReason | None = None


@dataclass(frozen=True, kw_only=True)
class Bank:
    """ENTITIES.md Bank: the FIFO queue next to Shrek; the head is queue[0]."""

    queue: tuple[int, ...] = ()


def item_type(items_cfg: ItemsConfig, kind: str) -> ItemType:
    return items_cfg.types[kind]


def kind_of(u: float, items_cfg: ItemsConfig) -> str:
    """I-01: inverse CDF over the item types in sorted name order (independent of the YAML order)."""
    names = sorted(items_cfg.types)
    total = 0.0
    for name in names:
        total += items_cfg.types[name].prob
        if u < total:
            return name
    return names[-1]  # u within rounding of 1 (the probabilities sum to 1 only within PROB_SUM_ABS_TOL)


def draw_arrivals(rngs: Rngs, items_cfg: ItemsConfig) -> tuple[np.ndarray, Rngs]:
    """I-01, R-02: N_t ~ Poisson(λ_items), then N_t uniforms, in one rng_items call every tick."""
    return draw(rngs, "items", lambda g: g.random(g.poisson(items_cfg.arrival_rate_per_tick)))


def set_item(tick: Tick, item: Item) -> Tick:
    """Replace items[item.id]."""
    items = tick.state.items
    return evolve(tick, state=evolve(tick.state, items=items[: item.id] + (item,) + items[item.id + 1:]))


def lose(tick: Tick, item_id: int, reason: LostReason, origin: ItemStatus | None = None) -> Tick:
    """I-03: the item becomes LOST (absorbing); ItemLost records the status it had before."""
    item = tick.state.items[item_id]
    origin = item.status if origin is None else origin
    tick = set_item(tick, evolve(item, status=ItemStatus.LOST, pos=None, lost_reason=reason))
    return tick.emit(ItemLost, item_id=item_id, reason=reason, origin=origin)


def bank_stage(tick: Tick) -> Tick:
    """TICK.md step 9: I-01 arrivals join the queue (I-02); at a full queue they are lost (bank_overflow)."""
    cfg = tick.state.config.items
    us, rngs = draw_arrivals(tick.rngs, cfg)
    tick = evolve(tick, rngs=rngs)
    for u in us:
        state = tick.state
        item = Item(id=len(state.items), kind=kind_of(float(u), cfg), status=ItemStatus.ON_BANK)
        full = len(state.bank.queue) >= cfg.bank_capacity
        queue = state.bank.queue if full else state.bank.queue + (item.id,)
        tick = evolve(tick, state=evolve(state, items=state.items + (item,), bank=Bank(queue=queue)))
        tick = tick.emit(ItemArrived, item_id=item.id, kind=item.kind, queue_len=len(queue))
        if full:
            tick = set_item(tick, evolve(item, status=ItemStatus.LOST, lost_reason=LostReason.BANK_OVERFLOW))
            tick = tick.emit(ItemLost, item_id=item.id, reason=LostReason.BANK_OVERFLOW, origin=None)
    return tick
