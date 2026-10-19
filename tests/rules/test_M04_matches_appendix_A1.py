"""MODEL.md Appendix A.1: the engine's own maps reproduce the design-time percolation table (9x9, no guarantee).

The appendix came from a separate 20 000-map simulation and is rounded to two decimals. Tolerance per
probability: 4 combined standard errors (our sample + theirs) plus the 0.005 rounding. Seeds are fixed, so the
test is deterministic; it fails only if the engine's distribution really moved.
"""

import math

import numpy as np
import pytest

from engine.rng import make_rngs
from engine.world import build_world, draw_world_block

from tests.support import config_with

MAPS = 2000
APPENDIX_MAPS = 20_000
ROUNDING = 0.005

# p -> P(rock-free path), from MODEL.md A.1
P_PATH = {0.45: 0.085, 0.50: 0.193, 0.55: 0.353, 0.58: 0.482, 0.62: 0.641, 0.70: 0.894}
# p -> P(n_rock = 0, 1, 2, 3, ≥4), where A.1 gives it
N_ROCK = {
    0.50: (0.18, 0.43, 0.30, 0.07, 0.00),
    0.58: (0.48, 0.41, 0.10, 0.01, 0.00),
    0.62: (0.64, 0.32, 0.04, 0.00, 0.00),
    0.70: (0.90, 0.10, 0.00, 0.00, 0.00),
}


def rock_counts(p: float) -> np.ndarray:
    cfg = config_with({"map": {"stone_density": p, "path_guarantee": "none"}}).map
    rngs = make_rngs(20261017)
    counts = []
    for _ in range(MAPS):
        block, rngs = draw_world_block(rngs, cfg)
        counts.append(build_world(block, cfg, seed=0, attempt=0).rocks_to_solve)
    return np.array(counts)


def tolerance(q: float) -> float:
    return 4 * math.sqrt(q * (1 - q) * (1 / MAPS + 1 / APPENDIX_MAPS)) + ROUNDING


@pytest.fixture(scope="module")
def counts():
    return {p: rock_counts(p) for p in P_PATH}


@pytest.mark.parametrize("p", P_PATH)
def test_probability_of_a_rock_free_path(counts, p):
    measured = np.mean(counts[p] == 0)
    assert abs(measured - P_PATH[p]) < tolerance(P_PATH[p]), f"p={p}: {measured:.3f} vs A.1 {P_PATH[p]}"


@pytest.mark.parametrize("p", N_ROCK)
def test_distribution_of_rocks_needed(counts, p):
    c = counts[p]
    measured = [np.mean(c == k) for k in range(4)] + [np.mean(c >= 4)]
    for k, (got, expected) in enumerate(zip(measured, N_ROCK[p], strict=True)):
        assert abs(got - expected) < tolerance(max(expected, 0.01)), f"p={p}, n_rock={k}: {got:.3f} vs {expected}"
