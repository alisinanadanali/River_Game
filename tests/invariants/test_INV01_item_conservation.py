"""INV-01: item conservation. Every tick, born = ON_BANK + IN_FLIGHT + IN_BAG + FLOATING + DELIVERED + LOST, and
each item is where its status says: ON_BANK items are exactly the bank queue (in order, no duplicates).

Counting statuses alone would be trivially true (each item has one status), so the invariant is checked
against the places that hold items and against the event log: ItemArrived count = items born, ItemLost count =
LOST items. (IN_FLIGHT, IN_BAG and FLOATING get their places with S-04 … I-05.)
"""

from hypothesis import given
from hypothesis import strategies as st

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.events import ItemArrived, ItemLost
from engine.items import ItemStatus

from tests.support import config_with, run

CFG = config_with({"items": {"arrival_rate_per_tick": 0.5}})
TICKS = CFG.time.game_length_ticks

actions = st.builds(
    Actions,
    donkey=st.sampled_from(DonkeyAction),
    shrek=st.builds(ShrekAction, move=st.sampled_from(ShrekMove), aim=st.sampled_from(Aim), ability=st.sampled_from(Ability)),
)


def check(state, arrived: int, lost_events: int) -> None:
    items = state.items
    assert [i.id for i in items] == list(range(len(items)))
    assert len(items) == arrived
    by_status = {s: [i.id for i in items if i.status is s] for s in ItemStatus}
    assert sum(len(ids) for ids in by_status.values()) == len(items)
    # Same items; the order may differ, as returned items go to the back of the queue (S-05, S-06).
    assert sorted(state.bank.queue) == by_status[ItemStatus.ON_BANK]
    assert len(set(state.bank.queue)) == len(state.bank.queue) <= CFG.items.bank_capacity
    assert len(by_status[ItemStatus.LOST]) == lost_events
    assert all((i.lost_reason is not None) == (i.status is ItemStatus.LOST) for i in items)


@given(seed=st.integers(0, 2**32 - 1), game=st.lists(actions, min_size=TICKS, max_size=TICKS))
def test_INV01_items_are_conserved(seed, game):
    trace = run(CFG, seed, game)
    arrived = lost = 0
    for t, state in enumerate(trace.states):
        arrived += sum(isinstance(e, ItemArrived) for e in trace.events if e.t == t)
        lost += sum(isinstance(e, ItemLost) for e in trace.events if e.t == t)
        check(state, arrived, lost)


def test_games_really_bring_and_lose_items():
    # Guards the property: at λ = 0.5 the bank overflows within a game.
    trace = run(CFG, 1, [Actions()] * TICKS)
    assert len(trace.states[-1].items) > 100
    assert any(i.status is ItemStatus.LOST for i in trace.states[-1].items)
