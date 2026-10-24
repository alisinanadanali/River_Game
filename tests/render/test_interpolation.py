"""VISUALS §9.1: the position between two ticks moves linearly from the old cell to the new one."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from render.interpolation import lerp, tick_progress

TICK_S = 0.6


@pytest.mark.parametrize(
    ("now_s", "expected"),
    [
        (10.0, 0.0),           # the tick just began
        (10.3, 0.5),
        (10.6, 1.0),           # the next tick is due
        (9.0, 0.0),            # clamped: before the tick (a clock that jumped back)
        (12.0, 1.0),           # clamped: a late frame, never past the new cell
    ],
)
def test_tick_progress(now_s, expected):
    assert tick_progress(now_s, tick_started_s=10.0, tick_seconds=TICK_S) == pytest.approx(expected)


@given(st.floats(0, 100), st.floats(0, 100))
def test_tick_progress_never_goes_back(a, b):
    early, late = sorted((a, b))
    assert 0 <= tick_progress(early, 10.0, TICK_S) <= tick_progress(late, 10.0, TICK_S) <= 1


def test_lerp():
    assert lerp((0.0, 4.0), (2.0, 0.0), 0.0) == (0.0, 4.0)
    assert lerp((0.0, 4.0), (2.0, 0.0), 1.0) == (2.0, 0.0)
    assert lerp((0.0, 4.0), (2.0, 0.0), 0.25) == pytest.approx((0.5, 3.0))
