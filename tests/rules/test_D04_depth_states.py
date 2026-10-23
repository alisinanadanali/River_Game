"""D-04: d = L(c) − e_i gives DRY (d < d₀), ANKLE (d₀ ≤ d < d₁), KNEE (d₁ ≤ d < d₂) or SWEPT (d ≥ d₂).
On a bank d is undefined (None) and the state is DRY. DonkeyDepthChanged is emitted when DRY/ANKLE/KNEE changes.
"""

import pytest

from engine.actions import Actions, DonkeyAction
from engine.donkey import DepthState, classify_depth
from engine.events import DonkeyDepthChanged

from tests.support import config_with, run, set_up, still

CFG = still({"map": {"rows": 3, "cols": 5}})
D = CFG.donkey
LINE = ["..#..", "..#..", "..#.."]
N, S = Actions(donkey=DonkeyAction.MOVE_N), Actions(donkey=DonkeyAction.MOVE_S)


@pytest.mark.parametrize(
    ("d", "expected"),
    [
        (-30.0, DepthState.DRY),
        (D.depth_ankle_cm - 1e-9, DepthState.DRY),
        (D.depth_ankle_cm, DepthState.ANKLE),
        (D.depth_knee_cm - 1e-9, DepthState.ANKLE),
        (D.depth_knee_cm, DepthState.KNEE),
        (D.depth_swept_cm - 1e-9, DepthState.KNEE),
        (D.depth_swept_cm, DepthState.SWEPT),
        (100.0, DepthState.SWEPT),
    ],
)
def test_thresholds_are_closed_below(d, expected):
    assert classify_depth(d, D) is expected


def test_thresholds_come_from_the_config():
    other = config_with({"donkey": {"depth_ankle_cm": -3, "depth_knee_cm": 2, "depth_swept_cm": 4}}).donkey
    assert [classify_depth(d, other) for d in (-4, -3, 2, 4)] == [
        DepthState.DRY, DepthState.ANKLE, DepthState.KNEE, DepthState.SWEPT,
    ]


def changes(trace):
    return [(e.t, e.old, e.new, e.depth_cm, e.row, e.col) for e in trace.events if isinstance(e, DonkeyDepthChanged)]


def test_stepping_onto_an_ankle_stone_and_back():
    # (0, 2): h = 2, so d = 2 (ANKLE); (1, 2): h = −5, d = 9 (KNEE, a jump of two states).
    start = set_up(CFG, LINE, {(0, 2): 2.0, (1, 2): -5.0})
    # From ANKLE and KNEE every move is slow: started at t, done at t + 1 (slow_move_ticks = 2).
    wait = Actions()
    trace = run(CFG, 1, [N, wait, N, wait, wait, S, wait, wait, S, wait], start=start)
    assert changes(trace) == [
        (0, DepthState.DRY, DepthState.ANKLE, pytest.approx(2.0), 0, 2),
        (3, DepthState.ANKLE, DepthState.KNEE, pytest.approx(9.0), 1, 2),
        (6, DepthState.KNEE, DepthState.ANKLE, pytest.approx(2.0), 0, 2),
        (9, DepthState.ANKLE, DepthState.DRY, None, -1, 2),
    ]
    assert trace.states[-1].donkey.depth is None


def test_no_event_while_the_state_stays():
    trace = run(CFG, 1, [N] + [Actions()] * 5, start=set_up(CFG, LINE))
    assert changes(trace) == []  # DRY on the bank, DRY on the stone
    assert [s.donkey.depth for s in trace.states] == [pytest.approx(-6.0)] * 6


def test_the_level_of_the_donkeys_column_counts():
    # A constant base level μ = 10 cm (σ = 0) raises every column: d = 10 − (10 − 4) = 4 → ANKLE.
    cfg = still({"map": {"rows": 3, "cols": 5}, "water": {"ou_mu_cm": 10.0}})
    trace = run(cfg, 1, [N], start=set_up(cfg, LINE))
    assert trace.states[0].donkey.depth == pytest.approx(4.0)
    assert trace.states[0].donkey.depth_state is DepthState.ANKLE
