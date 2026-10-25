"""VISUALS §4.1, §9.3: the view follows the session; the scene is what the frame draws. Pure, fake clock."""

import dataclasses

import numpy as np
import pytest

from controllers.keyboard import KeyDown, KeyUp
from engine.events import GameOverReason, Role
from engine.observe import observe
from game.session import Mode, frame, start
from game.view import follow, new_view, progress, scene
from render.characters.animator import look, new_animator, update
from render.board import stand_z
from render.layout import feet
from render.strings_tr import MODE_NAMES
from tests.support import config_with

CFG = config_with({})
TICK_S = CFG.time.tick_seconds
SEED = 7
D, A, X, DOT, F2, F5, ESC = 7, 4, 27, 56, 59, 62, 41
TACTICAL_CFG = config_with({"controls": {"tactical_mode": True}})


def tap(*codes):
    return [e for c in codes for e in (KeyDown(c), KeyUp(c))]


def ticked(events=()):
    """A session one tick in (a boundary crossed in the frame) and the view that followed it."""
    s = start(CFG, SEED, 0.0)
    view = new_view(s, 0.0)
    s = frame(s, events, TICK_S)
    return s, follow(view, s, TICK_S)


def test_a_new_view_starts_both_animators_from_the_observation():
    s = start(CFG, SEED, 2.0)
    view = new_view(s, 2.0)
    for role in Role:
        assert view.animators[role] == new_animator(role, observe(s.state, role), 2.0)
    assert view.restarts == 0


def test_a_frame_without_ticks_leaves_the_view():
    s = start(CFG, SEED, 0.0)
    view = new_view(s, 0.0)
    assert follow(view, frame(s, (), TICK_S / 2), TICK_S / 2) == view


def test_each_tick_updates_the_animators_with_its_events():
    s, view = ticked(tap(D))
    (record,) = s.ticks
    for role in Role:
        before = new_animator(role, observe(start(CFG, SEED, 0.0).state, role), 0.0)
        assert view.animators[role] == update(before, observe(s.state, role), record.events, TICK_S, CFG)
    assert view.animators[Role.DONKEY] != new_view(start(CFG, SEED, 0.0), 0.0).animators[Role.DONKEY]


def test_several_ticks_in_one_frame_all_reach_the_animators():
    s = start(TACTICAL_CFG, SEED, 0.0)
    view = new_view(s, 0.0)
    s = frame(s, tap(A, DOT, X, DOT), 0.1)                                   # two confirmed pairs: two ticks
    first, second = s.ticks
    animator = view.animators[Role.DONKEY]
    for record in (first, second):
        animator = update(animator, observe(s.state, Role.DONKEY), record.events, 0.1, TACTICAL_CFG)
    assert follow(view, s, 0.1).animators[Role.DONKEY] == animator
    assert animator.facing_right is False                                    # the first tick turned it west


def test_a_restart_starts_a_new_view():
    s, view = ticked(tap(D))
    s = frame(s, tap(F5), 2 * TICK_S - 0.01)
    assert follow(view, s, 2 * TICK_S - 0.01) == new_view(s, 2 * TICK_S - 0.01)
    assert follow(view, s, 2 * TICK_S - 0.01).restarts == 1


# --- between ticks -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("since", "u"), [(0.0, 0.0), (0.25, 0.25), (1.0, 1.0), (3.0, 1.0)])
def test_progress_is_the_share_of_a_tick_since_the_last_one(since, u):
    s = dataclasses.replace(start(CFG, SEED, 0.0), since_tick_s=since * TICK_S)
    assert progress(s) == pytest.approx(u)


