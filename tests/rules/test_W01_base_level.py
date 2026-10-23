"""W-01: base level B follows an Ornstein–Uhlenbeck AR(1) process, B(t+1) = B + θ(μ − B) + σ·ε, B(0) = μ."""

import math

import numpy as np
import pytest

from engine.config import load_config
from engine.rng import draw, make_rngs
from engine.state import new_game
from engine.water import initial_water, ou_step

from tests.support import config_with

CFG = load_config()
W = CFG.water


def test_one_step_by_hand():
    cfg = config_with({"water": {"ou_theta_per_tick": 0.08, "ou_mu_cm": 0.0, "ou_sigma_cm": 2.5}}).water
    assert ou_step(4.0, 0.5, cfg) == pytest.approx(4.0 + 0.08 * (0.0 - 4.0) + 2.5 * 0.5, abs=1e-12)


def test_pulls_towards_mu():
    cfg = config_with({"water": {"ou_mu_cm": 3.0, "ou_sigma_cm": 0.0}}).water
    assert ou_step(10.0, 0.0, cfg) < 10.0 and ou_step(-10.0, 0.0, cfg) > -10.0
    assert ou_step(3.0, 0.0, cfg) == 3.0


def test_without_noise_the_gap_shrinks_by_one_minus_theta():
    cfg = config_with({"water": {"ou_mu_cm": 0.0, "ou_sigma_cm": 0.0, "ou_theta_per_tick": 0.25}}).water
    b = 8.0
    for _ in range(3):
        b = ou_step(b, 123.0, cfg)  # ε is ignored when σ = 0
    assert b == pytest.approx(8.0 * 0.75**3)


def test_game_starts_at_mu_with_calm_water():
    cfg = config_with({"water": {"ou_mu_cm": 2.5}})
    water = initial_water(cfg)
    assert water.base_level == 2.5 and water.waves == () and water.next_wave_id == 0
    assert water.level.tolist() == [2.5] * cfg.map.cols


def test_new_game_holds_the_initial_water_and_an_idle_dam():
    state, _ = new_game(CFG, 42)
    assert state.water == initial_water(CFG)
    assert not state.dam.active and state.dam.volume == 0.0 and not state.dam.burst_lock


def test_level_is_read_only():
    with pytest.raises(ValueError):
        initial_water(CFG).level[0] = 1.0


# --- the process as a whole (deterministic seeds, 4 standard errors) -------------------------------

@pytest.fixture(scope="module")
def path():
    eps, _ = draw(make_rngs(2026), "water", lambda g: g.standard_normal(200_000))
    b, out = W.ou_mu_cm, np.empty(eps.size)
    for i, e in enumerate(eps):
        b = ou_step(b, float(e), W)
        out[i] = b
    return out[1_000:]  # drop the warm-up from B(0) = μ


def test_stationary_mean_and_sd(path):
    theta, sigma = W.ou_theta_per_tick, W.ou_sigma_cm
    sd = sigma / math.sqrt(1 - (1 - theta) ** 2)          # MODEL W-01: ≈ 6.4 cm with the defaults
    rho = 1 - theta
    n_eff = path.size * (1 - rho) / (1 + rho)             # autocorrelated samples count for less
    assert abs(path.mean() - W.ou_mu_cm) < 4 * sd / math.sqrt(n_eff)
    assert abs(path.std() - sd) < 4 * sd / math.sqrt(2 * n_eff)


def test_lag_one_correlation_is_one_minus_theta(path):
    centred = path - path.mean()
    rho = float(centred[1:] @ centred[:-1] / (centred @ centred))
    assert abs(rho - (1 - W.ou_theta_per_tick)) < 0.01
