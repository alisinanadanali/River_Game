"""GameState (ENTITIES.md): everything that changes during a game, as one immutable value.

Fields are added together with the rules that need them. The RNG streams
are not part of the state: step takes and returns them separately (ADR-011).
"""

from dataclasses import dataclass, field

from engine.config import Config
from engine.donkey import Donkey, initial_donkey
from engine.events import GameOverReason
from engine.rng import Rngs, make_rngs
from engine.shrek import Shrek, initial_shrek
from engine.stones import Stones, initial_stones
from engine.water import Dam, Water, initial_water
from engine.world import World, generate_world


@dataclass(frozen=True, kw_only=True)
class GameState:
    config: Config = field(repr=False)  # validated and frozen (ADR-008); step reads every parameter from here
    world: World                        # the immutable map (M-01 … M-05)
    water: Water                        # W-01 … W-07
    dam: Dam                            # W-04 … W-06, S-08
    stones: Stones                      # S-07: r_i and temporary stones
    donkey: Donkey                      # D-01 … D-10
    shrek: Shrek                        # S-01 … S-08
    t: int                              # tick counter; the next step processes tick t
    score: int                          # Σ delivered points (D-10)
    game_over: GameOverReason | None    # set once, by TICK.md step 7 (lives) or step 11 (time)


def new_game(config: Config, seed: int) -> tuple[GameState, Rngs]:
    """Tick 0 of a game: the map (M-05) and the five R-01 streams of `seed`, rng_world already advanced.

    Raises MapGenerationError when no map within max_regen_attempts meets the profile's guarantee.
    """
    world, rngs = generate_world(config.map, seed, make_rngs(seed))
    state = GameState(
        config=config,
        world=world,
        water=initial_water(config),
        dam=Dam(),
        stones=initial_stones(config),
        donkey=initial_donkey(config),
        shrek=initial_shrek(config),
        t=0,
        score=0,
        game_over=None,
    )
    return state, rngs
