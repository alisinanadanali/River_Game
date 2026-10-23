"""W-03: waves move v columns per tick, W(c) = Σ A·exp(−(c − x)²/2s²), culled past (C − 1) + k_cull·s."""

import dataclasses
import math

import numpy as np
import pytest

from engine.actions import Actions
from engine.events import WaveExited, WaveOrigin
from engine.state import new_game
from engine.step import step
from engine.water import Wave, advance_waves, cull_waves, wave_profile

from tests.support import config_with

QUIET = config_with({"water": {"wave_rate_per_tick": 0.0, "ou_sigma_cm": 0.0}})  # only our own waves
W = QUIET.water
S = W.wave_width_cols


def wave(x: float, amplitude: float = 10.0, id: int = 0) -> Wave:
    return Wave(id=id, amplitude=amplitude, x=x, origin=WaveOrigin.UPSTREAM, spawned_at=0)


def test_advance_moves_every_wave_by_v():
    moved = advance_waves((wave(-4.5, id=0), wave(2.0, id=1)), W)
    assert [w.x for w in moved] == [-4.5 + W.wave_speed_cols_per_tick, 2.0 + W.wave_speed_cols_per_tick]
    assert [w.id for w in moved] == [0, 1]


def test_profile_by_hand():
    profile = wave_profile((wave(3.0),), cols=9, s=1.5)
    assert profile[3] == 10.0
    assert profile[4] == pytest.approx(10.0 * math.exp(-1 / (2 * 1.5**2)))
    assert profile[2] == profile[4]  # symmetric around the centre


def test_profiles_add_up():
    a, b = wave(2.0, 4.0), wave(5.5, 7.0)
    assert np.allclose(wave_profile((a, b), 9, S), wave_profile((a,), 9, S) + wave_profile((b,), 9, S))


def test_no_waves_flat_profile():
    assert wave_profile((), 9, S).tolist() == [0.0] * 9


def test_volume_is_amplitude_times_s_root_two_pi():
    # W-03: V = A·s·√(2π). Summing the profile over a strip wide enough to hold both tails (±100 columns,
    # ~66 s) gives the volume in cm·columns; for s ≥ 1 the integer-column sum equals the integral to ~1e-17.
    profile = wave_profile((wave(100.3, 10.0),), cols=200, s=S)
    assert profile.sum() == pytest.approx(10.0 * S * math.sqrt(2 * math.pi), rel=1e-9)


def test_cull_is_strictly_past_the_edge():
    edge = (QUIET.map.cols - 1) + W.wave_cull_offset_widths * S
    kept, gone = cull_waves((wave(edge, id=0), wave(edge + 1e-9, id=1)), QUIET.map.cols, W)
    assert [w.id for w in kept] == [0] and [w.id for w in gone] == [1]


def test_wave_exits_at_the_kinematic_tick():
    # The wave sits at x0 when tick 0 begins; processing tick k moves it to x0 + (k+1)·v. It is culled while
    # processing the first tick whose move takes it past the edge, k = n − 1 with n = ⌊(edge − x0)/v⌋ + 1.
    # So the exit tick follows from WaveSpawned + v alone (kinematics); the event just makes it explicit.
    state, rngs = new_game(QUIET, 1)
    x0 = -W.wave_spawn_offset_widths * S
    water = dataclasses.replace(state.water, waves=(dataclasses.replace(wave(x0), id=0),), next_wave_id=1)
    state = dataclasses.replace(state, water=water)
    edge = (QUIET.map.cols - 1) + W.wave_cull_offset_widths * S
    n = math.floor((edge - x0) / W.wave_speed_cols_per_tick) + 1
    exits = []
    for _ in range(n + 3):
        state, rngs, events = step(state, Actions(), rngs)
        exits += [(e.t, e.wave_id) for e in events if isinstance(e, WaveExited)]
    assert exits == [(n - 1, 0)]
    assert state.water.waves == ()
