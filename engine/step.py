"""The transition function T (MODEL.md §1, TICK.md, ADR-011).

step(state, actions, rngs) -> (new_state, new_rngs, events) passes one Tick value through the 13 stages of
PIPELINE, TICK.md steps 0 … 12 in that order. Each stage takes a Tick and returns a new one; nothing is changed
in place. A stage whose rules are not implemented yet returns its Tick unchanged and says so in its docstring.
"""

import dataclasses
from dataclasses import dataclass

import numpy as np

from engine.actions import Actions
from engine.events import Event, GameOver, GameOverReason
from engine.rng import Rngs, draw_blocks
from engine.state import GameState


class GameFinishedError(RuntimeError):
    """TICK.md step 7: step was called on a state whose game is over."""


@dataclass(frozen=True, kw_only=True, eq=False)
class Tick:
    """One step's work in progress, handed from stage to stage."""

    state: GameState
    actions: Actions
    rngs: Rngs
    t: int                             # the tick being processed: state.t when step began, even after step 11
    u_throw: np.ndarray | None = None  # R-02 block, set by step 0
    u_slip: np.ndarray | None = None   # R-02 block, set by step 0
    events: tuple[Event, ...] = ()

    def emit(self, event_type: type[Event], **fields) -> "Tick":
        """Append one event, numbered with this tick's t and the next seq (TICK.md step 12)."""
        event = event_type(t=self.t, seq=len(self.events), **fields)
        return dataclasses.replace(self, events=self.events + (event,))


def step(state: GameState, actions: Actions, rngs: Rngs) -> tuple[GameState, Rngs, tuple[Event, ...]]:
    """ADR-011: one tick. Pure: equal inputs give equal outputs, and the inputs are never changed."""
    if state.game_over is not None:
        raise GameFinishedError(f"game ended at t={state.t} ({state.game_over}); start a new game")
    tick = Tick(state=state, actions=actions, rngs=rngs, t=state.t)
    for stage in PIPELINE:
        tick = stage(tick)
    return tick.state, tick.rngs, tick.events


# --- stages, TICK.md order ------------------------------------------------------------------

def _rng_blocks(tick: Tick) -> Tick:
    """TICK.md step 0: RNG blocks. Rules: R-02.

    The throw and slip blocks are drawn every tick, used or not, so the streams never depend on the actions.
    """
    u_throw, u_slip, rngs = draw_blocks(tick.rngs)
    return dataclasses.replace(tick, rngs=rngs, u_throw=u_throw, u_slip=u_slip)


def _validate_actions(tick: Tick) -> Tick:
    """TICK.md step 1: action validation. Rules: S-03, D-05, S-08.

    Nothing can be rejected yet: cooldowns, the dam and slow moves arrive with their rules (Phase 0 step 7).
    """
    return tick


def _shrek_actions(tick: Tick) -> Tick:
    """TICK.md step 2: Shrek's actions. Rules: S-01, S-02, S-04, S-06, S-07, S-08, W-05.

    Not implemented yet (Phase 0 step 7).
    """
    return tick


def _donkey_action(tick: Tick) -> Tick:
    """TICK.md step 3: the donkey's action. Rules: D-02, D-03, D-05, D-08.

    Not implemented yet (Phase 0 step 7).
    """
    return tick


def _projectiles(tick: Tick) -> Tick:
    """TICK.md step 4: projectiles. Rules: S-04, S-05, S-06, D-08, D-09, I-04.

    Not implemented yet (Phase 0 step 7).
    """
    return tick


def _water(tick: Tick) -> Tick:
    """TICK.md step 5: water. Rules: W-01 … W-07.

    Not implemented yet (Phase 0 step 6).
    """
    return tick


def _stones(tick: Tick) -> Tick:
    """TICK.md step 6: stones. Rules: S-07.

    Not implemented yet (Phase 0 step 7).
    """
    return tick


def _depth(tick: Tick) -> Tick:
    """TICK.md step 7: depth. Rules: D-01, D-04, D-06, D-07.

    Not implemented yet (Phase 0 step 7); it will also end the game when the last life is lost.
    """
    return tick


def _floating_items(tick: Tick) -> Tick:
    """TICK.md step 8: floating items. Rules: I-04, I-05.

    Not implemented yet (Phase 0 step 7).
    """
    return tick


def _bank(tick: Tick) -> Tick:
    """TICK.md step 9: bank. Rules: I-01, I-02.

    Not implemented yet (Phase 0 step 7).
    """
    return tick


def _delivery(tick: Tick) -> Tick:
    """TICK.md step 10: delivery. Rules: D-10.

    Not implemented yet (Phase 0 step 7).
    """
    return tick


def _clock(tick: Tick) -> Tick:
    """TICK.md step 11: clock. Rules: S-03, D-08.

    t += 1, and the game ends by time when t reaches game_length_ticks (unless step 7 already ended it).
    Cooldowns (S-03) and stance expiry (D-08) arrive with their rules (Phase 0 step 7).
    """
    state = tick.state
    t = state.t + 1
    ends = state.game_over is None and t == state.config.time.game_length_ticks
    tick = dataclasses.replace(
        tick,
        state=dataclasses.replace(state, t=t, game_over=GameOverReason.TIME if ends else state.game_over),
    )
    if ends:
        tick = tick.emit(GameOver, reason=GameOverReason.TIME, score=state.score)
    return tick


def _events(tick: Tick) -> Tick:
    """TICK.md step 12: events. Rules: —.

    Already in (t, seq) order: Tick.emit numbers each event as it is appended.
    """
    return tick


PIPELINE = (
    _rng_blocks,
    _validate_actions,
    _shrek_actions,
    _donkey_action,
    _projectiles,
    _water,
    _stones,
    _depth,
    _floating_items,
    _bank,
    _delivery,
    _clock,
    _events,
)
