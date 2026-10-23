"""D-02: δ = (m_R − m_L) / (m_R + m_L + m_D) ∈ (−1, 1); the heavy side is RIGHT for δ > 0, LEFT for δ < 0, and
for δ = 0 a coin from rng_slip (u < 0.5 → LEFT).
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine.donkey import Bag, Donkey, Side, balance, heavy_side

from tests.support import config_with

CFG = config_with({})


def donkey(left: float, right: float) -> Donkey:
    return Donkey(row=0, col=0, lives=3, bag_left=Bag(items=(0,) if left else (), mass=left),
                  bag_right=Bag(items=(1,) if right else (), mass=right))


@pytest.mark.parametrize(
    ("left", "right", "delta"),
    [(0, 0, 0.0), (0, 10, 10 / 210), (50, 0, -50 / 250), (30, 30, 0.0), (10, 60, 50 / 270)],
)
def test_delta(left, right, delta):
    assert balance(donkey(left, right), CFG) == pytest.approx(delta)


@given(left=st.floats(0, 1e6), right=st.floats(0, 1e6))
def test_delta_is_inside_minus_one_one(left, right):
    assert -1 < balance(donkey(left, right), CFG) < 1


@pytest.mark.parametrize(
    ("delta", "u", "side"),
    [(0.2, 0.1, Side.RIGHT), (0.2, 0.9, Side.RIGHT), (-0.2, 0.1, Side.LEFT), (0.0, 0.49, Side.LEFT), (0.0, 0.5, Side.RIGHT)],
)
def test_heavy_side(delta, u, side):
    assert heavy_side(delta, u) is side
