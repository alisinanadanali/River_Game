"""INV-03 with every action random (hypothesis): whatever both players do, the base level B(t), the upstream wave
births and the item arrivals are those of a game in which nobody does anything, and the water, items, throw and
slip streams are in exactly the same state after every tick (R-02: action-dependent streams draw fixed blocks).

Games lost by lives end early, so the two games are compared over the ticks both played.
"""

from hypothesis import given
from hypothesis import strategies as st

from engine.actions import Ability, Actions, Aim, DonkeyAction, ShrekAction, ShrekMove
from engine.events import ItemArrived, WaveOrigin, WaveSpawned

from tests.support import config_with, run

CFG = config_with({"water": {"wave_rate_per_tick": 0.1}, "items": {"arrival_rate_per_tick": 0.3}})
TICKS = CFG.time.game_length_ticks

actions = st.builds(
    Actions,
    donkey=st.sampled_from(DonkeyAction),
    shrek=st.builds(ShrekAction, move=st.sampled_from(ShrekMove), aim=st.sampled_from(Aim), ability=st.sampled_from(Ability)),
)


def randomness(trace):
    """Per tick: B(t), the streams other than rng_world, upstream births (amplitude, x), arrival kinds."""
    out = []
    for t, (state, rngs) in enumerate(zip(trace.states, trace.rngs, strict=True)):
        events = [e for e in trace.events if e.t == t]
        births = [(e.amplitude, e.x) for e in events if isinstance(e, WaveSpawned) and e.origin is WaveOrigin.UPSTREAM]
        arrivals = [e.kind for e in events if isinstance(e, ItemArrived)]
        out.append((state.water.base_level, rngs.water, rngs.items, rngs.throw, rngs.slip, births, arrivals))
    return out


@given(seed=st.integers(0, 2**32 - 1), game=st.lists(actions, min_size=TICKS, max_size=TICKS))
def test_INV03_actions_never_touch_the_random_numbers(seed, game):
    played = randomness(run(CFG, seed, game))
    idle = randomness(run(CFG, seed, [Actions()] * TICKS))
    assert played == idle[: len(played)]


def test_the_comparison_sees_differences():
    # Guards the property: two seeds give different random numbers, so equal lists above are not an accident.
    assert randomness(run(CFG, 1, [Actions()] * 50)) != randomness(run(CFG, 2, [Actions()] * 50))
