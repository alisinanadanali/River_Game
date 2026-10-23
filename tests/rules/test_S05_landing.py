"""S-05: when a projectile lands: a donkey in the river, in a valid stance (D-08) and within r_catch catches it
(ItemCaught(flight)), or it bounces off a full bag into the water (ItemBounced). Otherwise ItemMissed, and the
landing cell round(landing) (half up) decides: south of row 0 → back to the queue; north of R−1 or off the
columns → LOST(off_map); else the item falls into the water there (I-04), also when the cell is a stone.
"""

import pytest

from engine.actions import Ability, Actions, DonkeyAction, ShrekAction
from engine.donkey import Bag, Side
from engine.events import (
    CatchSource, ItemBounced, ItemCaught, ItemFloated, ItemLost, ItemMissed, ItemReturnedToBank, ItemSank,
    LostReason, MissReason, ProjectileKind, ReturnCause,
)
from engine.items import Bank, Item, ItemStatus, Projectile, landing_cell, round_half_up

from tests.support import run, set_up, still

# No throw noise: every throw lands exactly on its target.
CFG = still({"shrek": {"throw_sigma0_cells": 0.0, "throw_sigma_per_row_cells": 0.0, "throw_sigma_per_kg_cells": 0.0}})
LINE = ["...." + "#" + "...."] * 9   # a stone path up column 4, Shrek's column
THROW = Actions(shrek=ShrekAction(ability=Ability.THROW))
LEFT, NOOP = Actions(donkey=DonkeyAction.STANCE_LEFT), Actions()
STANDING = {"row": 0, "col": 4}      # the donkey on the first stone, where Shrek aims


def loaded(kinds=("apple_crate",), **fields):
    items = tuple(Item(id=i, kind=k, status=ItemStatus.ON_BANK) for i, k in enumerate(kinds))
    return set_up(CFG, LINE, items=items, bank=Bank(queue=tuple(range(len(kinds)))), **fields)


def of(trace, kind):
    return [e for e in trace.events if isinstance(e, kind)]


@pytest.mark.parametrize(("x", "r"), [(0.5, 1), (1.5, 2), (2.5, 3), (-0.5, 0), (-0.51, -1), (0.49, 0), (-1.5, -1)])
def test_round_half_up(x, r):
    # Python's round(2.5) is 2 ("banker's rounding"); MODEL S-05 wants half up.
    assert round_half_up(x) == r


@pytest.mark.parametrize(
    ("landing", "cell"),
    [((0.0, 4.0), (0, 4)), ((-0.49, 4.0), (0, 4)), ((-0.5, 4.0), (0, 4)), ((-0.51, 4.0), (-1, 4)),
     ((8.4, 8.4), (8, 8)), ((8.5, 4.0), (9, 4)), ((3.0, -0.6), (3, -1))],
)
def test_landing_cell(landing, cell):
    assert landing_cell(landing) == cell


def test_timing_example_catch():
    # TICK.md: THROW at t, STANCE at t+1, landing at t+2 → caught (the stance is one tick old).
    trace = run(CFG, 1, [THROW, LEFT, NOOP], start=loaded(donkey=STANDING))
    assert [(e.t, e.item_id, e.side, e.source) for e in of(trace, ItemCaught)] == [(2, 0, Side.LEFT, CatchSource.FLIGHT)]
    assert of(trace, ItemCaught)[0].miss_distance == pytest.approx(0.0)
    donkey = trace.states[-1].donkey
    assert donkey.bag_left == Bag(items=(0,), mass=10.0, volume=1)
    assert trace.states[-1].items[0].status is ItemStatus.IN_BAG


def test_timing_example_late_stance():
    trace = run(CFG, 1, [THROW, NOOP, LEFT], start=loaded(donkey=STANDING))
    assert [(e.t, e.reason) for e in of(trace, ItemMissed)] == [(2, MissReason.STANCE_TOO_LATE)]


def test_no_stance():
    trace = run(CFG, 1, [THROW, NOOP, NOOP], start=loaded(donkey=STANDING))
    assert [e.reason for e in of(trace, ItemMissed)] == [MissReason.NO_STANCE]


def test_donkey_on_the_bank():
    trace = run(CFG, 1, [THROW, NOOP, NOOP], start=loaded(donkey={"col": 0}))
    assert [e.reason for e in of(trace, ItemMissed)] == [MissReason.DONKEY_ON_BANK]


def test_out_of_radius():
    trace = run(CFG, 1, [THROW, LEFT, NOOP], start=loaded(donkey={"row": 2, "col": 4}))  # 2 rows away
    (missed,) = of(trace, ItemMissed)
    assert (missed.reason, missed.landing) == (MissReason.OUT_OF_RADIUS, (0.0, 4.0))
    assert missed.miss_distance == pytest.approx(2.0)


