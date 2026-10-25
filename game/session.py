"""CONTROLS.md §7: the game session, the loop's state between frames. Pure: no pygame, no clock (ADR-002, ADR-005).

Each frame the shell passes the frame's key events and the wall clock `now_s`; frame() counts the frame's time,
handles the events in order, then checks the tick boundary. The real-time clock steps the engine at most once a
frame; in tactical mode every pair of confirmations is a tick. Two counters stand in for the wall clock, so a pause
simply stops them: `until_tick_s` (real time: seconds to the next tick boundary) and `since_tick_s` (seconds
since the last tick, for drawing between ticks).
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum

from controllers.keyboard import FocusLost, KeyBuffer, KeyDown, KeyEvent, feed, tick_actions
from controllers.tactical import Tactical, tactical_actions, tactical_feed
from engine.actions import Actions
from engine.config import Config
from engine.events import Event
from engine.rng import Rngs
from engine.state import GameState, new_game
from engine.step import step

CLOCK_EPS_S = 1e-9  # a boundary this close counts as reached: frame times summed as floats drift by ~1e-15 s


class Mode(StrEnum):
    REALTIME = "realtime"
    TACTICAL = "tactical"


@dataclass(frozen=True)
class TickRecord:
    """One engine step the session made: what went in and what came out (replay, drawing, animation)."""

    actions: Actions
    events: tuple[Event, ...]


@dataclass(frozen=True)
class Session:
    config: Config
    seed: int
    state: GameState
    rngs: Rngs
    previous: GameState               # the state before the last tick (drawing interpolates from it)
    mode: Mode
    last_frame_s: float               # wall clock of the last frame
    until_tick_s: float               # real time: seconds to the next tick boundary (reset on entering it)
    since_tick_s: float = 0.0         # running seconds since the last tick
    paused: bool = False
    debug: bool = False               # F1
    keys: KeyBuffer = KeyBuffer()
    tactical: Tactical = Tactical()
    ticks: tuple[TickRecord, ...] = ()  # the ticks made in the last frame, in order
    restarts: int = 0                   # F5 presses so far: a new game, a new replay


def start(config: Config, seed: int, now_s: float) -> Session:
    """A new game; the mode comes from controls.tactical_mode, the first boundary is tick_seconds away."""
    state, rngs = new_game(config, seed)
    mode = Mode.TACTICAL if config.controls.tactical_mode else Mode.REALTIME
    return Session(config, seed, state, rngs, state, mode, last_frame_s=now_s, until_tick_s=config.time.tick_seconds)


def frame(session: Session, events: Iterable[KeyEvent], now_s: float) -> Session:
    """§7: the frame's time (counted by the state at the frame's start), the key events in order, the boundary."""
    s = _elapse(replace(session, ticks=()), now_s)
    for event in events:
        s = _key(s, event)
    return _boundary(s)


def _key(s: Session, event: KeyEvent) -> Session:
    """§7: global keys act on a press (§4.1); role keys go to the mode's input, unless paused or the game is over."""
    globals_ = {code: name for name, code in s.config.controls.keymaps.global_.model_dump().items()}
    pressed = isinstance(event, KeyDown) and event.scancode not in s.keys.held
    action = globals_.get(event.scancode) if pressed else None
    keys = feed(s.keys, event)
    if not isinstance(event, FocusLost) and event.scancode in globals_:
        keys = KeyBuffer(held=keys.held, pressed=s.keys.pressed)       # global keys are the session's, not a role's
    if action == "TOGGLE_DEBUG":
        return replace(s, keys=keys, debug=not s.debug)
    if action == "RESTART":
        return _restart(replace(s, keys=keys))
    if s.state.game_over is not None:
        return replace(s, keys=keys)
    if action == "PAUSE":
        return replace(s, keys=keys, paused=not s.paused)
    if action == "TOGGLE_TACTICAL":
        mode = Mode.REALTIME if s.mode is Mode.TACTICAL else Mode.TACTICAL
        return replace(s, mode=mode, keys=KeyBuffer(held=keys.held), tactical=Tactical(),
                       until_tick_s=s.config.time.tick_seconds)
    if s.paused:
        return replace(s, keys=KeyBuffer(held=keys.held, pressed=s.keys.pressed))  # presses do not count
    if s.mode is Mode.REALTIME:
        return replace(s, keys=keys)
    if not pressed:
        return replace(s, keys=keys)                                    # §5.2: only presses
    tactical = tactical_feed(s.tactical, event, s.config.controls)
    if (actions := tactical_actions(tactical)) is None:
        return replace(s, keys=keys, tactical=tactical)
    return _tick(replace(s, keys=keys, tactical=Tactical()), actions, late_s=0.0)


def _restart(s: Session) -> Session:
    """F5: the same seed again; the mode and the held keys stay, everything pending goes."""
    state, rngs = new_game(s.config, s.seed)
    return replace(s, state=state, rngs=rngs, previous=state, paused=False, keys=KeyBuffer(held=s.keys.held),
                   tactical=Tactical(), until_tick_s=s.config.time.tick_seconds, since_tick_s=0.0, ticks=(),
                   restarts=s.restarts + 1)


def _elapse(s: Session, now_s: float) -> Session:
    """Running time since the last frame counts: toward the boundary in real time, and since the last tick."""
    dt = now_s - s.last_frame_s if not s.paused and s.state.game_over is None else 0.0
    return replace(s, last_frame_s=now_s, until_tick_s=s.until_tick_s - dt, since_tick_s=s.since_tick_s + dt)


def _boundary(s: Session) -> Session:
    """The fixed-step clock: a reached boundary makes one tick; more than a tick behind, the backlog is dropped."""
    if s.mode is not Mode.REALTIME or s.paused or s.state.game_over is not None or s.until_tick_s > CLOCK_EPS_S:
        return s
    actions, keys = tick_actions(s.keys, s.config.controls)
    s = _tick(replace(s, keys=keys), actions, late_s=-s.until_tick_s)
    until = s.until_tick_s + s.config.time.tick_seconds
    if until <= CLOCK_EPS_S:
        return replace(s, until_tick_s=s.config.time.tick_seconds, since_tick_s=0.0)
    return replace(s, until_tick_s=until)


def _tick(s: Session, actions: Actions, late_s: float) -> Session:
    """One engine step; late_s is how long ago the boundary was (drawing starts the new tick from there)."""
    state, rngs, events = step(s.state, actions, s.rngs)
    return replace(s, previous=s.state, state=state, rngs=rngs, ticks=(*s.ticks, TickRecord(actions, events)),
                   since_tick_s=max(late_s, 0.0))
