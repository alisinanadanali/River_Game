"""W-05: on release or burst (Q ≥ Q_max) a DAM wave A = Q/(s·√(2π)) is born at x = c_d, then Q = 0."""

import math

import pytest

from engine.actions import Actions
from engine.events import DamReleased, ReleaseReason, WaveOrigin, WaveSpawned
from engine.state import new_game
from engine.step import step
from engine.tick import Tick
from engine.water import release_dam, water_stage

from tests.support import config_with, press_dam

QUIET = config_with({"water": {"wave_rate_per_tick": 0.0}})
S = QUIET.water.wave_width_cols
Q_IN = QUIET.dam.downstream_drop_cm * QUIET.water.wave_speed_cols_per_tick
Q_MAX = QUIET.dam.q_max_cm_cols


def held(ticks: int, cfg=QUIET, col: int = 4):
    """State after holding the dam at `col` for `ticks` ticks (no release yet)."""
    state, rngs = new_game(cfg, 1)
    events = []
    for _ in range(ticks):
        state, _ = press_dam(state, hold=True, col=col)
        state, rngs, tick_events = step(state, Actions(), rngs)
        events += tick_events
    return state, rngs, events


def test_manual_release_by_hand():
    state, rngs, _ = held(10)
    tick = release_dam(Tick(state=state, actions=Actions(), rngs=rngs, t=state.t), ReleaseReason.MANUAL)
    amplitude = 10 * Q_IN / (S * math.sqrt(2 * math.pi))
    assert amplitude == pytest.approx(13.3, abs=0.05)  # MODEL W-05: 10 ticks held ≈ an average wave
    released, spawned = tick.events
    assert released == DamReleased(
        t=10, seq=0, col=4, volume=pytest.approx(50.0), amplitude=pytest.approx(amplitude),
        accumulated=pytest.approx(50.0), absorbed=0.0, held_ticks=10, reason=ReleaseReason.MANUAL,
    )
    assert spawned == WaveSpawned(t=10, seq=1, wave_id=0, amplitude=pytest.approx(amplitude), x=4.0, origin=WaveOrigin.DAM)


def test_release_resets_the_dam_and_records_the_wave():
    state, rngs, _ = held(10)
    tick = release_dam(Tick(state=state, actions=Actions(), rngs=rngs, t=state.t), ReleaseReason.MANUAL)
    dam, water = tick.state.dam, tick.state.water
    assert (dam.active, dam.col, dam.volume, dam.accumulated_volume, dam.held_ticks, dam.burst_lock) == (
        False, None, 0.0, 0.0, 0, False)
    (wave,) = water.waves
    assert (wave.id, wave.x, wave.origin, wave.spawned_at) == (0, 4.0, WaveOrigin.DAM, 10)
    assert water.next_wave_id == 1


def test_manual_release_wave_moves_in_the_same_tick():
    # TICK.md step 2(a) comes before step 5, so the released wave already advances once.
    state, rngs, _ = held(10)
    tick = release_dam(Tick(state=state, actions=Actions(), rngs=rngs, t=state.t), ReleaseReason.MANUAL)
    tick = water_stage(tick)
    assert tick.state.water.waves[0].x == 4.0 + QUIET.water.wave_speed_cols_per_tick


def test_release_of_an_idle_dam_is_a_bug():
    state, rngs = new_game(QUIET, 1)
    with pytest.raises(ValueError):
        release_dam(Tick(state=state, actions=Actions(), rngs=rngs, t=0), ReleaseReason.MANUAL)


# --- burst ----------------------------------------------------------------------------------

def test_burst_on_the_tick_q_reaches_q_max():
    ticks_to_burst = math.ceil(Q_MAX / Q_IN)   # 30 with the defaults
    state, _, events = held(ticks_to_burst)
    bursts = [e for e in events if isinstance(e, DamReleased)]
    assert [(e.t, e.reason, e.held_ticks) for e in bursts] == [(ticks_to_burst - 1, ReleaseReason.BURST, ticks_to_burst)]
    assert bursts[0].amplitude == pytest.approx(Q_MAX / (S * math.sqrt(2 * math.pi)))  # ≈ 40 cm (W-05)
    assert state.dam.burst_lock and not state.dam.active and state.dam.volume == 0.0


def test_burst_wave_does_not_move_in_its_tick():
    state, _, _ = held(math.ceil(Q_MAX / Q_IN))
    (wave,) = state.water.waves
    assert wave.x == 4.0 and wave.origin == WaveOrigin.DAM


def test_burst_lock_blocks_a_held_button_until_it_is_let_go():
    state, rngs, _ = held(math.ceil(Q_MAX / Q_IN))
    state, _ = press_dam(state, hold=True, col=4)
    assert not state.dam.active                     # still held: ignored
    state, _ = press_dam(state, hold=False, col=4)  # let go
    state, _ = press_dam(state, hold=True, col=4)
    assert state.dam.active


def test_burst_releases_q_unclipped():
    # Q_max is a trigger, not a cap: a q_in that jumps past it releases everything (no volume lost).
    cfg = config_with({"water": {"wave_rate_per_tick": 0.0}, "dam": {"q_max_cm_cols": 12.0}})
    _, _, events = held(3, cfg)
    (burst,) = [e for e in events if isinstance(e, DamReleased)]
    assert burst.volume == pytest.approx(15.0) and burst.volume > 12.0


def test_events_at_burst_are_released_then_spawned():
    _, _, events = held(math.ceil(Q_MAX / Q_IN))
    kinds = [type(e).__name__ for e in events if type(e).__name__ in ("DamReleased", "WaveSpawned")]
    assert kinds == ["DamReleased", "WaveSpawned"]
