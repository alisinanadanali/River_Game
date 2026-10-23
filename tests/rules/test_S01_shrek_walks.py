"""S-01: move = W/E changes Shrek's column by ±1, clipped silently to [0, C−1]; he starts at column ⌊C/2⌋."""

import pytest

from engine.actions import Actions, ShrekAction, ShrekMove
from engine.events import ShrekMoved
from engine.shrek import walk
from engine.state import new_game
from engine.step import step

from tests.support import config_with, run

CFG = config_with({})
WALK_E = Actions(shrek=ShrekAction(move=ShrekMove.E))
WALK_W = Actions(shrek=ShrekAction(move=ShrekMove.W))


@pytest.mark.parametrize(("cols", "start"), [(9, 4), (10, 5), (3, 1), (4, 2)])
def test_starts_in_the_middle_column(cols, start):
    state, _ = new_game(config_with({"map": {"cols": cols}}), 1)
    assert state.shrek.col == start


@pytest.mark.parametrize(
    ("col", "move", "expected"),
    [(4, ShrekMove.E, 5), (4, ShrekMove.W, 3), (4, ShrekMove.NONE, 4), (8, ShrekMove.E, 8), (0, ShrekMove.W, 0)],
)
def test_walk(col, move, expected):
    assert walk(col, move, cols=9) == expected


def test_one_step_east_emits_shrek_moved():
    state, rngs = new_game(CFG, 1)
    new_state, _, events = step(state, WALK_E, rngs)
    assert new_state.shrek.col == 5
    assert [e for e in events if isinstance(e, ShrekMoved)] == [ShrekMoved(t=0, seq=0, from_col=4, to_col=5)]


def test_walking_into_the_edge_is_silent():
    trace = run(CFG, 1, [WALK_E] * 10)
    assert [s.shrek.col for s in trace.states] == [5, 6, 7, 8, 8, 8, 8, 8, 8, 8]
    moved = [e for e in trace.events if isinstance(e, ShrekMoved)]
    assert [(e.t, e.to_col) for e in moved] == [(0, 5), (1, 6), (2, 7), (3, 8)]  # nothing after the edge


def test_west_edge():
    trace = run(CFG, 1, [WALK_W] * 6)
    assert [s.shrek.col for s in trace.states] == [3, 2, 1, 0, 0, 0]


def test_no_move_no_event():
    state, rngs = new_game(CFG, 1)
    _, _, events = step(state, Actions(), rngs)
    assert not any(isinstance(e, ShrekMoved) for e in events)
