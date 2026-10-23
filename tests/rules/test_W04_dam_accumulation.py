"""W-04: every tick the dam is held, Q grows by q_in = drop·v (derived, not a config key)."""

import dataclasses

import pytest

from engine.actions import Actions
from engine.step import step
from engine.state import new_game
from engine.water import Dam, accumulate, start_dam

from tests.support import config_with, press_dam

QUIET = config_with({"water": {"wave_rate_per_tick": 0.0}})  # no waves: nothing to absorb
Q_IN = QUIET.dam.downstream_drop_cm * QUIET.water.wave_speed_cols_per_tick


def test_q_in_is_derived_from_drop_and_wave_speed():
    assert Q_IN == 5.0  # MODEL W-04: default q_in = 5 cm·columns/tick
    dam = accumulate(start_dam(Dam(), 4, t=0), QUIET)
    assert (dam.volume, dam.accumulated_volume, dam.held_ticks) == (Q_IN, Q_IN, 1)


def test_start_dam_opens_a_fresh_episode():
    dam = start_dam(Dam(), col=3, t=17)
    assert (dam.active, dam.col, dam.started_at, dam.volume, dam.held_ticks) == (True, 3, 17, 0.0, 0)


def test_start_dam_on_an_active_dam_is_a_bug():
    with pytest.raises(ValueError):
        start_dam(start_dam(Dam(), 3, t=0), 3, t=1)


def test_ten_held_ticks_store_ten_q_in():
    state, rngs = new_game(QUIET, 1)
    for _ in range(10):
        state, _ = press_dam(state, hold=True, col=4)
        state, rngs, _ = step(state, Actions(), rngs)
    assert state.dam.volume == pytest.approx(10 * Q_IN)
    assert state.dam.accumulated_volume == pytest.approx(10 * Q_IN) and state.dam.held_ticks == 10


def test_idle_dam_does_not_accumulate():
    state, rngs = new_game(QUIET, 1)
    for _ in range(5):
        state, rngs, _ = step(state, Actions(), rngs)
    assert state.dam == Dam()


def test_accumulating_an_idle_dam_is_a_bug():
    with pytest.raises(ValueError):
        accumulate(Dam(), QUIET)


def test_east_of_the_dam_is_lower_while_it_is_held():
    state, rngs = new_game(QUIET, 1)
    state, _ = press_dam(state, hold=True, col=4)
    after, _, _ = step(state, Actions(), rngs)
    no_dam, _, _ = step(dataclasses.replace(state, dam=Dam()), Actions(), rngs)
    drop = QUIET.dam.downstream_drop_cm
    assert after.water.level[5:] == pytest.approx(no_dam.water.level[5:] - drop)
    assert after.water.level[:5] == pytest.approx(no_dam.water.level[:5])
