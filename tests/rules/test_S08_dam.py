"""S-08: ability = DAM holds the dam this tick. Not active + DAM → DamStarted at c_d = shrek.col; active + any other
ability (or NONE) → DamReleased(manual) in step 2(a). While held Shrek cannot walk; he can aim. After a burst
burst_lock ignores DAM until a tick without DAM.
"""

import math

import pytest

from engine.actions import Ability, Actions, Aim, ShrekAction, ShrekMove
from engine.events import (
    ActionRejected, Component, DamReleased, DamStarted, ReleaseReason, RejectReason, Role, ShrekAimed, ShrekMoved,
    WaveSpawned,
)

from tests.support import config_with, run

QUIET = config_with({"water": {"wave_rate_per_tick": 0.0}})
Q_IN = QUIET.dam.downstream_drop_cm * QUIET.water.wave_speed_cols_per_tick
TO_BURST = math.ceil(QUIET.dam.q_max_cm_cols / Q_IN)  # 30 ticks with the defaults
HOLD = Actions(shrek=ShrekAction(ability=Ability.DAM))
LET_GO = Actions()


def shrek(**kw) -> Actions:
    return Actions(shrek=ShrekAction(**kw))


def of(trace, kind):
    return [e for e in trace.events if isinstance(e, kind)]


def test_dam_starts_at_shreks_column():
    trace = run(QUIET, 1, [shrek(move=ShrekMove.E), shrek(move=ShrekMove.E), HOLD])
    assert of(trace, DamStarted) == [DamStarted(t=2, seq=0, col=6)]
    dam = trace.states[-1].dam
    assert (dam.active, dam.col, dam.started_at, dam.held_ticks) == (True, 6, 2, 1)


def test_holding_keeps_it_and_letting_go_releases_it():
    trace = run(QUIET, 1, [HOLD] * 10 + [LET_GO])
    assert [s.dam.active for s in trace.states] == [True] * 10 + [False]
    (released,) = of(trace, DamReleased)
    assert (released.t, released.reason, released.held_ticks) == (10, ReleaseReason.MANUAL, 10)
    assert released.volume == pytest.approx(10 * Q_IN)
    assert [type(e) for e in trace.events if e.t == 10][:2] == [DamReleased, WaveSpawned]  # step 2(a), W-05


@pytest.mark.parametrize("ability", [Ability.NONE, Ability.THROW, Ability.ROCK])
def test_any_other_ability_releases_it(ability):
    trace = run(QUIET, 1, [HOLD, HOLD, shrek(ability=ability)])
    assert [(e.t, e.reason) for e in of(trace, DamReleased)] == [(2, ReleaseReason.MANUAL)]


def test_no_walking_while_held():
    trace = run(QUIET, 1, [shrek(move=ShrekMove.E, ability=Ability.DAM)] * 3)
    assert [s.shrek.col for s in trace.states] == [4, 4, 4]  # also on the tick the dam starts
    assert [(e.t, e.role, e.component, e.reason) for e in of(trace, ActionRejected)] == [
        (t, Role.SHREK, Component.MOVE, RejectReason.DAM_ACTIVE) for t in range(3)
    ]
    assert of(trace, ShrekMoved) == []


def test_walking_on_the_release_tick_is_free():
    # TICK.md step 2: (a) release, then (b) walk.
    trace = run(QUIET, 1, [HOLD, shrek(move=ShrekMove.E)])
    assert [type(e) for e in trace.events if e.t == 1][:3] == [DamReleased, WaveSpawned, ShrekMoved]
    assert trace.states[-1].shrek.col == 5 and of(trace, ActionRejected) == []


def test_aiming_while_held():
    trace = run(QUIET, 1, [shrek(aim=Aim.UP, ability=Ability.DAM)] * 3)
    assert [e.row for e in of(trace, ShrekAimed)] == [1, 2, 3] and trace.states[-1].dam.active


def test_burst_lock_ignores_a_held_button_until_let_go():
    trace = run(QUIET, 1, [HOLD] * TO_BURST + [HOLD, HOLD, LET_GO, HOLD])
    bursts = [(e.t, e.reason) for e in of(trace, DamReleased)]
    assert bursts == [(TO_BURST - 1, ReleaseReason.BURST)]
    assert [s.dam.burst_lock for s in trace.states[TO_BURST - 1:]] == [True, True, True, False, False]
    assert [(e.t, e.reason) for e in of(trace, ActionRejected)] == [
        (TO_BURST, RejectReason.BURST_LOCK), (TO_BURST + 1, RejectReason.BURST_LOCK),
    ]
    assert [e.t for e in of(trace, DamStarted)] == [0, TO_BURST + 3]


def test_a_locked_dam_does_not_stop_walking():
    # DAM is ignored, so the dam is not held and the move is valid.
    trace = run(QUIET, 1, [HOLD] * TO_BURST + [shrek(move=ShrekMove.W, ability=Ability.DAM)])
    assert trace.states[-1].shrek.col == 3
    assert [e.component for e in of(trace, ActionRejected)] == [Component.ABILITY]
