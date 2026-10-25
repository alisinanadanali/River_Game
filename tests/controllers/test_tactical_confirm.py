"""CONTROLS.md §5.2: tactical mode in the window, selection and confirmation.

Scancodes from the CONTROLS.md §1–§3 tables (the doc is the oracle). The last test checks §5.2's promise that
the window and the text tactical mode (§5.1) give the same action for the same keys.
"""

from hypothesis import given
from hypothesis import strategies as st

from controllers.keyboard import FocusLost, KeyDown, KeyUp
from controllers.tactical import Tactical, tactical_actions, tactical_feed
from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.config import load_config
from tools.tactical import parse_shrek, shrek_keys

CFG = load_config()
ALT = CFG.controls.model_copy(update={"shrek_keymap": "alt"})

W, A, S, D, Q, E, X = 26, 4, 22, 7, 20, 8, 27
LEFT, RIGHT, UP, DOWN, R_CTRL, R_SHIFT, ENTER, DOT = 80, 79, 82, 81, 228, 229, 40, 56
J, L, I, K, U, O, SPACE, M = 13, 15, 12, 14, 24, 18, 44, 16
F1, F2, ESC, F5 = 58, 59, 41, 62
DONKEY_CODES = (W, A, S, D, Q, E, X)
SHREK_CODES = (LEFT, RIGHT, UP, DOWN, R_CTRL, R_SHIFT, ENTER, DOT)
UNKNOWN = 100


def presses(*codes, tactical=Tactical(), controls=CFG.controls):
    for code in codes:
        tactical = tactical_feed(tactical, KeyDown(code), controls)
    return tactical


# --- the donkey ---------------------------------------------------------------------------------------------------

def test_a_donkey_key_selects_and_confirms():
    assert presses(D).donkey is DonkeyAction.MOVE_E
    assert presses(Q).donkey is DonkeyAction.STANCE_LEFT
    assert presses(X).donkey is DonkeyAction.NOOP


def test_the_donkeys_confirmation_is_final():
    assert presses(D, W, X).donkey is DonkeyAction.MOVE_E


# --- Shrek: selection ---------------------------------------------------------------------------------------------

def test_move_and_aim_select_without_confirming():
    t = presses(RIGHT, UP)
    assert (t.move, t.aim, t.shrek) == (ShrekMove.E, Aim.UP, None)


def test_the_last_selection_per_component_wins():
    t = presses(LEFT, RIGHT, UP, DOWN)
    assert (t.move, t.aim) == (ShrekMove.E, Aim.DOWN)


def test_pressing_the_selected_key_again_clears_it():
    t = presses(LEFT, LEFT, UP, UP)
    assert t.move is ShrekMove.NONE and t.aim is Aim.NONE    # `is`: the StrEnums' NONE are equal strings, and
                                                             # the engine checks `move is not ShrekMove.NONE`
    assert presses(LEFT, LEFT, ENTER).shrek.move is ShrekMove.NONE
    assert presses(LEFT, LEFT, LEFT).move is ShrekMove.W


# --- Shrek: confirmation ------------------------------------------------------------------------------------------

def test_an_ability_confirms_the_selection():
    assert presses(RIGHT, UP, R_CTRL).shrek == ShrekAction(move=ShrekMove.E, aim=Aim.UP, ability=Ability.THROW)
    assert presses(R_SHIFT).shrek == ShrekAction(ability=Ability.ROCK)
    assert presses(DOWN, ENTER).shrek == ShrekAction(aim=Aim.DOWN, ability=Ability.DAM)


def test_the_wait_key_confirms_the_selection_without_an_ability():
    assert presses(LEFT, DOT).shrek == ShrekAction(move=ShrekMove.W)
    assert presses(DOT).shrek == ShrekAction()


def test_shreks_confirmation_is_final():
    t = presses(LEFT, R_CTRL, RIGHT, R_SHIFT, DOT)
    assert t.shrek == ShrekAction(move=ShrekMove.W, ability=Ability.THROW)


