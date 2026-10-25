"""CONTROLS.md §4 and §4.1: the real-time input buffer.

Scancodes are written out by hand from the CONTROLS.md §1–§3 tables, not read from config: the doc is the
oracle. One test per rule, then random key streams (hypothesis) against properties that must always hold.
"""

import dataclasses

from hypothesis import given
from hypothesis import strategies as st

from controllers.keyboard import (
    FocusLost,
    KeyBuffer,
    KeyDown,
    KeyUp,
    donkey_action,
    feed,
    shrek_action,
    tick_actions,
)
from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.config import load_config

CFG = load_config()
ALT = CFG.controls.model_copy(update={"shrek_keymap": "alt"})

# CONTROLS.md §1 (donkey, default Shrek), §2 (alt Shrek), §3 (global)
W, A, S, D, Q, E, X = 26, 4, 22, 7, 20, 8, 27
LEFT, RIGHT, UP, DOWN, R_CTRL, R_SHIFT, ENTER, DOT = 80, 79, 82, 81, 228, 229, 40, 56
J, L, I, K, U, O, SPACE, M = 13, 15, 12, 14, 24, 18, 44, 16
F1, F2, ESC, F5 = 58, 59, 41, 62
DONKEY_CODES = (W, A, S, D, Q, E, X)
SHREK_CODES = (LEFT, RIGHT, UP, DOWN, R_CTRL, R_SHIFT, ENTER, DOT)
UNKNOWN = 100


def down(*codes):
    return [KeyDown(c) for c in codes]


def up(*codes):
    return [KeyUp(c) for c in codes]


def tap(*codes):
    return [e for c in codes for e in (KeyDown(c), KeyUp(c))]


def fed(events, buffer=KeyBuffer()):
    for event in events:
        buffer = feed(buffer, event)
    return buffer


def ticks(*windows, controls=CFG.controls):
    """Feed each window's events, then cross a tick boundary; the actions of each tick."""
    buffer, out = KeyBuffer(), []
    for events in windows:
        actions, buffer = tick_actions(fed(events, buffer), controls)
        out.append(actions)
    return out


def donkey(*windows):
    return [a.donkey for a in ticks(*windows)]


def shrek(*windows, controls=CFG.controls):
    return [a.shrek for a in ticks(*windows, controls=controls)]


N, Wd, Ed, NOOP = DonkeyAction.MOVE_N, DonkeyAction.MOVE_W, DonkeyAction.MOVE_E, DonkeyAction.NOOP


# --- §4: the window and the boundary ---------------------------------------------------------------------------

def test_no_keys_no_action():
    assert ticks([]) == [Actions()]


def test_the_boundary_clears_the_presses_and_keeps_the_held_keys():
    _, nxt = tick_actions(fed(down(W) + tap(D)), CFG.controls)
    assert nxt == KeyBuffer(held=(W,), pressed=())


# --- §4: the last press wins, per component ---------------------------------------------------------------------

def test_the_donkeys_last_press_wins():
    assert donkey(tap(W, D)) == [Ed] and donkey(tap(D, W)) == [N]


def test_shrek_components_are_independent():
    assert shrek(tap(UP, R_CTRL)) == [ShrekAction(aim=Aim.UP, ability=Ability.THROW)]   # aim + 1, then throw
    assert shrek(tap(R_CTRL, UP)) == [ShrekAction(aim=Aim.UP, ability=Ability.THROW)]   # order across components
    assert shrek(tap(LEFT, RIGHT, DOWN)) == [ShrekAction(move=ShrekMove.E, aim=Aim.DOWN)]
    assert shrek(tap(R_CTRL, R_SHIFT)) == [ShrekAction(ability=Ability.ROCK)]


# --- §4: hold repeat ---------------------------------------------------------------------------------------------

def test_holding_a_move_key_walks():
    assert donkey(down(W), [], []) == [N, N, N]


def test_a_stance_does_not_repeat():
    assert donkey(down(Q), [], []) == [DonkeyAction.STANCE_LEFT, NOOP, NOOP]


def test_a_tap_beats_the_held_key_for_one_tick():
    assert donkey(down(W), tap(D), []) == [N, Ed, N]


def test_of_two_held_move_keys_the_last_pressed_repeats():
    assert donkey(down(W, D), [], up(D), []) == [Ed, Ed, N, N]
    assert donkey(down(D, W), [], up(W), []) == [N, N, Ed, Ed]


def test_shrek_walks_and_sweeps_the_aim_by_holding():
    assert shrek(down(LEFT, UP), []) == [ShrekAction(move=ShrekMove.W, aim=Aim.UP)] * 2


def test_throw_and_rock_do_not_repeat():
    assert shrek(down(R_CTRL), []) == [ShrekAction(ability=Ability.THROW), ShrekAction()]
    assert shrek(down(R_SHIFT), []) == [ShrekAction(ability=Ability.ROCK), ShrekAction()]


# --- §4: the dam -------------------------------------------------------------------------------------------------

def test_the_dam_holds_while_enter_is_down_and_releases_the_tick_after():
    dam = ShrekAction(ability=Ability.DAM)
    assert shrek(down(ENTER), [], up(ENTER), []) == [dam, dam, ShrekAction(), ShrekAction()]


def test_a_tapped_enter_holds_the_dam_for_that_tick():
    assert shrek(tap(ENTER), []) == [ShrekAction(ability=Ability.DAM), ShrekAction()]


def test_the_dam_overrides_throw_and_rock_but_not_move_or_aim():
    assert shrek(tap(ENTER, R_CTRL)) == [ShrekAction(ability=Ability.DAM)]
    assert shrek(down(ENTER), tap(R_SHIFT, UP)) == [
        ShrekAction(ability=Ability.DAM),
        ShrekAction(aim=Aim.UP, ability=Ability.DAM),
    ]


