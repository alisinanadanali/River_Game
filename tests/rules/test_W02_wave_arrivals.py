"""W-02: N_t ~ Poisson(λ) waves per tick, amplitudes ~ Exponential(mean ā), born at x = −k_spawn·s."""

import dataclasses

import numpy as np
import pytest

from engine.actions import Actions
from engine.config import load_config
from engine.events import WaveOrigin, WaveSpawned
from engine.rng import draw, make_rngs
from engine.state import new_game
from engine.step import step
from engine.water import draw_arrivals, initial_water, spawn_waves

from tests.support import config_with

CFG = load_config()


def test_spawn_by_hand():
    water = dataclasses.replace(initial_water(CFG), next_wave_id=7)
    water, born = spawn_waves(water, np.array([5.0, 12.5]), CFG.water, t=10)
    x0 = -CFG.water.wave_spawn_offset_widths * CFG.water.wave_width_cols
    assert [(w.id, w.amplitude, w.x, w.origin, w.spawned_at) for w in born] == [
        (7, 5.0, x0, WaveOrigin.UPSTREAM, 10),
        (8, 12.5, x0, WaveOrigin.UPSTREAM, 10),
    ]
    assert water.waves == born and water.next_wave_id == 9


def test_no_arrivals_change_nothing():
    water = initial_water(CFG)
    assert spawn_waves(water, np.array([]), CFG.water, t=0) == (water, ())


def test_new_waves_join_after_the_old_ones():
    water, first = spawn_waves(initial_water(CFG), np.array([1.0]), CFG.water, t=0)
    water, second = spawn_waves(water, np.array([2.0]), CFG.water, t=1)
    assert water.waves == first + second


def test_draws_are_one_normal_then_one_poisson_with_its_exponentials():
    # R-02: rng_water draws 1 normal + 1 Poisson + N_t exponentials per tick, whatever the actions or dam.
    state, rngs = new_game(CFG, 42)
    _, after, _ = step(state, Actions(), rngs)
    _, by_hand = draw(rngs, "water", lambda g: g.standard_normal())
    _, by_hand = draw(by_hand, "water", lambda g: g.exponential(CFG.water.wave_amp_mean_cm, g.poisson(CFG.water.wave_rate_per_tick)))
    assert after.water == by_hand.water


def test_zero_rate_never_spawns():
    # numpy's Poisson consumes no numbers when λ = 0, so the stream does not move either; what INV-03 needs
    # still holds: how much is drawn depends on the config and the stream only, never on actions or the dam.
    cfg = config_with({"water": {"wave_rate_per_tick": 0.0}}).water
    rngs = make_rngs(1)
    for _ in range(100):
        amplitudes, rngs = draw_arrivals(rngs, cfg)
        assert amplitudes.size == 0


def test_step_emits_one_wave_spawned_per_new_wave():
    cfg = config_with({"water": {"wave_rate_per_tick": 3.0}})
    state, rngs = new_game(cfg, 5)
    state, _, events = step(state, Actions(), rngs)
    spawned = [e for e in events if isinstance(e, WaveSpawned)]
    assert len(spawned) == len(state.water.waves) > 0
    assert [(e.wave_id, e.amplitude, e.x, e.origin) for e in spawned] == [
        (w.id, w.amplitude, w.x, w.origin) for w in state.water.waves
    ]


def test_new_waves_do_not_move_in_their_first_tick():
    cfg = config_with({"water": {"wave_rate_per_tick": 3.0}})
    state, rngs = new_game(cfg, 5)
    state, _, _ = step(state, Actions(), rngs)
    x0 = -cfg.water.wave_spawn_offset_widths * cfg.water.wave_width_cols
    assert all(w.x == x0 for w in state.water.waves)


# --- statistics (deterministic seeds, 4 standard errors) ------------------------------------------

@pytest.fixture(scope="module")
def arrivals():
    rngs, counts, amplitudes = make_rngs(77), [], []
    for _ in range(40_000):
        a, rngs = draw_arrivals(rngs, CFG.water)
        counts.append(a.size)
        amplitudes.extend(a.tolist())
    return np.array(counts), np.array(amplitudes)


def test_rate_matches_lambda(arrivals):
    counts, _ = arrivals
    lam = CFG.water.wave_rate_per_tick
    assert abs(counts.mean() - lam) < 4 * np.sqrt(lam / counts.size)


def test_count_variance_equals_its_mean(arrivals):
    # The Poisson signature (a fixed-gap or Bernoulli process would fail this).
    counts, _ = arrivals
    assert counts.var() == pytest.approx(counts.mean(), rel=0.1)


def test_amplitudes_are_exponential_with_mean_a_bar(arrivals):
    _, amplitudes = arrivals
    a_bar = CFG.water.wave_amp_mean_cm
    assert amplitudes.min() > 0
    assert abs(amplitudes.mean() - a_bar) < 4 * a_bar / np.sqrt(amplitudes.size)
    # Exponential: sd = mean, and P(A > ā) = 1/e.
    assert abs(np.mean(amplitudes > a_bar) - np.exp(-1)) < 4 * np.sqrt(np.exp(-1) * (1 - np.exp(-1)) / amplitudes.size)
