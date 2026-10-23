"""I-02: the bank queue is FIFO with capacity bank_capacity; an item arriving at a full queue is lost
(ItemArrived, then ItemLost(bank_overflow, origin=None)).
"""

from engine.actions import Actions
from engine.events import ItemArrived, ItemLost, LostReason
from engine.items import ItemStatus

from tests.support import config_with, run

FLOOD = config_with({"items": {"arrival_rate_per_tick": 3.0}})  # fills the 5 places within a few ticks
CAP = FLOOD.items.bank_capacity


def test_queue_never_exceeds_capacity_and_overflow_is_lost():
    trace = run(FLOOD, 1, [Actions()] * 10)
    assert max(len(s.bank.queue) for s in trace.states) == CAP
    items = trace.states[-1].items
    assert [i.id for i in items if i.status is ItemStatus.ON_BANK] == list(trace.states[-1].bank.queue)
    lost = [i for i in items if i.status is ItemStatus.LOST]
    assert lost and all(i.lost_reason is LostReason.BANK_OVERFLOW for i in lost)
    assert len(items) == CAP + len(lost)


def test_fifo_keeps_arrival_order():
    queue = run(FLOOD, 1, [Actions()] * 10).states[-1].bank.queue
    assert list(queue) == sorted(queue) == list(range(CAP))  # the first five arrivals stay, nothing is thrown yet


def test_overflow_events():
    trace = run(FLOOD, 1, [Actions()] * 10)
    first_lost = next(e for e in trace.events if isinstance(e, ItemLost))
    i = trace.events.index(first_lost)
    arrived = trace.events[i - 1]
    assert isinstance(arrived, ItemArrived) and arrived.item_id == first_lost.item_id
    assert arrived.queue_len == CAP
    assert (first_lost.reason, first_lost.origin) == (LostReason.BANK_OVERFLOW, None)


def test_queue_len_counts_after_the_arrival():
    trace = run(FLOOD, 1, [Actions()] * 10)
    lens = [e.queue_len for e in trace.events if isinstance(e, ItemArrived)]
    assert lens[:CAP] == list(range(1, CAP + 1))
