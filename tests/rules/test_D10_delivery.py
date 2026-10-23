"""D-10: while the donkey is on the north bank (row R), every item in its bags is delivered each tick, in id order,
and its points are added to the score. No key is needed.
"""

from engine.actions import Actions, DonkeyAction
from engine.donkey import Bag
from engine.events import GameOver, ItemDelivered
from engine.items import Item, ItemStatus

from tests.support import run, set_up, still

CFG = still({"map": {"rows": 3, "cols": 5}, "time": {"game_length_ticks": 5}})
LINE = ["..#..", "..#..", "..#.."]
N = Actions(donkey=DonkeyAction.MOVE_N)
ITEMS = (
    Item(id=0, kind="watermelon", status=ItemStatus.IN_BAG),
    Item(id=1, kind="apple_crate", status=ItemStatus.IN_BAG),
    Item(id=2, kind="potato_sack", status=ItemStatus.IN_BAG),
)
BAGS = {"bag_left": Bag(items=(2, 0), mass=80.0, volume=5), "bag_right": Bag(items=(1,), mass=10.0, volume=1)}


def delivered(trace):
    return [(e.t, e.item_id, e.kind, e.points) for e in trace.events if isinstance(e, ItemDelivered)]


def test_arriving_on_the_north_bank_delivers_everything_in_id_order():
    start = set_up(CFG, LINE, items=ITEMS, donkey={"row": 2, "col": 2, **BAGS})
    trace = run(CFG, 1, [N, Actions()], start=start)
    assert delivered(trace) == [(0, 0, "watermelon", 6), (0, 1, "apple_crate", 1), (0, 2, "potato_sack", 3)]
    state = trace.states[0]
    assert state.score == 10
    assert {i.status for i in state.items} == {ItemStatus.DELIVERED}
    assert state.donkey.bag_left == Bag() == state.donkey.bag_right


def test_nothing_happens_elsewhere():
    start = set_up(CFG, LINE, items=ITEMS, donkey={"row": 2, "col": 2, **BAGS})
    trace = run(CFG, 1, [Actions()], start=start)
    assert delivered(trace) == [] and trace.states[0].score == 0


def test_the_score_reaches_game_over():
    start = set_up(CFG, LINE, items=ITEMS, donkey={"row": 2, "col": 2, **BAGS})
    trace = run(CFG, 1, [N] + [Actions()] * 4, start=start)
    assert trace.events[-1] == GameOver(t=4, seq=0, reason=trace.events[-1].reason, score=10)


def test_a_whole_crossing():
    # Bank to bank over three stones with one apple in the bag: delivered in the arrival tick.
    apple = (Item(id=0, kind="apple_crate", status=ItemStatus.IN_BAG),)
    start = set_up(CFG, LINE, items=apple, donkey={"bag_right": Bag(items=(0,), mass=10.0, volume=1)})
    trace = run(CFG, 1, [N, N, N, N], start=start)
    assert [(e.t, e.item_id) for e in trace.events if isinstance(e, ItemDelivered)] == [(3, 0)]
    assert trace.states[-1].score == CFG.items.types["apple_crate"].points
