"""I-05: a floating item is caught (ItemCaught(floating), miss_distance |x − c|) when the donkey is in its cell
(r, round(x)), in a valid stance (D-08) and the stance bag has room; no room → no catch and no bounce. Several
items in one tick are caught in id order as long as they fit. The catch comes before the drift (step 8).
"""

import pytest

from engine.actions import Actions, DonkeyAction
from engine.donkey import Bag, Side
from engine.events import CatchSource, ItemBounced, ItemCaught
from engine.items import Item, ItemStatus

from tests.support import run, set_up, still

CFG = still()
LINE = ["...." + "#" + "...."] * 9
READY = {"row": 2, "col": 4, "stance": Side.LEFT, "stance_since": -1}


def afloat(*xs, kinds=None, donkey=READY):
    kinds = kinds or ["apple_crate"] * len(xs)
    items = tuple(Item(id=i, kind=k, status=ItemStatus.FLOATING, pos=(2, x)) for i, (x, k) in enumerate(zip(xs, kinds)))
    return set_up(CFG, LINE, items=items, donkey=donkey)


def caught(trace):
    return [(e.t, e.item_id, e.side, e.source, round(e.miss_distance, 9)) for e in trace.events if isinstance(e, ItemCaught)]


def test_caught_in_the_donkeys_cell():
    trace = run(CFG, 1, [Actions()], start=afloat(3.6))
    assert caught(trace) == [(0, 0, Side.LEFT, CatchSource.FLOATING, 0.4)]
    assert trace.states[0].donkey.bag_left.items == (0,) and trace.states[0].items[0].status is ItemStatus.IN_BAG


def test_the_catch_comes_before_the_drift():
    # At 3.6 the item is in column 4 now; after drifting (4.1) it would still be, but at 4.4 → 4.9 it would not.
    trace = run(CFG, 1, [Actions()], start=afloat(4.4))
    assert len(caught(trace)) == 1


@pytest.mark.parametrize(("x", "is_caught"), [(3.5, True), (4.49, True), (4.5, False), (3.49, False)])
def test_round_half_up_decides_the_cell(x, is_caught):
    assert bool(caught(run(CFG, 1, [Actions()], start=afloat(x)))) is is_caught


def test_a_stance_from_this_tick_is_too_late():
    start = afloat(4.0, donkey={"row": 2, "col": 4})
    trace = run(CFG, 1, [Actions(donkey=DonkeyAction.STANCE_LEFT), Actions()], start=start)
    assert [t for t, *_ in caught(trace)] == []  # at t=1 the apple has drifted to 5.0 (column 5)


def test_a_stance_one_tick_old_catches():
    start = afloat(3.0, donkey={"row": 2, "col": 4})
    trace = run(CFG, 1, [Actions(donkey=DonkeyAction.STANCE_LEFT), Actions()], start=start)
    assert [t for t, *_ in caught(trace)] == [1]  # 3.0 → 3.5 after tick 0 (column 4), caught at t=1


def test_no_room_no_catch_and_no_bounce():
    # A watermelon in the left bag leaves no room for a floating one (100 kg > 60 kg).
    items = (Item(id=0, kind="watermelon", status=ItemStatus.FLOATING, pos=(2, 4.0)),
             Item(id=1, kind="watermelon", status=ItemStatus.IN_BAG))
    start = set_up(CFG, LINE, items=items, donkey={**READY, "bag_left": Bag(items=(1,), mass=50.0, volume=3)})
    trace = run(CFG, 1, [Actions()], start=start)
    assert caught(trace) == [] and not any(isinstance(e, ItemBounced) for e in trace.events)
    assert trace.states[0].items[0].status is ItemStatus.FLOATING


def test_several_items_in_id_order_while_they_fit():
    # 50 + 10 = 60 kg fits the left bag; the second watermelon does not.
    start = afloat(4.0, 4.2, 3.8, kinds=["watermelon", "watermelon", "apple_crate"])
    trace = run(CFG, 1, [Actions()], start=start)
    assert [i for _, i, *_ in caught(trace)] == [0, 2]
    assert trace.states[0].items[1].status is ItemStatus.FLOATING


def test_another_row_is_not_caught():
    start = set_up(CFG, LINE, items=(Item(id=0, kind="apple_crate", status=ItemStatus.FLOATING, pos=(3, 4.0)),),
                   donkey=READY)
    assert caught(run(CFG, 1, [Actions()], start=start)) == []
