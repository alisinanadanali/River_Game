"""S-06: THROW while the donkey stands in stance on the south bank in Shrek's column is a noise-free handoff
(HANDOFF, bank_load_ticks). It goes into the chosen bag if the donkey is still there in stance when it lands
(the one-tick-earlier rule of D-08 does not apply); otherwise, or if the bag is full, it returns to the queue.
"""

from engine.actions import Ability, Actions, DonkeyAction, ShrekAction
from engine.donkey import Bag, Side
from engine.events import CatchSource, ItemCaught, ItemLost, ItemReturnedToBank, ItemThrown, LostReason, ProjectileKind, ReturnCause
from engine.items import Bank, Item, ItemStatus

from tests.support import run, set_up, still

CFG = still()
LINE = ["...." + "#" + "...."] * 9
THROW = Actions(shrek=ShrekAction(ability=Ability.THROW))
NOOP, LEFT = Actions(), Actions(donkey=DonkeyAction.STANCE_LEFT)
READY = {"stance": Side.LEFT, "stance_since": 0}  # on the bank in column 4, next to Shrek


def loaded(kinds=("watermelon",), donkey=READY, queue=None):
    items = tuple(Item(id=i, kind=k, status=ItemStatus.ON_BANK) for i, k in enumerate(kinds))
    return set_up(CFG, LINE, items=items, bank=Bank(queue=tuple(range(len(kinds))) if queue is None else queue), donkey=donkey)


def of(trace, kind):
    return [e for e in trace.events if isinstance(e, kind)]


def test_handoff_is_noise_free_and_takes_bank_load_ticks():
    trace = run(CFG, 1, [THROW] + [NOOP] * 3, start=loaded())
    (thrown,) = of(trace, ItemThrown)
    assert (thrown.kind, thrown.target, thrown.sigma, thrown.flight_ticks) == (
        ProjectileKind.HANDOFF, (-1, 4), 0.0, CFG.shrek.bank_load_ticks
    )
    assert [(e.t, e.side, e.source, e.miss_distance) for e in of(trace, ItemCaught)] == [
        (CFG.shrek.bank_load_ticks, Side.LEFT, CatchSource.HANDOFF, 0.0)
    ]
    assert trace.states[-1].donkey.bag_left == Bag(items=(0,), mass=50.0, volume=3)


def test_a_stance_taken_in_the_throw_tick_comes_too_late_to_make_a_handoff():
    # Step 2 (throw) runs before step 3 (stance): without a stance at the throw it is a normal throw.
    trace = run(CFG, 1, [Actions(donkey=DonkeyAction.STANCE_LEFT, shrek=ShrekAction(ability=Ability.THROW))],
                start=loaded(donkey={}))
    assert of(trace, ItemThrown)[0].kind is ProjectileKind.THROW


def test_no_handoff_from_another_column():
    trace = run(CFG, 1, [THROW], start=loaded(donkey={**READY, "col": 3}))
    assert of(trace, ItemThrown)[0].kind is ProjectileKind.THROW


def test_donkey_leaves_and_the_item_returns_to_the_back_of_the_queue():
    trace = run(CFG, 1, [THROW, Actions(donkey=DonkeyAction.MOVE_E), NOOP, NOOP], start=loaded(("watermelon", "apple_crate")))
    assert [(e.t, e.item_id, e.cause) for e in of(trace, ItemReturnedToBank)] == [(2, 0, ReturnCause.HANDOFF_CANCELLED)]
    assert trace.states[2].bank.queue == (1, 0)
    assert of(trace, ItemCaught) == []


def test_a_new_stance_on_the_other_side_still_counts():
    trace = run(CFG, 1, [THROW, Actions(donkey=DonkeyAction.STANCE_RIGHT), NOOP], start=loaded())
    assert [(e.side, e.source) for e in of(trace, ItemCaught)] == [(Side.RIGHT, CatchSource.HANDOFF)]


def test_a_full_bag_sends_it_back():
    items = (Item(id=0, kind="watermelon", status=ItemStatus.ON_BANK), Item(id=1, kind="watermelon", status=ItemStatus.IN_BAG))
    start = set_up(CFG, LINE, items=items, bank=Bank(queue=(0,)),
                   donkey={**READY, "bag_left": Bag(items=(1,), mass=50.0, volume=3)})
    trace = run(CFG, 1, [THROW, NOOP, NOOP], start=start)
    assert [e.cause for e in of(trace, ItemReturnedToBank)] == [ReturnCause.HANDOFF_CANCELLED]


def test_returning_to_a_full_queue_loses_it():
    # Arrivals refill the place the throw freed (step 9 of the throw tick), so the queue is full on return.
    cfg = still({"items": {"arrival_rate_per_tick": 5.0}})
    items = (Item(id=0, kind="watermelon", status=ItemStatus.ON_BANK),)
    start = set_up(cfg, LINE, items=items, bank=Bank(queue=(0,)), donkey=READY)
    trace = run(cfg, 1, [THROW, Actions(donkey=DonkeyAction.MOVE_E), NOOP], start=start)
    assert len(trace.states[1].bank.queue) == cfg.items.bank_capacity
    returned = [(e.reason, e.origin) for e in of(trace, ItemLost) if e.item_id == 0]
    assert returned == [(LostReason.BANK_OVERFLOW, ItemStatus.IN_FLIGHT)]
    assert of(trace, ItemReturnedToBank) == []