# --- the tick -----------------------------------------------------------------------------------------------------

def test_the_tick_waits_for_both_roles_in_either_order():
    assert tactical_actions(Tactical()) is None
    assert tactical_actions(presses(D)) is None
    assert tactical_actions(presses(R_CTRL)) is None
    both = Actions(donkey=DonkeyAction.MOVE_E, shrek=ShrekAction(ability=Ability.THROW))
    assert tactical_actions(presses(D, R_CTRL)) == both == tactical_actions(presses(R_CTRL, D))


def test_a_selection_alone_does_not_count_as_confirmed():
    assert tactical_actions(presses(D, LEFT, UP)) is None


def test_only_presses_count():
    t = presses(D)
    for event in (KeyDown(ENTER), KeyUp(ENTER), FocusLost()):
        t = tactical_feed(t, event, CFG.controls)
    assert tactical_actions(t) == Actions(donkey=DonkeyAction.MOVE_E, shrek=ShrekAction(ability=Ability.DAM))
    assert tactical_feed(Tactical(), KeyUp(LEFT), CFG.controls) == Tactical()
    assert tactical_feed(presses(LEFT), FocusLost(), CFG.controls) == presses(LEFT)


def test_keys_of_no_role_do_nothing():
    assert presses(F1, F2, ESC, F5, UNKNOWN) == Tactical()


def test_the_alt_layout_is_chosen_by_the_config():
    assert presses(L, I, U, controls=ALT).shrek == ShrekAction(move=ShrekMove.E, aim=Aim.UP, ability=Ability.THROW)
    assert presses(M, controls=ALT).shrek == ShrekAction()
    assert presses(RIGHT, R_CTRL, controls=ALT) == Tactical()


# --- random presses -----------------------------------------------------------------------------------------------

CODES = st.lists(st.sampled_from([*DONKEY_CODES, *SHREK_CODES, F1, F2, ESC, F5, UNKNOWN]), max_size=30)


@given(CODES)
def test_the_donkey_gets_its_first_key(codes):
    first = next((c for c in codes if c in DONKEY_CODES), None)
    expected = None if first is None else presses(first).donkey
    assert presses(*codes).donkey == expected


@given(CODES)
def test_shreks_ability_is_the_confirming_key_and_roles_do_not_mix(codes):
    t = presses(*codes)
    confirm = next((c for c in codes if c in (R_CTRL, R_SHIFT, ENTER, DOT)), None)
    abilities = {R_CTRL: Ability.THROW, R_SHIFT: Ability.ROCK, ENTER: Ability.DAM, DOT: Ability.NONE}
    assert (t.shrek is None) == (confirm is None)
    if confirm is not None:
        assert t.shrek.ability is abilities[confirm]
        assert type(t.shrek.move) is ShrekMove and type(t.shrek.aim) is Aim  # NONE values are equal strings
    shrek_only = presses(*(c for c in codes if c in SHREK_CODES))
    assert (t.shrek, t.move, t.aim) == (shrek_only.shrek, shrek_only.move, shrek_only.aim)


# --- the same action as the text tactical mode (§5.1) ------------------------------------------------------------

LINE_KEYS = {"move": ("j", "l"), "aim": ("i", "k"), "ability": ("u", "o", " ")}
CODE_OF = {"j": J, "l": L, "i": I, "k": K, "u": U, "o": O, " ": SPACE, "m": M}


@given(st.fixed_dictionaries({c: st.sampled_from((None, *keys)) for c, keys in LINE_KEYS.items()}), st.randoms())
def test_window_and_text_mode_agree(choice, random):
    line = "".join(k for k in choice.values() if k is not None) or "m"
    selection = [k for k in (choice["move"], choice["aim"]) if k is not None]
    random.shuffle(selection)                                     # selection order does not matter
    confirm = choice["ability"] or "m"
    t = presses(*(CODE_OF[k] for k in [*selection, confirm]), controls=ALT)
    assert t.shrek == parse_shrek(line, shrek_keys(CFG))