# --- §4.1: edge cases --------------------------------------------------------------------------------------------

def test_a_second_down_of_a_held_key_is_not_a_press():
    assert shrek(down(R_CTRL), down(R_CTRL)) == [ShrekAction(ability=Ability.THROW), ShrekAction()]
    assert fed(down(W, W)) == KeyBuffer(held=(W,), pressed=(W,))


def test_x_chooses_noop_and_cancels_the_repeat_for_one_tick():
    assert donkey(tap(W, X)) == [NOOP]
    assert donkey(down(W), tap(X), []) == [N, NOOP, N]


def test_the_shrek_wait_key_is_ignored_in_real_time():
    assert shrek(tap(LEFT, DOT)) == [ShrekAction(move=ShrekMove.W)]
    assert shrek(down(DOT)) == [ShrekAction()]


def test_focus_lost_forgets_the_held_keys_but_not_the_presses():
    assert ticks(down(W, ENTER) + [FocusLost()], []) == [
        Actions(donkey=N, shrek=ShrekAction(ability=Ability.DAM)),
        Actions(),
    ]
    assert donkey(down(W), [FocusLost()]) == [N, NOOP]


def test_keys_of_the_other_role_and_global_keys_do_not_act():
    assert donkey(tap(*SHREK_CODES, F1, F2, ESC, F5, UNKNOWN)) == [NOOP]
    assert shrek(tap(*DONKEY_CODES, F1, F2, ESC, F5, UNKNOWN)) == [ShrekAction()]


def test_the_alt_layout_is_chosen_by_the_config():
    assert shrek(tap(J, I, U), controls=ALT) == [ShrekAction(move=ShrekMove.W, aim=Aim.UP, ability=Ability.THROW)]
    assert shrek(down(SPACE), controls=ALT) == [ShrekAction(ability=Ability.DAM)]
    assert shrek(tap(LEFT, UP, R_CTRL), controls=ALT) == [ShrekAction()]
    assert shrek(tap(J), controls=CFG.controls) == [ShrekAction()]


# --- random key streams ------------------------------------------------------------------------------------------

BOUNDARY = "tick"
CODES = st.sampled_from([*DONKEY_CODES, *SHREK_CODES, F1, F2, ESC, F5, UNKNOWN])
EVENTS = st.lists(
    st.one_of(st.builds(KeyDown, CODES), st.builds(KeyUp, CODES), st.just(FocusLost()), st.just(BOUNDARY)),
    max_size=60,
)
KEYS = CFG.controls.keymaps


def boundaries(events, keep=lambda code: True):
    """(buffer at each boundary) for a stream, after dropping the key events `keep` rejects."""
    buffer, out = KeyBuffer(), []
    for event in events:
        if event == BOUNDARY:
            out.append(buffer)
            buffer = tick_actions(buffer, CFG.controls)[1]
        elif isinstance(event, FocusLost) or keep(event.scancode):
            buffer = fed([event], buffer)
    return out


@given(EVENTS)
def test_held_is_the_set_of_keys_down_without_repeats(events):
    model, buffer = set(), KeyBuffer()
    for event in events:
        if event == BOUNDARY:
            buffer = tick_actions(buffer, CFG.controls)[1]
            assert buffer.pressed == ()
            continue
        buffer = fed([event], buffer)
        if isinstance(event, KeyDown):
            model.add(event.scancode)
        elif isinstance(event, KeyUp):
            model.discard(event.scancode)
        else:
            model.clear()
        assert set(buffer.held) == model and len(buffer.held) == len(model)


@given(EVENTS)
def test_what_never_comes_from_holding_alone(events):
    for buffer in boundaries(events):
        actions = tick_actions(buffer, CFG.controls)[0]
        assert type(actions.donkey) is DonkeyAction                         # exact types: the StrEnums' NONE
        assert (type(actions.shrek.move), type(actions.shrek.aim), type(actions.shrek.ability)) == (
            ShrekMove, Aim, Ability)                                        # values compare equal as strings
        assert (actions.shrek.ability is Ability.DAM) == (ENTER in buffer.held or ENTER in buffer.pressed)
        if actions.shrek.ability in (Ability.THROW, Ability.ROCK):
            assert {R_CTRL, R_SHIFT} & set(buffer.pressed)
        if actions.donkey in (DonkeyAction.STANCE_LEFT, DonkeyAction.STANCE_RIGHT):
            assert {Q, E} & set(buffer.pressed)
        if actions.donkey is not NOOP and not set(DONKEY_CODES) & set(buffer.pressed):
            assert actions.donkey in (N, Wd, Ed, DonkeyAction.MOVE_S)                          # a hold repeat


@given(EVENTS)
def test_each_role_hears_only_its_own_keys(events):
    alone = {
        "donkey": boundaries(events, keep=lambda c: c in DONKEY_CODES),
        "shrek": boundaries(events, keep=lambda c: c in SHREK_CODES),
    }
    for i, buffer in enumerate(boundaries(events)):
        assert donkey_action(buffer, KEYS.donkey.model_dump()) == donkey_action(
            alone["donkey"][i], KEYS.donkey.model_dump()
        )
        assert shrek_action(buffer, KEYS.shrek_default.model_dump()) == shrek_action(
            alone["shrek"][i], KEYS.shrek_default.model_dump()
        )


def test_buffers_are_values():
    assert dataclasses.is_dataclass(KeyBuffer) and KeyBuffer.__dataclass_params__.frozen