def test_a_missed_apple_floats_where_it_landed_even_on_a_stone():
    trace = run(CFG, 1, [THROW, NOOP, NOOP], start=loaded(donkey={"col": 0}))
    assert [(e.item_id, e.row, e.x) for e in of(trace, ItemFloated)] == [(0, 0, 4.0)]
    item = trace.states[2].items[0]
    assert (item.status, item.pos) == (ItemStatus.FLOATING, (0, 4.0))


def test_a_missed_potato_sinks():
    trace = run(CFG, 1, [THROW, NOOP, NOOP], start=loaded(("potato_sack",), donkey={"col": 0}))
    assert [(e.item_id, e.row, e.col) for e in of(trace, ItemSank)] == [(0, 0, 4)]
    assert [(e.reason, e.origin) for e in of(trace, ItemLost)] == [(LostReason.SANK, ItemStatus.IN_FLIGHT)]


def test_a_full_bag_bounces_the_item_into_the_water():
    full = Bag(items=(1,), mass=50.0, volume=3)  # a second 50 kg watermelon would exceed 60 kg (an apple would fit)
    items = (Item(id=0, kind="watermelon", status=ItemStatus.ON_BANK), Item(id=1, kind="watermelon", status=ItemStatus.IN_BAG))
    start = set_up(CFG, LINE, items=items, bank=Bank(queue=(0,)), donkey={**STANDING, "bag_left": full})
    trace = run(CFG, 1, [THROW, LEFT, NOOP], start=start)
    assert [(e.t, e.item_id, e.side) for e in of(trace, ItemBounced)] == [(2, 0, Side.LEFT)]
    assert of(trace, ItemCaught) == []
    assert [(e.row, e.x) for e in of(trace, ItemFloated)] == [(0, 4.0)]  # in the donkey's cell (I-04)


def landing_from(landing, kinds=("apple_crate",), queue=(), donkey=None):
    """A projectile about to land at `landing` (ticks_left 1), by default with the donkey away on the bank."""
    items = tuple(
        Item(id=i, kind=k, status=ItemStatus.IN_FLIGHT if i == 0 else ItemStatus.ON_BANK) for i, k in enumerate(kinds)
    )
    p = Projectile(item_id=0, kind=ProjectileKind.THROW, target=(0, 4), landing=landing, sigma=1.0, ticks_left=1,
                   thrown_at=-1)
    return set_up(CFG, LINE, items=items, projectiles=(p,), bank=Bank(queue=queue), donkey=donkey or {"col": 0})


def test_landing_on_the_south_bank_returns_to_the_queue():
    trace = run(CFG, 1, [NOOP], start=landing_from((-0.7, 4.0), kinds=("apple_crate", "apple_crate"), queue=(1,)))
    assert [(e.item_id, e.cause) for e in of(trace, ItemReturnedToBank)] == [(0, ReturnCause.LANDED_ON_BANK)]
    assert trace.states[0].bank.queue == (1, 0)  # to the back
    assert trace.states[0].items[0].status is ItemStatus.ON_BANK


def test_landing_on_the_south_bank_with_a_full_queue_is_lost():
    kinds = ("apple_crate",) * (1 + CFG.items.bank_capacity)
    trace = run(CFG, 1, [NOOP], start=landing_from((-0.7, 4.0), kinds=kinds, queue=tuple(range(1, len(kinds)))))
    assert [(e.item_id, e.reason, e.origin) for e in of(trace, ItemLost)] == [
        (0, LostReason.BANK_OVERFLOW, ItemStatus.IN_FLIGHT)
    ]


@pytest.mark.parametrize("landing", [(8.6, 4.0), (3.0, -0.6), (3.0, 8.5)])
def test_landing_off_the_map_is_lost(landing):
    trace = run(CFG, 1, [NOOP], start=landing_from(landing))
    assert [(e.reason, e.origin) for e in of(trace, ItemLost)] == [(LostReason.OFF_MAP, ItemStatus.IN_FLIGHT)]


@pytest.mark.parametrize(("offset", "caught"), [(0.0, True), (1.0, True), (1.0 + 1e-9, False)])
def test_the_catch_radius_is_inclusive(offset, caught):
    r = CFG.shrek.catch_radius_cells
    ready = {"row": 0, "col": 4, "stance": Side.RIGHT, "stance_since": -5}
    trace = run(CFG, 1, [NOOP], start=landing_from((0.0, 4.0 + offset * r), donkey=ready))
    assert bool(of(trace, ItemCaught)) is caught
