"""I-04: an item in the water at (r, x) floats (FLOATING, pos (r, x)) if its type floats, else sinks (ItemSank,
ItemLost(sank)). A floating item drifts x += flow_speed each tick (step 8, after the I-05 catch) and is lost
(drifted_off) once x > C − 0.5. Its row never changes.
"""

import pytest

from engine.actions import Actions
from engine.events import ItemLost, LostReason
from engine.items import Item, ItemStatus

from tests.support import run, set_up, still

CFG = still()
V = CFG.water.flow_speed_cols_per_tick
EDGE = CFG.map.cols - 0.5
LINE = ["........."] * 9


def floating(x: float, row: int = 2, kind: str = "apple_crate"):
    return set_up(CFG, LINE, items=(Item(id=0, kind=kind, status=ItemStatus.FLOATING, pos=(row, x)),))


def test_drifts_east_at_flow_speed_and_keeps_its_row():
    trace = run(CFG, 1, [Actions()] * 4, start=floating(1.0))
    assert [s.items[0].pos for s in trace.states] == [(2, 1.0 + k * V) for k in (1, 2, 3, 4)]


def test_lost_once_past_the_east_edge():
    x0 = EDGE - 1.5 * V  # one step later still in (x ≤ C − 0.5), two steps later out
    trace = run(CFG, 1, [Actions()] * 3, start=floating(x0))
    assert [s.items[0].status for s in trace.states] == [ItemStatus.FLOATING, ItemStatus.LOST, ItemStatus.LOST]
    assert [(e.t, e.reason, e.origin) for e in trace.events if isinstance(e, ItemLost)] == [
        (1, LostReason.DRIFTED_OFF, ItemStatus.FLOATING)
    ]
    assert trace.states[-1].items[0].pos is None


def test_exactly_on_the_edge_is_still_in():
    trace = run(CFG, 1, [Actions()], start=floating(EDGE - V))
    assert trace.states[0].items[0].status is ItemStatus.FLOATING
    assert trace.states[0].items[0].pos == (2, pytest.approx(EDGE))


@pytest.mark.parametrize(("kind", "floats"), [("apple_crate", True), ("potato_sack", False), ("watermelon", True)])
def test_the_type_decides(kind, floats):
    assert CFG.items.types[kind].floats is floats
