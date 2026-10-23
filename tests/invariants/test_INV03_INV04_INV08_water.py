"""Water invariants under random dam play (hypothesis), with S-08 emulated by tests.support.press_dam.

INV-03  stream independence: dam play changes neither B(t), nor the upstream wave births, nor rng_water.
INV-04  dam conservation: each episode releases exactly Σ q_in + Σ absorbed volume, read from the events alone.
INV-08  (Q part) at the end of every tick 0 ≤ Q < Q_max.
"""

import math

from hypothesis import given
from hypothesis import strategies as st

from engine.actions import Actions
from engine.events import DamReleased, WaveAbsorbed, WaveOrigin, WaveSpawned
from engine.state import new_game
from engine.step import step

from tests.support import config_with, press_dam

TICKS = 300
# Busy water so that dams really absorb waves; default Q_max so long holds burst.
CFG = config_with({"water": {"wave_rate_per_tick": 0.3}})
Q_IN = CFG.dam.downstream_drop_cm * CFG.water.wave_speed_cols_per_tick

# A dam plan: segments of (hold?, column, length); expanded to one (hold, column) per tick.
segments = st.lists(
    st.tuples(st.booleans(), st.integers(0, CFG.map.cols - 1), st.integers(1, 45)), min_size=1, max_size=25
)


def expand(plan) -> list[tuple[bool, int]]:
    ticks = [(hold, col) for hold, col, length in plan for _ in range(length)]
    return (ticks + [(False, 0)] * TICKS)[:TICKS]


def play(seed: int, plan):
    """Run one game; yields (state after the tick, events of the tick incl. a manual release before it)."""
    state, rngs = new_game(CFG, seed)
    for hold, col in expand(plan):
        state, pressed = press_dam(state, hold, col)
        state, rngs, events = step(state, Actions(), rngs)
        yield state, rngs, pressed + events


def close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


@given(seed=st.integers(0, 2**32 - 1), plan=segments)
def test_INV04_each_episode_releases_what_went_in(seed, plan):
    absorbed_since_start = 0.0
    for _, _, events in play(seed, plan):
        for e in events:
            if isinstance(e, WaveAbsorbed):
                absorbed_since_start += e.volume
            elif isinstance(e, DamReleased):
                assert close(e.volume, e.accumulated + e.absorbed)           # the dam's own books
                assert close(e.accumulated, e.held_ticks * Q_IN)
                assert close(e.absorbed, absorbed_since_start)               # the log agrees
                absorbed_since_start = 0.0


@given(seed=st.integers(0, 2**32 - 1), plan=segments)
def test_INV08_q_stays_below_q_max_at_tick_end(seed, plan):
    for state, _, _ in play(seed, plan):
        assert 0.0 <= state.dam.volume < CFG.dam.q_max_cm_cols
        assert state.dam.active or state.dam.volume == 0.0


@given(seed=st.integers(0, 2**32 - 1), plan=segments)
def test_INV03_dam_play_does_not_touch_the_random_water(seed, plan):
    def trace(p):
        return [
            (
                state.water.base_level,
                rngs.water,
                [(e.amplitude, e.x) for e in events if isinstance(e, WaveSpawned) and e.origin is WaveOrigin.UPSTREAM],
            )
            for state, rngs, events in play(seed, p)
        ]

    # Wave ids differ (dam waves take ids too), so births are compared by tick, amplitude and position.
    assert trace(plan) == trace([(False, 0, TICKS)])


def test_the_plans_really_exercise_the_dam():
    # Guards the properties above: a plan that holds 45 ticks on busy water must absorb, accumulate and burst.
    events = [e for _, _, ev in play(3, [(True, 4, 45), (False, 4, 5), (True, 6, 3), (False, 0, 1)]) for e in ev]
    reasons = [e.reason.value for e in events if isinstance(e, DamReleased)]
    assert "burst" in reasons and "manual" in reasons
    assert any(isinstance(e, WaveAbsorbed) for e in events)
