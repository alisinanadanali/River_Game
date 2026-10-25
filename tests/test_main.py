"""CONTROLS.md §7.1: the window shell, on SDL's dummy driver with a fake clock and pygame events in the queue."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from controllers.keyboard import FocusLost, KeyDown, KeyUp  # noqa: E402
from engine.actions import Actions, DonkeyAction  # noqa: E402
from game.session import Mode  # noqa: E402
from main import choose_seed, main, run, translate  # noqa: E402
from tests.support import config_with  # noqa: E402
from tests.support import run as replay  # noqa: E402

CFG = config_with({})
TICK_S = CFG.time.tick_seconds
SEED = 7
D, F2 = 7, 59


def fake_clock(step_s: float = TICK_S):
    """Each read is step_s later: start() takes the first, then every frame crosses one tick boundary."""
    now = [0.0]

    def read():
        now[0] += step_s
        return now[0]

    return read


def posting(script: dict[int, list[pygame.event.Event]]):
    """inject(i): before frame i reads the queue, post that frame's events."""
    def inject(i):
        for event in script.get(i, ()):
            pygame.event.post(event)
    return inject


def key(kind, scancode):
    return pygame.event.Event(kind, scancode=scancode, key=0, mod=0, unicode="")


# --- translation -------------------------------------------------------------------------------------------------

def test_key_and_focus_events_become_session_events():
    assert translate(key(pygame.KEYDOWN, D)) == KeyDown(D)
    assert translate(key(pygame.KEYUP, D)) == KeyUp(D)
    assert translate(pygame.event.Event(pygame.WINDOWFOCUSLOST)) == FocusLost()


@pytest.mark.parametrize("kind", [pygame.QUIT, pygame.MOUSEBUTTONDOWN, pygame.WINDOWFOCUSGAINED])
def test_other_events_are_not_for_the_session(kind):
    assert translate(pygame.event.Event(kind)) is None


# --- the loop ----------------------------------------------------------------------------------------------------

def test_each_frame_reads_the_clock_and_steps_the_session():
    assert run(CFG, SEED, frames=5, clock=fake_clock()).state.t == 5


def test_keys_reach_the_engine_through_the_session():
    frames = 4
    s = run(CFG, SEED, frames=frames, clock=fake_clock(),
            inject=posting({0: [key(pygame.KEYDOWN, D), key(pygame.KEYUP, D)]}))
    expected = replay(CFG, SEED, [Actions(donkey=DonkeyAction.MOVE_E)] + [Actions()] * (frames - 1))
    assert s.state == expected.states[-1]


def test_a_held_key_repeats_until_the_window_loses_focus():
    s = run(CFG, SEED, frames=4, clock=fake_clock(),
            inject=posting({0: [key(pygame.KEYDOWN, D)], 2: [pygame.event.Event(pygame.WINDOWFOCUSLOST)]}))
    expected = replay(CFG, SEED, [Actions(donkey=DonkeyAction.MOVE_E)] * 2 + [Actions()] * 2)
    assert s.state == expected.states[-1]


def test_global_keys_work_through_the_shell():
    s = run(CFG, SEED, frames=2, clock=fake_clock(), inject=posting({0: [key(pygame.KEYDOWN, F2)]}))
    assert s.mode is Mode.TACTICAL


def test_closing_the_window_ends_the_loop():
    s = run(CFG, SEED, frames=10, clock=fake_clock(), inject=posting({3: [pygame.event.Event(pygame.QUIT)]}))
    assert s.state.t == 3


def test_the_caption_shows_the_seed():
    seen = []
    run(CFG, 424242, frames=1, clock=fake_clock(), inject=lambda i: seen.append(pygame.display.get_caption()[0]))
    assert "424242" in seen[0]


# --- the command line --------------------------------------------------------------------------------------------

def test_a_given_seed_is_kept_and_a_missing_one_is_chosen():
    assert choose_seed(42) == 42
    chosen = {choose_seed(None) for _ in range(5)}
    assert all(isinstance(s, int) and s >= 0 for s in chosen) and len(chosen) > 1


def test_main_runs_a_few_frames_and_exits_cleanly():
    assert main(["--seed", "3", "--frames", "2"]) == 0
    assert main(["--seed", "3", "--frames", "2", "--profile", "warmup"]) == 0
