"""CONTROLS.md §7: the game session, driven by a fake clock (each frame gets its `now_s`), no window.

Scancodes from the CONTROLS.md §1–§3 tables. The last tests replay the actions the session recorded through the
engine alone: the loop may change when a tick happens, never what it does (ADR-002, INV-02).
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from controllers.keyboard import FocusLost, KeyDown, KeyUp
from engine.actions import Ability, Actions, DonkeyAction, ShrekAction
from engine.state import new_game
from game.session import Mode, Session, frame, start
from tests.support import config_with, run

CFG = config_with({})
TICK_S = CFG.time.tick_seconds
FPS_S = 1 / CFG.render.fps
SEED = 7
TACTICAL_CFG = config_with({"controls": {"tactical_mode": True}})
SHORT_CFG = config_with({"time": {"game_length_ticks": 2}})

W, D, Q, X = 26, 7, 20, 27
R_CTRL, ENTER, DOT = 228, 40, 56
F1, F2, ESC, F5 = 58, 59, 41, 62


def tap(*codes):
    return [e for c in codes for e in (KeyDown(c), KeyUp(c))]


def play(session: Session, until_s: float, events=(), step_s: float = FPS_S) -> tuple[Session, list]:
    """Frames every step_s from the session's last frame up to until_s; `events` go into the first frame.
    Returns the last session and the TickRecords made on the way."""
    ticks, now, first = [], session.last_frame_s, True
    while now < until_s - 1e-9:
        now = min(now + step_s, until_s)
        session = frame(session, events if first else (), now)
        first = False
        ticks.extend(session.ticks)
    return session, ticks


def at(session: Session, now_s: float, events=()) -> Session:
    return frame(session, events, now_s)


# --- start -------------------------------------------------------------------------------------------------------

def test_a_new_session_is_a_new_game():
    s = start(CFG, SEED, 10.0)
    state, rngs = new_game(CFG, SEED)
    assert (s.state, s.rngs, s.previous) == (state, rngs, state)
    assert (s.mode, s.paused, s.debug, s.ticks, s.restarts) == (Mode.REALTIME, False, False, (), 0)


def test_the_mode_starts_from_the_config():
    assert start(TACTICAL_CFG, SEED, 0.0).mode is Mode.TACTICAL


# --- the fixed-step clock ----------------------------------------------------------------------------------------

def test_the_first_tick_comes_tick_seconds_after_the_start():
    s = start(CFG, SEED, 0.0)
    assert at(s, TICK_S - 0.01).ticks == ()
    assert at(s, TICK_S).ticks != () and at(s, TICK_S).state.t == 1


def test_one_point_three_seconds_are_two_ticks_and_a_tenth_left():
    s, ticks = play(start(CFG, SEED, 0.0), 2 * TICK_S + 0.1)
    assert len(ticks) == 2 and s.state.t == 2
    assert s.until_tick_s == pytest.approx(TICK_S - 0.1)
    assert s.since_tick_s == pytest.approx(0.1)


def test_a_stall_makes_one_tick_and_drops_the_backlog():
    s = at(start(CFG, SEED, 0.0), 5.0)                                        # 5 s in one frame
    assert s.state.t == 1 and s.until_tick_s == pytest.approx(TICK_S)
    assert at(s, 5.0 + TICK_S - 0.01).ticks == () and at(s, 5.0 + TICK_S).state.t == 2


def test_a_late_tick_counts_from_the_boundary():
    s = at(start(CFG, SEED, 0.0), TICK_S + 0.1)                                 # the frame came 0.1 s late
    assert s.state.t == 1 and s.since_tick_s == pytest.approx(0.1) and s.until_tick_s == pytest.approx(TICK_S - 0.1)


def test_esc_in_the_frame_that_crosses_the_boundary_holds_the_tick_until_resume():
    s = at(start(CFG, SEED, 0.0), TICK_S + 0.1, tap(ESC))
    assert s.paused and s.ticks == ()
    s = at(s, 5.0, tap(ESC))
    assert s.state.t == 1 and s.until_tick_s == pytest.approx(TICK_S - 0.1)


def test_the_tick_record_is_what_went_into_the_engine():
    s = at(start(CFG, SEED, 0.0), TICK_S, tap(W))
    state, rngs = new_game(CFG, SEED)
    assert s.ticks[0].actions == Actions(donkey=DonkeyAction.MOVE_N)
    assert run(CFG, SEED, [s.ticks[0].actions]).events == s.ticks[0].events
    assert s.previous == state


def test_since_tick_counts_from_the_last_tick():
    s = at(start(CFG, SEED, 0.0), TICK_S)
    assert s.since_tick_s == 0.0 and at(s, TICK_S + 0.25).since_tick_s == pytest.approx(0.25)


# --- real-time keys ----------------------------------------------------------------------------------------------

def test_presses_in_the_window_make_the_ticks_action():
    s = at(start(CFG, SEED, 0.0), 0.3, tap(D, R_CTRL))
    assert at(s, TICK_S).ticks[0].actions == Actions(donkey=DonkeyAction.MOVE_E, shrek=ShrekAction(ability=Ability.THROW))


def test_a_held_key_keeps_walking():
    s, ticks = play(start(CFG, SEED, 0.0), 3 * TICK_S, [KeyDown(W)])
    assert [t.actions.donkey for t in ticks] == [DonkeyAction.MOVE_N] * 3


# --- F1, Esc -----------------------------------------------------------------------------------------------------

def test_f1_toggles_the_debug_layer_only():
    s = at(start(CFG, SEED, 0.0), 0.1, tap(F1))
    assert s.debug and at(s, 0.2, tap(F1)).debug is False
    assert at(s, TICK_S).ticks[0].actions == Actions()                            # F1 is not a game key


def test_a_held_global_key_acts_once():
    assert at(start(CFG, SEED, 0.0), 0.1, [KeyDown(F1), KeyDown(F1), KeyDown(F1)]).debug


def test_pause_stops_the_clock_and_resume_goes_on_where_it_stopped():
    s = at(start(CFG, SEED, 0.0), 0.2, tap(ESC))
    s, ticks = play(s, 10.0)
    assert s.paused and ticks == [] and s.until_tick_s == pytest.approx(TICK_S - 0.2)
    s = at(s, 10.0, tap(ESC))
    assert not s.paused
    assert at(s, 10.0 + TICK_S - 0.21).ticks == () and at(s, 10.0 + TICK_S - 0.2).ticks != ()


def test_presses_while_paused_do_not_count_but_releases_do():
    s = at(start(CFG, SEED, 0.0), 0.1, [KeyDown(W), *tap(ESC)])               # W pressed before the pause
    s = at(s, 0.2, [*tap(D), KeyUp(W), KeyDown(Q)])                            # paused: D and Q do not count
    s = at(s, 0.3, tap(ESC))
    assert s.keys.held == (Q,) and s.keys.pressed == (W,)
    assert at(s, TICK_S + 0.2).ticks[0].actions.donkey is DonkeyAction.MOVE_N    # W's press survived the pause


def test_a_key_pressed_during_the_pause_and_held_repeats_after_it():
    s = at(start(CFG, SEED, 0.0), 0.1, tap(ESC))
    s = at(s, 0.2, [KeyDown(W), *tap(ESC)])
    assert at(s, TICK_S + 0.1).ticks[0].actions.donkey is DonkeyAction.MOVE_N


# --- F2: tactical mode -------------------------------------------------------------------------------------------

def test_f2_switches_mode_and_drops_pending_presses():
    s = at(start(CFG, SEED, 0.0), 0.1, [*tap(D), KeyDown(W), *tap(F2)])
    assert s.mode is Mode.TACTICAL and s.keys.pressed == () and s.keys.held == (W,)


def test_in_tactical_mode_the_clock_does_not_tick():
    s, ticks = play(start(TACTICAL_CFG, SEED, 0.0), 10.0)
    assert ticks == [] and s.state.t == 0


def test_in_tactical_mode_both_confirmations_make_the_tick():
    s = at(start(TACTICAL_CFG, SEED, 0.0), 1.0, tap(D))
    assert s.ticks == () and s.tactical.donkey is DonkeyAction.MOVE_E
    s = at(s, 5.0, tap(DOT))
    assert s.ticks[0].actions == Actions(donkey=DonkeyAction.MOVE_E) and s.state.t == 1
    assert s.tactical.donkey is None and s.since_tick_s == 0.0


def test_in_tactical_mode_a_held_keys_repeated_down_is_no_press():
    s = at(start(TACTICAL_CFG, SEED, 0.0), 1.0, [KeyDown(R_CTRL), *tap(W)])     # tick 1: W and THROW
    s = at(s, 2.0, [KeyDown(R_CTRL), *tap(D)])                                  # R_CTRL still held
    assert s.state.t == 1 and s.tactical.shrek is None and s.tactical.donkey is DonkeyAction.MOVE_E


def test_in_tactical_mode_two_confirmation_pairs_in_one_frame_are_two_ticks():
    s = at(start(TACTICAL_CFG, SEED, 0.0), 1.0, tap(W, DOT, D, DOT))
    assert [t.actions.donkey for t in s.ticks] == [DonkeyAction.MOVE_N, DonkeyAction.MOVE_E] and s.state.t == 2


def test_back_to_real_time_the_first_tick_is_tick_seconds_away():
    s = at(start(TACTICAL_CFG, SEED, 0.0), 3.0, tap(D, F2))
    assert s.mode is Mode.REALTIME and s.tactical.donkey is None
    assert at(s, 3.0 + TICK_S - 0.01).ticks == () and at(s, 3.0 + TICK_S).ticks[0].actions == Actions()


# --- F5 ----------------------------------------------------------------------------------------------------------

def test_f5_counts_the_restarts():
    s = at(start(CFG, SEED, 0.0), 0.1, tap(F5))
    assert s.restarts == 1 and at(s, 0.2, tap(F5)).restarts == 2


def test_f5_restarts_with_the_same_seed_and_keeps_the_mode():
    s, _ = play(start(CFG, SEED, 0.0), 3 * TICK_S, [KeyDown(W)])
    s = at(s, 2.0, [*tap(F2), *tap(ESC), *tap(D)])                             # tactical, paused
    s = at(s, 2.1, tap(F5))
    state, rngs = new_game(CFG, SEED)
    assert (s.state, s.rngs, s.mode, s.paused) == (state, rngs, Mode.TACTICAL, False)
    assert s.keys.pressed == () and s.keys.held == (W,) and s.tactical.donkey is None


def test_after_f5_the_clock_starts_again():
    s = at(at(start(CFG, SEED, 0.0), 0.5), 0.5, tap(F5))
    assert at(s, 0.5 + TICK_S - 0.01).ticks == () and at(s, 0.5 + TICK_S).state.t == 1


# --- game over ---------------------------------------------------------------------------------------------------

def test_after_game_over_only_f1_and_f5_work():
    s, ticks = play(start(SHORT_CFG, SEED, 0.0), 10.0)
    assert len(ticks) == 2 and s.state.game_over is not None
    after = at(s, 10.1, tap(W, F2, ESC))
    assert (after.state, after.mode, after.paused, after.ticks) == (s.state, Mode.REALTIME, False, ())
    assert at(s, 10.1, tap(F1)).debug and at(s, 10.1, tap(F5)).state.t == 0


# --- the loop changes when, never what --------------------------------------------------------------------------

KEYS = st.sampled_from([W, D, Q, X, R_CTRL, ENTER, DOT, F2, ESC, F5, 26 + 1000])
FRAMES = st.lists(
    st.tuples(
        st.floats(min_value=0.0, max_value=3 * TICK_S),
        st.lists(st.one_of(st.builds(KeyDown, KEYS), st.builds(KeyUp, KEYS), st.just(FocusLost())), max_size=4),
    ),
    max_size=40,
)


@given(FRAMES)
def test_replaying_the_recorded_actions_gives_the_same_game(frames):
    s, now, ticks = start(CFG, SEED, 0.0), 0.0, []
    for dt, events in frames:
        now += dt
        before = s
        s = frame(s, events, now)
        if s.restarts != before.restarts:
            ticks = []                                                          # F5: a new game from here
        if s.mode is Mode.REALTIME and before.mode is Mode.REALTIME:
            assert len(s.ticks) <= 1                                            # the clock: one tick a frame at most
        ticks.extend(s.ticks)
    trace = run(CFG, SEED, [t.actions for t in ticks])
    assert (trace.states[-1] if ticks else new_game(CFG, SEED)[0]) == s.state
    assert trace.events == tuple(e for t in ticks for e in t.events)
