"""W-07: L(c) = B + W_eff(c) − drop·1[dam active ∧ c > c_d]; W_eff drops west waves east of the dam (W-06)."""

import dataclasses

import numpy as np
import pytest

from engine.actions import Actions
from engine.config import load_config
from engine.events import WaveOrigin
from engine.state import new_game
from engine.step import step
from engine.water import Dam, Wave, column_levels, wave_profile

from tests.support import config_with

CFG = load_config()
COLS, S = CFG.map.cols, CFG.water.wave_width_cols
DROP = CFG.dam.downstream_drop_cm


def wave(x: float, amplitude: float = 10.0) -> Wave:
    return Wave(id=0, amplitude=amplitude, x=x, origin=WaveOrigin.UPSTREAM, spawned_at=0)


def test_without_a_dam_level_is_base_plus_waves():
    waves = (wave(2.0, 8.0), wave(6.0, 3.0))
    level = column_levels(4.0, waves, Dam(), CFG)
    assert np.allclose(level, 4.0 + wave_profile(waves, COLS, S))


def test_dam_lowers_the_east_by_drop_and_leaves_the_west():
    level = column_levels(1.0, (), Dam(active=True, col=4), CFG)
    assert level.tolist() == [1.0] * 5 + [1.0 - DROP] * 4  # c ≤ 4 unchanged, c > 4 lowered


def test_dam_cuts_the_east_tail_of_a_wave_west_of_it():
    west = wave(2.5)
    level = column_levels(0.0, (west,), Dam(active=True, col=4), CFG)
    assert np.allclose(level[:5], wave_profile((west,), COLS, S)[:5])  # west side sees the whole wave
    assert np.allclose(level[5:], -DROP)                               # east side: no tail at all


def test_waves_east_of_the_dam_still_count_on_both_sides():
    east = wave(6.0)
    level = column_levels(0.0, (east,), Dam(active=True, col=4), CFG)
    assert np.allclose(level, wave_profile((east,), COLS, S) - DROP * (np.arange(COLS) > 4))


def test_a_centre_exactly_on_the_dam_counts_as_east():
    on = wave(4.0)
    level = column_levels(0.0, (on,), Dam(active=True, col=4), CFG)
    assert level[5] == pytest.approx(wave_profile((on,), COLS, S)[5] - DROP)


def test_idle_dam_with_a_column_changes_nothing():
    # After a release col is None again, but the formula must only look at `active`.
    assert np.array_equal(column_levels(0.0, (wave(3.0),), Dam(active=False, col=4), CFG),
                          column_levels(0.0, (wave(3.0),), Dam(), CFG))


def test_step_stores_the_level_of_the_new_water():
    state, rngs = new_game(config_with({"water": {"wave_rate_per_tick": 0.5}}), 3)
    for _ in range(20):
        state, rngs, _ = step(state, Actions(), rngs)
    water = state.water
    assert np.array_equal(water.level, column_levels(water.base_level, water.waves, state.dam, state.config))
    with pytest.raises(ValueError):
        water.level[0] = 0.0


def test_step_changes_the_base_level():
    state, rngs = new_game(CFG, 42)
    after, _, _ = step(state, Actions(), rngs)
    assert after.water.base_level != state.water.base_level


def test_inputs_are_untouched_by_a_water_tick():
    state, rngs = new_game(config_with({"water": {"wave_rate_per_tick": 2.0}}), 9)
    state, rngs, _ = step(state, Actions(), rngs)
    before = dataclasses.replace(state)
    step(state, Actions(), rngs)
    assert state == before
