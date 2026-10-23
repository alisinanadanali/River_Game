"""D-08: STANCE_LEFT/RIGHT sets stance and stance_since = t. It ends when the donkey makes a (valid) move, is swept
(tests/rules/test_D07_*) or when t − stance_since ≥ stance_max_ticks (checked in step 11 before t += 1). It
catches only in ticks after the one it was taken in (t > stance_since). NOOP keeps it; a new stance renews it.
"""

import pytest

from engine.actions import Actions, DonkeyAction
from engine.donkey import Donkey, Side, stance_ready
from engine.events import DonkeyMoved, DonkeyStance, StanceReason

from tests.support import run, set_up, still

CFG = still({"map": {"rows": 3, "cols": 5}})
LINE = ["..#..", "..#..", "..#.."]
LEFT, RIGHT = Actions(donkey=DonkeyAction.STANCE_LEFT), Actions(donkey=DonkeyAction.STANCE_RIGHT)
NOOP, N, E = Actions(), Actions(donkey=DonkeyAction.MOVE_N), Actions(donkey=DonkeyAction.MOVE_E)
MAX = CFG.donkey.stance_max_ticks


def stances(trace):
    return [(e.t, e.side, e.reason) for e in trace.events if isinstance(e, DonkeyStance)]


def test_stance_is_set():
    trace = run(CFG, 1, [LEFT], start=set_up(CFG, LINE))
    assert (trace.states[0].donkey.stance, trace.states[0].donkey.stance_since) == (Side.LEFT, 0)
    assert stances(trace) == [(0, Side.LEFT, StanceReason.SET)]


def test_stance_expires_after_stance_max_ticks():
    trace = run(CFG, 1, [LEFT] + [NOOP] * (MAX + 2), start=set_up(CFG, LINE))
    assert [s.donkey.stance for s in trace.states] == [Side.LEFT] * MAX + [Side.NONE] * 3
    assert stances(trace) == [(0, Side.LEFT, StanceReason.SET), (MAX, Side.NONE, StanceReason.EXPIRED)]


@pytest.mark.parametrize("since", [0, 7])
def test_ready_only_after_the_tick_it_was_taken(since):
    donkey = Donkey(row=0, col=0, lives=3, stance=Side.RIGHT, stance_since=since)
    assert [stance_ready(donkey, since + k) for k in range(MAX + 1)] == [False] + [True] * MAX
    assert not stance_ready(Donkey(row=0, col=0, lives=3), since + 1)


def test_a_new_stance_renews_it():
    trace = run(CFG, 1, [LEFT, NOOP, RIGHT] + [NOOP] * (MAX + 1), start=set_up(CFG, LINE))
    assert stances(trace) == [
        (0, Side.LEFT, StanceReason.SET), (2, Side.RIGHT, StanceReason.SET), (2 + MAX, Side.NONE, StanceReason.EXPIRED),
    ]
    assert trace.states[2].donkey.stance_since == 2


def test_a_move_ends_it_before_moving():
    trace = run(CFG, 1, [LEFT, N], start=set_up(CFG, LINE))
    tick1 = [e for e in trace.events if e.t == 1]
    assert [type(e) for e in tick1] == [DonkeyStance, DonkeyMoved]
    assert (tick1[0].side, tick1[0].reason) == (Side.NONE, StanceReason.MOVED)
    assert trace.states[1].donkey.stance is Side.NONE


def test_a_rejected_move_keeps_it():
    trace = run(CFG, 1, [N, LEFT, E], start=set_up(CFG, LINE))  # (0, 3) is water
    assert trace.states[2].donkey.stance is Side.LEFT
