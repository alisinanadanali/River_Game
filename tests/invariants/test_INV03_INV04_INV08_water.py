"""Water invariants under random Shrek play with real DAM actions (hypothesis; S-08 since Phase 0 step 7c).

INV-03  stream independence: Shrek's play changes neither B(t), nor the upstream wave births, nor rng_water.
INV-04  dam conservation: each episode releases exactly Σ q_in + Σ absorbed volume, read from the events alone.
INV-08  (Q part) at the end of every tick 0 ≤ Q < Q_max.
"""

import math

from hypothesis import given
from hypothesis import strategies as st

from engine.actions import Ability, Actions, Aim, ShrekAction, ShrekMove
from engine.events import DamReleased, ReleaseReason, WaveAbsorbed, WaveOrigin, WaveSpawned

from tests.support import config_with, run

TICKS = 300
# Busy water so that dams really absorb waves; default Q_max so long holds burst.
CFG = config_with({"water": {"wave_rate_per_tick": 0.3}})
Q_IN = CFG.dam.downstream_drop_cm * CFG.water.wave_speed_cols_per_tick

# A plan: segments of (Shrek action, length); DAM segments of up to 45 ticks reach Q_max (30 ticks).
shrek_actions = st.builds(
    ShrekAction, move=st.sampled_from(ShrekMove), aim=st.sampled_from(Aim), ability=st.sampled_from(Ability)
)
segments = st.lists(st.tuples(shrek_actions, st.integers(1, 45)), min_size=1, max_size=25)


def expand(plan) -> list[Actions]:
    ticks = [Actions(shrek=action) for action, length in plan for _ in range(length)]
    return (ticks + [Actions()] * TICKS)[:TICKS]


def close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


@given(seed=st.integers(0, 2**32 - 1), plan=segments)
def test_INV04_each_episode_releases_what_went_in(seed, plan):
    absorbed_since_start = 0.0
    for e in run(CFG, seed, expand(plan)).events:
        if isinstance(e, WaveAbsorbed):
            absorbed_since_start += e.volume
        elif isinstance(e, DamReleased):
            assert close(e.volume, e.accumulated + e.absorbed)           # the dam's own books
            assert close(e.accumulated, e.held_ticks * Q_IN)
            assert close(e.absorbed, absorbed_since_start)               # the log agrees
            absorbed_since_start = 0.0


@given(seed=st.integers(0, 2**32 - 1), plan=segments)
def test_INV08_q_stays_below_q_max_at_tick_end(seed, plan):
    for state in run(CFG, seed, expand(plan)).states:
        assert 0.0 <= state.dam.volume < CFG.dam.q_max_cm_cols
        assert state.dam.active or state.dam.volume == 0.0


@given(seed=st.integers(0, 2**32 - 1), plan=segments)
def test_INV03_shreks_play_does_not_touch_the_random_water(seed, plan):
    def water(actions):
        trace = run(CFG, seed, actions)
        births = [
            [(e.amplitude, e.x) for e in trace.events if e.t == t and isinstance(e, WaveSpawned) and e.origin is WaveOrigin.UPSTREAM]
            for t in range(len(trace.states))
        ]
        return [s.water.base_level for s in trace.states], [r.water for r in trace.rngs], births

    # Wave ids differ (dam waves take ids too), so births are compared by tick, amplitude and position.
    assert water(expand(plan)) == water([Actions()] * TICKS)


def test_the_plans_really_exercise_the_dam():
    # Guards the properties above: holding 45 ticks on busy water must absorb, accumulate and burst; a second
    # dam two columns east is let go by hand.
    hold, walk_e = ShrekAction(ability=Ability.DAM), ShrekAction(move=ShrekMove.E)
    events = run(CFG, 3, expand([(hold, 45), (ShrekAction(), 5), (walk_e, 2), (hold, 3), (ShrekAction(), 1)])).events
    releases = [(e.reason, e.col) for e in events if isinstance(e, DamReleased)]
    assert (ReleaseReason.BURST, 4) in releases and (ReleaseReason.MANUAL, 6) in releases
    assert any(isinstance(e, WaveAbsorbed) for e in events)
