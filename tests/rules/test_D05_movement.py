"""D-05: a move onto the graph (banks ∪ stones, M-01) is valid, otherwise ActionRejected(no_stone). From DRY the
move is done in the same tick; from ANKLE or KNEE it takes slow_move_ticks ticks and the donkey's input is ignored
(busy_moving) until it arrives. The donkey starts on the south bank in column ⌊C/2⌋, next to Shrek.
"""

import pytest

from engine.actions import Actions, DonkeyAction
from engine.donkey import DepthState
from engine.events import ActionRejected, DonkeyMoved, DonkeyMoveStarted, RejectReason, Role
from engine.state import new_game

from tests.support import run, set_up, still

CFG = still({"map": {"rows": 3, "cols": 5}})
LINE = ["..#..", "..##.", "..#.."]  # rows 0, 1, 2 (south to north); a stone path up column 2, one step east at row 1
N, S, E, W = (Actions(donkey=a) for a in (DonkeyAction.MOVE_N, DonkeyAction.MOVE_S, DonkeyAction.MOVE_E, DonkeyAction.MOVE_W))
NOOP = Actions()
ANKLE_AT_0_2 = {(0, 2): 2.0}   # still water: e = 2 − 200/50 = −2, d = 2 → ANKLE
KNEE_AT_0_2 = {(0, 2): -5.0}   # d = 9 → KNEE


def cells(trace, kind=DonkeyMoved):
    return [(e.t, e.from_cell, e.to_cell) for e in trace.events if isinstance(e, kind)]


def rejections(trace):
    return [(e.t, e.reason) for e in trace.events if isinstance(e, ActionRejected) and e.role is Role.DONKEY]


@pytest.mark.parametrize("cols", [5, 9, 10])
def test_starts_on_the_south_bank_next_to_shrek(cols):
    state, _ = new_game(still({"map": {"cols": cols}}), 1)
    assert (state.donkey.row, state.donkey.col) == (-1, cols // 2) and state.donkey.col == state.shrek.col


def test_a_dry_move_is_done_in_the_same_tick():
    trace = run(CFG, 1, [N], start=set_up(CFG, LINE))
    assert (trace.states[0].donkey.row, trace.states[0].donkey.col) == (0, 2)
    assert cells(trace) == [(0, (-1, 2), (0, 2))]


def test_walk_across_to_the_north_bank():
    trace = run(CFG, 1, [N, N, E, W, N, N], start=set_up(CFG, LINE))
    assert [(s.donkey.row, s.donkey.col) for s in trace.states] == [(0, 2), (1, 2), (1, 3), (1, 2), (2, 2), (3, 2)]
    assert rejections(trace) == []


def test_water_is_off_the_graph():
    trace = run(CFG, 1, [N, E, W], start=set_up(CFG, LINE))
    assert [(s.donkey.row, s.donkey.col) for s in trace.states] == [(0, 2), (0, 2), (0, 2)]
    assert rejections(trace) == [(1, RejectReason.NO_STONE), (2, RejectReason.NO_STONE)]
    rejected = next(e for e in trace.events if isinstance(e, ActionRejected))
    assert (rejected.role, rejected.component) == (Role.DONKEY, "action")


def test_banks_are_walkable_along_their_whole_length():
    trace = run(CFG, 1, [W, W, W, S], start=set_up(CFG, LINE))
    assert [s.donkey.col for s in trace.states] == [1, 0, 0, 0]
    assert rejections(trace) == [(2, RejectReason.NO_STONE), (3, RejectReason.NO_STONE)]  # west edge, row −2


def test_north_of_the_north_bank_is_off_the_graph():
    trace = run(CFG, 1, [N, E], start=set_up(CFG, LINE, donkey={"row": 3, "col": 3}))
    assert rejections(trace) == [(0, RejectReason.NO_STONE)]
    assert (trace.states[-1].donkey.row, trace.states[-1].donkey.col) == (3, 4)  # E along the bank works


@pytest.mark.parametrize("heights", [ANKLE_AT_0_2, KNEE_AT_0_2])
def test_from_ankle_or_knee_a_move_takes_slow_move_ticks(heights):
    # Tick 0 measures the depth at (0, 2); tick 1 starts the move; it arrives in tick 2.
    trace = run(CFG, 1, [NOOP, N, NOOP, NOOP], start=set_up(CFG, LINE, heights, donkey={"row": 0, "col": 2}))
    assert trace.states[0].donkey.depth_state in (DepthState.ANKLE, DepthState.KNEE)
    assert cells(trace, DonkeyMoveStarted) == [(1, (0, 2), (1, 2))]
    assert next(e for e in trace.events if isinstance(e, DonkeyMoveStarted)).ticks == CFG.donkey.slow_move_ticks
    assert [(s.donkey.row, s.donkey.move_remaining) for s in trace.states] == [(0, 0), (0, 1), (1, 0), (1, 0)]
    assert cells(trace) == [(2, (0, 2), (1, 2))]


def test_input_while_moving_is_rejected_but_the_move_goes_on():
    trace = run(CFG, 1, [NOOP, N, E], start=set_up(CFG, LINE, ANKLE_AT_0_2, donkey={"row": 0, "col": 2}))
    assert rejections(trace) == [(2, RejectReason.BUSY_MOVING)]
    assert cells(trace) == [(2, (0, 2), (1, 2))]


def test_noop_while_moving_is_not_rejected():
    trace = run(CFG, 1, [NOOP, N, NOOP], start=set_up(CFG, LINE, ANKLE_AT_0_2, donkey={"row": 0, "col": 2}))
    assert rejections(trace) == []


@pytest.mark.parametrize(("slow", "arrival"), [(1, 1), (2, 2), (3, 3), (4, 4)])
def test_arrival_tick_follows_slow_move_ticks(slow, arrival):
    cfg = still({"map": {"rows": 3, "cols": 5}, "donkey": {"slow_move_ticks": slow}})
    trace = run(cfg, 1, [NOOP, N] + [NOOP] * 4, start=set_up(cfg, LINE, ANKLE_AT_0_2, donkey={"row": 0, "col": 2}))
    assert [t for t, _, _ in cells(trace)] == [arrival]
    assert (len(cells(trace, DonkeyMoveStarted)) == 1) == (slow > 1)  # slow_move_ticks = 1 is instant


def test_a_rejected_move_starts_nothing():
    trace = run(CFG, 1, [NOOP, E], start=set_up(CFG, LINE, ANKLE_AT_0_2, donkey={"row": 0, "col": 2}))
    assert cells(trace, DonkeyMoveStarted) == [] and trace.states[-1].donkey.move_remaining == 0