def test_characters_move_from_the_previous_cell_to_the_current_one():
    s, view = ticked(tap(D))
    before, after = s.previous.donkey, s.state.donkey
    assert (before.row, before.col) != (after.row, after.col)                  # D moved the donkey east
    bank = CFG.render.layout.bank_z_cm
    for u in (0.0, 0.5, 1.0):
        at = dataclasses.replace(s, since_tick_s=u * TICK_S)
        cell = (before.row + u * (after.row - before.row), before.col + u * (after.col - before.col))
        assert scene(view, at, TICK_S).feet[Role.DONKEY] == pytest.approx(feet(CFG, Role.DONKEY, cell, bank))
    shrek = s.state.shrek
    assert scene(view, s, TICK_S).feet[Role.SHREK] == feet(CFG, Role.SHREK, (-1, shrek.col), bank)


def onto_a_stone():
    """A session whose last tick took the donkey from the south bank onto the first stone of row 0."""
    s = start(CFG, SEED, 0.0)
    col = next(c for c in range(CFG.map.cols) if s.state.world.is_stone[0, c])
    state = dataclasses.replace(s.state, donkey=dataclasses.replace(s.state.donkey, row=0, col=col))
    return dataclasses.replace(s, state=state), col


def test_the_feet_rise_from_the_bank_top_to_the_stone_top_between_ticks():
    s, col = onto_a_stone()
    view = new_view(s, 0.0)
    z_bank, z_stone = stand_z(observe(s.previous, Role.DONKEY), -1, s.previous.donkey.col),         stand_z(observe(s.state, Role.DONKEY), 0, col)
    assert z_bank != z_stone
    for u in (0.0, 0.5, 1.0):
        at = dataclasses.replace(s, since_tick_s=u * TICK_S)
        cell = (-1 + u, s.previous.donkey.col + u * (col - s.previous.donkey.col))
        expected = feet(CFG, Role.DONKEY, cell, z_bank + u * (z_stone - z_bank))
        assert scene(view, at, 0.0).feet[Role.DONKEY] == pytest.approx(expected)


def test_a_character_between_rows_is_drawn_with_the_southern_one():
    s, _ = onto_a_stone()
    sc = scene(new_view(s, 0.0), dataclasses.replace(s, since_tick_s=TICK_S / 2), 0.0)
    assert (sc.rows[Role.DONKEY], sc.rows[Role.SHREK]) == (-1, -1)
    later = dataclasses.replace(s, previous=s.state)
    assert scene(new_view(s, 0.0), later, 0.0).rows[Role.DONKEY] == 0


def test_the_water_level_moves_between_ticks():
    s = start(CFG, SEED, 0.0)
    high = np.arange(CFG.map.cols, dtype=float) * 4.0
    s = dataclasses.replace(s, state=dataclasses.replace(s.state, water=dataclasses.replace(s.state.water,
                                                                                             level=high)))
    low = s.previous.water.level
    for u in (0.0, 0.25, 1.0):
        sc = scene(new_view(s, 0.0), dataclasses.replace(s, since_tick_s=u * TICK_S), 0.0)
        assert sc.levels == pytest.approx(tuple(low + u * (high - low)))


# --- the scene ---------------------------------------------------------------------------------------------------

def test_the_scene_has_the_observation_the_looks_and_the_status():
    s, view = ticked()
    sc = scene(view, s, TICK_S + 0.1)
    assert sc.obs == observe(s.state, Role.DONKEY)                              # V0: both roles see the same
    for role in Role:
        assert sc.looks[role] == look(view.animators[role], TICK_S + 0.1, CFG)
    assert (sc.mode, sc.paused, sc.seed) == (Mode.REALTIME.value, False, SEED)
    s = frame(s, tap(F2, ESC), TICK_S + 0.2)
    sc = scene(follow(view, s, TICK_S + 0.2), s, TICK_S + 0.2)
    assert (sc.mode, sc.paused) == (Mode.TACTICAL.value, True)


def test_every_mode_has_a_name():
    assert MODE_NAMES.keys() == {m.value for m in Mode}


def test_the_scene_shows_the_end_of_the_game():
    s, view = ticked()
    s = dataclasses.replace(s, state=dataclasses.replace(s.state, game_over=GameOverReason.TIME))
    assert scene(view, s, TICK_S).obs.game_over is GameOverReason.TIME
