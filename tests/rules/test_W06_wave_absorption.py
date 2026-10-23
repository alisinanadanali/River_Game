"""W-06: while the dam is held, a wave whose centre crosses c_d (x(t) < c_d ≤ x(t+1)) is removed into Q."""

import dataclasses
import math

import pytest

from engine.actions import Actions
from engine.events import WaveAbsorbed, WaveOrigin
from engine.state import new_game
from engine.step import step
from engine.water import Dam, Wave, absorb_waves, start_dam

from tests.support import config_with

QUIET = config_with({"water": {"wave_rate_per_tick": 0.0}})
V = QUIET.water.wave_speed_cols_per_tick
S = QUIET.water.wave_width_cols
DAM = start_dam(Dam(), col=4, t=0)


def wave(x_after_move: float, amplitude: float = 10.0, id: int = 0) -> Wave:
    """A wave as it is after this tick's move (sub-step b), so x(t) = x − v."""
    return Wave(id=id, amplitude=amplitude, x=x_after_move, origin=WaveOrigin.UPSTREAM, spawned_at=0)


@pytest.mark.parametrize(
    "x_after, absorbed",
    [
        (4.0, True),           # x(t) = 3.5 < 4 ≤ 4.0: lands exactly on c_d
        (4.25, True),          # 3.75 < 4 ≤ 4.25
        (4.5, False),          # x(t) = 4.0 is not < 4: was already on the dam, so it counts as east
        (3.9, False),          # not there yet
        (7.0, False),          # long gone
    ],
)
def test_crossing_condition(x_after, absorbed):
    kept, taken = absorb_waves((wave(x_after),), DAM, QUIET.water)
    assert (len(taken) == 1) == absorbed and len(kept) + len(taken) == 1


def test_idle_dam_absorbs_nothing():
    kept, taken = absorb_waves((wave(4.0),), Dam(), QUIET.water)
    assert taken == () and len(kept) == 1


def test_absorbed_volume_goes_into_q():
    state, rngs = new_game(QUIET, 1)
    state = dataclasses.replace(
        state,
        dam=DAM,
        water=dataclasses.replace(state.water, waves=(wave(3.75, amplitude=8.0, id=0),), next_wave_id=1),
    )
    after, _, events = step(state, Actions(), rngs)    # moves 3.75 -> 4.25, crossing c_d = 4
    volume = 8.0 * S * math.sqrt(2 * math.pi)
    assert [(e.wave_id, e.dam_col) for e in events if isinstance(e, WaveAbsorbed)] == [(0, 4)]
    assert [e.volume for e in events if isinstance(e, WaveAbsorbed)] == [pytest.approx(volume)]
    assert after.dam.absorbed_volume == pytest.approx(volume)
    q_in = QUIET.dam.downstream_drop_cm * V
    assert after.dam.volume == pytest.approx(volume + q_in)  # (c) absorb, then (d) accumulate
    assert after.water.waves == ()


def test_absorbed_wave_is_reported_before_accumulation_can_burst():
    # A big absorbed wave may push Q over Q_max in the same tick: W-05 says the burst happens then.
    state, rngs = new_game(QUIET, 1)
    big = QUIET.dam.q_max_cm_cols / (S * math.sqrt(2 * math.pi))
    state = dataclasses.replace(
        state, dam=DAM, water=dataclasses.replace(state.water, waves=(wave(3.75, big, 0),), next_wave_id=1)
    )
    after, _, events = step(state, Actions(), rngs)
    names = [type(e).__name__ for e in events]
    assert names[:3] == ["WaveAbsorbed", "DamReleased", "WaveSpawned"]
    assert after.dam.burst_lock
