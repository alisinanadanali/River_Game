"""MODEL Appendix A.3 (throw catch probability) reproduced with the engine's own σ and landing draw.

For an isotropic 2-D Gaussian, P(‖landing − target‖ ≤ r) = 1 − exp(−r²/2σ²). The table is checked once
analytically with the engine's throw_sigma and once by Monte Carlo through landing_point (4 standard errors).
"""

import math

import numpy as np
import pytest

from engine.items import landing_point
from engine.shrek import throw_sigma

from tests.support import config_with

SH = config_with({}).shrek
TABLE = {  # distance in rows (aim_row + 1): (apple 10 kg, potato 30 kg, watermelon 50 kg)
    1: (0.96, 0.87, 0.75),
    3: (0.84, 0.72, 0.61),
    5: (0.69, 0.58, 0.49),
    7: (0.55, 0.47, 0.39),
    9: (0.45, 0.38, 0.32),
}
MASSES = (10.0, 30.0, 50.0)
CASES = [(d, m, p) for d, ps in TABLE.items() for m, p in zip(MASSES, ps, strict=True)]


def p_catch(sigma: float, r: float) -> float:
    return 1 - math.exp(-r * r / (2 * sigma * sigma))


@pytest.mark.parametrize(("distance", "mass", "p"), CASES)
def test_analytic(distance, mass, p):
    sigma = throw_sigma(distance - 1, mass, SH)
    assert p_catch(sigma, SH.catch_radius_cells) == pytest.approx(p, abs=0.006)  # table has two decimals


@pytest.mark.parametrize(("distance", "mass", "p"), CASES[::4])
def test_monte_carlo_through_landing_point(distance, mass, p):
    n = 20_000
    g = np.random.Generator(np.random.PCG64(distance * 1000 + int(mass)))
    sigma = throw_sigma(distance - 1, mass, SH)
    target = (distance - 1, 4)
    hits = 0
    for z in g.standard_normal((n, 2)):
        row, col = landing_point(target, sigma, z)
        hits += math.hypot(row - target[0], col - target[1]) <= SH.catch_radius_cells
    exact = p_catch(sigma, SH.catch_radius_cells)
    assert abs(hits / n - exact) < 4 * math.sqrt(exact * (1 - exact) / n)
