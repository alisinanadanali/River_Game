"""VISUALS §4.1, §9.3: the view follows the session; the scene is what the frame draws. Pure, fake clock."""

import dataclasses

import numpy as np
import pytest

from controllers.keyboard import KeyDown, KeyUp
from engine.events import DonkeySwept, GameOverReason, Role, SweptCause
from engine.water import Dam
from engine.observe import observe
from game.session import Mode, frame, start
from game.view import follow, new_view, progress, scene
from render.characters.animator import ghost_look, look, new_animator, update
from render.characters.pose import Clip, duration_s
from render.board import stand_z, stone_top_z
from render.hud import hud
from render.layout import feet, water_line
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


# --- the water line and the sweep (§4.1, §9.1) ---------------------------------------------------------------

def with_donkey(s, *, previous=None, state=None):
    """The session with the donkey fields given replaced, in the previous and/or the current state."""
    def put(game, fields):
        return game if fields is None else dataclasses.replace(game, donkey=dataclasses.replace(game.donkey, **fields))
    return dataclasses.replace(s, previous=put(s.previous, previous), state=put(s.state, state))


def at_u(s, u):
    return dataclasses.replace(s, since_tick_s=u * TICK_S)


def test_on_the_bank_the_donkey_has_no_water_line():
    s, view = ticked()
    assert scene(view, s, TICK_S).water_y is None


def test_the_water_line_follows_the_depth_between_ticks():
    s, col = onto_a_stone()
    s = with_donkey(s, previous=dict(row=0, col=col, depth=2.0), state=dict(depth=6.0))
    view = new_view(s, 0.0)
    for u in (0.0, 0.5, 1.0):
        sc = scene(view, at_u(s, u), 0.0)
        assert sc.water_y == pytest.approx(water_line(CFG, sc.feet[Role.DONKEY][1], 2.0 + u * 4.0))


def test_stepping_off_the_bank_the_depth_grows_from_zero():
    s, _ = onto_a_stone()
    s = with_donkey(s, state=dict(depth=6.0))
    sc = scene(new_view(s, 0.0), at_u(s, 0.5), 0.0)
    assert sc.water_y == pytest.approx(water_line(CFG, sc.feet[Role.DONKEY][1], 3.0))


def test_on_one_stone_the_water_line_is_the_drawn_water():
    """The water rising over a dry stone: d goes from −4 to +6 cm, so the line is where the drawn water is (d < 0 is
    not counted as 0: that would put the line 3 cm up at u = 0.5, over the water)."""
    s, col = onto_a_stone()
    s = with_donkey(s, previous=dict(row=0, col=col, depth=-4.0), state=dict(depth=6.0))
    view = new_view(s, 0.0)
    assert scene(view, at_u(s, 0.3), 0.0).water_y is None                     # d = −1: the water under the feet
    sc = scene(view, at_u(s, 0.5), 0.0)
    assert sc.water_y == pytest.approx(water_line(CFG, sc.feet[Role.DONKEY][1], 1.0))


def test_a_dry_stone_has_no_water_line():
    s, _ = onto_a_stone()
    s = with_donkey(s, state=dict(depth=-4.0))
    assert scene(new_view(s, 0.0), at_u(s, 1.0), 0.0).water_y is None


SWEPT_AT = (3, 6)


def swept(s):
    """The last tick swept the donkey off SWEPT_AT: one life less, back on the south bank in the same column."""
    lives = s.state.donkey.lives
    return with_donkey(s, previous=dict(row=SWEPT_AT[0], col=SWEPT_AT[1], depth=25.0, lives=lives),
                       state=dict(row=-1, col=SWEPT_AT[1], depth=None, lives=lives - 1))


def test_a_swept_donkey_does_not_slide_back_to_the_bank():
    s = swept(start(CFG, SEED, 0.0))
    sc = scene(new_view(s, 0.0), at_u(s, 0.5), 0.0)
    bank = CFG.render.layout.bank_z_cm
    assert sc.feet[Role.DONKEY] == pytest.approx(feet(CFG, Role.DONKEY, (-1, SWEPT_AT[1]), bank))
    assert (sc.rows[Role.DONKEY], sc.water_y) == (-1, None)


def a_ghost_view(s, at_s):
    event = DonkeySwept(t=0, seq=0, row=SWEPT_AT[0], col=SWEPT_AT[1], depth_cm=25.0, cause=SweptCause.DEPTH,
                        items_dropped=0)
    view = new_view(s, 0.0)
    donkey = update(view.animators[Role.DONKEY], observe(s.state, Role.DONKEY), [event], at_s, CFG)
    return dataclasses.replace(view, animators={**view.animators, Role.DONKEY: donkey})


