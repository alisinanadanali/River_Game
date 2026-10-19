"""GameState (ENTITIES.md): everything that changes during a game, as one immutable value.

Fields are added together with the rules that need them (world in step 5, water in step 6, …). The RNG streams
are not part of the state: step takes and returns them separately (ADR-011).
"""

from dataclasses import dataclass, field

from engine.config import Config
from engine.events import GameOverReason
from engine.rng import Rngs, make_rngs


@dataclass(frozen=True, kw_only=True)
class GameState:
    config: Config = field(repr=False)  # validated and frozen (ADR-008); step reads every parameter from here
    t: int                              # tick counter; the next step processes tick t
    score: int                          # Σ delivered points (D-10)
    game_over: GameOverReason | None    # set once, by TICK.md step 7 (lives) or step 11 (time)


def new_game(config: Config, seed: int) -> tuple[GameState, Rngs]:
    """Tick 0 of a game: the initial state and the five R-01 streams of `seed`."""
    rngs = make_rngs(seed)
    return GameState(config=config, t=0, score=0, game_over=None), rngs
