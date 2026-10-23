"""D-06: in KNEE, each tick u_slip[2] < knee_drop_prob drops the top item of the heavy side (δ = 0: u_slip[3]
< 0.5 → left) into the water of the donkey's cell (ItemDropped(knee), I-04). Empty bags: no effect.
"""

import math

from engine.actions import Actions
from engine.donkey import Bag, DepthState, Side
from engine.events import DropCause, ItemDropped
from engine.items import Item, ItemStatus
from engine.rng import draw_blocks
from engine.step import step

from tests.support import run, set_up, still

CFG = still({"map": {"rows": 3, "cols": 5}})
LINE = ["..#..", "..#..", "..#.."]
KNEE = {(0, 2): -5.0}  # still water: d = 9 + load effect → KNEE for a lightly loaded donkey
ITEMS = (Item(id=0, kind="apple_crate", status=ItemStatus.IN_BAG), Item(id=1, kind="watermelon", status=ItemStatus.IN_BAG))
BAGS = {"bag_left": Bag(items=(0,), mass=10.0, volume=1), "bag_right": Bag(items=(1,), mass=50.0, volume=3)}


def knee_start(seed=1, cfg=CFG):
    return set_up(cfg, LINE, KNEE, seed=seed, items=ITEMS, donkey={"row": 0, "col": 2, **BAGS})


def drops(events):
    return [(e.item_id, e.side, e.cause) for e in events if isinstance(e, ItemDropped)]


def test_u_slip_2_decides_and_the_heavy_side_loses_its_top():
    seen = 0
    for seed in range(60):
        state, rngs = knee_start(seed)
        _, u_slip, _ = draw_blocks(rngs)
        new, _, events = step(state, Actions(), rngs)
        assert new.donkey.depth_state is DepthState.KNEE
        expected = [(1, Side.RIGHT, DropCause.KNEE)] if u_slip[2] < CFG.donkey.knee_drop_prob else []
        assert drops(events) == expected
        seen += bool(expected)
    assert seen > 0


def test_always_drops_with_probability_one():
    cfg = still({"map": {"rows": 3, "cols": 5}, "donkey": {"knee_drop_prob": 1.0}})
    trace = run(cfg, 1, [Actions()] * 3, start=knee_start(cfg=cfg))
    assert drops(trace.events) == [(1, Side.RIGHT, DropCause.KNEE), (0, Side.LEFT, DropCause.KNEE)]
    assert trace.states[1].items[1].status is ItemStatus.FLOATING


def test_no_drop_outside_knee():
    cfg = still({"map": {"rows": 3, "cols": 5}, "donkey": {"knee_drop_prob": 1.0}})
    start = set_up(cfg, LINE, items=ITEMS, donkey={"row": 0, "col": 2, **BAGS})  # h = 10: DRY
    assert drops(run(cfg, 1, [Actions()] * 3, start=start).events) == []


def test_rate_matches_knee_drop_prob():
    # Many independent KNEE ticks: drop frequency within 4 SE of knee_drop_prob.
    n, hits = 3000, 0
    state, rngs = knee_start()
    for _ in range(n):
        _, rngs, events = step(state, Actions(), rngs)
        hits += bool(drops(events))
    p = CFG.donkey.knee_drop_prob
    assert abs(hits / n - p) < 4 * math.sqrt(p * (1 - p) / n)