@pytest.mark.parametrize("on_stone", [True, False])
def test_the_ghost_plays_on_the_swept_cell_cropped_at_the_drawn_water(on_stone):
    s = swept(start(CFG, SEED, 0.0))
    world = s.state.world
    is_stone, base_h = world.is_stone.copy(), world.base_h.copy()
    is_stone[SWEPT_AT], base_h[SWEPT_AT] = on_stone, 0.0
    high = np.full(CFG.map.cols, 40.0)                                         # well over the stone
    state = dataclasses.replace(s.state, world=dataclasses.replace(world, is_stone=is_stone, base_h=base_h),
                                water=dataclasses.replace(s.state.water, level=high))
    s = at_u(dataclasses.replace(s, state=state), 0.5)
    view = a_ghost_view(s, 5.0)
    sc = scene(view, s, 5.3)
    ghost_seen, cell = ghost_look(view.animators[Role.DONKEY], 5.3, CFG)
    obs, level = observe(s.state, Role.DONKEY), sc.levels[SWEPT_AT[1]]
    top = stone_top_z(obs, *SWEPT_AT)
    assert (top is not None) is on_stone
    z = level if top is None else top
    assert sc.ghost.look == ghost_seen and sc.ghost.look.clip is Clip.SWEPT and sc.ghost.row == SWEPT_AT[0]
    assert sc.ghost.feet == pytest.approx(feet(CFG, Role.DONKEY, cell, z))
    expected = water_line(CFG, sc.ghost.feet[1], level - z)
    assert sc.ghost.water_y == (None if expected is None else pytest.approx(expected))
    assert (sc.ghost.water_y is None) is not on_stone


def test_the_ghost_is_gone_when_its_clip_ends():
    s = swept(start(CFG, SEED, 0.0))
    view = a_ghost_view(s, 5.0)
    assert scene(view, s, 5.0 + duration_s(Clip.SWEPT, CFG)).ghost is None
    assert scene(new_view(s, 0.0), s, 5.0).ghost is None


# --- the scene ---------------------------------------------------------------------------------------------------

def test_the_scene_has_the_observation_the_looks_and_the_status():
    s, view = ticked()
    sc = scene(view, s, TICK_S + 0.1)
    assert sc.obs == observe(s.state, Role.DONKEY)                              # V0: both roles see the same
    assert (sc.before, sc.u) == (observe(s.previous, Role.DONKEY), progress(s))
    for role in Role:
        assert sc.looks[role] == look(view.animators[role], TICK_S + 0.1, CFG)
    assert (sc.mode, sc.paused, sc.seed) == (Mode.REALTIME.value, False, SEED)
    s = frame(s, tap(F2, ESC), TICK_S + 0.2)
    sc = scene(follow(view, s, TICK_S + 0.2), s, TICK_S + 0.2)
    assert (sc.mode, sc.paused) == (Mode.TACTICAL.value, True)


def test_the_scene_carries_the_hud_of_the_current_observation():
    s, view = ticked()
    sc = scene(view, s, TICK_S + 0.1)
    assert sc.hud == hud(observe(s.state, Role.DONKEY), Mode.REALTIME.value, TICK_S + 0.1)


def test_the_hud_blinks_on_the_frames_clock():
    """VISUALS §5: the dam warning blinks with the wall clock, so the scene passes the frame's time to the HUD."""
    s = start(CFG, SEED, 0.0)
    held = Dam(active=True, col=4, volume=CFG.dam.q_max_cm_cols, started_at=0)
    s = dataclasses.replace(s, state=dataclasses.replace(s.state, dam=held))
    period = 1 / CFG.render.hud.blink_hz
    lit = [scene(new_view(s, 0.0), s, k * period).hud.shrek.dam.flash_on for k in (0.1, 0.6)]
    assert lit == [True, False]


def test_every_mode_has_a_name():
    assert MODE_NAMES.keys() == {m.value for m in Mode}


def test_the_scene_shows_the_end_of_the_game():
    s, view = ticked()
    s = dataclasses.replace(s, state=dataclasses.replace(s.state, game_over=GameOverReason.TIME))
    assert scene(view, s, TICK_S).obs.game_over is GameOverReason.TIME
