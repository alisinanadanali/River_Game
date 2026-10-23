"""The transition function T (MODEL.md §1, TICK.md, ADR-011).

step(state, actions, rngs) -> (new_state, new_rngs, events) passes one Tick value through the 13 stages of
PIPELINE, TICK.md steps 0 … 12 in that order. Each stage takes a Tick and returns a new one; nothing is changed
in place. A stage whose rules are not implemented yet returns its Tick unchanged and says so in its docstring.
"""


from engine.actions import Actions
from engine.donkey import depth_stage, donkey_stage, expire_stance
from engine.events import Event, GameOver, GameOverReason
from engine.evolve import evolve
from engine.rng import Rngs, draw_blocks
from engine.shrek import cool_down, shrek_stage
from engine.state import GameState
from engine.stones import stones_stage
from engine.tick import Tick
from engine.validation import validate_stage
from engine.water import water_stage


class GameFinishedError(RuntimeError):
    """TICK.md step 7: step was called on a state whose game is over."""


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
    return evolve(tick, rngs=rngs, u_throw=u_throw, u_slip=u_slip)


def _validate_actions(tick: Tick) -> Tick:
    """TICK.md step 1: action validation. Rules: S-03, D-05, S-08.

    engine/validation.py: rejected components become no-ops, each reported with ActionRejected.
    """
    return validate_stage(tick)


def _shrek_actions(tick: Tick) -> Tick:
    """TICK.md step 2: Shrek's actions. Rules: S-01, S-02, S-04, S-06, S-07, S-08, W-05.

    engine/shrek.py: (b) walk and (c) aim so far.
    """
    return shrek_stage(tick)


def _donkey_action(tick: Tick) -> Tick:
    """TICK.md step 3: the donkey's action. Rules: D-02, D-03, D-05, D-08.

    engine/donkey.py: moves (D-05) and stances (D-08).
    """
    return donkey_stage(tick)


def _projectiles(tick: Tick) -> Tick:
    """TICK.md step 4: projectiles. Rules: S-04, S-05, S-06, D-08, D-09, I-04.

    Not implemented yet (Phase 0 step 7).
    """
    return tick


def _water(tick: Tick) -> Tick:
    """TICK.md step 5: water. Rules: W-01 … W-07.

    engine/water.py: base level, waves, dam accumulation, absorption and burst, column levels.
    """
    return water_stage(tick)


def _stones(tick: Tick) -> Tick:
    """TICK.md step 6: stones. Rules: S-07.

    engine/stones.py: temporary stones sink and vanish, raises on permanent stones decay.
    """
    return stones_stage(tick)


def _depth(tick: Tick) -> Tick:
    """TICK.md step 7: depth. Rules: D-01, D-04, D-06, D-07.

    engine/donkey.py: effective height, depth state, and the sweep that may end the game by lives.
    """
    return depth_stage(tick)


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

    Cooldowns (S-03), stance expiry (D-08), then t += 1; the game ends by time when t reaches game_length_ticks
    (unless step 7 already ended it).
    """
    tick = expire_stance(tick)
    state = tick.state
    t = state.t + 1
    ends = state.game_over is None and t == state.config.time.game_length_ticks
    tick = evolve(
        tick,
        state=evolve(
            state, shrek=cool_down(state.shrek), t=t, game_over=GameOverReason.TIME if ends else state.game_over
        ),
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
