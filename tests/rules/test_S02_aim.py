"""S-02: aim = UP/DOWN moves aim_row by ±1, clipped silently to [0, R−1]; the aim cell is (aim_row, shrek.col)."""

import pytest

from engine.actions import Actions, Aim, ShrekAction, ShrekMove
from engine.events import ShrekAimed, ShrekMoved
from engine.shrek import aim, aim_cell
from engine.state import new_game
from engine.step import step

from tests.support import config_with, run

CFG = config_with({})
UP = Actions(shrek=ShrekAction(aim=Aim.UP))
DOWN = Actions(shrek=ShrekAction(aim=Aim.DOWN))


def test_starts_on_the_nearest_row():
    state, _ = new_game(CFG, 1)
    assert state.shrek.aim_row == 0
    assert aim_cell(state.shrek) == (0, 4)


@pytest.mark.parametrize(
    ("row", "direction", "expected"),
    [(0, Aim.UP, 1), (3, Aim.DOWN, 2), (3, Aim.NONE, 3), (0, Aim.DOWN, 0), (8, Aim.UP, 8)],
)
def test_aim(row, direction, expected):
    assert aim(row, direction, rows=9) == expected


def test_aim_up_emits_shrek_aimed():
    state, rngs = new_game(CFG, 1)
    new_state, _, events = step(state, UP, rngs)
    assert new_state.shrek.aim_row == 1
    assert [e for e in events if isinstance(e, ShrekAimed)] == [ShrekAimed(t=0, seq=0, row=1)]


def test_aim_is_clipped_silently():
    trace = run(CFG, 1, [DOWN] + [UP] * 10)
    assert [s.shrek.aim_row for s in trace.states] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 8, 8]
    assert [e.row for e in trace.events if isinstance(e, ShrekAimed)] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_walk_comes_before_aim():
    # TICK.md step 2: (b) walk, then (c) aim; the aim cell follows Shrek's new column.
    state, rngs = new_game(CFG, 1)
    new_state, _, events = step(state, Actions(shrek=ShrekAction(move=ShrekMove.E, aim=Aim.UP)), rngs)
    assert [type(e) for e in events if isinstance(e, (ShrekMoved, ShrekAimed))] == [ShrekMoved, ShrekAimed]
    assert aim_cell(new_state.shrek) == (1, 5)
