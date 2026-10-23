"""D-07: when the donkey is SWEPT it loses one life and respawns at once on the south bank in the same column;
stance and any slow move are cancelled. With no life left the game ends (GameOver(lives)) and no respawn is
emitted; the remaining stages of that tick still run, and the next step is an error.
"""

import pytest

from engine.actions import Actions, DonkeyAction
from engine.donkey import Bag, DepthState, Side
from engine.events import (
    DonkeyDepthChanged, DonkeyRespawned, DonkeyStance, DonkeySwept, DropCause, GameOver, GameOverReason, ItemDropped,
    LifeLost, StanceReason, SweptCause,
)
from engine.items import Item, ItemStatus
from engine.step import GameFinishedError, step

from tests.support import run, set_up, still

CFG = still({"map": {"rows": 3, "cols": 5}})
LINE = ["..##.", "..#..", "..#.."]
DEEP = {(0, 2): -20.0, (0, 3): -20.0}   # still water: d = 0 − (−20 − 4) = 24 ≥ d₂ = 20
N = Actions(donkey=DonkeyAction.MOVE_N)


def kinds(events):
    return [type(e) for e in events]


def test_stepping_onto_a_deep_stone():
    trace = run(CFG, 1, [N], start=set_up(CFG, LINE, DEEP))
    assert kinds(e for e in trace.events if e.type != "DonkeyMoved") == [DonkeySwept, LifeLost, DonkeyRespawned]
    sw = next(e for e in trace.events if isinstance(e, DonkeySwept))
    assert (sw.row, sw.col, sw.cause, sw.items_dropped) == (0, 2, SweptCause.DEPTH, 0)
    assert sw.depth_cm == pytest.approx(24.0)
    assert next(e for e in trace.events if isinstance(e, LifeLost)).lives_left == CFG.time.lives - 1
    assert next(e for e in trace.events if isinstance(e, DonkeyRespawned)).col == 2


def test_respawn_is_on_the_south_bank_dry():
    donkey = run(CFG, 1, [N], start=set_up(CFG, LINE, DEEP)).states[0].donkey
    assert (donkey.row, donkey.col, donkey.depth_state, donkey.depth) == (-1, 2, DepthState.DRY, None)
    assert donkey.lives == CFG.time.lives - 1


def test_same_column():
    trace = run(CFG, 1, [N], start=set_up(CFG, LINE, DEEP, donkey={"col": 3}))
    assert trace.states[0].donkey.col == 3
    assert [e.col for e in trace.events if isinstance(e, DonkeyRespawned)] == [3]


def test_swept_is_not_a_depth_change():
    trace = run(CFG, 1, [N], start=set_up(CFG, LINE, DEEP))
    assert not any(isinstance(e, DonkeyDepthChanged) for e in trace.events)


def test_stance_is_cancelled():
    start = set_up(CFG, LINE, DEEP, donkey={"row": 0, "col": 2, "stance": Side.LEFT, "stance_since": 0})
    trace = run(CFG, 1, [Actions()], start=start)
    assert kinds(trace.events) == [DonkeySwept, LifeLost, DonkeyStance, DonkeyRespawned]
    stance = next(e for e in trace.events if isinstance(e, DonkeyStance))
    assert (stance.side, stance.reason) == (Side.NONE, StanceReason.SWEPT)
    assert (trace.states[0].donkey.stance, trace.states[0].donkey.stance_since) == (Side.NONE, None)


def test_bags_empty_into_the_water_in_id_order():
    items = (
        Item(id=0, kind="potato_sack", status=ItemStatus.IN_BAG),
        Item(id=1, kind="apple_crate", status=ItemStatus.IN_BAG),
        Item(id=2, kind="watermelon", status=ItemStatus.IN_BAG),
    )
    bags = {"bag_left": Bag(items=(2, 0), mass=80.0, volume=5), "bag_right": Bag(items=(1,), mass=10.0, volume=1)}
    start = set_up(CFG, LINE, DEEP, items=items, donkey={"row": 0, "col": 2, **bags})
    trace = run(CFG, 1, [Actions()], start=start)
    assert next(e for e in trace.events if isinstance(e, DonkeySwept)).items_dropped == 3
    assert [(e.item_id, e.side, e.cause) for e in trace.events if isinstance(e, ItemDropped)] == [
        (0, Side.LEFT, DropCause.SWEPT), (1, Side.RIGHT, DropCause.SWEPT), (2, Side.LEFT, DropCause.SWEPT),
    ]
    after = trace.states[0]
    assert [i.status for i in after.items] == [ItemStatus.LOST, ItemStatus.FLOATING, ItemStatus.FLOATING]
    # Dropped at x = 2 (ItemFloated), then drifted in step 8 of the same tick (TICK.md step 8).
    assert after.items[1].pos == (0, 2.0 + CFG.water.flow_speed_cols_per_tick)
    assert after.donkey.bag_left == Bag() == after.donkey.bag_right
    names = [type(e).__name__ for e in trace.events]
    assert names == ["DonkeySwept", "ItemDropped", "ItemSank", "ItemLost", "ItemDropped", "ItemFloated",
                     "ItemDropped", "ItemFloated", "LifeLost", "DonkeyRespawned"]


def test_slow_move_is_cancelled():
    cfg = still({"map": {"rows": 3, "cols": 5}, "donkey": {"slow_move_ticks": 3}})
    start = set_up(cfg, LINE, DEEP, donkey={"row": 0, "col": 2, "move_target": (1, 2), "move_remaining": 2})
    donkey = run(cfg, 1, [Actions()], start=start).states[0].donkey
    assert (donkey.row, donkey.move_target, donkey.move_remaining) == (-1, None, 0)


def test_lives_run_out():
    start = set_up(CFG, LINE, DEEP, donkey={"row": 0, "col": 2, "lives": 1})
    trace = run(CFG, 1, [Actions()] * 5, start=start)
    assert len(trace.states) == 1  # run() stops at game over
    assert kinds(trace.events) == [DonkeySwept, LifeLost, GameOver]
    assert trace.events[-1] == GameOver(t=0, seq=2, reason=GameOverReason.LIVES, score=0)
    state = trace.states[0]
    assert (state.game_over, state.donkey.lives, state.donkey.row, state.t) == (GameOverReason.LIVES, 0, -1, 1)
    with pytest.raises(GameFinishedError):
        step(state, Actions(), trace.rngs[0])


def test_losing_the_last_life_on_the_last_tick_ends_the_game_once():
    cfg = still({"map": {"rows": 3, "cols": 5}, "time": {"game_length_ticks": 1}})
    trace = run(cfg, 1, [Actions()], start=set_up(cfg, LINE, DEEP, donkey={"row": 0, "col": 2, "lives": 1}))
    assert [e.reason for e in trace.events if isinstance(e, GameOver)] == [GameOverReason.LIVES]


def test_three_lives_three_sweeps():
    trace = run(CFG, 1, [N] * 10, start=set_up(CFG, LINE, DEEP))
    assert [e.lives_left for e in trace.events if isinstance(e, LifeLost)] == [2, 1, 0]
    assert len(trace.states) == 3 and trace.states[-1].game_over is GameOverReason.LIVES
